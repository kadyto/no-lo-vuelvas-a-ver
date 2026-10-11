"""Adaptador opcional: solo metadatos mínimos, nunca catálogo ni contenidos editoriales."""

import ipaddress
import re
import socket
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

HOSTS = {"www.filmaffinity.com", "m.filmaffinity.com", "filmaffinity.com"}
# Same compatibility User-Agent as changedetection.io's default HTTP fetcher.
# This is still an HTTP client: it does not run JavaScript or solve challenges.
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.66 Safari/537.36"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}
MAX_BYTES = 1_500_000
MAX_REDIRECTS = 3


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


class FilmAffinityAdapter:
    def __init__(self, enabled=False, transport=None, resolver=socket.getaddrinfo):
        self.enabled, self.transport, self.resolver = enabled, transport, resolver

    def _validate_public_host(self, url):
        addresses = self.resolver(urlsplit(url).hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
            raise MetadataUnavailable("El destino de FilmAffinity no resuelve a una dirección pública.")

    def _read(self, client, url, limit=MAX_BYTES, redirects=0):
        self._validate_public_host(url)
        with client.stream("GET", url) as response:
            if response.status_code in {301, 302, 303, 307, 308}:
                location = response.headers.get("Location", "")
                destination = urljoin(url, location)
                try:
                    if (
                        not location
                        or urlsplit(destination).scheme != "https"
                        or parse_url(destination) != parse_url(url)
                    ):
                        raise ValueError()
                except ValueError:
                    raise MetadataUnavailable(
                        f"FilmAffinity devuelve una redirección no permitida (HTTP {response.status_code} "
                        "al consultar la ficha). Completa los datos a mano."
                    ) from None
                if redirects >= MAX_REDIRECTS:
                    raise MetadataUnavailable(
                        "FilmAffinity devuelve demasiadas redirecciones al consultar la ficha. "
                        "Completa los datos a mano."
                    )
                response.close()
                return self._read(client, destination, limit, redirects + 1)
            challenge = response.headers.get("cf-mitigated") == "challenge"
            if response.status_code != 200 or challenge:
                detail = f"HTTP {response.status_code} al consultar la ficha"
                if response.status_code == 403 or challenge:
                    # Inspect only a bounded prefix; never expose, persist or execute the remote HTML.
                    chunks, size, sample_limit = [], 0, min(limit, 32_768)
                    for chunk in response.iter_bytes(chunk_size=8192):
                        part = chunk[: sample_limit - size]
                        chunks.append(part)
                        size += len(part)
                        if size >= sample_limit:
                            break
                    soup = BeautifulSoup(b"".join(chunks).decode("utf-8", errors="replace"), "html.parser")
                    if human_check_required(soup) or challenge:
                        message = (
                            f"FilmAffinity pide un captcha o una comprobación humana ({detail}). "
                            "El cliente HTTP no ejecuta JavaScript. Resolverla en tu navegador no habilita "
                            "necesariamente la consulta del servidor"
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
            return b"".join(chunks).decode("utf-8", errors="replace")

    def fetch(self, fa_id):
        url = canonical_url(fa_id)
        if not self.enabled:
            raise MetadataUnavailable(
                "Autocompletado desactivado en esta instalación. La URL y el ID se conservan; completa los datos a mano."
            )
        try:
            with httpx.Client(
                timeout=httpx.Timeout(8, connect=4),
                follow_redirects=False,
                headers=REQUEST_HEADERS,
                transport=self.transport,
            ) as client:
                return parse_metadata(self._read(client, url))
        except (httpx.HTTPError, OSError):
            raise MetadataUnavailable(
                "No se ha podido conectar con FilmAffinity. Completa los datos a mano."
            ) from None
