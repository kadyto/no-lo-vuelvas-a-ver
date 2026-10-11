"""Construye un contexto tar con la carpeta raíz de GitHub y ejecuta el smoke real.

BUILD_CA_CERT permite montar la CA de un proxy gestionado solo durante el build.
No depende de Git ni descarga el repositorio remoto durante las pruebas habituales.
"""

import io
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent.parent
    prefix = "no-lo-vuelvas-a-ver-main"
    image = "no-lo-vuelvas-a-ver:archive-test"
    with tempfile.TemporaryDirectory(prefix="nlvav-archive-") as directory:
        archive = Path(directory) / "source.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for name in ["Dockerfile", "requirements.lock", "alembic.ini", "LICENSE", "app", "migrations"]:
                tar.add(
                    root / name,
                    arcname=f"{prefix}/{name}",
                    filter=lambda info: None
                    if "__pycache__" in info.name or info.name.endswith("/_archive_revision.txt")
                    else info,
                )
            revision = b"1111111111111111111111111111111111111111\n"
            info = tarfile.TarInfo(f"{prefix}/app/_archive_revision.txt")
            info.size, info.mode = len(revision), 0o644
            tar.addfile(info, io.BytesIO(revision))
        command = [
            "docker",
            "build",
            "-t",
            image,
            "-f",
            f"{prefix}/Dockerfile",
            "--build-arg",
            f"SOURCE_DIR={prefix}",
        ]
        certificate = os.getenv("BUILD_CA_CERT")
        if certificate:
            command.extend(["--secret", f"id=proxy_ca,src={certificate}"])
        command.append("-")
        with archive.open("rb") as source:
            subprocess.run(command, stdin=source, cwd=root, check=True)
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--entrypoint",
                "python",
                image,
                "-c",
                "from app.updates import BuildInfo; "
                "assert BuildInfo.from_env().revision == '1' * 40; print('ARCHIVE_REVISION_OK')",
            ],
            cwd=root,
            check=True,
        )
        subprocess.run([sys.executable, str(root / "tests/smoke_image.py"), image], cwd=root, check=True)
    print("ARCHIVE_SMOKE_OK: nested GitHub tar context, COPY paths, access, persistence and backup")


if __name__ == "__main__":
    main()
