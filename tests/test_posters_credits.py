import base64
import io
import json
import shutil
import time

import httpx
import pytest
from PIL import Image
from sqlalchemy import func, select

from app import library, transfers
from app.db import backup, make_engine, migrate, now, sessions
from app.filmaffinity import FilmAffinityAdapter, MetadataUnavailable, parse_metadata
from app.models import Credit, MetadataCache, Poster, Work
from app.posters import MAX_DOWNLOAD_BYTES, PosterFetcher, normalize_poster
from app.schemas import PosterData, WorkData
from tests.conftest import csrf
from tests.requests_transport import RequestsTransport

SOURCE = "https://pics.filmaffinity.com/synthetic_story-123456-large.jpg"
HTML = f'''<main itemscope itemtype="https://schema.org/Movie">
<h1 id="main-title"><span>El faro sintético</span></h1>
<div id="movie-main-image"><a href="{SOURCE}"><img src="{SOURCE}"></a></div>
<dl><dt>Año</dt><dd>2024</dd><dt>Dirección</dt><dd>
<a href="/es/name.php?name-id=000101">María Prueba</a></dd><dt>Reparto</dt><dd>
<a href="https://www.filmaffinity.com/es/name.php?name-id=202">Actor Sintético</a>
<a href="/es/name.php?name-id=202">Actor Sintético</a><a href="/es/filmcredits.php?id=123">Ver todos</a>
</dd></dl></main>'''


def image_bytes(size=(600, 900), format="PNG"):
    output = io.BytesIO()
    Image.new("RGB", size, "#0052cc").save(output, format=format)
    return output.getvalue()


def poster_data():
    return PosterData(
        content=base64.b64encode(normalize_poster(image_bytes())).decode(),
        media_type="image/jpeg",
        source_url=SOURCE,
        fetched_at=now(),
    )


def resolver(*args, **kwargs):
    return [(2, 1, 6, "", ("8.8.8.8", 443))]


@pytest.fixture
def local_db(tmp_path):
    path = tmp_path / "library.sqlite3"
    migrate(path)
    engine = make_engine(path)
    with sessions(engine)() as db:
        yield db
    engine.dispose()


def test_parser_poster_and_credits():
    data = parse_metadata(HTML)
    assert data["poster_url"] == SOURCE
    assert data["directors"] == [{"name": "María Prueba", "fa_id": "101"}]
    assert data["actors"] == [{"name": "Actor Sintético", "fa_id": "202"}]
    assert "sinopsis" not in data and "reviews" not in data
    assert parse_metadata(HTML.replace(SOURCE, "https://evil.test/poster.jpg"))["poster_url"] is None


def test_structured_metadata_fallback():
    structured = {
        "@graph": [
            {
                "@type": "Movie",
                "director": {
                    "@type": "Person",
                    "name": "Dirección sintética",
                    "url": "https://www.filmaffinity.com/es/name.php?name-id=123",
                },
                "actor": [{"name": "Reparto ficticio"}],
                "image": {"contentUrl": SOURCE},
                "review": "No importar",
            }
        ]
    }
    data = parse_metadata(
        '<h1 id="main-title"><span>Otra prueba</span></h1><script type="application/ld+json">'
        + json.dumps(structured)
        + "</script>"
    )
    assert data["kind"] == "movie" and data["poster_url"] == SOURCE
    assert data["directors"][0]["fa_id"] == "123" and data["actors"][0]["name"] == "Reparto ficticio"
    assert "review" not in data


@pytest.mark.parametrize(
    "url",
    [
        "http://pics.filmaffinity.com/a.jpg",
        "https://pics.filmaffinity.com.evil.test/a.jpg",
        "https://127.0.0.1/a.jpg",
        "https://user:password@pics.filmaffinity.com/a.jpg",
        "https://pics.filmaffinity.com:443/a.jpg",
        "https://pics.filmaffinity.com/a.svg",
        "https://pics.filmaffinity.com/a.jpg?target=evil",
        "https://pics.filmaffinity.com/../a.jpg",
        "https://pics.filmaffinity.com/a.jpg\n",
        "file:///tmp/a.jpg",
    ],
)
def test_poster_destinations_rejected_before_network(url):
    calls = []
    fetcher = PosterFetcher(True, RequestsTransport(lambda request: calls.append(request)), resolver)
    with pytest.raises(ValueError):
        fetcher.fetch(url)
    assert calls == []


def test_poster_download_local_format_and_redirect_validation():
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(302, headers={"Location": "/synthetic_story-123456.jpg"})
        return httpx.Response(200, headers={"Content-Type": "image/png"}, content=image_bytes())

    result = PosterFetcher(True, RequestsTransport(handler), resolver).fetch(SOURCE)
    assert len(calls) == 2 and result["media_type"] == "image/jpeg" and result["source_url"] == SOURCE
    with Image.open(io.BytesIO(result["data"])) as image:
        assert image.size == (400, 600) and image.format == "JPEG" and not image.info.get("exif")


