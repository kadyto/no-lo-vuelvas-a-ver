import base64
import hashlib
import json
import time
from decimal import Decimal

from sqlalchemy import case, delete, exists, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.db import now
from app.filmaffinity import parse_url
from app.models import Alias, Category, Credit, MetadataCache, Person, Poster, Review, Work, work_categories
from app.schemas import WorkData
from app.text import normalize

DEFAULT_CATEGORIES = [
    "Thriller",
    "Comedia",
    "Drama",
    "Acción",
    "Ciencia ficción",
    "Terror",
    "Animación",
    "Documental",
]
PAGE_SIZE = 24


class DuplicateWork(ValueError):
    def __init__(self, existing):
        self.existing = existing
        super().__init__("Ya está en tu biblioteca")


def by_fa(db, fa_id):
    return db.scalar(select(Work).where(Work.fa_id == fa_id)) if fa_id else None


def category(db, name, create=True):
    name = " ".join(name.split())
    if not name or len(name) > 80:
        raise ValueError("La categoría necesita un nombre de 1 a 80 caracteres.")
    key = normalize(name)
    item = db.scalar(select(Category).where(Category.name_key == key))
    if not item and create:
        item = Category(name=name, name_key=key)
        db.add(item)
        db.flush()
    return item


def category_count(db, category_id):
    return db.scalar(
        select(func.count()).select_from(work_categories).where(work_categories.c.category_id == category_id)
    )


def person(db, data):
    key = "fa:" + data.fa_id if data.fa_id else "name:" + normalize(data.name)
    item = db.scalar(select(Person).where(Person.identity_key == key))
    if item:
        return item
    matches = list(db.scalars(select(Person).where(Person.name_key == normalize(data.name)).limit(2)))
    # Names entered by hand may reuse a single known identity, but never merge known homonyms.
    if not data.fa_id and len(matches) == 1:
        return matches[0]
    if data.fa_id and len(matches) == 1 and matches[0].fa_id is None:
        item = matches[0]
        item.fa_id, item.identity_key = data.fa_id, key
    else:
        item = Person(name=data.name, name_key=normalize(data.name), identity_key=key, fa_id=data.fa_id)
        db.add(item)
    db.flush()
    return item


def store_poster(db, content, media_type, source_url, fetched_at):
    digest = hashlib.sha256(content).hexdigest()
    item = db.get(Poster, digest)
    if not item:
        item = Poster(
            id=digest, data=content, media_type=media_type, source_url=source_url, fetched_at=fetched_at
        )
        db.add(item)
        db.flush()
    return item


def poster_data(poster):
    if poster is None:
        return None
    return {
        "content": base64.b64encode(poster.data).decode("ascii"),
        "media_type": poster.media_type,
        "source_url": poster.source_url,
        "fetched_at": poster.fetched_at,
    }


def prune_posters(db):
    used = exists(select(Work.id).where(Work.poster_id == Poster.id))
    cached = exists(
        select(MetadataCache.fa_id).where(
            MetadataCache.expires_at > int(time.time()),
            func.json_extract(MetadataCache.payload, "$.poster_id") == Poster.id,
        )
    )
    db.execute(delete(Poster).where(~used, ~cached).execution_options(synchronize_session=False))


def save_work(db, data: WorkData, work=None, commit=True):
    try:
        return _save_work(db, data, work, commit)
    except IntegrityError:
        db.rollback()
        existing = by_fa(db, data.fa_id)
        if existing:
            raise DuplicateWork(existing) from None
        raise


