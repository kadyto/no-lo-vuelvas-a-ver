import csv
import io
from datetime import datetime, timezone

from sqlalchemy import or_, select

from app.library import category, save_work, work_data
from app.models import Category, Work
from app.schemas import LibraryExport

MAX_IMPORT_BYTES = 10 * 1024 * 1024


def export_library(db):
    return LibraryExport(
        format="no-lo-vuelvas-a-ver",
        version=1,
        exported_at=datetime.now(timezone.utc),
        categories=list(db.scalars(select(Category.name).order_by(Category.name_key))),
        works=[work_data(x) for x in db.scalars(select(Work).order_by(Work.id)).unique()],
    )


def read_import(content):
    if len(content) > MAX_IMPORT_BYTES:
        raise ValueError(
            "El archivo supera el límite de 10 MiB. Divide la exportación o usa una restauración SQLite."
        )
    try:
        return LibraryExport.model_validate_json(content)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("JSON de biblioteca inválido: " + str(exc)[:1200]) from None


def conflict(db, item):
    return db.scalar(
        select(Work).where(or_(Work.uid == str(item.uid), Work.fa_id == item.fa_id if item.fa_id else False))
    )


def preview_import(db, data):
    return [(item, conflict(db, item)) for item in data.works]


def import_library(db, data, mode="skip"):
    if mode not in {"skip", "abort"}:
        raise ValueError("Selecciona omitir conflictos o cancelar si los hay.")
    # Validate again before taking the write lock, including callers other than HTTP.
    data = LibraryExport.model_validate(data.model_dump())
    db.rollback()
    db.connection().exec_driver_sql("BEGIN IMMEDIATE")
    inserted, skipped = 0, 0
    try:
        rows = preview_import(db, data)
        if mode == "abort" and any(existing for _, existing in rows):
            raise ValueError("Hay conflictos; se ha cancelado toda la importación.")
        for name in data.categories:
            category(db, name)
        for item, existing in rows:
            if existing:
                skipped += 1
            else:
                save_work(db, item, commit=False)
                inserted += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return inserted, skipped


def safe_csv(value):
    value = "" if value is None else str(value)
    # Also cover whitespace-prefixed formulas and control characters. Quote is retained as literal data.
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def export_csv(db):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "Título",
            "Título original",
            "Tipo",
            "Año",
            "FilmAffinity",
            "Alias (JSON)",
            "Categorías (JSON)",
            "Nota",
            "Recomendable",
            "Fecha de visionado",
            "Anotaciones",
        ]
    )
    import json

    for work in db.scalars(select(Work).order_by(Work.id)).unique():
        values = [
            work.title,
            work.original_title,
            "Película" if work.kind == "movie" else "Serie",
            work.year,
            work.fa_url,
            json.dumps(
                [{"title": a.title, "language": a.language} for a in work.aliases], ensure_ascii=False
            ),
            json.dumps([c.name for c in work.categories], ensure_ascii=False),
            work.review.score,
            "Sí" if work.review.recommended else "No",
            work.review.watched_on,
            work.review.notes,
        ]
        writer.writerow([safe_csv(x) for x in values])
    return "\ufeff" + buffer.getvalue()
