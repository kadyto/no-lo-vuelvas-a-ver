"""Adaptador opcional: solo metadatos mínimos, nunca catálogo ni contenidos editoriales."""

import fnmatch
import ipaddress
import re
import socket
import time
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

HOSTS = {"www.filmaffinity.com", "m.filmaffinity.com", "filmaffinity.com"}
USER_AGENT = "NoLoVuelvasAVer/0.1 (personal-library; metadata-on-request)"
MAX_BYTES = 1_500_000


class MetadataUnavailable(ValueError):
    pass


def parse_url(url: str) -> str:
    if len(url) > 500 or any(ord(x) < 33 for x in url) or "\\" in url:
        raise ValueError("Pega una URL válida de una ficha de FilmAffinity.")
    try:
        parts = urlsplit(url)
        if (
            parts.scheme not in {"http", "https"}
            or parts.hostname not in HOSTS
            or parts.username is not None
            or parts.password is not None
            or parts.port is not None
        ):
            raise ValueError()
        match = re.fullmatch(r"/[a-z]{2}/film([0-9]{1,16})\.html", parts.path)
        if not match or int(match[1]) == 0:
            raise ValueError()
        return str(int(match[1]))
    except ValueError:
        raise ValueError(
            "Solo se admiten fichas film<ID>.html de FilmAffinity, sin credenciales ni puertos."
        ) from None


def canonical_url(fa_id):
    if not re.fullmatch(r"[1-9][0-9]{0,15}", str(fa_id)):
        raise ValueError("ID inválido.")
    return f"https://www.filmaffinity.com/es/film{fa_id}.html"


def human_check_required(soup):
    return bool(
        soup.select(".g-recaptcha, .h-captcha, .cf-turnstile, #captcha, #challenge-form")
        or re.search(
            r"captcha|just a moment|verify you are human|verifica que eres humano",
            soup.get_text(),
            re.I,
        )
    )


def parse_metadata(html):
    soup = BeautifulSoup(html, "html.parser")
    if human_check_required(soup):
        raise MetadataUnavailable(
            "FilmAffinity pide un captcha o una comprobación humana en la ficha (HTTP 200). "
            "Resolverla en tu navegador no habilita necesariamente la consulta del servidor. "
            "Completa los datos a mano."
        )
    title_el = soup.select_one("#main-title span, h1[itemprop='name']")
    if not title_el or not title_el.get_text(strip=True):
        raise MetadataUnavailable(
            "El HTML de FilmAffinity ha cambiado o no contiene una ficha. Completa los datos a mano."
        )
    title = title_el.get_text(" ", strip=True)
    original, year, genres, kind = None, None, [], None
    for dt in soup.select("dt"):
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        label = dt.get_text(" ", strip=True).lower()
        value = dd.get_text(" ", strip=True)
        if label == "título original":
            original = value
        elif label == "año":
            match = re.match(r"(\d{4})", value)
            year = int(match[1]) if match else None
        elif label == "género":
            genres = [
                a.get_text(strip=True) for a in dd.select("a") if "/moviegenre.php" in a.get("href", "")
            ]
            if "Serie de TV" in value:
                kind = "series"
    # An explicit schema.org type is accepted; absent evidence leaves type for the user.
    if soup.select_one('[itemtype="https://schema.org/Movie"], [itemtype="http://schema.org/Movie"]'):
        kind = kind or "movie"
    if soup.select_one('[itemtype="https://schema.org/TVSeries"], [itemtype="http://schema.org/TVSeries"]'):
        kind = "series"
    return {
        "title": title[:300],
        "original_title": (original or "")[:300] or None,
        "year": year,
        "kind": kind,
        "genres": list(dict.fromkeys(genres))[:12],
        "aliases": [],
    }


def robots_allowed(text, path):
    # Honor * and $ conservatively, longest matching Allow/Disallow; specific agent overrides *.
    groups, agents, rules = [], [], []
    for line in text.splitlines() + ["User-agent: end-sentinel"]:
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        name, value = [x.strip() for x in line.split(":", 1)]
        name = name.lower()
        if name == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(value.lower())
        elif name in {"allow", "disallow"} and agents and value:
            rules.append((name, value))
    specific = [r for a, r in groups if any(x != "*" and x in USER_AGENT.lower() for x in a)]
    chosen = specific or [r for a, r in groups if "*" in a]
    matches = []
    for group in chosen:
        for name, pattern in group:
            anchored = pattern.endswith("$")
            pattern = pattern.rstrip("$")
            if fnmatch.fnmatchcase(path, pattern + ("" if anchored else "*")):
                matches.append((len(pattern.replace("*", "")), name == "allow"))
    return max(matches, default=(0, True))[1]


