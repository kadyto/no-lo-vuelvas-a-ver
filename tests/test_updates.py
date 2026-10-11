import io
import shutil
import subprocess
import tarfile
import threading

import httpx
import pytest

from app.updates import CACHE_SECONDS, PROJECT_URL, RETRY_SECONDS, BuildInfo, UpdateChecker

OLD, NEW = "1" * 40, "2" * 40


def checker(build=None, payload=None, status=200):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "api.github.com"
        assert "Authorization" not in request.headers and "Cookie" not in request.headers
        return httpx.Response(status, json=payload)

    return UpdateChecker(build or BuildInfo("v1.0.0", OLD), transport=httpx.MockTransport(handler)), calls


@pytest.mark.parametrize(
    "tag,expected",
    [("v1.0.0", "current"), ("v0.9.9", "current"), ("v1.0.1", "available"), ("v1.10.0", "available")],
)
def test_stable_versions_compare_numerically(tag, expected):
    service, calls = checker(payload={"tag_name": tag, "html_url": "https://evil.test/"})
    result = service.check()
    assert result["status"] == expected
    assert calls[0].url.path.endswith("/releases/latest")
    if expected == "available":
        assert result["url"] == f"{PROJECT_URL}/releases/tag/{tag}"


def test_no_release_published():
    service, _ = checker(status=404)
    assert service.check()["status"] == "no_releases"


@pytest.mark.parametrize("sha,expected", [(OLD, "current"), (NEW, "available")])
def test_main_build_compares_installed_snapshot(sha, expected):
    service, calls = checker(BuildInfo("development", OLD), {"object": {"type": "commit", "sha": sha}})
    result = service.check()
    assert result["status"] == expected
    assert calls[0].url.path.endswith("/git/ref/heads/main")
    if expected == "available":
        assert result["url"] == f"{PROJECT_URL}/compare/{OLD}...{NEW}"


def test_unknown_build_and_disabled_do_not_connect():
    service, calls = checker(BuildInfo())
    assert service.check()["status"] == "unknown"
    service.enabled = False
    assert service.check()["status"] == "disabled"
    assert calls == []


def test_shared_cache_success_and_offline_backoff():
    service, calls = checker(payload={"tag_name": "v1.0.1"})
    clock = [100]
    service.clock = lambda: clock[0]
    first = service.check()
    assert service.check() == first and len(calls) == 1
    first["status"] = "modified"
    assert service.check()["status"] == "available"
    clock[0] += CACHE_SECONDS
    assert service.check()["status"] == "available" and len(calls) == 2

    def offline(request):
        calls.append(request)
        raise httpx.ConnectError("synthetic offline")

    service.transport = httpx.MockTransport(offline)
    clock[0] += CACHE_SECONDS
    assert service.check()["status"] == "unavailable"
    assert service.check()["status"] == "unavailable" and len(calls) == 3
    clock[0] += RETRY_SECONDS
    assert service.check()["status"] == "unavailable" and len(calls) == 4


@pytest.mark.parametrize("status", [302, 403, 429, 500])
def test_http_failures_do_not_follow_redirects_or_retry(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, headers={"Location": "https://evil.test/"})

    service = UpdateChecker(BuildInfo("v1.0.0"), transport=httpx.MockTransport(handler))
    assert service.check()["status"] == "unavailable"
    assert service.check()["status"] == "unavailable" and len(calls) == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"tag_name": "v1.0.1-rc1"},
        {"tag_name": "../../evil"},
        {"tag_name": "v1.0.1", "draft": True},
        {"tag_name": "v1.0.1", "prerelease": True},
        [],
        {"tag_name": 100},
    ],
)
def test_invalid_release_not_shown(payload):
    service, _ = checker(payload=payload)
    assert service.check()["status"] == "unavailable"


def test_response_size_limit():
    service = UpdateChecker(
        BuildInfo("v1.0.0"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="X" * 262_145)),
    )
    assert service.check()["status"] == "unavailable"


def test_concurrent_checks_do_not_block_or_duplicate_requests():
    entered, release = threading.Event(), threading.Event()
    calls = []

    def handler(request):
        calls.append(request)
        entered.set()
        assert release.wait(2)
        return httpx.Response(200, json={"tag_name": "v1.0.1"})

    service = UpdateChecker(BuildInfo("v1.0.0"), transport=httpx.MockTransport(handler))
    thread = threading.Thread(target=service.check)
    thread.start()
    try:
        assert entered.wait(2)
        assert service.check()["status"] == "checking"
        assert len(calls) == 1
    finally:
        release.set()
        thread.join(timeout=2)
    assert not thread.is_alive() and service.check()["status"] == "available"


def test_archive_revision_and_release_environment(tmp_path, monkeypatch):
    for name in ["APP_REVISION", "APP_VERSION", "APP_SOURCE"]:
        monkeypatch.delenv(name, raising=False)
    path = tmp_path / "revision.txt"
    path.write_text(OLD)
    build = BuildInfo.from_env(path)
    assert build.revision == OLD and build.label == "Desarrollo · 1111111"
    monkeypatch.setenv("APP_VERSION", "v1.2.3")
    monkeypatch.setenv("APP_REVISION", NEW)
    monkeypatch.setenv("APP_SOURCE", "https://github.com/synthetic/library.git")
    build = BuildInfo.from_env(path)
    assert build.label == "v1.2.3" and build.revision == NEW
    assert build.project_url == "https://github.com/synthetic/library"
    monkeypatch.setenv("APP_REVISION", "")
    path.write_text("$Format:%H$")
    monkeypatch.setenv("APP_SOURCE", "https://github.com.evil.test/synthetic/library")
    assert BuildInfo.from_env(path).revision == ""
    assert BuildInfo.from_env(path).project_url == PROJECT_URL


@pytest.mark.skipif(shutil.which("git") is None, reason="Requiere git archive")
def test_git_archive_records_snapshot_revision(tmp_path, monkeypatch):
    (tmp_path / "app").mkdir()
    (tmp_path / "app/_archive_revision.txt").write_text("$Format:%H$\n")
    (tmp_path / ".gitattributes").write_text("app/_archive_revision.txt export-subst\n")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Pruebas",
            "-c",
            "user.email=synthetic@example.invalid",
            "commit",
            "-qm",
            "Synthetic",
        ],
        cwd=tmp_path,
        check=True,
    )
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
    data = subprocess.check_output(["git", "archive", "HEAD"], cwd=tmp_path)
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        revision = archive.extractfile("app/_archive_revision.txt").read().decode().strip()
    assert revision == sha
    path = tmp_path / "exported-revision.txt"
    path.write_text(revision)
    monkeypatch.delenv("APP_REVISION", raising=False)
    assert BuildInfo.from_env(path).revision == sha


def test_endpoint_authentication_and_offline_library(client, application):
    service, _ = checker(payload={"tag_name": "v1.0.1"})
    application.state.updates = service
    result = client.get("/updates")
    assert result.status_code == 200 and result.json()["status"] == "available"
    response = client.get("/")
    assert (
        "Una historia, un recuerdo." not in response.text
        and "EL ARCHIVO DE LO QUE YA VISTE" not in response.text
    )
    assert f'href="{PROJECT_URL}"' in response.text and "Proyecto en GitHub" in response.text
    service.enabled = False
    assert client.get("/updates").json()["status"] == "disabled"
    assert client.get("/").status_code == 200
    client.cookies.clear()
    assert client.get("/updates", follow_redirects=False).headers["location"] == "/login"
