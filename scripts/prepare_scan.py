"""Genera un esquema de escaneo de donantes y un JWT temporal de prueba."""
import json
import os
from pathlib import Path

import httpx

from app.core import issue_token

base = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
token = issue_token(1, os.environ["JWT_SECRET"], minutes=60)
with httpx.Client(base_url=base, timeout=20) as client:
    response = client.get("/auth/me", headers={"Authorization": "Bearer " + token})
    response.raise_for_status()
    assert response.json()["role"] == "administrador"
    schema = client.get("/openapi.json").json()
schema["paths"] = {path: value for path, value in schema["paths"].items() if path.startswith("/donors")}
schema["servers"] = [{"url": base}]
schema["components"]["schemas"]["DonorInput"]["example"] = {
    "name": "Donante ZAP", "email": "zap@example.org", "organization": "Empresa de prueba"}
Path("reports/openapi-scan.json").write_text(json.dumps(schema), encoding="utf-8")
with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as env:
    env.write(f"ZAP_AUTH_HEADER_VALUE=Bearer {token}\n")
print(f"::add-mask::{token}")
print("Esquema limitado a donantes; autenticación del administrador comprobada.")
