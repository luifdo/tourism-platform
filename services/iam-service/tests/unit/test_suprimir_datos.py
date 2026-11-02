"""SuprimirDatos y los eventos del outbox (C-27, C-48, C-63)."""

from dataclasses import replace

import pytest

from app.application.use_cases.suprimir_datos import SuprimirDatos, SuprimirDatosCommand
from app.domain.entities.usuario import Usuario
from app.domain.events.prestador_suspendido import PrestadorSuspendido
from app.domain.events.usuario_suprimido import UsuarioSuprimido
from app.domain.value_objects.enums import Rol
from tests.fakes import (
    AHORA,
    FakeAlmacenDocumentos,
    FakePasswordHasher,
    FakeRevocacion,
    FakeUnitOfWork,
    reloj_fijo,
)

CLAVE = "Actual12345"


def sembrar(uow: FakeUnitOfWork, rol: Rol, email: str, activo: bool = True) -> Usuario:
    return uow.usuarios.sembrar(
        Usuario(
            email=email,
            password_hash=FakePasswordHasher().hash(CLAVE),
            nombre_completo="Persona Real",
            rol=rol,
            activo=activo,
            habeas_data_aceptado=True,
            habeas_data_aceptado_en=AHORA,
        )
    )


async def suprimir(uow: FakeUnitOfWork, usuario: Usuario) -> None:
    assert usuario.id is not None
    await SuprimirDatos(
        uow=uow,
        hasher=FakePasswordHasher(),
        almacen=FakeAlmacenDocumentos(),
        revocacion=FakeRevocacion(),
        reloj=reloj_fijo,
    ).execute(SuprimirDatosCommand(usuario_id=usuario.id, password=CLAVE, ip_origen=None))


@pytest.mark.parametrize("rol", [Rol.TURISTA, Rol.ENTIDAD, Rol.ADMIN])
async def test_sin_perfil_publico_solo_publica_usuario_suprimido(rol: Rol) -> None:
    uow = FakeUnitOfWork()
    # Otro Admin activo: si no, la plataforma se quedaría sin ninguno (C-29).
    sembrar(uow, Rol.ADMIN, "otro.admin@example.com")
    u = sembrar(uow, rol, "persona@example.com")

    await suprimir(uow, u)

    assert uow.outbox.eventos == [UsuarioSuprimido(ocurrido_en=AHORA, usuario_id=u.id, rol=rol)]  # type: ignore[arg-type]
    assert uow.commits == 1


async def test_prestador_visible_publica_primero_la_suspension_con_el_mismo_instante() -> None:
    uow = FakeUnitOfWork()
    u = sembrar(uow, Rol.PRESTADOR, "prestador@example.com")

    await suprimir(uow, u)

    suspension, supresion = uow.outbox.eventos
    assert isinstance(suspension, PrestadorSuspendido)
    assert supresion == UsuarioSuprimido(ocurrido_en=AHORA, usuario_id=u.id, rol=Rol.PRESTADOR)  # type: ignore[arg-type]
    # Mismo instante: catalog descarta solo lo anterior (<) al último evento que aplicó.
    assert suspension.ocurrido_en == supresion.ocurrido_en == AHORA


async def test_prestador_ya_inactivo_solo_publica_usuario_suprimido() -> None:
    uow = FakeUnitOfWork()
    u = sembrar(uow, Rol.PRESTADOR, "prestador@example.com", activo=False)

    await suprimir(uow, u)

    assert [type(e) for e in uow.outbox.eventos] == [UsuarioSuprimido]


async def test_payload_con_el_rol_que_tenia() -> None:
    uow = FakeUnitOfWork()
    u = sembrar(uow, Rol.PRESTADOR, "prestador@example.com")
    uow.usuarios.por_email[u.email] = replace(u, rol=Rol.ENTIDAD)

    await suprimir(uow, u)

    [evento] = uow.outbox.eventos
    assert evento.payload() == {"usuario_id": str(u.id), "rol": "Entidad"}


async def test_contrasena_incorrecta_no_publica_nada() -> None:
    uow = FakeUnitOfWork()
    u = sembrar(uow, Rol.TURISTA, "persona@example.com")
    assert u.id is not None

    with pytest.raises(Exception):  # noqa: B017 - el tipo exacto lo prueba test_supresion_api
        await SuprimirDatos(
            uow=uow,
            hasher=FakePasswordHasher(),
            almacen=FakeAlmacenDocumentos(),
            revocacion=FakeRevocacion(),
            reloj=reloj_fijo,
        ).execute(SuprimirDatosCommand(usuario_id=u.id, password="Otra12345", ip_origen=None))

    assert uow.outbox.eventos == []
