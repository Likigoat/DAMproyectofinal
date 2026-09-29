import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.core import create_user

SECRET = "test-only-key-" * 4
PASSWORD = "TestPassword!2026"


@pytest.fixture
def setup(tmp_path):
    path = str(tmp_path / "test.db")
    app = create_app(path, SECRET)
    ids = {role: create_user(path, role + "@example.org", PASSWORD, role)
           for role in ("administrador", "usuario")}
    with TestClient(app) as client:
        yield client, path, ids


@pytest.fixture
def client(setup):
    return setup[0]


@pytest.fixture
def headers(client):
    def authenticate(role="usuario"):
        response = client.post("/auth/login", json={"email": role + "@example.org", "password": PASSWORD})
        assert response.status_code == 200
        return {"Authorization": "Bearer " + response.json()["access_token"]}
    return authenticate