@pytest.mark.parametrize("status", [403, 429, 500])
def test_poster_http_failure_not_retried(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="No disponible")

    with pytest.raises(MetadataUnavailable, match=f"HTTP {status}"):
        PosterFetcher(True, RequestsTransport(handler), resolver).fetch(SOURCE)
    assert len(calls) == 1


def test_private_redirect_and_untrusted_redirect():
    for target in ["https://evil.test/a.jpg", "http://pics.filmaffinity.com/a.jpg"]:
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(302, headers={"Location": target})

        with pytest.raises(ValueError):
            PosterFetcher(True, RequestsTransport(handler), resolver).fetch(SOURCE)
        assert len(calls) == 1

    def private(*args, **kwargs):
        return [(2, 1, 6, "", ("127.0.0.1", 443))]

    with pytest.raises(MetadataUnavailable, match="dirección pública"):
        PosterFetcher(
            True, RequestsTransport(lambda request: pytest.fail("No debe conectar")), private
        ).fetch(SOURCE)


def test_invalid_oversized_or_animated_images():
    for media, content in [
        ("image/svg+xml", b"<svg/>"),
        ("image/png", b"<script>bad</script>"),
        ("image/png", b"X" * (MAX_DOWNLOAD_BYTES + 1)),
    ]:

        def handler(request):
            return httpx.Response(200, headers={"Content-Type": media}, content=content)

        with pytest.raises(MetadataUnavailable):
            PosterFetcher(True, RequestsTransport(handler), resolver).fetch(SOURCE)
    with pytest.raises(MetadataUnavailable):
        normalize_poster(image_bytes((4000, 4000)))
    buffer = io.BytesIO()
    Image.new("RGB", (10, 10)).save(
        buffer, format="PNG", save_all=True, append_images=[Image.new("RGB", (10, 10), "red")]
    )
    with pytest.raises(MetadataUnavailable):
        normalize_poster(buffer.getvalue())


def test_person_identity_roles_filters_and_manual_names(local_db):
    db = local_db
    first = library.save_work(
        db,
        WorkData(
            title="Uno",
            kind="movie",
            fa_id="111",
            directors=[{"name": "María Prueba", "fa_id": "101"}],
            actors=[{"name": "María Prueba", "fa_id": "101"}],
            poster=poster_data(),
            score="8.5",
            notes="Conservar\nanotación",
            categories=["Drama"],
        ),
    )
    second = library.save_work(
        db,
        WorkData(
            title="Dos", kind="series", fa_id="222", actors=[{"name": "MARIA   PRUEBA"}], recommended=True
        ),
    )
    member = first.directors[0]
    assert second.actors[0].id == member.id
    assert library.search(db, person_id=member.id)["count"] == 2
    assert (
        library.search(db, person_id=member.id, kind="series", recommended=True)["works"][0].id == second.id
    )
    old = library.work_data(first)
    library.update_metadata(db, first, {"title": "Uno editado"})
    changed = library.work_data(first)
    assert {k: v for k, v in old.items() if k not in {"title", "updated_at"}} == {
        k: v for k, v in changed.items() if k not in {"title", "updated_at"}
    }
    db.delete(first)
    db.commit()
    assert library.search(db, person_id=member.id)["works"][0].id == second.id
    assert db.scalar(select(func.count()).select_from(Credit)) == 1


def test_people_homonyms_do_not_merge_known_ids(local_db):
    db = local_db
    one = library.save_work(
        db, WorkData(title="Uno", kind="movie", actors=[{"name": "Nombre Igual", "fa_id": "101"}])
    )
    two = library.save_work(
        db, WorkData(title="Dos", kind="movie", actors=[{"name": "Nombre Igual", "fa_id": "202"}])
    )
    manual = library.save_work(db, WorkData(title="Tres", kind="movie", actors=[{"name": "Nombre Igual"}]))
    assert len({one.actors[0].id, two.actors[0].id, manual.actors[0].id}) == 3
    assert library.search(db, person_id=one.actors[0].id)["count"] == 1
    parsed = library.parse_people(
        "Nombre Igual\nNombre Igual",
        [{"name": "Nombre Igual", "fa_id": "101"}, {"name": "Nombre Igual", "fa_id": "202"}],
    )
    assert [p["fa_id"] for p in parsed] == ["101", "202"]


