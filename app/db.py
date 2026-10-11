import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker


def now():
    return datetime.now(timezone.utc).isoformat()


def backup(source: Path, destination: Path):
    if source.resolve() == destination.resolve() or destination.exists():
        raise ValueError("El destino de la copia debe ser un archivo nuevo y diferente.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src:
        with sqlite3.connect(destination) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("La copia no supera integrity_check.")
    destination.chmod(0o600)


def make_engine(path):
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 10})

    @event.listens_for(engine, "connect")
    def configure(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")

    return engine


def migrate(path):
    root = Path(__file__).resolve().parent.parent
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{path}".replace("%", "%%"))
    # Backup every existing database before any pending upgrade, including legacy databases.
    from alembic.script import ScriptDirectory
    target = ScriptDirectory.from_config(config).get_current_head()
    current = None
    if path.exists():
        with sqlite3.connect(path) as conn:
            if conn.execute("SELECT 1 FROM sqlite_master WHERE name='alembic_version'").fetchone():
                row = conn.execute("SELECT version_num FROM alembic_version").fetchone()
                current = row[0] if row else None
        if current != target:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            backup(path, path.parent / "backups" / f"before-{target}-{stamp}.sqlite3")
    command.upgrade(config, "head")


def sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)
