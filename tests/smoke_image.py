"""Smoke reproducible de imagen: autenticación, persistencia, copia y recreación.
Uso: python tests/smoke_image.py no-lo-vuelvas-a-ver:test
Solo utiliza contenedores efímeros propios y una carpeta temporal sintética.
"""

import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


def docker(*args):
    return subprocess.check_output(["docker", *args], text=True).strip()


def csrf(response):
    return re.search(r'name="csrf" value="([^"]+)"', response.text)[1]


def main():
    image = sys.argv[1]
    password = secrets.token_urlsafe(24)
    name = "nlvav-smoke-" + secrets.token_hex(6)
    with tempfile.TemporaryDirectory(prefix="nlvav-smoke-") as directory:

        def start():
            # Bind publication only on loopback, arbitrary free port; actual container still listens on 0.0.0.0.
            docker(
                "run",
                "-d",
                "--name",
                name,
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--security-opt",
                "no-new-privileges:true",
                "-p",
                "127.0.0.1::8000",
                "-v",
                f"{directory}:/data",
                "-e",
                "INITIAL_ADMIN_USER=smoke",
                "-e",
                f"INITIAL_ADMIN_PASSWORD={password}",
                image,
            )
            address = "http://" + docker("port", name, "8000/tcp")
            for _ in range(60):
                try:
                    if httpx.get(address + "/healthz", timeout=2).status_code == 200:
                        return address
                except httpx.HTTPError:
                    pass
                time.sleep(1)
            raise RuntimeError("El contenedor no alcanza estado saludable")

        try:
            address = start()
            with httpx.Client(base_url=address, follow_redirects=True) as client:
                token = csrf(client.get("/login"))
                page = client.post("/login", data={"csrf": token, "username": "smoke", "password": password})
                assert page.status_code == 200
                token = csrf(client.get("/works/new"))
                page = client.post(
                    "/works",
                    data={
                        "csrf": token,
                        "title": "Obra sintética del contenedor",
                        "kind": "movie",
                        "score": "8.5",
                        "aliases": "Synthetic title | en",
                        "notes": "Una reseña\ncon salto",
                        "category_ids": "3",
                        "recommended": "on",
                    },
                )
                assert "Ficha guardada" in page.text
                expected = client.get("/export/json").json()["works"]
                assert expected[0]["notes"] == "Una reseña\ncon salto" and expected[0]["categories"]
            docker("exec", name, "python", "-m", "app.cli", "backup", "/data/backup.sqlite3")
            assert Path(directory, "backup.sqlite3").is_file()
            docker("restart", name)
            # Recreation uses the same volume and a new process; bootstrap does not reset credentials.
            docker("rm", "-f", name)
            address = start()
            with httpx.Client(base_url=address, follow_redirects=True) as client:
                token = csrf(client.get("/login"))
                client.post("/login", data={"csrf": token, "username": "smoke", "password": password})
                assert client.get("/export/json").json()["works"] == expected
            state = json.loads(docker("inspect", name))[0]
            assert state["Config"]["User"] == f"{os.getuid()}:{os.getgid()}"
            print(
                "IMAGE_SMOKE_OK: login, CRUD, restart, recreation, persistence, SQLite backup, custom UID/GID"
            )
        finally:
            subprocess.run(["docker", "rm", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