def test_json_v2_legacy_import_invalid_asset_and_consistent_backup(local_db, tmp_path):
    db = local_db
    work = library.save_work(
        db,
        WorkData(
            title="Obra de prueba",
            kind="movie",
            score="7.5",
            notes="Saltos\nde línea",
            aliases=[{"title": "Alias sintético"}],
            categories=["Drama"],
            directors=[{"name": "Dirección", "fa_id": "101"}],
            actors=[{"name": "Reparto", "fa_id": "202"}],
            poster=poster_data(),
        ),
    )
    before = library.work_data(work)
    export = transfers.export_library(db)
    assert export.version == 2
    assert transfers.import_library(db, transfers.read_import(export.model_dump_json().encode())) == (0, 1)
    corrupt = export.model_dump(mode="json")
    corrupt["works"][0]["poster"]["content"] = "Not base64"
    with pytest.raises(ValueError):
        transfers.read_import(json.dumps(corrupt).encode())
    assert library.work_data(db.get(Work, work.id)) == before
    path = tmp_path / "copy.sqlite3"
    backup(tmp_path / "library.sqlite3", path)
    restored = tmp_path / "restored.sqlite3"
    shutil.copyfile(path, restored)
    engine = make_engine(restored)
    with sessions(engine)() as other:
        assert library.work_data(other.get(Work, work.id)) == before
    engine.dispose()
    db.delete(work)
    db.commit()
    assert transfers.import_library(db, export) == (1, 0)
    assert library.work_data(db.scalar(select(Work))) == before
    legacy = export.model_dump(mode="json")
    legacy["version"] = 1
    for row in legacy["works"]:
        for key in ["poster", "actors", "directors"]:
            row.pop(key)
    assert transfers.read_import(json.dumps(legacy).encode()).works[0].poster is None


def test_orphan_posters_keep_cached_and_live_assets(local_db):
    db = local_db
    saved = library.save_work(db, WorkData(title="Una", kind="movie", poster=poster_data()))
    item = saved.poster
    db.delete(saved)
    db.commit()
    db.add(
        MetadataCache(
            fa_id="123",
            payload=json.dumps({"poster_id": item.id}),
            fetched_at=now(),
            expires_at=int(time.time()) + 60,
        )
    )
    db.commit()
    library.prune_posters(db)
    db.commit()
    assert db.get(Poster, item.id) is not None
    db.get(MetadataCache, "123").expires_at = 0
    db.commit()
    library.prune_posters(db)
    db.commit()
    assert db.scalar(select(func.count()).select_from(Poster)) == 0


def test_endpoint_preview_save_edit_person_navigation_and_image_failure(client, db, application):
    adapter = FilmAffinityAdapter(
        True,
        RequestsTransport(
            lambda request: httpx.Response(200, headers={"Content-Type": "image/png"}, content=image_bytes())
            if request.url.host == "pics.filmaffinity.com"
            else httpx.Response(200, text=HTML)
        ),
        resolver,
    )
    application.state.adapter = adapter
    token = csrf(client.get("/works/new"))
    response = client.post(
        "/metadata", data={"csrf": token, "fa_url": "https://m.filmaffinity.com/es/film123.html"}
    )
    assert (
        response.status_code == 200
        and "Conservar carátula" in response.text
        and "María Prueba" in response.text
    )
    cached = db.get(MetadataCache, "123")
    data = {
        "csrf": token,
        "fa_url": "https://www.filmaffinity.com/es/film123.html",
        "title": "El faro sintético",
        "kind": "movie",
        "directors": "María Prueba",
        "actors": "Actor Sintético",
        "metadata_confirm": "on",
        "metadata_obtained_at": cached.fetched_at,
        "poster_control": "1",
        "use_poster": "on",
        "score": "8.5",
        "notes": "Conservar mi opinión",
        "category_ids": "3",
    }
    response = client.post("/works", data=data)
    assert response.status_code == 200
    work = db.scalar(select(Work))
    assert work.poster_id and work.directors[0].fa_id == "101"
    image = client.get("/posters/" + work.poster_id)
    assert image.status_code == 200 and image.headers["content-type"] == "image/jpeg"
    assert "pics.filmaffinity.com" not in response.text.split("<img")[1].split(">")[0]
    person = client.get("/?person=" + str(work.directors[0].id))
    assert "Obras de" in person.text and "El faro sintético" in person.text
    assert client.post("/works/1/metadata", data={"fa_url": work.fa_url}).status_code == 403
    # Expire interval and request an explicit refresh whose image fails independently.
    from app.models import LoginLimit

    db.get(LoginLimit, "metadata-interval").reset_at = 0
    db.commit()
    application.state.adapter = FilmAffinityAdapter(
        True,
        RequestsTransport(
            lambda request: httpx.Response(403)
            if request.url.host == "pics.filmaffinity.com"
            else httpx.Response(200, text=HTML)
        ),
        resolver,
    )
    before = library.work_data(work)
    old_poster_id = work.poster_id
    response = client.post(f"/works/{work.id}/metadata", data={**data, "refresh_metadata": "1"})
    assert response.status_code == 200 and "No se ha obtenido la carátula" in response.text
    db.expire_all()
    assert library.work_data(db.get(Work, work.id)) == before
    cached = db.get(MetadataCache, "123")
    data["metadata_obtained_at"] = cached.fetched_at
    response = client.post(f"/works/{work.id}/edit", data=data)
    db.expire_all()
    updated = db.get(Work, work.id)
    assert updated.review.score == 8.5 and updated.review.notes == "Conservar mi opinión"
    assert updated.poster_id == old_poster_id and [c.id for c in updated.categories] == [3]
    data["poster_control"], data["use_poster"] = "1", ""
    client.post(f"/works/{work.id}/edit", data=data)
    db.expire_all()
    assert db.get(Work, work.id).poster_id is None
