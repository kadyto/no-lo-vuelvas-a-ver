from datetime import date, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.filmaffinity import canonical_url, parse_url


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AliasData(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    language: str | None = Field(default=None, max_length=30)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("El título no puede estar vacío.")
        return value


class WorkData(StrictModel):
    title: str = Field(min_length=1, max_length=300)
    original_title: str | None = Field(default=None, max_length=300)
    kind: Literal["movie", "series"]
    year: int | None = Field(default=None, ge=1800, le=2200)
    fa_url: str | None = Field(default=None, max_length=500)
    fa_id: str | None = Field(default=None, max_length=16)
    aliases: list[AliasData] = Field(default_factory=list, max_length=50)
    categories: list[str] = Field(default_factory=list, max_length=100)
    score: Decimal | None = None
    notes: str = Field(default="", max_length=100_000)
    recommended: bool = False
    watched_on: date | None = None
    uid: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata_source: Literal["FilmAffinity"] | None = None
    metadata_fetched_at: datetime | None = None
    metadata_snapshot: dict | None = None

    @field_validator("title")
    @classmethod
    def title_required(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Escribe un título principal.")
        return value

    @field_validator("score")
    @classmethod
    def valid_score(cls, value):
        if value is not None and (
            not value.is_finite() or not 1 <= value <= 10 or value * 2 != int(value * 2)
        ):
            raise ValueError(
                "La nota debe estar entre 1 y 10, en pasos de 0,5; déjala vacía si es desconocida."
            )
        return value

    @field_validator("categories")
    @classmethod
    def valid_categories(cls, value):
        if any(not x.strip() or len(x.strip()) > 80 for x in value):
            raise ValueError("Cada categoría necesita un nombre de 1 a 80 caracteres.")
        return value

    @model_validator(mode="after")
    def identity(self):
        if self.fa_url:
            external_id = parse_url(self.fa_url)
            if self.fa_id is not None and self.fa_id != external_id:
                raise ValueError("La URL y el ID de FilmAffinity no coinciden.")
            self.fa_id = external_id
            self.fa_url = canonical_url(external_id)
        elif self.fa_id:
            if not self.fa_id.isascii() or not self.fa_id.isdigit() or not 1 <= int(self.fa_id) < 10**16:
                raise ValueError("ID de FilmAffinity inválido.")
            self.fa_id = str(int(self.fa_id))
            self.fa_url = canonical_url(self.fa_id)
        else:
            self.fa_id = self.fa_url = None
        return self


class LibraryExport(StrictModel):
    format: Literal["no-lo-vuelvas-a-ver"]
    version: Literal[1]
    exported_at: datetime
    categories: list[str] = Field(max_length=1000)
    works: list[WorkData] = Field(max_length=50_000)

    @model_validator(mode="after")
    def identities(self):
        seen_uid, seen_fa = set(), set()
        for item in self.works:
            if item.uid is None or item.created_at is None or item.updated_at is None:
                raise ValueError("La exportación debe incluir UUID y fechas internas de cada ficha.")
            if item.uid in seen_uid or (item.fa_id and item.fa_id in seen_fa):
                raise ValueError("El archivo contiene identidades repetidas.")
            seen_uid.add(item.uid)
            if item.fa_id:
                seen_fa.add(item.fa_id)
        WorkData.valid_categories(self.categories)
        return self
