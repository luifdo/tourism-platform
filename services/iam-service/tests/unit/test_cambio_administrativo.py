"""UC27: cambio de rol y de estado (C-17, C-21, C-29, C-41, C-42)."""

import logging
import uuid
from dataclasses import replace
from datetime import timedelta

import pytest

from app.application.use_cases.cambiar_estado_usuario import (
    CambiarEstadoCommand,
    CambiarEstadoUsuario,
)
from app.application.use_cases.cambiar_rol_usuario import CambiarRolCommand, CambiarRolUsuario
from app.domain.entities.usuario import Usuario
from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.domain.exceptions import (
    AutogestionNoPermitidaError,
    ServicioNoDisponibleError,
    UltimoAdminError,
    UsuarioNoEncontradoError,
)
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from tests.fakes import AHORA, FakeRevocacion, FakeUnitOfWork

IP = "190.24.10.5"


class RelojQueAvanza:
    """Cada lectura avanza un segundo: distingue la revocación previa de la posterior."""

    def __init__(self) -> None:
        self.lecturas = 0

    def __call__(self):  # type: ignore[no-untyped-def]
        self.lecturas += 1
        return AHORA + timedelta(seconds=self.lecturas - 1)


def cuenta(email: str, rol: Rol, activo: bool = True) -> Usuario:
    return Usuario(
        email=email,
        password_hash="x",
        nombre_completo="Persona de Prueba",
        rol=rol,
        activo=activo,
        habeas_data_aceptado=True,
        habeas_data_aceptado_en=AHORA,
    )


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def revocacion() -> FakeRevocacion:
    return FakeRevocacion()


@pytest.fixture
def reloj() -> RelojQueAvanza:
    return RelojQueAvanza()


@pytest.fixture
def admin(uow: FakeUnitOfWork) -> Usuario:
    return uow.usuarios.sembrar(cuenta("admin@example.com", Rol.ADMIN))


@pytest.fixture
def otro_admin(uow: FakeUnitOfWork) -> Usuario:
    return uow.usuarios.sembrar(cuenta("admin2@example.com", Rol.ADMIN))


@pytest.fixture
def prestador(uow: FakeUnitOfWork) -> Usuario:
    return uow.usuarios.sembrar(cuenta("prestador@example.com", Rol.PRESTADOR))


@pytest.fixture
def turista(uow: FakeUnitOfWork) -> Usuario:
    return uow.usuarios.sembrar(cuenta("turista@example.com", Rol.TURISTA))


def rol(
    uow: FakeUnitOfWork, revocacion: FakeRevocacion, reloj: RelojQueAvanza
) -> CambiarRolUsuario:
    return CambiarRolUsuario(uow=uow, revocacion=revocacion, reloj=reloj)


def estado(
    uow: FakeUnitOfWork, revocacion: FakeRevocacion, reloj: RelojQueAvanza
) -> CambiarEstadoUsuario:
    return CambiarEstadoUsuario(uow=uow, revocacion=revocacion, reloj=reloj)


def cmd_rol(
    admin: Usuario, objetivo: Usuario | uuid.UUID, nuevo: Rol, motivo: str | None = None
) -> CambiarRolCommand:
    objetivo_id = objetivo if isinstance(objetivo, uuid.UUID) else objetivo.id
    assert admin.id is not None and objetivo_id is not None
    return CambiarRolCommand(
        admin_id=admin.id, usuario_id=objetivo_id, motivo=motivo, ip_origen=IP, rol=nuevo
    )


def cmd_estado(
    admin: Usuario, objetivo: Usuario, activo: bool, motivo: str | None = None
) -> CambiarEstadoCommand:
    assert admin.id is not None and objetivo.id is not None
    return CambiarEstadoCommand(
        admin_id=admin.id, usuario_id=objetivo.id, motivo=motivo, ip_origen=IP, activo=activo
    )


