"""Controladores aislados: sin HTTP ni base de datos; dependencias simuladas."""
import asyncio
import importlib
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials

from app.api import Credentials, DonorInput, create_app
from conftest import PASSWORD, SECRET

USER = {"id": 7, "email": "user@example.org", "role": "usuario"}
DONOR = {"id": 3, "owner_id": 7, "name": "Ana", "email": "ana@example.org", "organization": "Empresa"}


@pytest.fixture
def isolated():
    with patch("app.api.initialize"), patch("app.api.passwords") as passwords, patch("app.api.database") as db:
        app = create_app("unused.db", SECRET)
        conn = db.return_value.__enter__.return_value
        routes = {r.path: r for r in app.routes if hasattr(r, "dependant")}
        yield app, routes, conn, passwords


def route(app, path, method):
    return next(r.endpoint for r in app.routes if r.path == path and method in r.methods)


def test_registration_never_passes_client_role(isolated):
    app, _, _, _ = isolated
    register = route(app, "/auth/register", "POST")
    data = Credentials(email="user@example.org", password=PASSWORD)
    with patch("app.api.create_user", return_value=7) as create:
        assert register(data) == USER
        assert create.call_args.args == ("unused.db", data.email, PASSWORD)
    with patch("app.api.create_user", side_effect=sqlite3.IntegrityError):
        with pytest.raises(HTTPException) as error:
            register(data)
        assert error.value.status_code == 409


def test_login_validates_hash_and_uses_generic_errors(isolated):
    app, _, conn, passwords = isolated
    login = route(app, "/auth/login", "POST")
    data = Credentials(email=USER["email"], password=PASSWORD)
    conn.execute.return_value.fetchone.return_value = {**USER, "password_hash": "stored-hash"}
    passwords.verify.return_value = True
    with patch("app.api.issue_token", return_value="signed-token"):
        assert login(data)["access_token"] == "signed-token"
    passwords.verify.assert_called_with(PASSWORD, "stored-hash")
    passwords.verify.return_value = False
    with pytest.raises(HTTPException) as wrong:
        login(data)
    conn.execute.return_value.fetchone.return_value = None
    with pytest.raises(HTTPException) as missing:
        login(data)
    assert wrong.value.status_code == missing.value.status_code == 401
    assert wrong.value.detail == missing.value.detail


def test_auth_dependency_checks_current_database_identity(isolated):
    _, routes, conn, _ = isolated
    current = routes["/auth/me"].dependant.dependencies[0].call
    token = HTTPAuthorizationCredentials(scheme="Bearer", credentials="supplied-token")
    with pytest.raises(HTTPException) as missing:
        current(None)
    assert missing.value.status_code == 401
    with patch("app.api.decode_token", return_value=7):
        conn.execute.return_value.fetchone.return_value = USER
        assert current(token) == USER
        conn.execute.return_value.fetchone.return_value = None
        with pytest.raises(HTTPException) as deleted:
            current(token)
        assert deleted.value.status_code == 401
    with patch("app.api.decode_token", side_effect=ValueError):
        with pytest.raises(HTTPException) as invalid:
            current(token)
        assert invalid.value.status_code == 401


def test_admin_dependency_denies_regular_user(isolated):
    _, routes, _, _ = isolated
    admin = routes["/donors/{donor_id}"].dependant.dependencies[0].call
    with pytest.raises(HTTPException) as denied:
        admin(USER)
    assert denied.value.status_code == 403
    assert admin({**USER, "role": "administrador"})["role"] == "administrador"


def test_creation_uses_owner_and_parameterized_sql(isolated):
    app, _, conn, _ = isolated
    create = route(app, "/donors", "POST")
    payload = "Robert'); DROP TABLE donors;--"
    data = DonorInput(name=payload, email=DONOR["email"], organization=DONOR["organization"])
    conn.execute.return_value.fetchone.return_value = {**DONOR, "name": payload}
    conn.execute.return_value.lastrowid = 3
    assert create(data, USER)["owner_id"] == USER["id"]
    sql, params = conn.execute.call_args_list[0].args
    assert payload not in sql
    assert params == (payload, data.email, data.organization, USER["id"])
    conn.execute.side_effect = sqlite3.IntegrityError
    with pytest.raises(HTTPException) as duplicate:
        create(data, USER)
    assert duplicate.value.status_code == 409


def test_listing_enforces_owner_filter(isolated):
    app, _, conn, _ = isolated
    listing = route(app, "/donors", "GET")
    conn.execute.return_value = [DONOR]
    assert listing(USER, 10, 0) == [DONOR]
    assert conn.execute.call_args.args[1] == (USER["id"], 10, 0)
    assert "WHERE owner_id = ?" in conn.execute.call_args.args[0]
    assert listing({**USER, "role": "administrador"}, 10, 0) == [DONOR]
    assert conn.execute.call_args.args[1] == (10, 0)


def test_delete_distinguishes_missing_record(isolated):
    app, _, conn, _ = isolated
    delete = route(app, "/donors/{donor_id}", "DELETE")
    admin = {**USER, "role": "administrador"}
    conn.execute.return_value.rowcount = 1
    assert delete(3, admin).status_code == 204
    conn.execute.return_value.rowcount = 0
    with pytest.raises(HTTPException) as missing:
        delete(3, admin)
    assert missing.value.status_code == 404


def test_health_and_identity_contracts(isolated):
    app, _, _, _ = isolated
    assert route(app, "/health", "GET")() == {"status": "ok"}
    assert route(app, "/auth/me", "GET")(USER) == USER


def test_security_headers_keep_interactive_docs_usable(isolated):
    app, _, _, _ = isolated
    middleware = app.user_middleware[0].kwargs["dispatch"]
    async def next_response(request):
        return Response()
    for path in ("/donors", "/docs"):
        request = MagicMock()
        request.url.path = path
        response = asyncio.run(middleware(request, next_response))
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["Cache-Control"] == "no-store"
        assert ("Content-Security-Policy" in response.headers) == (path != "/docs")


def test_entrypoint_reads_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", "configured.db")
    monkeypatch.setenv("JWT_SECRET", SECRET)
    with patch("app.api.create_app") as factory:
        import app.main
        importlib.reload(app.main)
        factory.assert_called_with("configured.db", SECRET)
