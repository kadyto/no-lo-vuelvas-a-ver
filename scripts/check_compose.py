"""Valida el Compose mediante Docker Compose, sin ejecutar contenedores."""

import json
import os
import secrets
import subprocess
import sys
import tempfile


def main():
    filename = sys.argv[1] if len(sys.argv) > 1 else "compose.yaml"
    archive = filename == "compose.dockhand.yaml"
    compose = ["docker", "compose", "-f", filename]
    env = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="nlvav-compose-") as directory:
        env.update(
            APP_IMAGE="no-lo-vuelvas-a-ver:test",
            DATA_DIR=directory,
            INITIAL_ADMIN_USER="synthetic",
            INITIAL_ADMIN_PASSWORD=secrets.token_urlsafe(24),
            APP_UID=str(os.getuid()),
            APP_GID=str(os.getgid()),
        )
        result = subprocess.run(
            [*compose, "config", "--format", "json"],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        config = json.loads(result.stdout)
        assert set(config["services"]) == {"library"}
        service = config["services"]["library"]
        assert "container_name" not in service
        if archive:
            assert "image" not in service
            build = service["build"]
            assert build["context"].endswith("/archive/refs/heads/main.tar.gz")
            assert build["dockerfile"] == "no-lo-vuelvas-a-ver-main/Dockerfile"
            assert build["args"]["SOURCE_DIR"] == "no-lo-vuelvas-a-ver-main"
        else:
            assert "build" not in service
        assert service["volumes"][0]["target"] == "/data" and service["healthcheck"]
        assert service["restart"] == "unless-stopped"
        # Never print rendered environment: it contains installation secrets.
        required = ["DATA_DIR", "INITIAL_ADMIN_USER", "INITIAL_ADMIN_PASSWORD"]
        if not archive:
            required.append("APP_IMAGE")
        for name in required:
            invalid = env.copy()
            invalid[name] = ""
            result = subprocess.run([*compose, "config", "--quiet"], env=invalid, capture_output=True)
            assert result.returncode != 0, name
    print(f"COMPOSE_OK: {filename}, single service, explicit bind, required variables, healthcheck")


if __name__ == "__main__":
    main()