class FilmAffinityAdapter:
    def __init__(self, enabled=False, transport=None, resolver=socket.getaddrinfo):
        self.enabled, self.transport, self.resolver = enabled, transport, resolver
        self._robots = None

    def _read(self, client, url, limit=MAX_BYTES):
        with client.stream("GET", url) as response:
            resource = "robots.txt" if urlsplit(url).path == "/robots.txt" else "la ficha"
            if response.status_code != 200:
                detail = f"HTTP {response.status_code} al consultar {resource}"
                if response.status_code == 403:
                    # Inspect only a bounded prefix; never expose, persist or execute the remote HTML.
                    chunks, size, sample_limit = [], 0, min(limit, 32_768)
                    for chunk in response.iter_bytes(chunk_size=8192):
                        part = chunk[: sample_limit - size]
                        chunks.append(part)
                        size += len(part)
                        if size >= sample_limit:
                            break
                    soup = BeautifulSoup(b"".join(chunks).decode("utf-8", errors="replace"), "html.parser")
                    if human_check_required(soup):
                        message = (
                            f"FilmAffinity pide un captcha o una comprobación humana ({detail}). "
                            "Resolverla en tu navegador no habilita necesariamente la consulta del servidor"
                        )
                    else:
                        message = (
                            f"FilmAffinity ha bloqueado el acceso ({detail}). "
                            "Esta respuesta no permite confirmar si exige un captcha"
                        )
                elif response.status_code == 429:
                    message = (
                        f"FilmAffinity limita las consultas ({detail}). Espera antes de volver a intentarlo"
                    )
                elif 300 <= response.status_code < 400:
                    message = (
                        f"FilmAffinity devuelve una redirección ({detail}). Por seguridad no se ha seguido"
                    )
                else:
                    message = f"FilmAffinity no permite obtener los datos ({detail})"
                raise MetadataUnavailable(message + ". Completa los datos a mano.")
            size, chunks = 0, []
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > limit:
                    raise MetadataUnavailable("La respuesta es demasiado grande. Completa los datos a mano.")
                chunks.append(chunk)
            body = b"".join(chunks).decode("utf-8", errors="replace")
            if resource == "robots.txt" and (
                "text/html" in response.headers.get("content-type", "").lower()
                or re.search(r"<(?:!doctype\s+html|html|body|head|form|div|script)\b", body, re.I)
            ):
                if human_check_required(BeautifulSoup(body, "html.parser")):
                    raise MetadataUnavailable(
                        "FilmAffinity pide un captcha o una comprobación humana al consultar robots.txt (HTTP 200). "
                        "Resolverla en tu navegador no habilita necesariamente la consulta del servidor. "
                        "Completa los datos a mano."
                    )
                raise MetadataUnavailable(
                    "FilmAffinity devolvió HTML en lugar de reglas de acceso (robots.txt, HTTP 200). "
                    "No se ha consultado la ficha. Completa los datos a mano."
                )
            return body

    def fetch(self, fa_id):
        url = canonical_url(fa_id)
        if not self.enabled:
            raise MetadataUnavailable(
                "Autocompletado desactivado: no se ha verificado el permiso de acceso automatizado. La URL y el ID se conservan; completa los datos a mano."
            )
        try:
            addresses = self.resolver("www.filmaffinity.com", 443, type=socket.SOCK_STREAM)
            if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
                raise MetadataUnavailable("El destino de FilmAffinity no resuelve a una dirección pública.")
            with httpx.Client(
                timeout=httpx.Timeout(8, connect=4),
                follow_redirects=False,
                headers={"User-Agent": USER_AGENT},
                transport=self.transport,
            ) as client:
                if self._robots is None or self._robots[0] < time.time():
                    robots = self._read(client, "https://www.filmaffinity.com/robots.txt", 100_000)
                    self._robots = (time.time() + 86400, robots)
                if not robots_allowed(self._robots[1], urlsplit(url).path):
                    raise MetadataUnavailable(
                        "Las reglas de acceso de FilmAffinity (robots.txt) no permiten consultar esta ficha. "
                        "No es un captcha que puedas resolver. Completa los datos a mano."
                    )
                return parse_metadata(self._read(client, url))
        except (httpx.HTTPError, OSError):
            raise MetadataUnavailable(
                "No se ha podido conectar con FilmAffinity. Completa los datos a mano."
            ) from None
