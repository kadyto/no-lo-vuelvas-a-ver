import uuid

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, LargeBinary, String, Table, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db import now


class Base(DeclarativeBase):
    pass


work_categories = Table(
    "work_categories",
    Base.metadata,
    Column("work_id", ForeignKey("works.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Work(Base):
    __tablename__ = "works"
    __table_args__ = (CheckConstraint("kind IN ('movie','series')"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(36), unique=True, default=lambda: str(uuid.uuid4()))
    fa_id: Mapped[str | None] = mapped_column(String(16), unique=True)
    fa_url: Mapped[str | None]
    title: Mapped[str] = mapped_column(String(300))
    title_key: Mapped[str] = mapped_column(String(300), index=True)
    original_title: Mapped[str | None] = mapped_column(String(300))
    original_key: Mapped[str] = mapped_column(String(300), default="", index=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)
    year: Mapped[int | None]
    created_at: Mapped[str] = mapped_column(default=now, index=True)
    updated_at: Mapped[str] = mapped_column(default=now)
    metadata_source: Mapped[str | None]
    metadata_fetched_at: Mapped[str | None]
    metadata_snapshot: Mapped[str | None] = mapped_column(Text)
    poster_id: Mapped[str | None] = mapped_column(ForeignKey("posters.id"), index=True)
    poster: Mapped["Poster | None"] = relationship(lazy="joined")
    credits: Mapped[list["Credit"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="Credit.position"
    )
    aliases: Mapped[list["Alias"]] = relationship(cascade="all, delete-orphan", lazy="selectin")
    review: Mapped["Review"] = relationship(cascade="all, delete-orphan", uselist=False, lazy="joined")
    categories: Mapped[list["Category"]] = relationship(secondary=work_categories, lazy="selectin")

    @property
    def directors(self):
        return [c.person for c in self.credits if c.role == "director"]

    @property
    def actors(self):
        return [c.person for c in self.credits if c.role == "actor"]


class Poster(Base):
    __tablename__ = "posters"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    media_type: Mapped[str] = mapped_column(String(30))
    source_url: Mapped[str]
    fetched_at: Mapped[str]


class Person(Base):
    __tablename__ = "people"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200), index=True)
    identity_key: Mapped[str] = mapped_column(String(220), unique=True)
    fa_id: Mapped[str | None] = mapped_column(String(16), unique=True)


class Credit(Base):
    __tablename__ = "credits"
    __table_args__ = (CheckConstraint("role IN ('director','actor')"),)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(10), primary_key=True)
    position: Mapped[int]
    person: Mapped[Person] = relationship(lazy="joined")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("score_half IS NULL OR score_half BETWEEN 2 AND 20"),)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), primary_key=True)
    score_half: Mapped[int | None] = mapped_column(Integer, index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    recommended: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    watched_on: Mapped[str | None] = mapped_column(String(10), index=True)

    @property
    def score(self):
        return self.score_half / 2 if self.score_half is not None else None


class Alias(Base):
    __tablename__ = "aliases"
    id: Mapped[int] = mapped_column(primary_key=True)
    work_id: Mapped[int] = mapped_column(ForeignKey("works.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    title_key: Mapped[str] = mapped_column(String(300), index=True)
    language: Mapped[str | None] = mapped_column(String(30))


class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    name_key: Mapped[str] = mapped_column(String(80), unique=True)


class Admin(Base):
    __tablename__ = "admin"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str]
    password_hash: Mapped[str]


class BrowserSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(primary_key=True)
    csrf: Mapped[str]
    authenticated: Mapped[bool] = mapped_column(default=False)
    expires_at: Mapped[int] = mapped_column(index=True)


class LoginLimit(Base):
    __tablename__ = "login_limits"
    key: Mapped[str] = mapped_column(primary_key=True)
    count: Mapped[int]
    reset_at: Mapped[int]


class MetadataCache(Base):
    __tablename__ = "metadata_cache"
    fa_id: Mapped[str] = mapped_column(primary_key=True)
    payload: Mapped[str]
    fetched_at: Mapped[str]
    expires_at: Mapped[int]


class ImportPreview(Base):
    __tablename__ = "import_previews"
    token: Mapped[str] = mapped_column(primary_key=True)
    session_hash: Mapped[str]
    payload: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[int]
