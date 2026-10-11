import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    data_dir: Path = Path("/data")
    initial_user: str = ""
    initial_password: str = ""
    secure_cookies: bool = False
    filmaffinity_enabled: bool = False
    update_check_enabled: bool = True
    session_hours: int = 12

    def __post_init__(self):
        if not self.data_dir.is_absolute():
            raise ValueError("DATA_DIR debe ser una ruta absoluta.")
        if not 1 <= self.session_hours <= 168:
            raise ValueError("SESSION_HOURS debe estar entre 1 y 168.")

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", "/data")),
            initial_user=os.getenv("INITIAL_ADMIN_USER", ""),
            initial_password=os.getenv("INITIAL_ADMIN_PASSWORD", ""),
            secure_cookies=os.getenv("COOKIE_SECURE", "false").lower() == "true",
            filmaffinity_enabled=os.getenv("FILMAFFINITY_ENABLED", "false").lower() == "true",
            update_check_enabled=os.getenv("UPDATE_CHECK_ENABLED", "true").lower() == "true",
            session_hours=int(os.getenv("SESSION_HOURS", "12")),
        )

    @property
    def db_path(self):
        return self.data_dir / "library.sqlite3"
