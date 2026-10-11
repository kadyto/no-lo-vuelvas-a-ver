"""Valida el Compose mediante Docker Compose, sin ejecutar contenedores."""

import json
import os
import secrets
import subprocess
import tempfile


def main():
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
            ["docker", "compose", "config", "--format", "json"],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        config = json.loads(result.stdout)
        assert set(config["services"]) == {"library"}
        service = config["services"]["library"]
        assert "build" not in service and "container_name" not in service
        assert service["volumes"][0]["target"] == "/data" and service["healthcheck"]
        assert service["restart"] == "unless-stopped"
        # Never print rendered environment: it contains installation secrets.
        for name in ["DATA_DIR", "APP_IMAGE", "INITIAL_ADMIN_USER", "INITIAL_ADMIN_PASSWORD"]:
            invalid = env.copy()
            invalid[name] = ""
            result = subprocess.run(
                ["docker", "compose", "config", "--quiet"], env=invalid, capture_output=True
            )
            assert result.returncode != 0, name
    print("COMPOSE_OK: single service, explicit bind, required variables, healthcheck, image only")


if __name__ == "__main__":
    main()
