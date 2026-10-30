"""Casos de uso contra los adaptadores en memoria (sin Postgres ni RabbitMQ)."""

import asyncio
import json
from pathlib import Path
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from application.base import Contexto
from application.calendario import (
    AbrirRangoCalendario,
    ConsultarCalendario,
    ConsultarDisponibilidad,
    GuardarDiaCalendario,
)
from application.consultas import ListarReservas, ObtenerReserva
from application.errores import DiaExistente, NoEncontrado, ReservaDuplicada, VersionDistinta
from application.ports import FiltroReservas
from application.reservas import (
    CancelarReserva,
    ConfirmarReserva,
    ModificarReserva,
    RechazarReserva,
    SolicitarReserva,
)
from application.servicios import AplicarServicioPublicado
from application.tareas import ExpirarSolicitudes, FinalizarReservas
from domain.errores import CuposComprometidos, CuposInsuficientes, NoDisponible, SuperaAforo, Validacion
from domain.reglas import ZONA
from domain.reserva import Actor, EstadoReserva
from infrastructure.messaging.memoria import PublicadorMemoria
from infrastructure.persistence.memoria import AlmacenMemoria, fabrica_memoria
from infrastructure.reloj import RelojFijo

AHORA = datetime(2026, 11, 1, 10, 0, tzinfo=ZONA)
ESQUEMA_DISPONIBILIDAD = Path(__file__).resolve().parents[4] / "contracts" / "events" / "disponibilidad.actualizada.v1.json"
DIA_1 = date(2026, 11, 10)
DIA_2 = date(2026, 11, 11)


class Escenario:
    """Un servicio publicado por el catálogo, con su prestador y un calendario abierto."""

    def __init__(self) -> None:
        self.almacen = AlmacenMemoria()
        self.publicador = PublicadorMemoria()
        self.reloj = RelojFijo(AHORA)
        self.ctx = Contexto(fabrica_memoria(self.almacen, self.publicador), self.reloj)
        self.servicio_id = uuid4()
        self.prestador_id = uuid4()  # perfil en el catálogo
        self.prestador_usuario_id = uuid4()  # usuario en iam
        self.turista_id = uuid4()

    async def publicar_servicio(self, version: int = 1, activo: bool = True, aforo: int = 20, **otros) -> bool:
        payload = {
            "servicio_id": str(self.servicio_id),
            "prestador_id": str(self.prestador_id),
            "prestador_usuario_id": str(self.prestador_usuario_id),
            "capacidad_aforo_diario": aforo,
            "tarifa_base": 50000,
            "activo": activo,
            "version": version,
            **otros,
        }
        return await AplicarServicioPublicado(self.ctx)(payload)

    async def abrir(self, cupos: int = 10, desde: date = DIA_1, hasta: date = DIA_2):
        return await AbrirRangoCalendario(self.ctx)(
            self.prestador_usuario_id, self.servicio_id, desde, hasta, cupos
        )

    async def solicitar(self, personas: int = 2, fecha: date = DIA_1, turista: UUID | None = None):
        return await SolicitarReserva(self.ctx)(turista or self.turista_id, self.servicio_id, fecha, personas)

    def cupos(self, fecha: date = DIA_1) -> int:
        return self.almacen.dias[(self.servicio_id, fecha)].cupos_disponibles

    def dias_publicados(self) -> list[dict]:
        """Payloads de los disponibilidad.actualizada publicados después del último clear()."""
        return [s["payload"] for s in self.publicador.publicados if s["event_type"] == "disponibilidad.actualizada"]


@pytest.fixture
async def esc() -> Escenario:
    e = Escenario()
    await e.publicar_servicio()
    await e.abrir()
    e.publicador.publicados.clear()
    return e


# ---------- servicio.publicado ----------

class TestServicioPublicado:
    async def test_guarda_y_actualiza_con_version_mayor(self):
        e = Escenario()
        assert await e.publicar_servicio(version=1)
        assert await e.publicar_servicio(version=2, aforo=8)
        assert e.almacen.servicios[e.servicio_id].capacidad_aforo_diario == 8

    @pytest.mark.parametrize("version", [1, 2])
    async def test_ignora_eventos_viejos_o_repetidos(self, version):
        e = Escenario()
        await e.publicar_servicio(version=2, aforo=8)
        assert not await e.publicar_servicio(version=version, aforo=99)
        assert e.almacen.servicios[e.servicio_id].capacidad_aforo_diario == 8


