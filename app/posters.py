"""Bounded FilmAffinity image download and local, non-executable poster assets."""

import io
import ipaddress
import re
import socket
import time
import warnings
from urllib.parse import urljoin, urlsplit

import requests
from PIL import Image, ImageOps

from app.filmaffinity import MAX_REDIRECTS, REQUEST_HEADERS, MetadataSession, MetadataUnavailable

IMAGE_HOSTS = {"pics.filmaffinity.com"}
MAX_DOWNLOAD_BYTES = 3 * 1024 * 1024
MAX_SAVED_BYTES = 180_000
MAX_PIXELS = 12_000_000
FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def poster_url(value):
    if not isinstance(value, str) or len(value) > 1000 or "\\" in value or any(ord(c) < 33 for c in value):
        raise ValueError("URL de carátula no admitida.")
    try:
        parts = urlsplit(value)
        if (
            parts.scheme != "https"
            or parts.hostname not in IMAGE_HOSTS
            or parts.username is not None
            or parts.password is not None
            or parts.port is not None
            or parts.query
            or parts.fragment
            or not re.fullmatch(r"/[A-Za-z0-9_/-]+\.(?:jpg|jpeg|png|webp)", parts.path, re.I)
        ):
            raise ValueError()
    except ValueError:
        raise ValueError(
            "Solo se admiten imágenes HTTPS de pics.filmaffinity.com, sin credenciales ni puertos."
        ) from None
    return value


def _image(data):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if (
                    image.format not in FORMATS
                    or image.width * image.height > MAX_PIXELS
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise ValueError()
                image.load()
                return image.copy(), FORMATS[image.format]
    except (OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise MetadataUnavailable(
            "La carátula no es una imagen estática válida o supera el tamaño permitido."
        ) from None


def normalize_poster(data):
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise MetadataUnavailable("La carátula supera el límite de 3 MiB.")
    image, _ = _image(data)
    image = ImageOps.exif_transpose(image)
    image.thumbnail((400, 600), Image.Resampling.LANCZOS)
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", image.size, "white")
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        image = canvas
    else:
        image = image.convert("RGB")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=80, optimize=True)
    content = output.getvalue()
    if len(content) > MAX_SAVED_BYTES:
        raise MetadataUnavailable("La carátula optimizada es demasiado grande.")
    return content


def validate_saved_poster(data, media_type):
    if not data or len(data) > MAX_SAVED_BYTES:
        raise ValueError("La carátula guardada supera el tamaño permitido.")
    image, actual_type = _image(data)
    if actual_type != media_type or image.width > 400 or image.height > 600:
        raise ValueError("Formato o dimensiones de carátula inválidos.")


class PosterFetcher:
    def __init__(self, enabled=False, transport=None, resolver=socket.getaddrinfo):
        self.enabled, self.transport, self.resolver = enabled, transport, resolver

    def fetch(self, source):
        source = poster_url(source)
        if not self.enabled:
            raise MetadataUnavailable("La descarga de carátulas está desactivada junto al autocompletado.")
        started = time.monotonic()
        try:
            with MetadataSession() as client:
                client.headers.update(REQUEST_HEADERS)
                if self.transport is not None:
                    client.mount("https://", self.transport)
                destination = source
                for hop in range(MAX_REDIRECTS + 1):
                    poster_url(destination)
                    addresses = self.resolver(urlsplit(destination).hostname, 443, type=socket.SOCK_STREAM)
                    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
                        raise MetadataUnavailable(
                            "El destino de la carátula no resuelve a una dirección pública."
                        )
                    with client.get(
                        destination, stream=True, allow_redirects=False, timeout=(4, 8)
                    ) as response:
                        if response.status_code in {301, 302, 303, 307, 308}:
                            location = response.headers.get("Location", "")
                            if not location or hop == MAX_REDIRECTS:
                                raise MetadataUnavailable(
                                    "Redirección de carátula no permitida o demasiado larga."
                                )
                            destination = poster_url(urljoin(destination, location))
                            continue
                        if response.status_code != 200 or response.headers.get("cf-mitigated") == "challenge":
                            raise MetadataUnavailable(
                                f"FilmAffinity no permite descargar la carátula (HTTP {response.status_code})."
                            )
                        media_type = response.headers.get("Content-Type", "").split(";")[0].lower().strip()
                        if media_type not in FORMATS.values():
                            raise MetadataUnavailable(
                                "La respuesta de la carátula no tiene un formato de imagen permitido."
                            )
                        chunks, size = [], 0
                        for chunk in response.iter_content(chunk_size=8192):
                            size += len(chunk)
                            if size > MAX_DOWNLOAD_BYTES or time.monotonic() - started > 24:
                                raise MetadataUnavailable(
                                    "La descarga de carátula supera el tamaño o tiempo permitido."
                                )
                            chunks.append(chunk)
                        return {
                            "data": normalize_poster(b"".join(chunks)),
                            "media_type": "image/jpeg",
                            "source_url": source,
                        }
        except (requests.RequestException, OSError):
            raise MetadataUnavailable("No se ha podido conectar para descargar la carátula.") from None
