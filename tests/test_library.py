from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app import library
from app.models import Category, Review, Work
from app.schemas import WorkData
from tests.conftest import csrf


def data(**kwargs):
    return WorkData(title="El faro sintético", kind="movie", **kwargs)


def test_crud_null_score_and_review(db):
    work = library.save_work(db, data())
    assert work.review.score is None and work.review.watched_on is None
    work = library.save_work(
        db, data(score=Decimal("7.5"), notes="Primera línea\nSegunda", recommended=True), work
    )
    assert work.review.score == 7.5 and work.review.recommended
    db.delete(work)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Work)) == 0
    assert db.scalar(select(func.count()).select_from(Review)) == 0


@pytest.mark.parametrize("score", [0, -1, 0.5, 10.5, 7.2, "NaN", "Infinity", "texto"])
def test_invalid_scores(score):
    with pytest.raises(ValidationError):
        data(score=score)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.filmaffinity.com/es/film123.html",
        "http://filmaffinity.com/en/film123.html?x=1#top",
        "https://www.filmaffinity.com/uk/film000123.html",
        "https://m.filmaffinity.com/es/film123.html?mobile=1#top",
    ],
)
def test_fa_language_identity(db, url):
    work = library.save_work(db, data(fa_url="https://www.filmaffinity.com/es/film123.html"))
    with pytest.raises(library.DuplicateWork) as exc:
        library.save_work(db, data(fa_url=url))
    assert exc.value.existing.id == work.id
    assert db.scalar(select(func.count()).select_from(Work)) == 1


def test_concurrent_creation(application, client):
    barrier = Barrier(2)

    def create(_):
        with application.state.db() as db:
            barrier.wait(timeout=10)
            try:
                return library.save_work(db, data(fa_id="987654")).id
            except library.DuplicateWork as exc:
                return exc.existing.id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(create, [1, 2]))
    assert ids[0] == ids[1]
    with application.state.db() as db:
        assert db.scalar(select(func.count()).select_from(Work)) == 1


def test_remakes_and_attach_url(db):
    first = library.save_work(db, data(fa_id="123", year=1995))
    second = library.save_work(db, data(fa_id="124", year=2025))
    manual = library.save_work(db, data())
    assert first.id != second.id
    with pytest.raises(library.DuplicateWork):
        library.update_metadata(db, manual, {"fa_url": "https://www.filmaffinity.com/fr/film123.html"})


@pytest.mark.parametrize(
    "query",
    [
        "fáro",
        "FARO sintetico",
        "Synthetic Lighthouse",
        "LA LUZ",
        "la lúz",
        "456",
        "https://filmaffinity.com/en/film456.html?q=1#x",
        "https://m.filmaffinity.com/es/film456.html",
    ],
)
def test_search(db, query):
    work = library.save_work(
        db,
        data(
            fa_id="456",
            original_title="Synthetic Lighthouse",
            aliases=[{"title": "La luz", "language": "es"}, {"title": "La luz alternativa"}],
        ),
    )
    result = library.search(db, q=query)
    assert [w.id for w in result["works"]] == [work.id]
    if query.casefold() in {"la luz", "la lúz"}:
        assert result["matches"][work.id] == "La luz"


def test_categories_and_metadata_preservation(db):
    work = library.save_work(
        db, data(categories=["Drama", "Ciencia ficción"], notes="Mi reseña", score="4.5", recommended=True)
    )
    library.update_metadata(db, work, {"title": "Nuevo título"})
    assert work.review.notes == "Mi reseña" and work.review.score == 4.5 and work.review.recommended
    assert len(work.categories) == 2
    library.save_work(db, WorkData.model_validate({**library.work_data(work), "categories": ["Drama"]}), work)
    assert db.scalar(select(Category).where(Category.name == "Ciencia ficción"))
    drama = db.scalar(select(Category).where(Category.name == "Drama"))
    assert library.category_count(db, drama.id) == 1
    db.delete(drama)
    db.commit()
    db.expire_all()
    assert db.get(Work, work.id) and db.get(Work, work.id).categories == []


def test_category_normalization(db):
    first = library.category(db, "  Cine   familiar  ")
    second = library.category(db, "CINE FAMILIAR")
    assert first.id == second.id


def test_filter_dimensions_and_exact_priority(db):
    a = library.save_work(
        db, WorkData(title="Luz", kind="movie", categories=["Drama"], score=8, recommended=True)
    )
    library.save_work(
        db,
        WorkData(title="La luz de prueba", kind="movie", categories=["Comedia"], score=7, recommended=True),
    )
    library.save_work(
        db, WorkData(title="Luz de serie", kind="series", categories=["Drama"], recommended=True)
    )
    cats = list(db.scalars(select(Category.id).where(Category.name.in_(["Drama", "Comedia"]))))
    result = library.search(
        db, q="luz", kind="movie", category_ids=cats, recommended=True, minimum=7, maximum=8
    )
    assert result["count"] == 2 and result["works"][0].id == a.id
    assert library.search(db, unrated=True)["count"] == 1


