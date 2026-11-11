"""Flujo completo de la plataforma a través del gateway, con los servicios reales y JWT.

Uso (desde la raíz del repositorio, con la plataforma arriba y el Admin sembrado):
    python gateway/pruebas/flujo_completo.py --entorno compose   # infra/docker-compose.yml (gateway en :80)
    python gateway/pruebas/flujo_completo.py --entorno k3s       # infra/k8s/k3s_local.py (gateway en :8081)

Recorre iam -> catalog -> booking -> review -> recommendation y los eventos entre ellos: registro y
aprobación del prestador, documentos en SeaweedFS, servicio publicado, calendario y cupos, reservas y
correos (Mailpit), cron de finalización, reseña y moderación, bitácora de auditoría y suspensión.

Los datos que crea se quedan (sirven para probar el frontend): al final imprime los correos y la clave
de los usuarios y el id del servicio. Cada corrida usa un sufijo nuevo, así que no choca con la anterior.
Variables: ADMIN_EMAIL y ADMIN_PASSWORD (por defecto, las del compose).
"""

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx

RAIZ = Path(__file__).resolve().parents[2]
CLAVE = "Tayrona2026"
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@turismo.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Cambiar-en-local1")
# booking decide "hoy" en hora de Bogotá (TZ=America/Bogota). Con date.today(), en un equipo en UTC la
# prueba fallaba después de las 7 p. m.: su "ayer" era el "hoy" de booking y el cron no finalizaba la
# reserva. Colombia no cambia de hora, así que basta un desfase fijo (y no hace falta tzdata en Windows).
BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")


def hoy():
    return datetime.now(BOGOTA).date()


# ---------- entornos ----------