# ---------- Calendario (UC19) ----------

class TestCalendario:
    async def test_abrir_rango_y_omitir_existentes(self, esc):
        creados, omitidos = await esc.abrir(desde=DIA_2, hasta=date(2026, 11, 12))
        assert creados == [date(2026, 11, 12)] and omitidos == [DIA_2]

    async def test_abrir_solo_algunos_dias_de_la_semana(self):
        e = Escenario()
        await e.publicar_servicio()
        creados, _ = await AbrirRangoCalendario(e.ctx)(
            e.prestador_usuario_id, e.servicio_id, date(2026, 11, 2), date(2026, 11, 8), 5, dias_semana={6, 7}
        )
        assert creados == [date(2026, 11, 7), date(2026, 11, 8)]  # sábado y domingo

    async def test_otro_prestador_no_ve_el_servicio(self, esc):
        with pytest.raises(NoEncontrado):
            await AbrirRangoCalendario(esc.ctx)(uuid4(), esc.servicio_id, DIA_1, DIA_1, 5)

    async def test_el_perfil_no_sirve_para_autorizar(self, esc):
        with pytest.raises(NoEncontrado):
            await ConsultarCalendario(esc.ctx)(esc.prestador_id, esc.servicio_id, DIA_1, DIA_2)

    async def test_servicio_desconocido(self, esc):
        with pytest.raises(NoEncontrado):
            await AbrirRangoCalendario(esc.ctx)(esc.prestador_usuario_id, uuid4(), DIA_1, DIA_1, 5)

    async def test_servicio_inactivo_no_admite_cambios(self, esc):
        await esc.publicar_servicio(version=2, activo=False)
        with pytest.raises(NoDisponible):
            await esc.abrir(desde=date(2026, 11, 20), hasta=date(2026, 11, 20))

    async def test_respeta_el_aforo_de_servicio_ref(self, esc):
        with pytest.raises(SuperaAforo):
            await esc.abrir(cupos=21, desde=date(2026, 11, 20), hasta=date(2026, 11, 20))

    async def test_no_abre_dias_pasados(self, esc):
        with pytest.raises(Validacion):
            await esc.abrir(desde=date(2026, 10, 31), hasta=DIA_1)

    async def test_guardar_dia_crea_edita_y_controla_version(self, esc):
        guardar = GuardarDiaCalendario(esc.ctx)
        dia, creado = await guardar(esc.prestador_usuario_id, esc.servicio_id, date(2026, 11, 20), 6, None, None)
        assert creado and dia.version == 1
        with pytest.raises(DiaExistente):
            await guardar(esc.prestador_usuario_id, esc.servicio_id, date(2026, 11, 20), 8, None, None)
        dia, creado = await guardar(esc.prestador_usuario_id, esc.servicio_id, date(2026, 11, 20), 8, Decimal("60000"), 1)
        assert not creado and (dia.cupos_totales, dia.version) == (8, 2)
        with pytest.raises(VersionDistinta):
            await guardar(esc.prestador_usuario_id, esc.servicio_id, date(2026, 11, 20), 9, None, 1)

    async def test_no_baja_de_lo_reservado(self, esc):
        await esc.solicitar(personas=6)
        with pytest.raises(CuposComprometidos):
            await GuardarDiaCalendario(esc.ctx)(esc.prestador_usuario_id, esc.servicio_id, DIA_1, 5, None, 1)


# ---------- Solicitar (UC11) ----------

