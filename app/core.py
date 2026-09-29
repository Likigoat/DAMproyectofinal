"""Persistencia y seguridad del módulo de donantes."""
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

passwords = PasswordHash.recommended()


@contextmanager
def database(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize(path):
    with database(path) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('administrador', 'usuario'))
            );
            CREATE TABLE IF NOT EXISTS donors (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                organization TEXT NOT NULL,
                owner_id INTEGER NOT NULL REFERENCES users(id)
            );
        """)


def create_user(path, email, password, role="usuario"):
    hashed = passwords.hash(password)
    with database(path) as conn:
        cursor = conn.execute(
            "INSERT INTO users(email, password_hash, role) VALUES (?, ?, ?)",
            (email.lower(), hashed, role),
        )
        return cursor.lastrowid


def issue_token(user_id, secret, minutes=30):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=minutes),
         "iss": "donaciones", "aud": "donaciones-api"},
        secret, algorithm="HS256",
    )


def decode_token(token, secret):
    claims = jwt.decode(
        token, secret, algorithms=["HS256"], audience="donaciones-api",
        issuer="donaciones", options={"require": ["sub", "exp", "iat", "iss", "aud"]},
    )
    return int(claims["sub"])
