"""API HTTP de punta a punta sobre los adaptadores en memoria (httpx, sin levantar uvicorn)."""

from datetime import datetime
from uuid import uuid4

import httpx
import pytest

from config import Configuracion
from domain.reglas import ZONA
from infrastructure.http import demo
from infrastructure.reloj import RelojFijo
from main import contenedor_memoria, crear_app

AHORA = datetime(2026, 11, 1, 10, 0, tzinfo=ZONA)
SERVICIO = str(demo.SERVICIO_DEMO)
TURISTA = {"X-Usuario-Id": str(demo.USUARIO_TURISTA_DEMO), "X-Usuario-Rol": "Turista"}
PRESTADOR = {"X-Usuario-Id": str(demo.USUARIO_PRESTADOR_DEMO), "X-Usuario-Rol": "Prestador"}
BASE = "/api/bookings"


@pytest.fixture
async def cliente():
    config = Configuracion(datos_demo=True)
    contenedor = contenedor_memoria(config, RelojFijo(AHORA))
    await demo.cargar_datos_demo(contenedor)  # calendario del 2 al 31 de noviembre, 10 cupos
    contenedor.publicador.publicados.clear()
    app = crear_app(config, contenedor)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://booking") as c:
        c.contenedor = contenedor
        yield c


async def solicitar(cliente, personas=2, fecha="2026-11-10", **headers):
    return await cliente.post(
        BASE, json={"servicio_id": SERVICIO, "fecha_reserva": fecha, "numero_personas": personas},
        headers={**TURISTA, **headers},
    )


async def test_health_y_metricas(cliente):
    r = await cliente.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "checks": {"almacen_memoria": "up"}}
    await solicitar(cliente)
    metricas = (await cliente.get("/metrics")).text
    # Mismas series que catalog, iam y recommendation (prometheus-fastapi-instrumentator).
    assert 'handler="/api/bookings"' in metricas and "http_requests_total" in metricas
    assert "http_request_duration_seconds" in metricas
    assert "booking_eventos_consumidos_total" in metricas


async def test_correlation_id_se_respeta_y_viaja_al_error_y_al_evento(cliente):
    r = await solicitar(cliente, **{"X-Correlation-ID": "corr-prueba-1"})
    assert r.headers["X-Correlation-ID"] == "corr-prueba-1"
    assert cliente.contenedor.publicador.publicados[-1]["correlation_id"] == "corr-prueba-1"

    r = await cliente.get(f"{BASE}/{uuid4()}", headers={**TURISTA, "X-Correlation-ID": "corr-prueba-2"})
    assert r.status_code == 404 and r.json()["correlation_id"] == "corr-prueba-2"


async def test_correlation_id_se_genera_si_falta_o_no_es_valido(cliente):
    r = await cliente.get("/health", headers={"X-Correlation-ID": "valor con espacios"})
    generado = r.headers["X-Correlation-ID"]
    assert generado.startswith("corr-") and generado != "valor con espacios"


async def test_ciclo_completo_solicitar_confirmar(cliente):
    r = await solicitar(cliente)
    assert r.status_code == 201 and r.headers["ETag"] == '"1"'
    reserva = r.json()
    assert reserva["estado"] == "SOLICITADA" and reserva["prestador_id"] == str(demo.PERFIL_PRESTADOR_DEMO)
    assert "prestador_usuario_id" not in reserva

    panel = (await cliente.get(f"{BASE}/prestador/solicitudes", headers=PRESTADOR)).json()
    assert [x["id"] for x in panel["items"]] == [reserva["id"]]

    r = await cliente.post(f"{BASE}/{reserva['id']}/confirmar", headers=PRESTADOR)
    assert r.json()["estado"] == "CONFIRMADA"

    historial = (await cliente.get(f"{BASE}/mis-reservas", headers=TURISTA)).json()
    assert historial["total"] == 1 and historial["items"][0]["estado"] == "CONFIRMADA"
    assert "reserva.confirmada" in [s["event_type"] for s in cliente.contenedor.publicador.publicados]


async def test_errores_con_formato_comun(cliente):
    r = await solicitar(cliente, personas=11, **{"X-Correlation-ID": "corr-prueba"})
    assert r.status_code == 409
    assert r.json() == {
        "error": "CUPOS_INSUFICIENTES",
        "message": "Solo quedan 10 cupos para el 2026-11-10.",
        "correlation_id": "corr-prueba",
    }


