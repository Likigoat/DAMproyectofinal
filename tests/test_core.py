from datetime import datetime, timedelta, timezone

import jwt
import pytest
from pydantic import ValidationError

from app.api import Credentials, DonorInput, create_app
from app.core import create_user, database, decode_token, initialize, issue_token, passwords
from conftest import PASSWORD, SECRET


def test_password_hash_and_normalized_email(tmp_path):
    path = str(tmp_path / "unit.db")
    initialize(path)
    initialize(path)
    user_id = create_user(path, "USER@example.org", PASSWORD)
    with database(path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    assert row["email"] == "user@example.org"
    assert row["password_hash"] != PASSWORD
    assert passwords.verify(PASSWORD, row["password_hash"])
    assert not passwords.verify("wrong-password", row["password_hash"])
    assert row["role"] == "usuario"


def test_database_rolls_back(tmp_path):
    path = str(tmp_path / "rollback.db")
    initialize(path)
    with pytest.raises(RuntimeError):
        with database(path) as conn:
            conn.execute("INSERT INTO users VALUES (1, 'a', 'hash', 'usuario')")
            raise RuntimeError("Simular operación fallida")
    with database(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_valid_token():
    assert decode_token(issue_token(7, SECRET), SECRET) == 7


@pytest.mark.parametrize("kind", ["expired", "signature", "audience", "issuer", "missing", "algorithm"])
def test_invalid_tokens(kind):
    now = datetime.now(timezone.utc)
    claims = {"sub": "7", "iat": now, "exp": now + timedelta(minutes=5),
              "iss": "donaciones", "aud": "donaciones-api"}
    key, algorithm = SECRET, "HS256"
    if kind == "expired":
        claims["exp"] = now - timedelta(minutes=1)
    elif kind == "signature":
        key = "different-secret" * 4
    elif kind == "audience":
        claims["aud"] = "other"
    elif kind == "issuer":
        claims["iss"] = "other"
    elif kind == "missing":
        del claims["exp"]
    else:
        algorithm = "HS384"
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(jwt.encode(claims, key, algorithm=algorithm), SECRET)


def test_weak_secret_fails(tmp_path):
    with pytest.raises(ValueError, match="JWT_SECRET"):
        create_app(str(tmp_path / "weak.db"), "short")


@pytest.mark.parametrize("field,value", [("name", "<script>alert(1)</script>"),
                                         ("organization", "<img onerror=alert(1)>"),
                                         ("name", "\x00bad"), ("name", " "),
                                         ("email", "invalid")])
def test_input_validation(field, value):
    data = {"name": "Donante", "organization": "Empresa", "email": "donor@example.org"}
    data[field] = value
    with pytest.raises(ValidationError):
        DonorInput(**data)


def test_cannot_request_admin_role():
    with pytest.raises(ValidationError):
        Credentials(email="user@example.org", password=PASSWORD, role="administrador")
