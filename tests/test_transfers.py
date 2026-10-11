import csv
import io
import json

import pytest
from sqlalchemy import func, select

from app import library, transfers
from app.models import Work
from app.schemas import WorkData
from tests.conftest import csrf


def populated(db):
    return library.save_work(db, WorkData(title="=Obra ficticia", kind="series", original_title="Synthetic Story", year=2024,
        fa_id="333", aliases=[{"title":"Alias con tilde á", "language":"es"}], categories=["Drama","Categoría propia"],
        score="8.5", notes="Primera línea\nSegunda, con coma", recommended=True, watched_on="2025-02-03"))


def test_roundtrip_conflicts_and_csv(db):
    work = populated(db)
    exported = transfers.export_library(db)
    content = exported.model_dump_json()
    validated = transfers.read_import(content.encode())
    assert transfers.import_library(db, validated) == (0,1)
    before = library.work_data(work)
    db.delete(work)
    db.commit()
    assert transfers.import_library(db, validated) == (1,0)
    after = library.work_data(db.scalar(select(Work)))
    assert before == after
    rows = list(csv.reader(io.StringIO(transfers.export_csv(db).lstrip("\ufeff"))))
    assert rows[1][0].startswith("'=") and rows[1][-1] == before["notes"]


def test_invalid_and_abort_no_partial_changes(db):
    populated(db)
    payload = transfers.export_library(db).model_dump(mode="json")
    payload["works"].append({**payload["works"][0], "uid":"e3b13c0d-f32a-490d-b929-c0d0192438fb", "fa_id":"444", "fa_url":None})
    valid = transfers.read_import(json.dumps(payload).encode())
    with pytest.raises(ValueError, match="cancelado"):
        transfers.import_library(db, valid, mode="abort")
    assert db.scalar(select(func.count()).select_from(Work)) == 1
    payload["works"][1]["score"] = "0"
    with pytest.raises(ValueError):
        transfers.read_import(json.dumps(payload).encode())
    assert db.scalar(select(func.count()).select_from(Work)) == 1


def test_import_http_preview_confirm(client, db):
    populated(db)
    payload = transfers.export_library(db).model_dump_json()
    token = csrf(client.get("/settings"))
    response = client.post("/import/preview", data={"csrf":token}, files={"file":("library.json",payload,"application/json")})
    assert response.status_code == 200 and "con conflicto" in response.text
    import re
    preview_token = re.search(r'name="token" value="([^"]+)"',response.text)[1]
    response = client.post("/import/confirm", data={"csrf":token,"token":preview_token,"mode":"skip"})
    assert "0 nuevas, 1 omitidas" in response.text
    assert client.post("/import/confirm", data={"csrf":token,"token":preview_token}).status_code == 422
    response = client.post("/import/preview",data={"csrf":token}, files={"file":("bad.json",'{"version":2}',"application/json")})
    assert response.status_code == 422
    assert "password_hash" not in client.get("/export/json").text


@pytest.mark.parametrize("value",["=1+1"," +cmd","\t=1","@SUM(A1)","\rcontenido","-3"])
def test_csv_formula(value):
    assert transfers.safe_csv(value).startswith("'")
