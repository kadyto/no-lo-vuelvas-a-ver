import shutil
import sqlite3
import time
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import insert

from app import library
from app.config import Settings
from app.db import backup, make_engine, migrate, now, sessions
from app.main import create_app
from app.models import Alias, Review, Work
from app.schemas import WorkData
from tests.conftest import PASSWORD, csrf


def test_backup_restore_and_restart(tmp_path):
    data_dir=tmp_path / "data"
    app=create_app(Settings(data_dir=data_dir,initial_user="test",initial_password=PASSWORD))
    with TestClient(app):
        with app.state.db() as db:
            work=library.save_work(db,WorkData(title="Historia sintética",kind="movie",aliases=[{"title":"Synthetic Story"}],
                categories=["Drama","Comedia"],score="6.5",notes="Anotaciones\ncon salto",recommended=True))
            expected=library.work_data(work)
        destination=tmp_path / "copy.sqlite3"
        backup(data_dir / "library.sqlite3",destination)
    # Recreate the app against the same mount; initialization variables must be ignored.
    replacement=create_app(Settings(data_dir=data_dir,initial_user="ignored",initial_password=""))
    with TestClient(replacement) as client:
        page=client.get("/login")
        assert client.post("/login",data={"csrf":csrf(page),"username":"test","password":PASSWORD}).status_code==200
        with replacement.state.db() as db:
            assert library.work_data(db.get(Work,work.id))==expected
    restored=tmp_path / "restored"
    restored.mkdir()
    shutil.copyfile(destination,restored / "library.sqlite3")
    with TestClient(create_app(Settings(data_dir=restored))) as client:
        page=client.get("/login")
        client.post("/login",data={"csrf":csrf(page),"username":"test","password":PASSWORD})
        assert "Anotaciones" in client.get(f"/works/{work.id}").text


def test_migration_keeps_data_and_backups(tmp_path):
    path=tmp_path / "library.sqlite3"
    root=Path(__file__).resolve().parent.parent
    config=Config(str(root / "alembic.ini"))
    config.set_main_option("script_location",str(root / "migrations"))
    config.set_main_option("sqlalchemy.url",f"sqlite:///{path}")
    command.upgrade(config,"0001")
    engine=make_engine(path)
    with sessions(engine)() as db:
        work=library.save_work(db,WorkData(title="Antes de migrar",kind="series",fa_id="555",score="9.5",notes="Se conserva",aliases=[{"title":"Before"}],categories=["Drama"]))
        expected=library.work_data(work)
    engine.dispose()
    migrate(path)
    copies=list((tmp_path / "backups").glob("*.sqlite3"))
    assert len(copies)==1
    with sqlite3.connect(copies[0]) as db:
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0001"
    engine=make_engine(path)
    with sessions(engine)() as db:
        assert library.work_data(db.get(Work,work.id))==expected
    engine.dispose()
    migrate(path)
    assert len(list((tmp_path / "backups").glob("*.sqlite3")))==1


def test_search_10000_measured(db, capsys):
    stamp=now()
    works=[{"id":i,"uid":str(uuid4()),"title":f"Historia sintética {i:05}","title_key":f"historia sintetica {i:05}",
            "original_title":f"Synthetic story {i:05}","original_key":f"synthetic story {i:05}",
            "kind":"movie" if i%2 else "series", "year":2000+i%25,"created_at":stamp,"updated_at":stamp}
           for i in range(1,10001)]
    db.execute(insert(Work),works)
    db.execute(insert(Review),[{"work_id":i,"score_half":i%19+2,"notes":"","recommended":bool(i%2)} for i in range(1,10001)])
    db.execute(insert(Alias),[{"work_id":i,"title":f"Alias {i:05}","title_key":f"alias {i:05}"} for i in range(1,10001)])
    db.commit()
    timings=[]
    for _ in range(5):
        started=time.perf_counter()
        result=library.search(db,q="HISTÓRIA sintética",page=2)
        timings.append((time.perf_counter()-started)*1000)
        assert result["count"]==10000 and len(result["works"])==24 and result["page"]==2
    assert library.search(db,q="Alias 09999")["works"][0].id==9999
    assert library.search(db,q="%_")["count"]==0
    with capsys.disabled():
        print(f"\nSEARCH_10000_MS min={min(timings):.1f} median={sorted(timings)[2]:.1f} max={max(timings):.1f}; page_size=24")
    assert max(timings)<5000  # Broad regression ceiling, not a promise about NAS hardware.