async def test_validacion_es_400(cliente):
    r = await cliente.post(BASE, json={"servicio_id": "no-es-uuid"}, headers=TURISTA)
    assert r.status_code == 400 and r.json()["error"] == "VALIDACION"


async def test_sin_identidad_es_401(cliente):
    r = await cliente.get(f"{BASE}/mis-reservas")
    assert r.status_code == 401 and r.json()["error"] == "NO_AUTENTICADO"


async def test_rol_incorrecto_es_403_y_queda_en_auditoria(cliente):
    r = await cliente.get(f"{BASE}/mis-reservas", headers=PRESTADOR)
    assert r.status_code == 403 and r.json()["error"] == "ROL_NO_PERMITIDO"
    [sobre] = cliente.contenedor.publicador.publicados
    assert sobre["event_type"] == "auditoria.registrada"
    assert (sobre["payload"]["accion"], sobre["payload"]["resultado"]) == ("ACCESS_DENIED", "DENEGADO")


async def test_otro_prestador_recibe_404(cliente):
    reserva = (await solicitar(cliente)).json()
    otro = {"X-Usuario-Id": str(uuid4()), "X-Usuario-Rol": "Prestador"}
    r = await cliente.post(f"{BASE}/{reserva['id']}/confirmar", headers=otro)
    assert r.status_code == 404


async def test_idempotency_key_no_crea_dos_reservas(cliente):
    clave = {"Idempotency-Key": str(uuid4())}
    primera = await solicitar(cliente, **clave)
    segunda = await solicitar(cliente, **clave)
    assert segunda.status_code == 201 and segunda.json()["id"] == primera.json()["id"]
    assert (await cliente.get(f"{BASE}/mis-reservas", headers=TURISTA)).json()["total"] == 1


async def test_reintento_mientras_la_primera_sigue_en_proceso_responde_409(cliente):
    clave = str(uuid4())
    # La primera petición tomó la clave y aún no termina (p. ej. otra réplica esperando el bloqueo).
    await cliente.contenedor.idempotencia.reservar(f"idem:booking:{demo.USUARIO_TURISTA_DEMO}:POST:{BASE}:{clave}")
    r = await solicitar(cliente, **{"Idempotency-Key": clave})
    assert r.status_code == 409 and r.json()["error"] == "PETICION_EN_PROCESO"
    assert (await cliente.get(f"{BASE}/mis-reservas", headers=TURISTA)).json()["total"] == 0


async def test_si_la_operacion_falla_la_clave_queda_libre(cliente):
    clave = {"Idempotency-Key": str(uuid4())}
    r = await solicitar(cliente, fecha="2027-03-01", **clave)  # día no abierto en el calendario
    assert r.status_code == 409 and r.json()["error"] == "DIA_NO_DISPONIBLE"
    # El reintento se ejecuta de nuevo (no se guardan los errores ni queda "en proceso").
    r = await solicitar(cliente, fecha="2027-03-01", **clave)
    assert r.json()["error"] == "DIA_NO_DISPONIBLE"


async def test_modificar_exige_if_match_y_controla_version(cliente):
    reserva = (await solicitar(cliente)).json()
    url = f"{BASE}/{reserva['id']}"
    assert (await cliente.patch(url, json={"numero_personas": 3}, headers=TURISTA)).status_code == 428
    r = await cliente.patch(url, json={"numero_personas": 3}, headers={**TURISTA, "If-Match": '"1"'})
    assert r.status_code == 200 and r.headers["ETag"] == '"2"'
    r = await cliente.patch(url, json={"numero_personas": 4}, headers={**TURISTA, "If-Match": '"1"'})
    assert r.status_code == 409 and r.json()["error"] == "VERSION_DISTINTA" and r.headers["ETag"] == '"2"'
    # El cuerpo trae la reserva como está ahora, igual que GET /{id}: la PWA muestra el conflicto.
    cuerpo = r.json()
    assert cuerpo["version_actual"] == 2
    assert cuerpo["actual"] == (await cliente.get(url, headers=TURISTA)).json()
    assert cuerpo["actual"]["numero_personas"] == 3