class TestSolicitar:
    async def test_descuenta_cupos_y_publica_despues_del_commit(self, esc):
        r = await esc.solicitar(personas=3)
        assert r.estado is EstadoReserva.SOLICITADA
        assert (r.prestador_id, r.prestador_usuario_id) == (esc.prestador_id, esc.prestador_usuario_id)
        assert esc.cupos() == 7
        assert esc.publicador.tipos() == ["reserva.solicitada", "auditoria.registrada", "disponibilidad.actualizada"]
        sobre = esc.publicador.publicados[0]
        assert sobre["producer"] == "booking-service"
        assert sobre["payload"]["prestador_id"] == str(esc.prestador_id)

    async def test_cupos_insuficientes_no_cambia_nada(self, esc):
        with pytest.raises(CuposInsuficientes):
            await esc.solicitar(personas=11)
        assert esc.cupos() == 10 and not esc.almacen.reservas and not esc.publicador.publicados

    async def test_una_sola_reserva_activa_por_servicio_y_fecha(self, esc):
        await esc.solicitar()
        with pytest.raises(ReservaDuplicada):
            await esc.solicitar()

    async def test_dia_no_abierto(self, esc):
        with pytest.raises(NoDisponible):
            await esc.solicitar(fecha=date(2026, 11, 25))

    async def test_servicio_desconocido(self, esc):
        with pytest.raises(NoEncontrado):
            await SolicitarReserva(esc.ctx)(esc.turista_id, uuid4(), DIA_1, 1)

    async def test_servicio_inactivo(self, esc):
        await esc.publicar_servicio(version=2, activo=False)
        with pytest.raises(NoDisponible):
            await esc.solicitar()

    async def test_cincuenta_turistas_por_el_ultimo_cupo(self, esc):
        await GuardarDiaCalendario(esc.ctx)(esc.prestador_usuario_id, esc.servicio_id, DIA_1, 1, None, 1)
        resultados = await asyncio.gather(
            *(esc.solicitar(personas=1, turista=uuid4()) for _ in range(50)), return_exceptions=True
        )
        exitos = [r for r in resultados if not isinstance(r, Exception)]
        fallos = [r for r in resultados if isinstance(r, CuposInsuficientes)]
        assert (len(exitos), len(fallos), esc.cupos()) == (1, 49, 0)


# ---------- Modificar (UC12) ----------

class TestModificar:
    async def test_cambia_de_fecha_y_mueve_los_cupos(self, esc):
        r = await esc.solicitar(personas=2)
        esc.publicador.publicados.clear()
        r = await ModificarReserva(esc.ctx)(esc.turista_id, r.id, r.version, fecha_reserva=DIA_2, numero_personas=4)
        assert (r.fecha_reserva, esc.cupos(DIA_1), esc.cupos(DIA_2)) == (DIA_2, 10, 6)
        assert "reserva.modificada" in esc.publicador.tipos()
        # Un evento por cada día tocado: se liberó el 10 y se descontó en el 11.
        assert {(d["fecha"], d["cupos_disponibles"]) for d in esc.dias_publicados()} == {
            ("2026-11-10", 10), ("2026-11-11", 6),
        }

    async def test_si_la_nueva_fecha_no_alcanza_no_cambia_nada(self, esc):
        r = await esc.solicitar(personas=2)
        with pytest.raises(CuposInsuficientes):
            await ModificarReserva(esc.ctx)(esc.turista_id, r.id, r.version, fecha_reserva=DIA_2, numero_personas=11)
        assert (esc.cupos(DIA_1), esc.cupos(DIA_2)) == (8, 10)
        assert esc.almacen.reservas[r.id].fecha_reserva == DIA_1

    async def test_version_distinta(self, esc):
        r = await esc.solicitar()
        with pytest.raises(VersionDistinta):
            await ModificarReserva(esc.ctx)(esc.turista_id, r.id, r.version + 1, numero_personas=3)

    async def test_otro_turista_no_la_ve(self, esc):
        r = await esc.solicitar()
        with pytest.raises(NoEncontrado):
            await ModificarReserva(esc.ctx)(uuid4(), r.id, r.version, numero_personas=3)


# ---------- Confirmar, rechazar y cancelar (UC12, UC20) ----------

class TestRespuestaDelPrestador:
    async def test_confirmar_con_el_usuario_del_prestador(self, esc):
        r = await esc.solicitar()
        r = await ConfirmarReserva(esc.ctx)(esc.prestador_usuario_id, r.id)
        assert r.estado is EstadoReserva.CONFIRMADA

    async def test_el_perfil_no_autoriza_a_confirmar(self, esc):
        r = await esc.solicitar()
        with pytest.raises(NoEncontrado):
            await ConfirmarReserva(esc.ctx)(esc.prestador_id, r.id)

    async def test_rechazar_libera_cupos(self, esc):
        r = await esc.solicitar(personas=4)
        await RechazarReserva(esc.ctx)(esc.prestador_usuario_id, r.id, "Sin guía disponible")
        assert esc.cupos() == 10

    async def test_turista_cancela_y_libera(self, esc):
        r = await esc.solicitar(personas=4)
        r = await CancelarReserva(esc.ctx)(Actor.TURISTA, esc.turista_id, r.id)
        assert (r.estado, esc.cupos()) == (EstadoReserva.CANCELADA, 10)

    async def test_prestador_cancela_confirmada_con_motivo(self, esc):
        r = await esc.solicitar()
        await ConfirmarReserva(esc.ctx)(esc.prestador_usuario_id, r.id)
        r = await CancelarReserva(esc.ctx)(Actor.PRESTADOR, esc.prestador_usuario_id, r.id, "Alerta de oleaje")
        assert (r.cancelada_por, esc.cupos()) == (Actor.PRESTADOR, 10)


