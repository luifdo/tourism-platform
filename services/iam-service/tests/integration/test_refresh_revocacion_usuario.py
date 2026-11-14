"""C-21: cada camino que llama a revocar_usuario deja inservible un refresh emitido antes.

Corre los casos de uso reales, sin cambios, contra los adaptadores de Valkey reales. Solo la base
y el almacén son dobles: aquí lo que se prueba es la marca revocado-desde y el script Lua.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.application.use_cases.cambiar_contrasena import (
    CambiarContrasena,
    CambiarContrasenaCommand,
)
from app.application.use_cases.cambiar_estado_usuario import (
    CambiarEstadoCommand,
    CambiarEstadoUsuario,
)
from app.application.use_cases.cambiar_rol_usuario import CambiarRolCommand, CambiarRolUsuario
from app.application.use_cases.restablecer_contrasena import (
    RestablecerContrasena,
    RestablecerContrasenaCommand,
)
from app.application.use_cases.suprimir_datos import SuprimirDatos, SuprimirDatosCommand
from app.config import get_settings
from app.domain.entities.usuario import Usuario
from app.domain.value_objects.enums import Rol
from app.domain.value_objects.sesion import RotacionOk, RotacionRevocada
from app.infrastructure.cache.valkey_revocacion import (
    ValkeyRevocacionTokens,
    build_valkey_client,
)
from app.infrastructure.cache.valkey_sesiones_renovacion import ValkeySesionesRenovacion
from tests.fakes import (
    AHORA,
    FakeAlmacenDocumentos,
    FakePasswordHasher,
    FakeTokensRecuperacion,
    FakeUnitOfWork,
)

pytestmark = pytest.mark.valkey

TTL = 300
CLAVE = "Actual12345"
NUEVA = "Nueva123456"
TOKEN_ENLACE = "enlace-de-recuperacion"


def ahora() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
async def valkey() -> AsyncIterator[Redis]:
    client = build_valkey_client(get_settings().valkey_url)
    try:
        await asyncio.wait_for(client.ping(), timeout=3)
    except (RedisError, OSError, TimeoutError) as exc:
        await client.aclose()
        pytest.skip(f"Valkey no responde: {type(exc).__name__}")
    try:
        yield client
    finally:
        await client.aclose()


class Entorno:
    def __init__(self, valkey: Redis) -> None:
        self.uow = FakeUnitOfWork()
        self.hasher = FakePasswordHasher()
        self.revocacion = ValkeyRevocacionTokens(valkey, ahora, ttl_revocado_desde=TTL)
        self.sesiones = ValkeySesionesRenovacion(
            valkey, ahora, ttl_refresh=TTL, ttl_sesion_revocada=TTL
        )
        self.usuario = self.uow.usuarios.sembrar(
            Usuario(
                email=f"refresh.{uuid.uuid4().hex[:8]}@example.com",
                password_hash=self.hasher.hash(CLAVE),
                nombre_completo="Persona Real",
                rol=Rol.TURISTA,
                habeas_data_aceptado=True,
                habeas_data_aceptado_en=AHORA,
            )
        )
        assert self.usuario.id is not None
        self.id = self.usuario.id

    async def sesion(self, emitido_en: datetime) -> str:
        creada = await self.sesiones.crear(self.id, str(uuid.uuid4()), emitido_en)
        return creada.refresh_token


@pytest.fixture
def entorno(valkey: Redis) -> Entorno:
    return Entorno(valkey)


async def cambiar_rol(e: Entorno) -> None:
    await CambiarRolUsuario(e.uow, e.revocacion, ahora).execute(
        CambiarRolCommand(
            admin_id=uuid.uuid4(),
            usuario_id=e.id,
            motivo=None,
            ip_origen=None,
            rol=Rol.ENTIDAD,
        )
    )


async def desactivar(e: Entorno) -> None:
    await CambiarEstadoUsuario(e.uow, e.revocacion, ahora).execute(
        CambiarEstadoCommand(
            admin_id=uuid.uuid4(),
            usuario_id=e.id,
            motivo=None,
            ip_origen=None,
            activo=False,
        )
    )


async def cambiar_contrasena(e: Entorno) -> None:
    await CambiarContrasena(e.uow, e.hasher, e.revocacion, ahora).execute(
        CambiarContrasenaCommand(
            usuario_id=e.id, password_actual=CLAVE, password_nueva=NUEVA, ip_origen=None
        )
    )


async def restablecer(e: Entorno) -> None:
    tokens = FakeTokensRecuperacion()
    await tokens.guardar(TOKEN_ENLACE, e.id)
    await RestablecerContrasena(e.uow, tokens, e.hasher, e.revocacion, ahora).execute(
        RestablecerContrasenaCommand(token=TOKEN_ENLACE, password=NUEVA, ip_origen=None)
    )


async def suprimir(e: Entorno) -> None:
    await SuprimirDatos(e.uow, e.hasher, FakeAlmacenDocumentos(), e.revocacion, ahora).execute(
        SuprimirDatosCommand(usuario_id=e.id, password=CLAVE, ip_origen=None)
    )


@pytest.mark.parametrize(
    "camino",
    [cambiar_rol, desactivar, cambiar_contrasena, restablecer, suprimir],
    ids=["rol", "desactivar", "cambiar_contrasena", "restablecer", "suprimir"],
)
async def test_el_refresh_emitido_antes_queda_inservible(
    entorno: Entorno, camino: Callable[[Entorno], Awaitable[None]]
) -> None:
    antes = await entorno.sesion(ahora())
    # Posterior a las dos marcas: si esta sesión no sobreviviera, la prueba no distinguiría una
    # revocación por usuario de un script que rechaza todo.
    despues = await entorno.sesion(ahora() + timedelta(seconds=30))

    await camino(entorno)

    assert isinstance(await entorno.sesiones.rotar(antes), RotacionRevocada)
    assert isinstance(await entorno.sesiones.rotar(despues), RotacionOk)


async def test_la_sesion_de_otro_usuario_no_se_ve_afectada(entorno: Entorno) -> None:
    otra = await entorno.sesiones.crear(uuid.uuid4(), str(uuid.uuid4()), ahora())

    await cambiar_rol(entorno)

    assert isinstance(await entorno.sesiones.rotar(otra.refresh_token), RotacionOk)


async def test_sin_efecto_no_revoca(entorno: Entorno) -> None:
    # Mismo rol que ya tenía: UC27 no audita ni revoca.
    token = await entorno.sesion(ahora())

    await CambiarRolUsuario(entorno.uow, entorno.revocacion, ahora).execute(
        CambiarRolCommand(
            admin_id=uuid.uuid4(),
            usuario_id=entorno.id,
            motivo=None,
            ip_origen=None,
            rol=Rol.TURISTA,
        )
    )

    assert isinstance(await entorno.sesiones.rotar(token), RotacionOk)
