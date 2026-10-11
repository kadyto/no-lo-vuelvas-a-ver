"""Optional GitHub update notice; no library data, credentials or automatic installation."""

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

PROJECT_URL = "https://github.com/kadyto/no-lo-vuelvas-a-ver"
STABLE_VERSION = re.compile(r"v?([0-9]+)\.([0-9]+)\.([0-9]+)")
REVISION = re.compile(r"[0-9a-f]{40}")
CACHE_SECONDS = 6 * 3600
RETRY_SECONDS = 15 * 60
MAX_BYTES = 262_144


@dataclass(frozen=True)
class BuildInfo:
    version: str = "development"
    revision: str = ""
    project_url: str = PROJECT_URL

    @classmethod
    def from_env(cls, archive_path=None):
        version = os.getenv("APP_VERSION", "development")[:64]
        revision = os.getenv("APP_REVISION", "").strip()
        if not REVISION.fullmatch(revision):
            path = archive_path or Path(__file__).with_name("_archive_revision.txt")
            try:
                revision = path.read_text().strip()
            except OSError:
                revision = ""
        revision = revision if REVISION.fullmatch(revision) else ""
        source = os.getenv("APP_SOURCE", PROJECT_URL).rstrip("/").removesuffix(".git")
        try:
            parts = urlsplit(source)
            if (
                parts.scheme != "https"
                or parts.netloc != "github.com"
                or parts.query
                or parts.fragment
                or not re.fullmatch(r"/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", parts.path)
                or parts.path.split("/")[-1] in {".", ".."}
            ):
                source = PROJECT_URL
        except ValueError:
            source = PROJECT_URL
        return cls(version, revision, source)

    @property
    def stable(self):
        match = STABLE_VERSION.fullmatch(self.version)
        return tuple(map(int, match.groups())) if match else None

    @property
    def label(self):
        if self.stable is not None:
            return "v" + ".".join(map(str, self.stable))
        return "Desarrollo" + (f" · {self.revision[:7]}" if self.revision else "")


class UpdateChecker:
    def __init__(self, build, enabled=True, transport=None, clock=time.monotonic):
        self.build, self.enabled, self.transport, self.clock = build, enabled, transport, clock
        self._lock = threading.Lock()
        self._next_check = 0
        self._result = {"status": "checking", "message": "Comprobando actualizaciones…"}

    def _fetch(self, endpoint):
        repository = self.build.project_url.removeprefix("https://github.com/")
        url = f"https://api.github.com/repos/{repository}/{endpoint}"
        started = time.monotonic()
        with httpx.Client(
            timeout=httpx.Timeout(4, connect=2),
            follow_redirects=False,
            transport=self.transport,
            headers={"Accept": "application/vnd.github+json", "User-Agent": "NoLoVuelvasAVer-update-check"},
        ) as client:
            with client.stream("GET", url) as response:
                if response.status_code == 404 and endpoint == "releases/latest":
                    return None
                response.raise_for_status()
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES or time.monotonic() - started > 8:
                        raise ValueError("Respuesta demasiado grande")
                    chunks.append(chunk)
                result = json.loads(b"".join(chunks))
                if not isinstance(result, dict):
                    raise ValueError("Respuesta inválida")
                return result

    def _lookup(self):
        if self.build.stable is not None:
            latest = self._fetch("releases/latest")
            if latest is None:
                return {"status": "no_releases", "message": "Sin releases publicadas"}
            tag = latest.get("tag_name", "")
            match = STABLE_VERSION.fullmatch(tag) if isinstance(tag, str) else None
            if not match or latest.get("prerelease") or latest.get("draft"):
                raise ValueError("No es una versión estable")
            version = tuple(map(int, match.groups()))
            if version > self.build.stable:
                return {
                    "status": "available",
                    "message": f"Nueva versión: {tag}",
                    "url": f"{self.build.project_url}/releases/tag/{tag}",
                }
        elif self.build.revision:
            latest = self._fetch("git/ref/heads/main")
            ref = latest.get("object", {})
            revision = ref.get("sha", "")
            if (
                ref.get("type") != "commit"
                or not isinstance(revision, str)
                or not REVISION.fullmatch(revision)
            ):
                raise ValueError("Referencia inválida")
            if revision != self.build.revision:
                return {
                    "status": "available",
                    "message": "Actualización disponible en main",
                    "url": f"{self.build.project_url}/compare/{self.build.revision}...{revision}",
                }
        else:
            return {"status": "unknown", "message": "Versión instalada sin identificador"}
        return {"status": "current", "message": "Al día"}

    def check(self):
        if not self.enabled:
            return {"status": "disabled", "message": "Aviso de actualizaciones desactivado"}
        if self.clock() < self._next_check:
            return dict(self._result)
        if not self._lock.acquire(blocking=False):
            return dict(self._result)
        try:
            if self.clock() < self._next_check:
                return dict(self._result)
            duration = CACHE_SECONDS
            try:
                self._result = self._lookup()
            except (httpx.HTTPError, OSError, ValueError, TypeError, AttributeError):
                duration = RETRY_SECONDS
                self._result = {
                    "status": "unavailable",
                    "message": "No se pudieron comprobar las actualizaciones",
                }
            self._next_check = self.clock() + duration
            return dict(self._result)
        finally:
            self._lock.release()
