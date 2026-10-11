"""Prueba visual explícita con biblioteca sintética y servidor temporal local.
Uso: uv run --frozen python tests/browser_smoke.py
Requiere Chromium del sistema o `uv run playwright install chromium`.
"""

import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright


def main():
    artifacts = Path("test-results")
    artifacts.mkdir(exist_ok=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    password = secrets.token_urlsafe(24)
    with tempfile.TemporaryDirectory(prefix="nlvav-browser-") as directory:
        env = os.environ.copy()
        env.update(
            DATA_DIR=directory,
            INITIAL_ADMIN_USER="demo",
            INITIAL_ADMIN_PASSWORD=password,
            FILMAFFINITY_ENABLED="false",
            COOKIE_SECURE="false",
        )
        with open(Path(directory) / "server.log", "w") as logs:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--no-access-log",
                ],
                env=env,
                stdout=logs,
                stderr=logs,
            )
            try:
                base = f"http://127.0.0.1:{port}"
                for _ in range(100):
                    try:
                        if httpx.get(base + "/healthz", timeout=1, trust_env=False).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    if process.poll() is not None:
                        raise RuntimeError("El servidor temporal no ha arrancado")
                    time.sleep(0.1)
                else:
                    raise RuntimeError("El servidor temporal no responde")
                with sync_playwright() as p:
                    executable = shutil.which("chromium") or shutil.which("chromium-browser")
                    browser = p.chromium.launch(
                        executable_path=executable, args=["--no-sandbox", "--disable-dev-shm-usage"]
                    )
                    context = browser.new_context(viewport={"width": 1440, "height": 1000})
                    page = context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(base)
                    page.get_by_label("Usuario", exact=True).fill("demo")
                    page.get_by_label("Contraseña", exact=True).fill(password)
                    page.get_by_role("button", name="Entrar", exact=True).click()
                    assert page.get_by_text("Tu próxima historia empieza aquí").is_visible()
                    records = [
                        ("El último proyector", "movie", "8.5", True),
                        ("La ciudad de papel", "series", "9.0", True),
                        ("Un verano en Saturno", "movie", "7.5", True),
                        ("El eco del bosque", "movie", "6.0", False),
                        ("Estación de medianoche", "series", "", False),
                        ("Una tarde cualquiera", "movie", "7.0", False),
                    ]
                    for title, kind, score, recommended in records:
                        page.goto(base + "/works/new")
                        page.locator("#title").fill(title)
                        page.locator("#kind").select_option(kind)
                        page.locator("#year").fill("2024")
                        page.locator("#score").select_option(score)
                        page.locator("#aliases").fill(
                            "Synthetic alternate title | en" if title == records[0][0] else ""
                        )
                        page.locator("#notes").fill(
                            "Una historia ficticia para probar la biblioteca.\nLos datos de esta captura son sintéticos."
                        )
                        if recommended:
                            page.locator("input[name=recommended]").check()
                        page.get_by_role("button", name="Guardar en mi biblioteca", exact=True).click()
                        assert page.get_by_text("Ficha guardada.", exact=True).is_visible()
                    page.goto(base)
                    page.screenshot(path=str(artifacts / "biblioteca-escritorio.png"), full_page=True)
                    page.locator("#search").fill("ULTIMO proyector")
                    page.get_by_role("button", name="Buscar", exact=True).click()
                    results_url = page.url
                    page.get_by_role("heading", name="El último proyector", exact=True).click()
                    page.get_by_role("link", name="Editar ficha", exact=True).click()
                    page.locator("#notes").fill("Texto editado\ncon dos líneas")
                    page.get_by_role("button", name="Guardar cambios", exact=True).click()
                    assert page.get_by_text("Texto editado", exact=False).is_visible()
                    page.get_by_role("link", name="Volver a los resultados", exact=False).click()
                    assert page.url == results_url
                    assert page.locator(".work-card").count() == 1
                    mobile = browser.new_context(
                        viewport={"width": 390, "height": 844},
                        is_mobile=True,
                        has_touch=True,
                        device_scale_factor=1,
                    )
                    mp = mobile.new_page()
                    mp.goto(base)
                    mp.locator("#username").fill("demo")
                    mp.locator("#password").fill(password)
                    mp.get_by_role("button", name="Entrar", exact=True).click()
                    mp.screenshot(path=str(artifacts / "biblioteca-movil.png"), full_page=True)
                    assert mp.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    mp.get_by_role("link", name="Añadir obra", exact=False).click()
                    mp.locator("#fa-url").fill("https://www.filmaffinity.com/en/film123456.html?synthetic=1")
                    mp.get_by_role("button", name="Comprobar y obtener metadatos").click()
                    assert mp.get_by_role("alert").is_visible()
                    assert "film123456.html" in mp.locator("#fa-url").input_value()
                    mp.locator("#title").fill("La ficha móvil de prueba")
                    mp.locator("#kind").select_option("movie")
                    assert mp.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    mp.get_by_role("button", name="Guardar en mi biblioteca").click()
                    mp.get_by_role("button", name="Marcar Recomendable").click()
                    assert mp.get_by_role("button", name="✦ Recomendable", exact=True).is_visible()
                    mp.get_by_role("link", name="Editar ficha").click()
                    mp.locator("#score").select_option("5.5")
                    mp.get_by_role("button", name="Guardar cambios").click()
                    assert mp.get_by_text("5,5", exact=False).is_visible()
                    mp.get_by_role("link", name="Eliminar ficha").click()
                    mp.get_by_role("button", name="Eliminar ficha", exact=True).click()
                    mp.locator("#search").fill("La ficha móvil de prueba")
                    mp.get_by_role("button", name="Buscar", exact=True).click()
                    assert mp.get_by_role("heading", name="No consta en tu biblioteca").is_visible()
                    assert not errors
                    browser.close()
                    print(
                        "BROWSER_OK: desktop/mobile login, create, search, return state, edit, recommendation, deletion, manual fallback, no horizontal overflow"
                    )
            finally:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