async def test_cambio_de_rol_audita_revoca_dos_veces_y_confirma(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    turista: Usuario,
) -> None:
    commits_al_revocar: list[int] = []
    revocacion.al_revocar_usuario = lambda: commits_al_revocar.append(uow.commits)

    actualizado = await rol(uow, revocacion, reloj).execute(
        cmd_rol(admin, turista, Rol.ENTIDAD, motivo="  Funcionario de la Alcaldía  ")
    )

    assert actualizado.rol is Rol.ENTIDAD
    assert (await uow.usuarios.find_by_id(turista.id)).rol is Rol.ENTIDAD  # type: ignore[arg-type, union-attr]
    assert uow.commits == 1
    assert uow.usuarios.bloqueos_admins == 1
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == ("ROLE_CHANGE", ResultadoAuditoria.EXITO)
    assert (registro.usuario_id, registro.ip_origen) == (admin.id, IP)
    assert registro.detalles == {
        "usuario_afectado": str(turista.id),
        "antes": {"rol": "Turista"},
        "despues": {"rol": "Entidad"},
        "motivo": "Funcionario de la Alcaldía",
    }
    # Una antes del commit (falla cerrado) y otra después, con un "desde" más nuevo (C-21).
    assert commits_al_revocar == [0, 1]
    [(id1, desde1), (id2, desde2)] = revocacion.revocaciones_usuario
    assert id1 == id2 == turista.id
    assert desde2 > desde1
    assert uow.outbox.eventos == []  # no era Prestador


async def test_prestador_a_otro_rol_publica_suspendido(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    prestador: Usuario,
) -> None:
    await rol(uow, revocacion, reloj).execute(cmd_rol(admin, prestador, Rol.TURISTA, "x"))

    [evento] = uow.outbox.eventos
    assert isinstance(evento, PrestadorSuspendido)
    assert evento.ocurrido_en == AHORA
    assert evento.payload() == {
        "prestador_id": str(prestador.id),
        "usuario_id": str(prestador.id),
        "suspendido_por": str(admin.id),
    }


async def test_hacia_prestador_no_publica(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    turista: Usuario,
) -> None:
    await rol(uow, revocacion, reloj).execute(cmd_rol(admin, turista, Rol.PRESTADOR))

    assert uow.outbox.eventos == []
    assert uow.commits == 1


async def test_desactivar_prestador_publica_suspendido_sin_motivo(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    prestador: Usuario,
) -> None:
    largo = "m" * 600

    actualizado = await estado(uow, revocacion, reloj).execute(
        cmd_estado(admin, prestador, activo=False, motivo=largo)
    )

    assert actualizado.activo is False
    [evento] = uow.outbox.eventos
    assert "motivo" not in evento.payload()  # el texto libre no viaja por el bus (C-41)
    [registro] = uow.auditoria.registros
    assert registro.accion == "USER_STATUS_CHANGE"
    assert registro.detalles["antes"] == {"activo": True}
    assert registro.detalles["despues"] == {"activo": False}
    assert registro.detalles["motivo"] == "m" * 500
    assert len(revocacion.revocaciones_usuario) == 2


async def test_desactivar_prestador_ya_inactivo_por_rol_no_publica_otra_vez(
    uow: FakeUnitOfWork, revocacion: FakeRevocacion, reloj: RelojQueAvanza, admin: Usuario
) -> None:
    inactivo = uow.usuarios.sembrar(cuenta("p2@example.com", Rol.PRESTADOR, activo=False))

    await rol(uow, revocacion, reloj).execute(cmd_rol(admin, inactivo, Rol.TURISTA))

    assert uow.outbox.eventos == []  # ya estaba oculto desde su desactivación


async def test_reactivar_no_revoca_ni_publica(
    uow: FakeUnitOfWork, revocacion: FakeRevocacion, reloj: RelojQueAvanza, admin: Usuario
) -> None:
    inactivo = uow.usuarios.sembrar(cuenta("p3@example.com", Rol.PRESTADOR, activo=False))

    actualizado = await estado(uow, revocacion, reloj).execute(
        cmd_estado(admin, inactivo, activo=True)
    )

    assert actualizado.activo is True
    assert uow.outbox.eventos == []  # C-42: la oferta vuelve con el bloque 5
    assert revocacion.revocaciones_usuario == []
    [registro] = uow.auditoria.registros
    assert registro.detalles["motivo"] is None
    assert uow.commits == 1


