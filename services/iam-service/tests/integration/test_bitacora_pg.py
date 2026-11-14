"""UC33 contra PostgreSQL: filtros, rango de fechas, orden y paginación (C-43).

La base de desarrollo ya tiene filas en la bitácora (y no se pueden borrar): cada prueba usa
un `servicio_origen` propio para ver solo las suyas.
"""

import uuid
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.use_cases.consultar_bitacora import ConsultarBitacora
from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from app.domain.value_objects.evento_auditoria import EventoAuditoria
from app.domain.value_objects.filtro_bitacora import FiltroBitacora
from app.infrastructure.observabilidad.contexto_correlacion import fijar_correlation_id
from app.infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.db

Sesiones = async_sessionmaker[AsyncSession]
BASE = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)


def evento(servicio: str, horas: int, **cambios: object) -> EventoAuditoria:
    valores: dict[str, object] = {
        "event_id": uuid.uuid4(),
        "servicio_origen": servicio,
        "ocurrido_en": BASE + timedelta(hours=horas),
        "accion": "RESERVA_CONFIRMADA",
        "resultado": ResultadoAuditoria.EXITO,
        "ip_origen": "10.0.0.7",
        "detalles": {"hora": horas},
        "correlation_id": f"corr-{horas}",
    }
    return EventoAuditoria(**{**valores, **cambios})  # type: ignore[arg-type]


async def guardar(session_factory: Sesiones, *eventos: EventoAuditoria) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        for e in eventos:
            assert await uow.auditoria.registrar_evento(e)
        await uow.commit()


async def consultar(session_factory: Sesiones, **filtro: object) -> list[int]:
    """Horas (`detalles.hora`) de las filas devueltas, en el orden en que llegan.

    Lee con el repositorio: estas pruebas son del SQL, y así no agregan filas AUDIT_VIEW.
    """
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        pagina = await uow.auditoria.listar(FiltroBitacora(**filtro))  # type: ignore[arg-type]
    return [e.detalles["hora"] for e in pagina.items]


@pytest.fixture
def servicio() -> str:
    return f"prueba-{uuid.uuid4().hex[:8]}"


async def test_orden_por_fecha_descendente_y_paginacion(
    session_factory: Sesiones, servicio: str
) -> None:
    # Se insertan desordenados: el orden lo da `fecha` (el momento del hecho, C-39).
    await guardar(session_factory, *(evento(servicio, h) for h in (2, 0, 4, 1, 3)))

    assert await consultar(session_factory, servicio_origen=servicio) == [4, 3, 2, 1, 0]
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        pagina = await uow.auditoria.listar(
            FiltroBitacora(servicio_origen=servicio, pagina=2, tamano=2)
        )
    assert ([e.detalles["hora"] for e in pagina.items], pagina.total) == ([2, 1], 5)
    assert await consultar(session_factory, servicio_origen=servicio, pagina=4, tamano=2) == []


async def test_rango_semiabierto(session_factory: Sesiones, servicio: str) -> None:
    await guardar(session_factory, *(evento(servicio, h) for h in range(4)))

    horas = await consultar(
        session_factory,
        servicio_origen=servicio,
        desde=BASE + timedelta(hours=1),
        hasta=BASE + timedelta(hours=3),
    )

    assert horas == [2, 1]  # desde incluido, hasta excluido
    # Mismo instante expresado en hora de Colombia (UTC-5): se compara el instante, no el texto.
    colombia = BASE.astimezone(timezone(timedelta(hours=-5)))
    assert await consultar(session_factory, servicio_origen=servicio, hasta=colombia) == []
    assert await consultar(session_factory, servicio_origen=servicio, desde=colombia) == [
        3,
        2,
        1,
        0,
    ]


async def test_filtros_de_accion_resultado_y_usuario(
    session_factory: Sesiones, servicio: str
) -> None:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        u = await uow.usuarios.add(
            Usuario(
                email=f"bitacora.{servicio}@example.com",
                password_hash="$argon2id$fake",
                nombre_completo="Prueba Bitácora",
                rol=Rol.TURISTA,
                habeas_data_aceptado=True,
                habeas_data_aceptado_en=datetime.now(UTC),
            )
        )
        await uow.commit()
    await guardar(
        session_factory,
        evento(servicio, 0, accion="ACCESS_DENIED", resultado=ResultadoAuditoria.DENEGADO),
        evento(
            servicio,
            1,
            accion="ACCESS_DENIED",
            resultado=ResultadoAuditoria.DENEGADO,
            usuario_id=u.id,
        ),
        evento(servicio, 2, accion="EXPORT", usuario_id=u.id),
        evento(servicio, 3, resultado=ResultadoAuditoria.ERROR),
    )

    assert await consultar(session_factory, servicio_origen=servicio, accion="ACCESS_DENIED") == [
        1,
        0,
    ]
    assert await consultar(
        session_factory, servicio_origen=servicio, resultado=ResultadoAuditoria.ERROR
    ) == [3]
    assert await consultar(session_factory, usuario_id=u.id) == [2, 1]
    assert await consultar(
        session_factory, usuario_id=u.id, accion="EXPORT", resultado=ResultadoAuditoria.EXITO
    ) == [2]
    # `accion` es exacta: no es una búsqueda por prefijo.
    assert await consultar(session_factory, servicio_origen=servicio, accion="ACCESS") == []


