"""Prueba de humo del iam-service contra el servicio levantado.
Uso: uv run python scripts/smoke_test.py
"""

import sys
import uuid

import httpx
import jwt

BASE = "http://localhost:8001"
todo_ok = True


def check(nombre: str, condicion: bool, detalle: str = "") -> None:
    global todo_ok
    print(("OK    " if condicion else "FALLA ") + nombre + ("" if condicion else f"  -> {detalle}"))
    todo_ok = todo_ok and condicion


with httpx.Client(base_url=BASE, timeout=10) as c:
    # Operación
    r = c.get("/health")
    check("GET /health -> 200", r.status_code == 200, r.text)
    r = c.get("/metrics")
    check("GET /metrics expone métricas", r.status_code == 200 and "http_requests_total" in r.text)

    # Registro (UC1 + UC6)
    email = f"smoke.{uuid.uuid4().hex[:8]}@example.com"
    clave = "Smoke12345"
    datos = {
        "email": email,
        "password": clave,
        "nombre_completo": "Prueba Humo",
        "rol": "Turista",
        "habeas_data_aceptado": True,
        "es_mayor_de_edad": True,
    }
    r = c.post("/api/iam/register", json=datos)
    check("Registro -> 201", r.status_code == 201, r.text)
    check("Registro no devuelve el hash", "password" not in r.text)
    r = c.post("/api/iam/register", json=datos)
    check(
        "Duplicado -> 409 EMAIL_EN_USO",
        r.status_code == 409 and r.json().get("code") == "EMAIL_EN_USO",
        r.text,
    )
    r = c.post(
        "/api/iam/register", json={**datos, "email": "otro." + email, "habeas_data_aceptado": False}
    )
    check(
        "Sin habeas data -> 422",
        r.status_code == 422 and r.json().get("code") == "HABEAS_DATA_REQUERIDO",
        r.text,
    )
    r = c.post("/api/iam/register", json={**datos, "email": "otro2." + email, "rol": "Admin"})
    check("Rol Admin rechazado -> 422", r.status_code == 422, r.text)

    # Login (UC2)
    r = c.post("/api/iam/login", json={"email": email, "password": clave})
    check("Login -> 200", r.status_code == 200, r.text)
    token = r.json()["access_token"]
    r1 = c.post("/api/iam/login", json={"email": email, "password": "Incorrecta99"})
    r2 = c.post(
        "/api/iam/login", json={"email": "nadie.existe@example.com", "password": "Incorrecta99"}
    )
    check(
        "Los dos 401 son idénticos",
        r1.status_code == r2.status_code == 401 and r1.content == r2.content,
        f"{r1.text} / {r2.text}",
    )

    # JWKS y firma RS256
    r = c.get("/api/iam/.well-known/jwks.json")
    check(
        "JWKS -> 200 con Cache-Control",
        r.status_code == 200 and "max-age" in r.headers.get("cache-control", ""),
    )
    llave = jwt.PyJWK(r.json()["keys"][0])
    claims = jwt.decode(token, llave.key, algorithms=["RS256"], issuer="iam-service")
    check("Token verificado con la llave del JWKS", claims["rol"] == "Turista" and "jti" in claims)

    # ForwardAuth (RF-09) y RBAC
    auth = {"Authorization": f"Bearer {token}"}
    traefik = {"X-Forwarded-Method": "GET", "X-Forwarded-Uri": "/api/bookings/reservas"}
    r = c.get("/api/iam/auth/verificar", headers={**auth, **traefik})
    check(
        "Verificar con token válido -> 200 + X-Usuario-*",
        r.status_code == 200
        and r.headers.get("x-usuario-id") == claims["sub"]
        and r.headers.get("x-usuario-rol") == "Turista"
        and r.headers.get("cache-control") == "no-store",
        f"{r.status_code} {dict(r.headers)}",
    )
    r = c.get("/api/iam/auth/verificar", headers=traefik)
    check(
        "Verificar sin token -> 401 TOKEN_INVALIDO",
        r.status_code == 401 and r.json().get("code") == "TOKEN_INVALIDO",
        r.text,
    )
    r = c.get("/api/iam/admin/ping", headers=auth)
    check(
        "admin/ping con Turista -> 403 ROL_INSUFICIENTE",
        r.status_code == 403 and r.json().get("code") == "ROL_INSUFICIENTE",
        r.text,
    )

    # Logout y revocación
    r = c.post("/api/iam/logout", headers=auth)
    check("Logout -> 204", r.status_code == 204, r.text)
    r = c.get("/api/iam/auth/verificar", headers={**auth, **traefik})
    check("Verificar después del logout -> 401", r.status_code == 401, r.text)
    r = c.post("/api/iam/logout", headers=auth)
    check("Token revocado -> 401", r.status_code == 401, r.text)
    r = c.post("/api/iam/logout")
    check("Logout sin token -> 401", r.status_code == 401, r.text)

print("\nTODO FUNCIONA" if todo_ok else "\nHAY FALLAS")
sys.exit(0 if todo_ok else 1)
