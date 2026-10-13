"""Explicit browser-test server with synthetic metadata, never a production provider."""

import io

from PIL import Image, ImageDraw

from app.filmaffinity import MetadataUnavailable
from app.main import create_app
from app.posters import normalize_poster

SOURCE = "https://pics.filmaffinity.com/synthetic_preview-900001-large.jpg"


class SyntheticAdapter:
    def fetch(self, fa_id, source_url=None):
        if fa_id != "900001":
            raise MetadataUnavailable(
                "Autocompletado no disponible para esta ficha sintética. Completa los datos a mano."
            )
        return {
            "title": "El último proyector",
            "original_title": None,
            "kind": "movie",
            "year": 2024,
            "aliases": [],
            "genres": ["Drama"],
            "directors": [{"name": "Dirección ficticia", "fa_id": "901"}],
            "actors": [{"name": "Actor ficticio", "fa_id": "902"}],
            "poster_url": SOURCE,
        }

    def fetch_poster(self, url):
        if url != SOURCE:
            raise MetadataUnavailable("Carátula sintética desconocida.")
        image = Image.new("RGB", (400, 600), "#081d49")
        draw = ImageDraw.Draw(image)
        draw.rectangle((24, 24, 376, 576), outline="#ffcc00", width=3)
        draw.ellipse((80, 120, 320, 360), fill="#ffcc00")
        for x, y in [(200, 180), (138, 220), (262, 220), (162, 295), (238, 295)]:
            draw.ellipse((x - 27, y - 27, x + 27, y + 27), fill="#0052cc")
        draw.text((52, 45), "DATOS FICTICIOS", fill="white", font_size=27)
        draw.multiline_text((52, 420), "EL ÚLTIMO\nPROYECTOR", fill="white", font_size=40, spacing=8)
        output = io.BytesIO()
        image.save(output, format="PNG")
        return {"data": normalize_poster(output.getvalue()), "media_type": "image/jpeg", "source_url": SOURCE}


app = create_app(adapter=SyntheticAdapter())