def test_manual_failure_duplicate_before_fetch(client, application):
    class FailingAdapter:
        calls = 0

        def fetch(self, fa_id, source_url=None):
            assert source_url == "https://m.filmaffinity.com/es/film111.html"
            self.calls += 1
            from app.filmaffinity import MetadataUnavailable

            raise MetadataUnavailable("Sin conexión")

    adapter = FailingAdapter()
    application.state.adapter = adapter
    token = csrf(client.get("/works/new"))
    response = client.post(
        "/metadata", data={"csrf": token, "fa_url": "https://m.filmaffinity.com/en/film111.html"}
    )
    assert response.status_code == 422 and "Sin conexión" in response.text and "film111.html" in response.text
    assert 'href="https://www.filmaffinity.com/es/film111.html"' in response.text
    assert "Abrir ficha en FilmAffinity" in response.text
    response = client.post(
        "/works",
        data={
            "csrf": token,
            "fa_url": "https://m.filmaffinity.com/en/film111.html",
            "title": "Manual",
            "kind": "movie",
        },
    )
    assert response.status_code == 200 and "Manual" in response.text
    response = client.post(
        "/metadata", data={"csrf": token, "fa_url": "https://filmaffinity.com/es/film111.html?x=y"}
    )
    assert response.status_code == 409 and "Ya está en tu biblioteca" in response.text
    assert adapter.calls == 1


def test_requests_preview_mobile_host_cache_and_canonical_save(client, application, db):
    import httpx

    from app.filmaffinity import FilmAffinityAdapter
    from tests.requests_transport import RequestsTransport
    from tests.test_security_metadata import HTML, resolver

    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200, text=HTML)

    application.state.adapter = FilmAffinityAdapter(True, RequestsTransport(handler), resolver)
    token = csrf(client.get("/works/new"))
    response = client.post(
        "/metadata",
        data={"csrf": token, "fa_url": "https://m.filmaffinity.com/en/film000123.html?shared=1"},
    )
    assert response.status_code == 200 and "Datos obtenidos de FilmAffinity" in response.text
    assert calls == ["https://m.filmaffinity.com/es/film123.html"]
    assert db.scalar(select(Work)) is None
    response = client.post(
        "/metadata", data={"csrf": token, "fa_url": "https://www.filmaffinity.com/es/film123.html"}
    )
    assert response.status_code == 200 and len(calls) == 1
    response = client.post(
        "/works",
        data={
            "csrf": token,
            "fa_url": "https://m.filmaffinity.com/es/film123.html",
            "title": "El faro de prueba",
            "kind": "movie",
            "metadata_confirm": "on",
            "score": "8.5",
            "notes": "Una opinión sintética",
        },
    )
    assert response.status_code == 200 and "Ficha guardada" in response.text
    work = db.scalar(select(Work))
    assert work.fa_id == "123" and work.fa_url == "https://www.filmaffinity.com/es/film123.html"
    assert work.metadata_source == "FilmAffinity" and work.review.notes == "Una opinión sintética"


def test_http_edit_delete_recommend_and_similarity(client, db):
    token = csrf(client.get("/works/new"))
    fields = {
        "csrf": token,
        "title": "Obra manual",
        "kind": "series",
        "notes": "Notas\nprivadas",
        "score": "7.5",
    }
    response = client.post("/works", data=fields)
    assert "Ficha guardada" in response.text
    work = db.scalar(select(Work))
    response = client.post("/works", data=fields)
    assert response.status_code == 409 and "Posibles coincidencias" in response.text
    response = client.post("/works", data={**fields, "allow_similar": "on"})
    assert response.status_code == 200
    response = client.post(f"/works/{work.id}/recommend", data={"csrf": token})
    assert "✦ Recomendable" in response.text and "7,5" in response.text
    response = client.post(f"/works/{work.id}/edit", data={**fields, "title": "Editada", "score": ""})
    assert "Editada" in response.text and "Sin nota" in response.text
    assert client.post(f"/works/{work.id}/delete", data={"csrf": token}).status_code == 422
    assert client.post(f"/works/{work.id}/delete", data={"csrf": token, "confirm": "yes"}).status_code == 200
    assert client.get(f"/works/{work.id}").status_code == 404


def test_category_ui(client, db):
    token = csrf(client.get("/categories"))
    assert client.post("/categories", data={"csrf": token, "name": "Nueva"}).status_code == 200
    assert client.post("/categories", data={"csrf": token, "name": " nueva "}).status_code == 422
    item = db.scalar(select(Category).where(Category.name == "Nueva"))
    category_id = item.id
    work = library.save_work(db, data(categories=["Nueva"]))
    response = client.post("/categories", data={"csrf": token, "id": str(item.id), "action": "delete"})
    assert "1 fichas" in response.text and db.get(Category, item.id)
    client.post("/categories", data={"csrf": token, "id": str(item.id), "action": "delete", "confirm": "yes"})
    db.expire_all()
    assert db.get(Work, work.id) and db.get(Category, category_id) is None
