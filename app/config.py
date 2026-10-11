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
    session_hours: int = 12

    @classmethod
    def from_env(cls):
        return cls(
            data_dir=Path(os.getenv("DATA_DIR", "/data")),
            initial_user=os.getenv("INITIAL_ADMIN_USER", ""),
            initial_password=os.getenv("INITIAL_ADMIN_PASSWORD", ""),
            secure_cookies=os.getenv("COOKIE_SECURE", "false").lower() == "true",
            filmaffinity_enabled=os.getenv("FILMAFFINITY_ENABLED", "false").lower() == "true",
            session_hours=int(os.getenv("SESSION_HOURS", "12")),
        )

    @property
    def db_path(self):
        return self.data_dir / "library.sqlite3"