def _save_work(db, data: WorkData, work=None, commit=True):
    existing = by_fa(db, data.fa_id)
    if existing and (not work or existing.id != work.id):
        raise DuplicateWork(existing)
    selected_categories = list({c.id: c for c in [category(db, x) for x in data.categories]}.values())
    new = work is None
    work = work or Work(review=Review())
    db.add(work)
    for field in ("title", "original_title", "kind", "year", "fa_id", "fa_url"):
        setattr(work, field, getattr(data, field))
    work.title_key, work.original_key = normalize(data.title), normalize(data.original_title)
    work.updated_at = now()
    if new and data.uid:
        work.uid = str(data.uid)
    if new and data.created_at:
        work.created_at = data.created_at.isoformat()
    if new and data.updated_at:
        work.updated_at = data.updated_at.isoformat()
    if data.metadata_source:
        work.metadata_source = data.metadata_source
        work.metadata_fetched_at = data.metadata_fetched_at.isoformat() if data.metadata_fetched_at else None
        work.metadata_snapshot = (
            json.dumps(data.metadata_snapshot, ensure_ascii=False) if data.metadata_snapshot else None
        )
    work.aliases = [
        Alias(title=a.title, title_key=normalize(a.title), language=a.language) for a in data.aliases
    ]
    work.categories = selected_categories
    review = work.review
    review.score_half = int(data.score * 2) if data.score is not None else None
    review.notes, review.recommended = data.notes, data.recommended
    review.watched_on = data.watched_on.isoformat() if data.watched_on else None
    previous = {(c.role, c.person_id): c for c in work.credits}
    credits = []
    for role, people in [("director", data.directors), ("actor", data.actors)]:
        seen = set()
        for position, entry in enumerate(people):
            member = person(db, entry)
            if member.id in seen:
                continue
            seen.add(member.id)
            credit = previous.get((role, member.id)) or Credit(person=member, role=role)
            credit.position = position
            credits.append(credit)
    work.credits = credits
    work.poster = (
        store_poster(
            db,
            data.poster.raw,
            data.poster.media_type,
            data.poster.source_url,
            data.poster.fetched_at.isoformat(),
        )
        if data.poster
        else None
    )
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError:
        db.rollback()
        existing = by_fa(db, data.fa_id)
        if existing:
            raise DuplicateWork(existing) from None
        raise
    return work


def update_metadata(db, work, fields):
    """Explicit metadata patch preserves review and category relationships."""
    current = work_data(work)
    allowed = {
        "title",
        "original_title",
        "kind",
        "year",
        "fa_url",
        "aliases",
        "directors",
        "actors",
        "poster",
    }
    for key, value in fields.items():
        if key not in allowed:
            raise ValueError("Campo de metadatos desconocido.")
        current[key] = value
    if "fa_url" in fields:
        current["fa_id"] = None
    return save_work(db, WorkData.model_validate(current), work)


def work_data(work):
    return {
        "uid": work.uid,
        "title": work.title,
        "original_title": work.original_title,
        "kind": work.kind,
        "year": work.year,
        "fa_id": work.fa_id,
        "fa_url": work.fa_url,
        "aliases": [{"title": a.title, "language": a.language} for a in work.aliases],
        "categories": sorted([c.name for c in work.categories], key=normalize),
        "score": work.review.score,
        "notes": work.review.notes,
        "recommended": work.review.recommended,
        "watched_on": work.review.watched_on,
        "created_at": work.created_at,
        "updated_at": work.updated_at,
        "metadata_source": work.metadata_source,
        "metadata_fetched_at": work.metadata_fetched_at,
        "metadata_snapshot": json.loads(work.metadata_snapshot) if work.metadata_snapshot else None,
        "directors": [{"name": p.name, "fa_id": p.fa_id} for p in work.directors],
        "actors": [{"name": p.name, "fa_id": p.fa_id} for p in work.actors],
        "poster": poster_data(work.poster),
    }


def possible_matches(db, data):
    keys = {normalize(data.title), normalize(data.original_title)} | {
        normalize(a.title) for a in data.aliases
    }
    keys.discard("")
    stmt = select(Work).where(
        Work.kind == data.kind,
        or_(
            Work.title_key.in_(keys),
            Work.original_key.in_(keys),
            exists(select(Alias.id).where(Alias.work_id == Work.id, Alias.title_key.in_(keys))),
        ),
    )
    if data.year is not None:
        stmt = stmt.where(or_(Work.year == data.year, Work.year.is_(None)))
    return list(db.scalars(stmt.limit(20)).unique())