@pytest.mark.parametrize(
    "aplicar",
    [
        lambda uow, rev, reloj, admin, u: rol(uow, rev, reloj).execute(
            cmd_rol(admin, u, Rol.TURISTA)
        ),
        lambda uow, rev, reloj, admin, u: estado(uow, rev, reloj).execute(
            cmd_estado(admin, u, activo=True)
        ),
    ],
    ids=["mismo_rol", "mismo_estado"],
)
async def test_sin_efecto_no_audita_revoca_ni_publica(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    turista: Usuario,
    aplicar,  # type: ignore[no-untyped-def]
) -> None:
    resultado = await aplicar(uow, revocacion, reloj, admin, turista)

    assert resultado == turista
    assert uow.commits == 0
    assert uow.auditoria.registros == []
    assert revocacion.revocaciones_usuario == []
    assert uow.outbox.eventos == []


async def test_sin_efecto_sobre_si_mismo_tambien_es_200(
    uow: FakeUnitOfWork, revocacion: FakeRevocacion, reloj: RelojQueAvanza, admin: Usuario
) -> None:
    assert await rol(uow, revocacion, reloj).execute(cmd_rol(admin, admin, Rol.ADMIN)) == admin


async def test_no_puede_cambiar_su_propio_rol(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    otro_admin: Usuario,
) -> None:
    with pytest.raises(AutogestionNoPermitidaError):
        await rol(uow, revocacion, reloj).execute(cmd_rol(admin, admin, Rol.TURISTA))
    assert (uow.commits, uow.auditoria.registros) == (0, [])


async def test_no_puede_desactivarse(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    otro_admin: Usuario,
) -> None:
    with pytest.raises(AutogestionNoPermitidaError):
        await estado(uow, revocacion, reloj).execute(cmd_estado(admin, admin, activo=False))


async def test_ultimo_admin(
    uow: FakeUnitOfWork, revocacion: FakeRevocacion, reloj: RelojQueAvanza, admin: Usuario
) -> None:
    # Solo queda otro Admin activo: el que actúa ya no lo es en la base (p. ej. lo desactivó
    # otro Admin un instante antes) y su token aún no expiró.
    unico = uow.usuarios.sembrar(cuenta("unico@example.com", Rol.ADMIN))
    uow.usuarios.por_email[admin.email] = replace(admin, activo=False)

    with pytest.raises(UltimoAdminError):
        await rol(uow, revocacion, reloj).execute(cmd_rol(admin, unico, Rol.TURISTA))
    with pytest.raises(UltimoAdminError):
        await estado(uow, revocacion, reloj).execute(cmd_estado(admin, unico, activo=False))
    assert uow.commits == 0
    assert revocacion.revocaciones_usuario == []


async def test_con_dos_admins_se_puede_degradar_al_otro(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    otro_admin: Usuario,
) -> None:
    actualizado = await rol(uow, revocacion, reloj).execute(cmd_rol(admin, otro_admin, Rol.ENTIDAD))

    assert actualizado.rol is Rol.ENTIDAD


async def test_usuario_inexistente(
    uow: FakeUnitOfWork, revocacion: FakeRevocacion, reloj: RelojQueAvanza, admin: Usuario
) -> None:
    with pytest.raises(UsuarioNoEncontradoError):
        await rol(uow, revocacion, reloj).execute(cmd_rol(admin, uuid.uuid4(), Rol.TURISTA))


async def test_valkey_caido_antes_del_commit_no_confirma_nada(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    prestador: Usuario,
) -> None:
    revocacion.caida = True

    with pytest.raises(ServicioNoDisponibleError):
        await estado(uow, revocacion, reloj).execute(cmd_estado(admin, prestador, activo=False))

    assert uow.commits == 0
    assert uow.rollbacks == 1


async def test_si_falla_la_segunda_revocacion_solo_queda_en_el_log(
    uow: FakeUnitOfWork,
    revocacion: FakeRevocacion,
    reloj: RelojQueAvanza,
    admin: Usuario,
    turista: Usuario,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def caer_tras_el_commit() -> None:
        revocacion.caida = uow.commits == 1

    revocacion.al_revocar_usuario = caer_tras_el_commit

    with caplog.at_level(logging.ERROR):
        actualizado = await rol(uow, revocacion, reloj).execute(
            cmd_rol(admin, turista, Rol.ENTIDAD)
        )

    assert actualizado.rol is Rol.ENTIDAD
    assert uow.commits == 1
    assert len(revocacion.revocaciones_usuario) == 1
    assert "No se pudo repetir la revocación" in caplog.text
