import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app import auth, library
from app.filmaffinity import FilmAffinityAdapter, MetadataUnavailable, parse_metadata, parse_url, robots_allowed
from app.models import BrowserSession
from app.schemas import WorkData
from tests.conftest import PASSWORD, csrf

HTML = '''<main itemscope itemtype="https://schema.org/Movie"><h1 id="main-title"><span>El faro de prueba</span></h1><dl><dt>Título original</dt><dd>Synthetic Lighthouse</dd><dt>Año</dt><dd>2024</dd><dt>Género</dt><dd><a href="/es/moviegenre.php?genre=DR">Drama</a><a href="/es/movietopic.php?topic=1">Tema</a></dd></dl></main>'''


@pytest.mark.parametrize("url",["https://evil.test/es/film1.html","https://www.filmaffinity.com.evil.test/es/film1.html","https://u:p@filmaffinity.com/es/film1.html","https://filmaffinity.com:443/es/film1.html","https://127.0.0.1/es/film1.html","file:///es/film1.html","https://filmaffinity.com/es/film0.html","https://filmaffinity.com/es/search.php","https://filmaffinity.com/\\@evil.test/es/film1.html","https://filmaffinity.com/es/film1.html\n"])
def test_invalid_urls(url):
    with pytest.raises(ValueError):
        parse_url(url)


def test_parser_synthetic():
    data = parse_metadata(HTML)
    assert data == {"title":"El faro de prueba", "original_title":"Synthetic Lighthouse", "year":2024, "kind":"movie", "genres":["Drama"], "aliases":[]}
    assert parse_metadata(HTML.replace("Drama</a>","Serie de TV</a>"))["kind"] == "series"
    with pytest.raises(MetadataUnavailable):
        parse_metadata("<html>captcha</html>")
    with pytest.raises(MetadataUnavailable):
        parse_metadata("<html>nuevo formato</html>")


def resolver(*args, **kwargs):
    return [(2, 1, 6, "", ("8.8.8.8",443))]


@pytest.mark.parametrize("status", [403,429,302,500])
def test_simulated_http_refusals(status):
    calls=[]
    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200,text="User-agent: *\nAllow: /") if request.url.path == "/robots.txt" else httpx.Response(status,headers={"Location":"https://evil.test/"})
    adapter = FilmAffinityAdapter(True,httpx.MockTransport(handler),resolver)
    with pytest.raises(MetadataUnavailable):
        adapter.fetch("123")
    assert len(calls)==2 and not any("evil" in x for x in calls)


def test_adapter_limits_robots_offline_and_private():
    assert not robots_allowed("User-agent: *\nDisallow: /es/film*", "/es/film1.html")
    assert robots_allowed("User-agent: *\nDisallow: /\nAllow: /es/film1.html$", "/es/film1.html")
    requests=[]
    def handler(request):
        requests.append(request.url.path)
        return httpx.Response(200,text="User-agent: *\nDisallow: /" if request.url.path == "/robots.txt" else HTML)
    adapter=FilmAffinityAdapter(True,httpx.MockTransport(handler),resolver)
    with pytest.raises(MetadataUnavailable):
        adapter.fetch("123")
    assert requests == ["/robots.txt"]
    with pytest.raises(MetadataUnavailable):
        FilmAffinityAdapter().fetch("123")
    def private(*a, **kw):
        return [(2,1,6,"",("127.0.0.1",443))]
    with pytest.raises(MetadataUnavailable):
        FilmAffinityAdapter(True,httpx.MockTransport(handler),private).fetch("123")
    def offline(request):
        raise httpx.ConnectError("offline")
    with pytest.raises(MetadataUnavailable):
        FilmAffinityAdapter(True,httpx.MockTransport(offline),resolver).fetch("123")
    def oversized(request):
        return httpx.Response(200,text="User-agent: *\nAllow: /" if request.url.path == "/robots.txt" else "X"*1_500_001)
    with pytest.raises(MetadataUnavailable):
        FilmAffinityAdapter(True,httpx.MockTransport(oversized),resolver).fetch("123")


def test_auth_csrf_escape_cookie(client, db):
    assert client.post("/works",data={"title":"Inseguro","kind":"movie"}).status_code == 403
    work=library.save_work(db,WorkData(title="<script>alert(1)</script>",kind="movie",notes="<img src=x onerror=alert(2)>"))
    page=client.get(f"/works/{work.id}")
    assert "&lt;script&gt;" in page.text and "<img src=x" not in page.text
    assert "frame-ancestors 'none'" in page.headers["content-security-policy"]
    cookie=client.cookies.get("nlvav_session")
    session=db.get(BrowserSession,auth.token_hash(cookie))
    session.expires_at=int(time.time())-1
    db.commit()
    assert client.get("/",follow_redirects=False).headers["location"] == "/login"


def test_login_limits_logout_change_password(application):
    with TestClient(application) as client:
        response=client.get("/login")
        assert "HttpOnly" in response.headers["set-cookie"] and "SameSite=lax" in response.headers["set-cookie"]
        assert "Secure;" not in response.headers["set-cookie"]
        token=csrf(response)
        assert client.post("/login",data={"csrf":"bad","username":"test","password":PASSWORD}).status_code == 403
        for _ in range(10):
            assert client.post("/login",data={"csrf":token,"username":"test","password":"incorrecta"}).status_code==401
        assert client.post("/login",data={"csrf":token,"username":"test","password":PASSWORD}).status_code==429


def test_password_change(client):
    token=csrf(client.get("/settings"))
    response=client.post("/password",data={"csrf":token,"current":PASSWORD,"new":"nueva-contraseña-larga","repeat":"nueva-contraseña-larga"})
    assert response.url.path == "/login"
    token=csrf(response)
    assert client.post("/login",data={"csrf":token,"username":"test","password":"nueva-contraseña-larga"}).status_code==200
    token=csrf(client.get("/settings"))
    assert client.post("/logout",data={"csrf":token}).url.path == "/login"


def test_hash():
    first,second=auth.password_hash(PASSWORD),auth.password_hash(PASSWORD)
    assert first != second and PASSWORD not in first and auth.verify_password(PASSWORD,first)