def search(
    db,
    *,
    q="",
    kind="",
    category_ids=(),
    recommended=False,
    minimum=None,
    maximum=None,
    unrated=False,
    sort="title",
    page=1,
    person_id=None,
):
    q = q.strip()[:500]
    stmt = select(Work).join(Review)
    key = normalize(q)
    external_id = None
    if q.startswith(("http://", "https://")):
        try:
            external_id = parse_url(q)
        except ValueError:
            pass
    elif q.isascii() and q.isdigit():
        external_id = str(int(q))
    if external_id:
        stmt = stmt.where(Work.fa_id == external_id)
    elif key:
        for word in key.split():
            stmt = stmt.where(
                or_(
                    Work.title_key.contains(word, autoescape=True),
                    Work.original_key.contains(word, autoescape=True),
                    exists(
                        select(Alias.id).where(
                            Alias.work_id == Work.id, Alias.title_key.contains(word, autoescape=True)
                        )
                    ),
                )
            )
    if kind in {"movie", "series"}:
        stmt = stmt.where(Work.kind == kind)
    if person_id is not None:
        stmt = stmt.where(
            exists(select(Credit.work_id).where(Credit.work_id == Work.id, Credit.person_id == person_id))
        )
    if category_ids:
        stmt = stmt.where(
            exists(
                select(work_categories.c.work_id).where(
                    work_categories.c.work_id == Work.id, work_categories.c.category_id.in_(category_ids)
                )
            )
        )
    if recommended:
        stmt = stmt.where(Review.recommended.is_(True))
    if unrated:
        stmt = stmt.where(Review.score_half.is_(None))
    for value, lower in [(minimum, True), (maximum, False)]:
        if value not in (None, ""):
            try:
                score = Decimal(str(value))
                if not score.is_finite() or not 1 <= score <= 10:
                    raise ValueError()
            except (ValueError, ArithmeticError):
                raise ValueError("El rango de nota debe estar entre 1 y 10.") from None
            stmt = stmt.where(Review.score_half >= score * 2 if lower else Review.score_half <= score * 2)
    count = db.scalar(select(func.count()).select_from(stmt.subquery()))
    pages = max(1, (count + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(1, page), pages)
    order = {
        "title": Work.title_key,
        "score": Review.score_half.desc().nulls_last(),
        "added": Work.created_at.desc(),
        "watched": Review.watched_on.desc().nulls_last(),
    }.get(sort, Work.title_key)
    exact = or_(
        Work.title_key == key,
        Work.original_key == key,
        exists(select(Alias.id).where(Alias.work_id == Work.id, Alias.title_key == key)),
    )
    stmt = (
        stmt.order_by(case((exact, 0), else_=1), order, Work.id)
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    )
    works = list(db.scalars(stmt).unique())
    matches = {}
    for work in works:
        for alias in work.aliases:
            if key and all(word in alias.title_key for word in key.split()) and key not in work.title_key:
                matches[work.id] = alias.title
                break
    return {"works": works, "count": count, "page": page, "pages": pages, "matches": matches}


def parse_people(value, known=()):
    names = [" ".join(line.split()) for line in value.splitlines() if line.strip()]
    result, offsets = [], {}
    for name in names:
        key = normalize(name)
        matches = [p for p in known if normalize(p["name"]) == key]
        match = None
        if len(matches) == 1:
            match = matches[0]
        elif len(matches) > 1 and sum(normalize(x) == key for x in names) == len(matches):
            index = offsets.get(key, 0)
            match = matches[index]
            offsets[key] = index + 1
        result.append({"name": name, "fa_id": match.get("fa_id") if match else None})
    return result


def parse_form(form, categories, known_people=None):
    aliases = []
    for line in form.get("aliases", "").splitlines():
        if line.strip():
            title, _, language = line.partition("|")
            aliases.append({"title": title.strip(), "language": language.strip() or None})
    selected = set(form.getlist("category_ids"))
    valid = {str(c.id): c.name for c in categories}
    if selected - valid.keys():
        raise ValueError("Hay categorías que ya no existen. Revisa la selección.")
    return WorkData(
        title=form.get("title", ""),
        original_title=form.get("original_title") or None,
        kind=form.get("kind", ""),
        year=form.get("year") or None,
        fa_url=form.get("fa_url") or None,
        aliases=aliases,
        categories=[valid[x] for x in selected],
        score=form.get("score") or None,
        notes=form.get("notes", ""),
        recommended=form.get("recommended") == "on",
        watched_on=form.get("watched_on") or None,
        directors=parse_people(form.get("directors", ""), (known_people or {}).get("directors", [])),
        actors=parse_people(form.get("actors", ""), (known_people or {}).get("actors", [])),
    )