async def test_devuelve_las_columnas_tal_como_se_guardaron(
    session_factory: Sesiones, servicio: str
) -> None:
    recibido = evento(servicio, 0, ip_origen="2001:db8::1", correlation_id="corr-uc33")
    await guardar(session_factory, recibido)

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        [e] = (await uow.auditoria.listar(FiltroBitacora(servicio_origen=servicio))).items

    assert e.fecha == recibido.ocurrido_en
    assert (e.accion, e.resultado, e.servicio_origen) == (
        "RESERVA_CONFIRMADA",
        ResultadoAuditoria.EXITO,
        servicio,
    )
    assert (e.ip_origen, e.correlation_id, e.event_id) == (
        "2001:db8::1",
        "corr-uc33",
        recibido.event_id,
    )
    assert e.detalles == {"hora": 0}


async def test_incluye_las_filas_propias_del_iam(session_factory: Sesiones) -> None:
    accion = f"PRUEBA_{uuid.uuid4().hex[:8].upper()}"
    fijar_correlation_id("corr-propia")
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        await uow.auditoria.registrar(
            accion=accion,
            resultado=ResultadoAuditoria.DENEGADO,
            usuario_id=None,
            ip_origen="190.24.10.5",
            detalles={"motivo": "sin_token"},
        )
        await uow.commit()

    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        [e] = (await uow.auditoria.listar(FiltroBitacora(accion=accion))).items

    assert (e.servicio_origen, e.event_id, e.correlation_id) == ("iam-service", None, "corr-propia")
    assert e.ip_origen == "190.24.10.5"


async def sembrar_admin(session_factory: Sesiones) -> uuid.UUID:
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        admin = await uow.usuarios.add(
            Usuario(
                email=f"bitacora.admin.{uuid.uuid4().hex[:8]}@example.com",
                password_hash="$argon2id$fake",
                nombre_completo="Admin Bitácora",
                rol=Rol.ADMIN,
                habeas_data_aceptado=True,
                habeas_data_aceptado_en=datetime.now(UTC),
            )
        )
        await uow.commit()
    assert admin.id is not None
    return admin.id


async def test_cada_consulta_deja_su_fila_audit_view(
    session_factory: Sesiones, servicio: str
) -> None:
    admin_id = await sembrar_admin(session_factory)
    await guardar(session_factory, evento(servicio, 0))
    consultar_bitacora = ConsultarBitacora(SqlAlchemyUnitOfWork(session_factory))
    fijar_correlation_id("corr-audit-view")

    pagina = await consultar_bitacora.execute(
        FiltroBitacora(servicio_origen=servicio, desde=BASE, tamano=5),
        admin_id=admin_id,
        ip_origen="190.24.10.5",
    )

    assert [e.detalles["hora"] for e in pagina.items] == [0]
    async with SqlAlchemyUnitOfWork(session_factory) as uow:
        [fila] = (
            await uow.auditoria.listar(FiltroBitacora(usuario_id=admin_id, accion="AUDIT_VIEW"))
        ).items
    assert (fila.resultado, fila.servicio_origen, fila.ip_origen, fila.correlation_id) == (
        ResultadoAuditoria.EXITO,
        "iam-service",
        "190.24.10.5",
        "corr-audit-view",
    )
    assert fila.detalles == {
        "filtros": {"servicio_origen": servicio, "desde": BASE.isoformat()},
        "pagina": 1,
        "tamano": 5,
    }


async def test_la_fila_se_escribe_despues_de_leer(session_factory: Sesiones) -> None:
    # La consulta no se ve a sí misma: su AUDIT_VIEW aparece recién en la siguiente.
    admin_id = await sembrar_admin(session_factory)
    consultar_bitacora = ConsultarBitacora(SqlAlchemyUnitOfWork(session_factory))
    filtro = FiltroBitacora(usuario_id=admin_id, accion="AUDIT_VIEW")

    primera = await consultar_bitacora.execute(filtro, admin_id=admin_id, ip_origen=None)
    segunda = await consultar_bitacora.execute(filtro, admin_id=admin_id, ip_origen=None)

    assert (primera.total, segunda.total) == (0, 1)
