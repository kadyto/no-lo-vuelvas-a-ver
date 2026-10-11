import re

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PASSWORD = "contraseña-sintética-para-pruebas"


def csrf(response):
    return re.search(r'name="csrf" value="([^"]+)"', response.text)[1]


@pytest.fixture
def application(tmp_path):
    return create_app(Settings(data_dir=tmp_path, initial_user="test", initial_password=PASSWORD))


@pytest.fixture
def client(application):
    with TestClient(application) as client:
        page = client.get("/login")
        response = client.post("/login", data={"csrf": csrf(page), "username": "test", "password": PASSWORD})
        assert response.status_code == 200
        yield client


@pytest.fixture
def db(client, application):
    with application.state.db() as db:
        yield db