# ---------- Tareas programadas ----------

class TestTareas:
    async def test_expirar_libera_cupos_y_publica(self, esc):
        await esc.solicitar(personas=3)
        esc.reloj.avanzar(hours=48)
        assert await ExpirarSolicitudes(esc.ctx)() == 1
        [r] = esc.almacen.reservas.values()
        assert (r.estado, esc.cupos()) == (EstadoReserva.RECHAZADA, 10)
        assert "reserva.rechazada" in esc.publicador.tipos()

    async def test_no_expira_antes_del_plazo(self, esc):
        await esc.solicitar()
        esc.reloj.avanzar(hours=47)
        assert await ExpirarSolicitudes(esc.ctx)() == 0

    async def test_finalizar_al_dia_siguiente(self, esc):
        r = await esc.solicitar()
        await ConfirmarReserva(esc.ctx)(esc.prestador_usuario_id, r.id)
        esc.reloj.avanzar(days=10)  # 11 de noviembre
        assert await FinalizarReservas(esc.ctx)() == 1
        assert esc.almacen.reservas[r.id].estado is EstadoReserva.FINALIZADA
        assert "reserva.finalizada" in esc.publicador.tipos()


# ---------- disponibilidad.actualizada (para catalog) ----------

class TestDisponibilidadActualizada:
    async def test_solicitar_publica_el_estado_completo_del_dia(self, esc):
        await esc.solicitar(personas=3)
        [dia] = esc.dias_publicados()
        assert dia == {
            "servicio_id": str(esc.servicio_id), "fecha": "2026-11-10",
            "cupos_totales": 10, "cupos_disponibles": 7, "version": 2,
        }

    async def test_la_version_del_evento_sube_con_cada_cambio_aunque_no_cambie_el_etag(self, esc):
        r = await esc.solicitar(personas=3)
        await RechazarReserva(esc.ctx)(esc.prestador_usuario_id, r.id, "Sin guía disponible")
        versiones = [d["version"] for d in esc.dias_publicados()]
        assert versiones == sorted(versiones) and len(set(versiones)) == 2  # siempre sube
        assert esc.almacen.dias[(esc.servicio_id, DIA_1)].version == 1  # el ETag del prestador no cambió

    async def test_una_solicitud_rechazada_por_cupos_no_publica_nada(self, esc):
        with pytest.raises(CuposInsuficientes):
            await esc.solicitar(personas=11)
        assert esc.dias_publicados() == []

    async def test_abrir_un_rango_publica_un_evento_por_dia_creado(self, esc):
        await esc.abrir(cupos=5, desde=DIA_2, hasta=date(2026, 11, 12))  # el 11 ya existía
        assert [(d["fecha"], d["version"]) for d in esc.dias_publicados()] == [("2026-11-12", 1)]

    async def test_cerrar_el_dia_publica_cupos_totales_en_cero(self, esc):
        await GuardarDiaCalendario(esc.ctx)(esc.prestador_usuario_id, esc.servicio_id, DIA_1, 0, None, 1)
        [dia] = esc.dias_publicados()
        assert (dia["cupos_totales"], dia["cupos_disponibles"]) == (0, 0)

    async def test_expirar_dos_solicitudes_del_mismo_dia_publica_un_solo_evento_final(self, esc):
        await esc.solicitar(personas=2)
        await esc.solicitar(personas=3, turista=uuid4())
        esc.publicador.publicados.clear()
        esc.reloj.avanzar(hours=48)
        assert await ExpirarSolicitudes(esc.ctx)() == 2
        [dia] = esc.dias_publicados()
        assert dia["cupos_disponibles"] == 10

    async def test_confirmar_y_finalizar_no_mueven_cupos_ni_publican_disponibilidad(self, esc):
        r = await esc.solicitar()
        esc.publicador.publicados.clear()
        await ConfirmarReserva(esc.ctx)(esc.prestador_usuario_id, r.id)
        esc.reloj.avanzar(days=10)
        await FinalizarReservas(esc.ctx)()
        assert esc.dias_publicados() == []

    async def test_el_payload_cumple_el_esquema_del_contrato(self, esc):
        await esc.solicitar()
        [dia] = esc.dias_publicados()
        esquema = json.loads(ESQUEMA_DISPONIBILIDAD.read_text(encoding="utf-8"))
        assert set(dia) == set(esquema["properties"]) and set(esquema["required"]) <= set(dia)
        assert 0 <= dia["cupos_disponibles"] <= dia["cupos_totales"] and dia["version"] >= 1


