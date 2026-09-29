"""Prueba HTTP real contra el despliegue; sólo usar en un entorno de prueba."""
import json
import os
import secrets
from pathlib import Path

import httpx

base = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
with httpx.Client(base_url=base, timeout=20) as client:
    response = client.get("/health")
    response.raise_for_status()
    assert response.json() == {"status": "ok"}
    credentials = {"email": f"smoke-{secrets.token_hex(6)}@example.org", "password": secrets.token_urlsafe(24)}
    response = client.post("/auth/register", json=credentials)
    assert response.status_code == 201, response.text
    response = client.post("/auth/login", json=credentials)
    response.raise_for_status()
    auth = {"Authorization": "Bearer " + response.json()["access_token"]}
    donor = {"name": "Donante de prueba", "email": credentials["email"], "organization": "Empresa de prueba"}
    response = client.post("/donors", json=donor, headers=auth)
    assert response.status_code == 201, response.text
    donor_id = response.json()["id"]
    response = client.get("/donors", headers=auth)
    assert any(d["id"] == donor_id for d in response.json())
    assert client.delete(f"/donors/{donor_id}", headers=auth).status_code == 403
    assert client.get("/donors").status_code == 401

Path("reports").mkdir(exist_ok=True)
Path("reports/smoke.json").write_text(json.dumps({"status": "passed", "checks": 7, "base_url": base}, indent=2))
print("Smoke: 7 comprobaciones HTTP aprobadas.")