async def test_conflicto_del_calendario_trae_el_dia_actual(cliente):
    """ESC-09: el prestador editó sin conexión la versión 1; mientras tanto el día pasó a la 2."""
    url = f"{BASE}/prestador/calendario/{SERVICIO}/2026-11-10"
    await cliente.put(url, json={"cupos_totales": 8}, headers={**PRESTADOR, "If-Match": '"1"'})  # el otro cambio
    r = await cliente.put(url, json={"cupos_totales": 12}, headers={**PRESTADOR, "If-Match": '"1"'})
    assert r.status_code == 409 and r.headers["ETag"] == '"2"'
    cuerpo = r.json()
    assert (cuerpo["error"], cuerpo["version_actual"]) == ("VERSION_DISTINTA", 2)
    assert cuerpo["correlation_id"]  # sigue siendo el formato común de error
    calendario = (await cliente.get(
        f"{BASE}/prestador/calendario/{SERVICIO}", params={"desde": "2026-11-10", "hasta": "2026-11-10"},
        headers=PRESTADOR,
    )).json()
    assert cuerpo["actual"] == calendario["dias"][0]
    assert cuerpo["actual"]["cupos_totales"] == 8  # lo que hay en el servidor, no lo que envió


async def test_cancelar_sin_cuerpo_y_rechazar_con_motivo(cliente):
    a = (await solicitar(cliente)).json()
    b = (await solicitar(cliente, fecha="2026-11-11")).json()
    assert (await cliente.post(f"{BASE}/{a['id']}/cancelar", headers=TURISTA)).json()["estado"] == "CANCELADA"
    r = await cliente.post(f"{BASE}/{b['id']}/rechazar", json={"motivo": "Sin guía"}, headers=PRESTADOR)
    assert (r.json()["estado"], r.json()["motivo"]) == ("RECHAZADA", "Sin guía")


async def test_disponibilidad(cliente):
    await solicitar(cliente, personas=8)
    r = await cliente.get(f"{BASE}/disponibilidad", params={"servicio_id": SERVICIO, "desde": "2026-11-10", "hasta": "2026-11-11"})
    assert [d["cupos_disponibles"] for d in r.json()["dias"]] == [2, 10]


async def test_calendario_del_prestador(cliente):
    url = f"{BASE}/prestador/calendario/{SERVICIO}"
    r = await cliente.get(url, params={"desde": "2026-11-10", "hasta": "2026-11-10"}, headers=PRESTADOR)
    [dia] = r.json()["dias"]
    assert (dia["cupos_totales"], dia["version"]) == (10, 1)
    r = await cliente.put(f"{url}/2026-11-10", json={"cupos_totales": 12, "tarifa_dia": 90000},
                          headers={**PRESTADOR, "If-Match": '"1"'})
    assert r.status_code == 200 and r.json()["cupos_totales"] == 12 and r.headers["ETag"] == '"2"'
    r = await cliente.put(f"{url}/2026-11-10", json={"cupos_totales": 25}, headers={**PRESTADOR, "If-Match": '"2"'})
    assert r.status_code == 422 and r.json()["error"] == "SUPERA_AFORO"
    r = await cliente.post(f"{url}/rango", json={"desde": "2026-12-05", "hasta": "2026-12-07", "cupos_totales": 5},
                           headers=PRESTADOR)
    assert r.status_code == 201 and len(r.json()["creados"]) == 3


async def test_demo_publicar_servicio_y_expirar(cliente):
    otro = {"servicio_id": str(uuid4()), "prestador_id": str(uuid4()), "prestador_usuario_id": str(uuid4()),
            "capacidad_aforo_diario": 5, "tarifa_base": 1000, "version": 1}
    assert (await cliente.post("/dev/servicios", json=otro)).json()["aplicado"] is True
    await solicitar(cliente)
    await cliente.post("/dev/reloj/avanzar", params={"horas": 48})
    assert (await cliente.post("/dev/tareas/expirar")).json() == {"expiradas": 1}
    eventos = (await cliente.get("/dev/eventos")).json()
    # /dev/eventos muestra los más recientes primero: el último lote fue rechazada + auditoría + disponibilidad.
    assert [e["event_type"] for e in eventos[:3]] == [
        "disponibilidad.actualizada", "auditoria.registrada", "reserva.rechazada",
    ]
