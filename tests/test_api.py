import importlib

import jwt
import pytest

from app.core import database, issue_token
from conftest import PASSWORD, SECRET

DONOR = {"name": "Ana Pérez", "email": "ana@example.org", "organization": "Alimentos del Norte"}


def test_health_and_headers(client):
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert client.get("/docs").status_code == 200


def test_register_and_duplicate(client):
    data = {"email": "new@example.org", "password": PASSWORD}
    response = client.post("/auth/register", json=data)
    assert response.status_code == 201
    assert response.json()["role"] == "usuario"
    assert "password_hash" not in response.text
    assert client.post("/auth/register", json=data).status_code == 409


@pytest.mark.parametrize("change", [{"role": "administrador"}, {"password": "short"}, {"email": "bad"}])
def test_register_rejects_invalid(client, change):
    assert client.post("/auth/register", json={"email": "new@example.org", "password": PASSWORD, **change}).status_code == 422


@pytest.mark.parametrize("email,password", [("absent@example.org", PASSWORD), ("usuario@example.org", "WrongPassword123")])
def test_login_failure(client, email, password):
    assert client.post("/auth/login", json={"email": email, "password": password}).status_code == 401


def test_current_user(client, headers):
    response = client.get("/auth/me", headers=headers())
    assert response.json()["role"] == "usuario"
    assert "password" not in response.text


@pytest.mark.parametrize("token", [None, "bad", issue_token(1, SECRET, -1), issue_token(9999, SECRET),
                                  issue_token(1, "wrong-secret" * 4),
                                  issue_token("not-an-int", SECRET)])
def test_unauthorized(client, token):
    headers = {} if token is None else {"Authorization": "Bearer " + token}
    assert client.get("/donors", headers=headers).status_code == 401


def test_donor_lifecycle_and_permissions(client, headers):
    user, admin = headers(), headers("administrador")
    response = client.post("/donors", json=DONOR, headers=user)
    assert response.status_code == 201
    donor_id = response.json()["id"]
    assert client.post("/donors", json=DONOR, headers=user).status_code == 409
    assert len(client.get("/donors", headers=user).json()) == 1
    assert len(client.get("/donors", headers=admin).json()) == 1
    assert client.delete(f"/donors/{donor_id}", headers=user).status_code == 403
    assert client.delete(f"/donors/{donor_id}", headers=admin).status_code == 204
    assert client.delete(f"/donors/{donor_id}", headers=admin).status_code == 404


def test_ownership_and_role_changes(setup, headers):
    client, path, ids = setup
    token = headers()
    client.post("/donors", json=DONOR, headers=headers("administrador"))
    assert client.get("/donors", headers=token).json() == []
    with database(path) as conn:
        conn.execute("UPDATE users SET role = 'administrador' WHERE id = ?", (ids["usuario"],))
    assert len(client.get("/donors", headers=token).json()) == 1
    with database(path) as conn:
        conn.execute("UPDATE users SET role = 'usuario' WHERE id = ?", (ids["usuario"],))
    assert client.get("/donors", headers=token).json() == []


@pytest.mark.parametrize("payload", ["' OR 1=1 --", "Robert'); DROP TABLE donors;--"])
def test_sqli_is_data(client, headers, payload):
    auth = headers()
    response = client.post("/donors", json={**DONOR, "name": payload}, headers=auth)
    assert response.status_code == 201
    assert client.get("/donors", headers=auth).json()[0]["name"] == payload
    assert client.get("/health").status_code == 200


def test_xss_and_owner_spoof_rejected(client, headers):
    auth = headers()
    assert client.post("/donors", json={**DONOR, "name": "<script>alert(1)</script>"}, headers=auth).status_code == 422
    assert client.post("/donors", json={**DONOR, "owner_id": 999}, headers=auth).status_code == 422
    assert client.get("/donors", headers=auth).json() == []


def test_pagination(client, headers):
    auth = headers()
    client.post("/donors", json=DONOR, headers=auth)
    assert client.get("/donors?offset=1", headers=auth).json() == []
    assert client.get("/donors?limit=101", headers=auth).status_code == 422
    assert client.get("/donors?offset=-1", headers=auth).status_code == 422


def test_entrypoint(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "main.db"))
    assert importlib.import_module("app.main").app.title == "Red de Donaciones"