def sh(*args: str, entrada: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", input=entrada)


class Compose:
    gateway = "http://localhost:80"
    mailpit = "http://localhost:8025"

    def iniciar(self) -> None:
        pass

    def terminar(self) -> None:
        pass

    def psql(self, base: str, sql: str) -> str:
        r = sh("docker", "exec", "tourism-platform-postgres-1", "psql", "-U", "turismo", "-d", base, "-Atc", sql)
        return r.stdout.strip()

    def python_en_recommendation(self, script: str) -> subprocess.CompletedProcess:
        return sh(
            "docker", "compose", "-f", "infra/docker-compose.yml",
            "exec", "-T", "recommendation-service", "python", "-c", script,
        )  # fmt: skip

    def finalizar_reservas(self) -> subprocess.CompletedProcess:
        return sh(
            "docker", "compose", "-f", "infra/docker-compose.yml",
            "run", "--rm", "booking-service", "python", "-m", "cron", "finalizar-reservas",
        )  # fmt: skip

    def url_publica(self, url: str) -> tuple[str, dict[str, str]]:
        return url, {}


class K3s:
    """k3s de infra/k8s/k3s_local.py: kubectl del propio clúster y port-forward de Mailpit con el del PC."""

    gateway = "http://localhost:8081"
    mailpit = "http://localhost:18025"

    def __init__(self) -> None:
        self._reenvio: subprocess.Popen | None = None

    def kubectl(self, *args: str) -> subprocess.CompletedProcess:
        return sh("docker", "exec", "turismo-k3s", "kubectl", *args)

    def iniciar(self) -> None:
        kubeconfig = RAIZ / "infra" / "k8s" / "local" / "k3s.kubeconfig"
        self._reenvio = subprocess.Popen(
            ["kubectl", "--kubeconfig", str(kubeconfig), "-n", "turismo-datos",
             "port-forward", "svc/mailpit", "18025:8025"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )  # fmt: skip
        time.sleep(3)

    def terminar(self) -> None:
        if self._reenvio:
            self._reenvio.terminate()

    def psql(self, base: str, sql: str) -> str:
        r = self.kubectl(
            "-n", "turismo-datos", "exec", "postgres-1", "-c", "postgres", "--", "psql", "-d", base, "-Atc", sql
        )  # fmt: skip
        return r.stdout.strip()

    def python_en_recommendation(self, script: str) -> subprocess.CompletedProcess:
        return self.kubectl(
            "-n", "turismo-app", "exec", "deploy/recommendation-service", "--", "python", "-c", script
        )  # fmt: skip

    def finalizar_reservas(self) -> subprocess.CompletedProcess:
        # Lo mismo que hace el CronJob cada 15 minutos, disparado a mano.
        nombre = f"finalizar-{uuid.uuid4().hex[:6]}"
        creado = self.kubectl(
            "-n", "turismo-app", "create", "job", nombre, "--from=cronjob/booking-finalizar-reservas"
        )  # fmt: skip
        if creado.returncode != 0:
            return creado
        return self.kubectl("-n", "turismo-app", "wait", f"job/{nombre}", "--for=condition=complete", "--timeout=3m")

    def url_publica(self, url: str) -> tuple[str, dict[str, str]]:
        # Windows no resuelve s3.localhost (los navegadores sí): se conecta a localhost con el mismo Host,
        # que es el que va dentro de la firma.
        partes = urlsplit(url)
        if partes.hostname and partes.hostname.endswith(".localhost"):
            return urlunsplit(partes._replace(netloc=f"localhost:{partes.port}")), {"Host": partes.netloc}
        return url, {}


# ---------- utilidades ----------

fallos: list[str] = []
c = httpx.Client(timeout=60)


def ok(nombre: str, cond: object, extra: str = "") -> bool:
    print(("OK   " if cond else "FALLA"), nombre, "" if cond else extra)
    if not cond:
        fallos.append(nombre)
    return bool(cond)


def esperar(fn, seg: int = 60):
    fin = time.time() + seg
    ultimo = None
    while time.time() < fin:
        ultimo = fn()
        if ultimo:
            return ultimo
        time.sleep(0.5)
    return ultimo


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def idem() -> dict[str, str]:
    return {"Idempotency-Key": str(uuid.uuid4())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--entorno", choices=["compose", "k3s"], required=True)
    entorno = Compose() if parser.parse_args().entorno == "compose" else K3s()
    entorno.iniciar()
    try:
        flujo(entorno)
    finally:
        entorno.terminar()
    print("\n== resumen ==")
    print("Fallos:", fallos or "ninguno")
    sys.exit(1 if fallos else 0)


def flujo(e: Compose | K3s) -> None:
    gw = e.gateway
    sufijo = uuid.uuid4().hex[:8]

    def correos(a: str) -> list:
        try:
            return c.get(f"{e.mailpit}/api/v1/search", params={"query": f"to:{a}"}).json().get("messages", [])
        except httpx.HTTPError:
            return []

    def login(email: str, clave: str) -> dict:
        r = c.post(f"{gw}/api/iam/login", json={"email": email, "password": clave})
        r.raise_for_status()
        return r.json()

    def registrar(email: str, rol: str) -> str:
        r = c.post(
            f"{gw}/api/iam/register",
            json={
                "email": email, "password": CLAVE, "nombre_completo": f"{rol} Prueba", "rol": rol,
                "habeas_data_aceptado": True, "es_mayor_de_edad": True, "idioma": "es",
            },
        )  # fmt: skip
        ok(f"iam registro {rol}", r.status_code == 201, r.text)
        return r.json()["id"]

    def bitacora(token: str, **filtros) -> list:
        r = c.get(f"{gw}/api/iam/admin/bitacora", params={"tamano": 100, **filtros}, headers=bearer(token))
        r.raise_for_status()
        return r.json()["items"]

    def leer_publico(url: str) -> httpx.Response:
        destino, encabezados = e.url_publica(url)
        return c.get(destino, headers=encabezados)

    # ---------- iam: Admin, prestador, documentos ----------
    print("\n== iam ==")
    adm = login(ADMIN_EMAIL, ADMIN_PASSWORD)
    adm_t, adm_id = adm["access_token"], adm["usuario"]["id"]
    ok("iam login del Admin sembrado", bool(adm_t))
    auth = bearer(adm_t)
    v = c.get(f"{gw}/api/iam/auth/verificar", headers=auth)
    ok(
        "iam verificar devuelve identidad",
        v.status_code == 200 and v.headers.get("x-usuario-rol") == "Admin" and v.headers.get("x-usuario-id") == adm_id,
        v.text,
    )

    mail_p, mail_t = f"prestador{sufijo}@example.com", f"turista{sufijo}@example.com"
    pid = registrar(mail_p, "Prestador")
    tid = registrar(mail_t, "Turista")
    ident_p = bearer(login(mail_p, CLAVE)["access_token"])
    ident_t = bearer(login(mail_t, CLAVE)["access_token"])

    print("\n== gateway ==")
    perfil_url = f"{gw}/api/catalog/prestador/perfil"
    ok("sin token: 401", c.get(perfil_url).status_code == 401)
    falsos = {"X-Usuario-Id": adm_id, "X-Usuario-Rol": "Admin"}
    ok("encabezados falsos sin token: 401", c.get(perfil_url, headers=falsos).status_code == 401)
    r = c.get(f"{gw}/api/reviews/moderacion/resenas", headers={**ident_t, **falsos})
    ok("rol falso con token de turista: lo reemplaza y da 403", r.status_code == 403)
    ok("ruta pública sin token", c.get(f"{gw}/api/catalog/buscar").status_code == 200)
    ok("/internal no se publica", c.get(f"{gw}/internal/usuarios/{adm_id}/contacto").status_code == 404)
    ok("/metrics no se publica", c.get(f"{gw}/metrics").status_code == 404)
    ok("/health no se publica", c.get(f"{gw}/health").status_code == 404)

    pdf = b"%PDF-1.4\n%prueba\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    for tipo, extra in (("RNT", {}), ("RUT", {"razon_social": "Tours Prueba SAS"})):
        r = c.post(
            f"{gw}/api/iam/prestador/documentos",
            headers=ident_p,
            data={"tipo": tipo, **extra},
            files={"archivo": (f"{tipo}.pdf", pdf, "application/pdf")},
        )
        ok(f"iam carga {tipo} en SeaweedFS", r.status_code == 201, r.text)
    doc_id = r.json()["id"]
    u = c.get(f"{gw}/api/iam/admin/documentos/{doc_id}/url", headers=auth).json()["url"]
    ok("seaweedfs URL firmada del RUT sirve", leer_publico(u).status_code == 200)
    ok("seaweedfs el RUT sin firma NO se lee", leer_publico(u.split("?")[0]).status_code in (401, 403))

    r = c.post(f"{gw}/api/catalog/servicios", headers={**ident_p, **idem()}, json={})
    ok("catalog rechaza prestador sin aprobar o cuerpo inválido", r.status_code in (400, 403), r.text)
    r = c.post(f"{gw}/api/iam/admin/prestadores/{pid}/aprobar", headers=auth)
    ok("iam aprueba prestador", r.status_code == 200, r.text)
    perfil = esperar(lambda: (x := c.get(perfil_url, headers=ident_p)).status_code == 200 and x.json())
    ok(
        "prestador.aprobado -> catalog crea perfil con razón social",
        bool(perfil) and perfil.get("razon_social") == "Tours Prueba SAS",
        str(perfil),
    )

    # ---------- catalog -> booking y review ----------
    print("\n== servicio.publicado ==")
    cuerpo = {
        "nombre": {"es": f"Tour prueba {sufijo}", "en": f"Test tour {sufijo}"},
        "descripcion": {"es": "Recorrido de prueba por la Sierra Nevada.", "en": "Test walk in the Sierra Nevada."},
        "tipo": "SENDERISMO",
        "ubicacion": {"lat": 11.1944, "lon": -74.2306},
        "tarifa_base": 90000,
        "unidad_tarifa": "POR_PERSONA",
        "capacidad_aforo_diario": 20,
        "atributos": {"experiencia": {"duracion_minutos": 120, "nivel_fisico": "BAJO"}},
    }
    r = c.post(f"{gw}/api/catalog/servicios", headers={**ident_p, **idem()}, json=cuerpo)
    if not ok("catalog crea servicio", r.status_code == 201, r.text):
        return
    sid = r.json()["id"]

    r = c.post(
        f"{gw}/api/catalog/prestador/imagenes", headers=ident_p, json={"content_type": "image/png", "tamano_bytes": 8}
    )
    if ok("catalog firma subida de imagen", r.status_code in (200, 201), r.text):
        d = r.json()
        destino, host = e.url_publica(d["subida_url"])
        put = c.request(
            d.get("metodo", "PUT"),
            destino,
            content=b"\x89PNG\r\n\x1a\n",
            headers={"Content-Type": "image/png", **d.get("encabezados", {}), **host},
        )
        ok("seaweedfs acepta la imagen con credencial limitada", put.status_code in (200, 204), put.text[:200])
        pub = leer_publico(d["url_publica"])
        ok("seaweedfs imagen pública sin firma", pub.status_code == 200, str(pub.status_code))

    v10, v11, v12 = ((hoy() + timedelta(days=n)).isoformat() for n in (10, 11, 12))
    abierto = esperar(
        lambda: (
            c.post(
                f"{gw}/api/bookings/prestador/calendario/{sid}/rango",
                headers={**ident_p, **idem()},
                json={"desde": v10, "hasta": v12, "cupos_totales": 10},
            ).status_code
            == 201
        )
    )
    ok("servicio.publicado -> booking lo conoce y su dueño abre calendario", bool(abierto))
    sql = f"select count(*) from servicio_dueno where servicio_id='{sid}'"
    ok("servicio.publicado -> review guarda el dueño", bool(esperar(lambda: e.psql("review_db", sql) == "1")))

    print("\n== disponibilidad ==")
    d = c.get(f"{gw}/api/bookings/disponibilidad", params={"servicio_id": sid, "desde": v10, "hasta": v10}).json()
    ok("booking disponibilidad pública", d["dias"][0]["cupos_disponibles"] == 10, str(d))

    def cupos():
        x = c.get(f"{gw}/api/catalog/buscar", params={"texto": sufijo, "fecha": v10, "personas": 2}).json()
        return next((i.get("cupos_disponibles") for i in x["items"] if i["id"] == sid), None)

    ok("disponibilidad.actualizada -> catalog muestra cupos", esperar(lambda: cupos() == 10) is True, str(cupos()))

    # ---------- reserva y correos ----------
    print("\n== reservas y correos ==")
    reservas = f"{gw}/api/bookings/"
    r = c.post(
        reservas, headers={**ident_t, **idem()}, json={"servicio_id": sid, "fecha_reserva": v10, "numero_personas": 2}
    )
    ok("booking solicitar", r.status_code == 201, r.text)
    rid = r.json()["id"]
    ok("reserva.solicitada -> correo al prestador (contacto en iam + Mailpit)", bool(esperar(lambda: correos(mail_p))))
    ok("descuento de cupos llega a catalog", esperar(lambda: cupos() == 8) is True, str(cupos()))
    sql = f"select count(*) from reserva_proyeccion where reserva_id='{rid}'"
    ok("reserva.solicitada -> catalog.demanda", bool(esperar(lambda: e.psql("catalog_db", sql) == "1")))
    r = c.post(f"{reservas}{rid}/confirmar", headers=ident_p)
    ok("booking confirmar", r.status_code == 200, r.text)
    ok("reserva.confirmada -> correo al turista", bool(esperar(lambda: correos(mail_t))))

    # Otra reserva que el prestador rechaza y otra que el turista modifica y cancela.
    r = c.post(
        reservas, headers={**ident_t, **idem()}, json={"servicio_id": sid, "fecha_reserva": v11, "numero_personas": 1}
    )
    r2 = c.post(f"{reservas}{r.json()['id']}/rechazar", headers=ident_p, json={"motivo": "Sin guía ese día"})
    ok("booking rechazar", r2.status_code == 200, r2.text)
    ok("reserva.rechazada -> correo con motivo", bool(esperar(lambda: len(correos(mail_t)) >= 2)))
    r = c.post(
        reservas, headers={**ident_t, **idem()}, json={"servicio_id": sid, "fecha_reserva": v12, "numero_personas": 1}
    )
    rc = r.json()
    n_prev = len(correos(mail_p))
    rm = c.patch(
        f"{reservas}{rc['id']}",
        headers={**ident_t, "If-Match": f'"{rc["version"]}"'},
        json={"fecha_reserva": v12, "numero_personas": 2},
    )
    ok("booking modificar", rm.status_code == 200, rm.text)
    rc = rm.json()
    ok("reserva.modificada -> correo al prestador", bool(esperar(lambda: len(correos(mail_p)) > n_prev)))
    n_prev = len(correos(mail_p))
    r2 = c.post(
        f"{reservas}{rc['id']}/cancelar",
        headers={**ident_t, "If-Match": f'"{rc["version"]}"'},
        json={"motivo": "Cambio de planes"},
    )
    ok("booking cancelar por turista", r2.status_code == 200, r2.text)
    ok("reserva.cancelada(Turista) -> correo al prestador", bool(esperar(lambda: len(correos(mail_p)) > n_prev)))

    # ---------- chatbot ----------
    print("\n== recommendation -> catalog, booking y review ==")
    script = f"""
import asyncio, dataclasses, json, uuid, httpx
from src.config import Configuracion
from src.application.ports.herramientas import ContextoTurista
from src.infrastructure.tools.herramientas_plataforma import HerramientasPlataforma
async def main():
    cfg = Configuracion()
    async with httpx.AsyncClient(timeout=10) as cl:
        h = HerramientasPlataforma(cl, cfg.catalog_url, cfg.booking_url, cfg.review_url)
        ctx = ContextoTurista(**{{f.name: (uuid.UUID('{tid}') if f.name == 'turista_id' else 'es')
                                 for f in dataclasses.fields(ContextoTurista)}})
        s = '{sid}'
        for n, a in [('buscar_servicios', {{'texto': '{sufijo}', 'fecha': '{v10}', 'personas': 2}}),
                     ('detalle_servicio', {{'servicio_id': s}}),
                     ('consultar_disponibilidad', {{'servicio_id': s, 'desde': '{v10}'}}),
                     ('historial_turista', {{}}), ('resenas_servicio', {{'servicio_id': s}}),
                     ('presion_capacidad_carga', {{}}), ('alertas_oficiales', {{}})]:
            r = await h.ejecutar(n, a, ctx)
            print(json.dumps({{'tool': n, 'error': r.error, 'datos': r.datos}}, default=str, ensure_ascii=False))
asyncio.run(main())
"""
    r = e.python_en_recommendation(script)
    ok("tools se ejecutan en el contenedor", r.returncode == 0, r.stderr[-800:])
    for linea in r.stdout.splitlines():
        x = json.loads(linea)
        ok(f"tool {x['tool']}", x["error"] is None, json.dumps(x["datos"], ensure_ascii=False)[:300])
    r = c.post(f"{gw}/api/recommendations/chat", headers=ident_t, json={"mensaje": "hola"})
    ok(
        "chat sin clave responde 503 con formato común",
        r.status_code == 503 and r.json().get("error") == "ASISTENTE_NO_DISPONIBLE",
        r.text,
    )
    r = c.post(f"{gw}/api/recommendations/chat", headers=ident_p, json={"mensaje": "hola"})
    ok("chat rechaza otro rol", r.status_code == 403, r.text)

    # ---------- finalizar y reseñar ----------
    print("\n== reserva.finalizada y reseñas ==")
    resenas = f"{gw}/api/reviews/resenas"
    r = c.post(resenas, headers={**ident_t, **idem()}, json={"servicio_id": sid, "puntuacion": 4})
    no_elegible = r.status_code == 403 and r.json().get("error") == "NO_ELEGIBLE"
    ok("review rechaza sin visita (NO_ELEGIBLE)", no_elegible, r.text)
    # La reserva confirmada pasa a ayer para que el cron la finalice.
    ayer = (hoy() - timedelta(days=1)).isoformat()
    e.psql(
        "booking_db",
        f"create temp table t as select * from disponibilidad_cupo where servicio_id='{sid}' and fecha='{v10}';"
        f" update t set fecha='{ayer}'; insert into disponibilidad_cupo select * from t;"
        f" update solicitud_reserva set fecha_reserva='{ayer}' where id='{rid}';",
    )
    r = e.finalizar_reservas()
    ok("booking cron finalizar-reservas corre", r.returncode == 0, (r.stderr or r.stdout)[-400:])
    sql = f"select estado from solicitud_reserva where id='{rid}'"
    ok("reserva FINALIZADA", e.psql("booking_db", sql) == "FINALIZADA", e.psql("booking_db", sql))

    def pendiente() -> bool:
        x = c.get(f"{gw}/api/reviews/turista/pendientes", headers=ident_t)
        return x.status_code == 200 and sid in x.text

    ok("reserva.finalizada -> review habilita la reseña", bool(esperar(pendiente)))
    sql = f"select estado from reserva_proyeccion where reserva_id='{rid}'"
    ok(
        "reserva.finalizada -> catalog.demanda",
        bool(esperar(lambda: e.psql("catalog_db", sql).upper().startswith("FINALIZ"))),
        e.psql("catalog_db", sql),
    )
    r = c.post(
        resenas,
        headers={**ident_t, **idem()},
        json={"servicio_id": sid, "puntuacion": 4, "comentario": "Muy buen recorrido por la montaña"},
    )
    ok("review crea reseña", r.status_code == 201, r.text)
    res = r.json()
    rs_id = res["id"]

    def promedio():
        x = c.get(f"{gw}/api/catalog/servicios/{sid}")
        return x.json().get("calificacion_promedio") if x.status_code == 200 else None

    ok("resena.publicada -> catalog actualiza promedio", esperar(lambda: promedio() == 4) is True, str(promedio()))
    r = c.get(f"{gw}/api/reviews/servicios/{sid}/resumen")
    ok("review y catalog coinciden en el promedio", r.json()["promedio"] == 4, r.text)
    r = c.put(
        f"{resenas}/{rs_id}/respuesta",
        headers={**ident_p, "If-Match": f'"{res.get("version", 1)}"'},
        json={"texto": "Gracias por visitarnos"},
    )
    ok("review el dueño (de servicio.publicado) responde", r.status_code == 200, r.text)
    et = r.headers.get("etag")
    r2 = c.put(f"{resenas}/{rs_id}/respuesta", headers={**ident_t, "If-Match": et}, json={"texto": "No soy el dueño"})
    ok("review otro usuario no responde", r2.status_code == 403, r2.text)
    r = c.post(
        f"{resenas}/{rs_id}/moderacion",
        headers={**auth, "If-Match": et},
        json={"decision": "OCULTAR", "motivo": "Prueba de moderación"},
    )
    ok("review modera", r.status_code == 200, r.text)
    ok("resena.ocultada -> catalog quita del promedio", bool(esperar(lambda: promedio() is None)), str(promedio()))

    # ---------- auditoría ----------
    print("\n== auditoria.registrada -> bitácora de iam ==")
    ok("403 en catalog", c.get(perfil_url, headers=ident_t).status_code == 403)
    ok("403 en booking", c.get(f"{gw}/api/bookings/prestador/solicitudes", headers=ident_t).status_code == 403)
    ok("403 en review", c.get(f"{gw}/api/reviews/moderacion/resenas", headers=ident_t).status_code == 403)
    for prod in ("catalog-service", "booking-service", "review-service"):
        filas = esperar(lambda p=prod: bitacora(adm_t, servicio_origen=p, accion="ACCESS_DENIED"))
        ok(f"ACCESS_DENIED de {prod} en bitácora", bool(filas))
    ok("MODERACION en bitácora", bool(bitacora(adm_t, accion="MODERACION")))
    ok("RESERVA_CONFIRMADA en bitácora", bool(bitacora(adm_t, accion="RESERVA_CONFIRMADA")))

    # ---------- suspensión ----------
    print("\n== prestador.suspendido ==")
    estado_p = f"{gw}/api/iam/admin/usuarios/{pid}/estado"
    r = c.patch(estado_p, headers=auth, json={"activo": False, "motivo": "Prueba"})
    ok("iam desactiva prestador", r.status_code == 200, r.text)
    ok(
        "prestador.suspendido -> catalog oculta el servicio",
        bool(esperar(lambda: c.get(f"{gw}/api/catalog/servicios/{sid}").status_code == 404)),
    )

    def booking_rechaza() -> bool:
        x = c.post(
            reservas,
            headers={**ident_t, **idem()},
            json={"servicio_id": sid, "fecha_reserva": v11, "numero_personas": 1},
        )
        return x.status_code >= 400

    ok("servicio.publicado(activo=false) -> booking no acepta reservas", bool(esperar(booking_rechaza)))
    r = c.patch(estado_p, headers=auth, json={"activo": True, "motivo": "Prueba"})
    ok(
        "prestador.aprobado al rehabilitar -> catalog restaura",
        bool(esperar(lambda: c.get(f"{gw}/api/catalog/servicios/{sid}").status_code == 200)),
    )

    print("\n== datos que quedan para el frontend ==")
    print(f"Prestador {mail_p} / {CLAVE}  (id {pid})")
    print(f"Turista   {mail_t} / {CLAVE}  (id {tid})")
    print(f"Servicio  {sid}  ('Tour prueba {sufijo}')")


if __name__ == "__main__":
    main()