# ---------- Lecturas con y sin bloqueo (paso 5.2a) ----------

class TestBloqueos:
    async def test_ver_una_reserva_no_la_bloquea(self, esc):
        r = await esc.solicitar()
        esc.almacen.bloqueos.clear()
        await ObtenerReserva(esc.ctx)(esc.turista_id, r.id)
        assert esc.almacen.bloqueos == []

    async def test_confirmar_bloquea_la_reserva(self, esc):
        r = await esc.solicitar()
        esc.almacen.bloqueos.clear()
        await ConfirmarReserva(esc.ctx)(esc.prestador_usuario_id, r.id)
        assert esc.almacen.bloqueos == [("reserva", r.id)]

    async def test_cancelar_bloquea_la_reserva_y_su_dia(self, esc):
        r = await esc.solicitar()
        esc.almacen.bloqueos.clear()
        await CancelarReserva(esc.ctx)(Actor.TURISTA, esc.turista_id, r.id)
        assert esc.almacen.bloqueos == [("reserva", r.id), ("dia", (esc.servicio_id, DIA_1))]

    async def test_solicitar_bloquea_el_dia(self, esc):
        esc.almacen.bloqueos.clear()
        await esc.solicitar()
        assert esc.almacen.bloqueos == [("dia", (esc.servicio_id, DIA_1))]

    async def test_consultar_disponibilidad_y_listar_no_bloquean(self, esc):
        await esc.solicitar()
        esc.almacen.bloqueos.clear()
        await ConsultarDisponibilidad(esc.ctx)(esc.servicio_id, DIA_1, DIA_2)
        await ListarReservas(esc.ctx)(FiltroReservas(turista_id=esc.turista_id), 1, 20)
        assert esc.almacen.bloqueos == []

    async def test_modificar_bloquea_los_dias_en_orden_de_fecha(self, esc):
        r = await esc.solicitar(fecha=DIA_2)
        esc.almacen.bloqueos.clear()
        await ModificarReserva(esc.ctx)(esc.turista_id, r.id, r.version, fecha_reserva=DIA_1)
        dias = [clave[1] for tipo, clave in esc.almacen.bloqueos if tipo == "dia"]
        assert dias == [DIA_1, DIA_2]  # ascendente, aunque la reserva pase del 11 al 10


# ---------- Consultas ----------

class TestConsultas:
    async def test_disponibilidad_de_servicio_inactivo_es_vacia(self, esc):
        await esc.publicar_servicio(version=2, activo=False)
        assert await ConsultarDisponibilidad(esc.ctx)(esc.servicio_id, DIA_1, DIA_2) == []

    async def test_historial_y_panel(self, esc):
        r = await esc.solicitar()
        mias, total = await ListarReservas(esc.ctx)(FiltroReservas(turista_id=esc.turista_id), 1, 20)
        panel, _ = await ListarReservas(esc.ctx)(
            FiltroReservas(prestador_usuario_id=esc.prestador_usuario_id, estado=EstadoReserva.SOLICITADA), 1, 20
        )
        assert [x.id for x in mias] == [x.id for x in panel] == [r.id] and total == 1

    async def test_un_tercero_no_ve_la_reserva(self, esc):
        r = await esc.solicitar()
        assert (await ObtenerReserva(esc.ctx)(esc.prestador_usuario_id, r.id)).id == r.id
        with pytest.raises(NoEncontrado):
            await ObtenerReserva(esc.ctx)(uuid4(), r.id)
