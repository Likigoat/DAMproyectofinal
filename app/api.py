"""API de ejemplo académico; la configuración se inyecta al crearla."""
import sqlite3
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core import create_user, database, decode_token, initialize, issue_token, passwords


class Credentials(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class DonorInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    organization: str = Field(min_length=2, max_length=150)

    @field_validator("name", "organization")
    @classmethod
    def plain_text(cls, value):
        if any(c in value for c in "<>\x00"):
            raise ValueError("Utiliza texto sin etiquetas HTML ni caracteres nulos")
        return value


class UserOutput(BaseModel):
    id: int
    email: str
    role: str


class DonorOutput(DonorInput):
    id: int
    owner_id: int


def create_app(db_path, secret):
    if len(secret) < 32:
        raise ValueError("JWT_SECRET debe contener al menos 32 caracteres aleatorios")
    initialize(db_path)
    app = FastAPI(title="Red de Donaciones", version="1.0.0")
    bearer = HTTPBearer(auto_error=False)
    dummy_hash = passwords.hash("dummy-password-never-used")

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path not in ("/docs", "/redoc"):
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response

    def current_user(auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        denied = HTTPException(401, "Token ausente o inválido", headers={"WWW-Authenticate": "Bearer"})
        if auth is None:
            raise denied
        try:
            user_id = decode_token(auth.credentials, secret)
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise denied from None
        with database(db_path) as conn:
            user = conn.execute("SELECT id, email, role FROM users WHERE id = ?", (user_id,)).fetchone()
        if user is None:
            raise denied
        return dict(user)

    def administrator(user: Annotated[dict, Depends(current_user)]):
        if user["role"] != "administrador":
            raise HTTPException(403, "Se requiere rol administrador")
        return user

    @app.get("/health")
    def health():
        with database(db_path) as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ok"}

    @app.post("/auth/register", response_model=UserOutput, status_code=201)
    def register(data: Credentials):
        try:
            user_id = create_user(db_path, str(data.email), data.password)
        except sqlite3.IntegrityError:
            raise HTTPException(409, "Correo ya registrado") from None
        return {"id": user_id, "email": str(data.email).lower(), "role": "usuario"}

    @app.post("/auth/login")
    def login(data: Credentials):
        with database(db_path) as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (str(data.email).lower(),)).fetchone()
        valid = passwords.verify(data.password, user["password_hash"] if user else dummy_hash)
        if not user or not valid:
            raise HTTPException(401, "Credenciales inválidas")
        return {"access_token": issue_token(user["id"], secret), "token_type": "bearer", "expires_in": 1800}

    @app.get("/auth/me", response_model=UserOutput)
    def me(user: Annotated[dict, Depends(current_user)]):
        return user

    @app.post("/donors", response_model=DonorOutput, status_code=201)
    def add_donor(data: DonorInput, user: Annotated[dict, Depends(current_user)]):
        with database(db_path) as conn:
            try:
                cursor = conn.execute(
                    "INSERT INTO donors(name, email, organization, owner_id) VALUES (?, ?, ?, ?)",
                    (data.name, str(data.email).lower(), data.organization, user["id"]),
                )
            except sqlite3.IntegrityError:
                raise HTTPException(409, "Donante ya registrado") from None
            return dict(conn.execute("SELECT * FROM donors WHERE id = ?", (cursor.lastrowid,)).fetchone())

    @app.get("/donors", response_model=list[DonorOutput])
    def list_donors(user: Annotated[dict, Depends(current_user)],
                    limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        with database(db_path) as conn:
            if user["role"] == "administrador":
                rows = conn.execute("SELECT * FROM donors ORDER BY id LIMIT ? OFFSET ?", (limit, offset))
            else:
                rows = conn.execute("SELECT * FROM donors WHERE owner_id = ? ORDER BY id LIMIT ? OFFSET ?",
                                    (user["id"], limit, offset))
            return [dict(row) for row in rows]

    @app.delete("/donors/{donor_id}", status_code=204)
    def delete_donor(donor_id: int, user: Annotated[dict, Depends(administrator)]):
        with database(db_path) as conn:
            result = conn.execute("DELETE FROM donors WHERE id = ?", (donor_id,))
            if result.rowcount == 0:
                raise HTTPException(404, "Donante no encontrado")
        return Response(status_code=204)

    return app
