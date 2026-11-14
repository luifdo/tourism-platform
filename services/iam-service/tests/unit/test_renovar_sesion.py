import logging
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.application.use_cases.registrar_acceso_denegado import RegistrarAccesoDenegado
from app.application.use_cases.renovar_sesion import RenovarSesion
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import ServicioNoDisponibleError, TokenInvalidoError
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from app.infrastructure.security.jwt_token_service import JwtTokenService
from tests.fakes import AHORA, FakeSesionesRenovacion, FakeUnitOfWork

IP = "190.0.0.1"
FAMILIA = "familia-1"


def sembrar(uow: FakeUnitOfWork, **campos: object) -> Usuario:
    return uow.usuarios.sembrar(
        replace(
            Usuario(
                email="maria.perez@example.com",
                password_hash="x",
                nombre_completo="María Pérez",
                rol=Rol.PRESTADOR,
                habeas_data_aceptado=True,
                habeas_data_aceptado_en=AHORA,
            ),
            **campos,  # type: ignore[arg-type]
        )
    )


def caso(
    uow: FakeUnitOfWork, tokens: JwtTokenService, sesiones: FakeSesionesRenovacion
) -> RenovarSesion:
    return RenovarSesion(
        uow=uow, tokens=tokens, sesiones=sesiones, registrar=RegistrarAccesoDenegado(uow)
    )


async def sesion_de(sesiones: FakeSesionesRenovacion, usuario: Usuario) -> str:
    assert usuario.id is not None
    creada = await sesiones.crear(usuario.id, FAMILIA, datetime.now(UTC))
    return creada.refresh_token


async def test_ok_entrega_tokens_nuevos_con_el_mismo_sid_y_sin_bitacora(
    token_service: JwtTokenService,
) -> None:
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()
    usuario = sembrar(uow)
    token = await sesion_de(sesiones, usuario)

    renovada = await caso(uow, token_service, sesiones).execute(token, IP)

    assert renovada.usuario.id == usuario.id
    assert renovada.rotacion.nuevo_token != token
    claims = token_service.verificar(renovada.token.access_token)
    assert (claims.sid, claims.sub, claims.rol) == (FAMILIA, str(usuario.id), Rol.PRESTADOR)
    assert uow.auditoria.registros == []


async def test_el_token_lleva_el_rol_vigente(token_service: JwtTokenService) -> None:
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()
    usuario = sembrar(uow)
    token = await sesion_de(sesiones, usuario)
    uow.usuarios.por_email[usuario.email] = replace(usuario, rol=Rol.ENTIDAD)

    renovada = await caso(uow, token_service, sesiones).execute(token, IP)

    assert token_service.verificar(renovada.token.access_token).rol is Rol.ENTIDAD


async def test_invalido(token_service: JwtTokenService) -> None:
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()

    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(uow, token_service, sesiones).execute("no-existe", IP)

    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("invalido", None)
    assert uow.auditoria.registros == []  # lo audita el router, como en el logout


async def test_familia_revocada(token_service: JwtTokenService) -> None:
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()
    usuario = sembrar(uow)
    token = await sesion_de(sesiones, usuario)
    await sesiones.revocar_familia(FAMILIA)

    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(uow, token_service, sesiones).execute(token, IP)

    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("revocado", usuario.id)


async def test_reutilizado_deja_su_fila_y_revoca_la_familia(
    token_service: JwtTokenService,
) -> None:
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()
    usuario = sembrar(uow)
    token = await sesion_de(sesiones, usuario)
    renovar = caso(uow, token_service, sesiones)
    renovada = await renovar.execute(token, IP)

    with pytest.raises(TokenInvalidoError) as exc_info:
        await renovar.execute(token, IP)

    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("reutilizado", usuario.id)
    assert sesiones.revocada(FAMILIA) is True
    assert uow.commits == 1
    [registro] = uow.auditoria.registros
    assert (registro.accion, registro.resultado) == (
        "REFRESH_REUTILIZADO",
        ResultadoAuditoria.DENEGADO,
    )
    assert (registro.usuario_id, registro.ip_origen) == (usuario.id, IP)
    assert registro.detalles == {"familia": FAMILIA}

    # El token vigente de la familia también queda inservible, sin otra fila de robo.
    with pytest.raises(TokenInvalidoError) as exc_info:
        await renovar.execute(renovada.rotacion.nuevo_token, IP)
    assert exc_info.value.motivo == "revocado"
    assert len(uow.auditoria.registros) == 1


async def test_reutilizado_con_la_bitacora_caida_sigue_siendo_401(
    token_service: JwtTokenService, caplog: pytest.LogCaptureFixture
) -> None:
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()
    usuario = sembrar(uow)
    token = await sesion_de(sesiones, usuario)
    renovar = caso(uow, token_service, sesiones)
    await renovar.execute(token, IP)
    uow.caida = True

    with caplog.at_level(logging.ERROR), pytest.raises(TokenInvalidoError) as exc_info:
        await renovar.execute(token, IP)

    assert exc_info.value.motivo == "reutilizado"
    assert "No se pudo registrar REFRESH_REUTILIZADO" in caplog.text
    assert token not in caplog.text


@pytest.mark.parametrize(
    "campos",
    [{"activo": False}, {"activo": False, "datos_suprimidos_en": AHORA}],
    ids=["inactiva", "suprimida"],
)
async def test_cuenta_inactiva_o_suprimida_pierde_la_sesion(
    token_service: JwtTokenService, campos: dict[str, object]
) -> None:
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()
    usuario = sembrar(uow, **campos)
    token = await sesion_de(sesiones, usuario)

    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(uow, token_service, sesiones).execute(token, IP)

    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("revocado", usuario.id)
    assert sesiones.revocada(FAMILIA) is True


async def test_cuenta_inexistente_no_atribuye_el_rechazo(token_service: JwtTokenService) -> None:
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()
    usuario = sembrar(uow)
    token = await sesion_de(sesiones, usuario)
    del uow.usuarios.por_email[usuario.email]

    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(uow, token_service, sesiones).execute(token, IP)

    # La bitácora tiene una llave foránea: un usuario que no existe rompería su fila.
    assert (exc_info.value.motivo, exc_info.value.usuario_id) == ("revocado", None)
    assert sesiones.revocada(FAMILIA) is True


async def test_postgres_caido_tras_rotar_responde_503_y_revoca_la_familia(
    token_service: JwtTokenService, caplog: pytest.LogCaptureFixture
) -> None:
    # Si no se revocara, el reintento con el token viejo dejaría una fila de robo falsa.
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()
    usuario = sembrar(uow)
    token = await sesion_de(sesiones, usuario)
    uow.caida = True

    with caplog.at_level(logging.ERROR), pytest.raises(ServicioNoDisponibleError):
        await caso(uow, token_service, sesiones).execute(token, IP)

    assert sesiones.revocada(FAMILIA) is True
    assert token not in caplog.text
    uow.caida = False
    with pytest.raises(TokenInvalidoError) as exc_info:
        await caso(uow, token_service, sesiones).execute(token, IP)
    assert exc_info.value.motivo == "revocado"
    assert uow.auditoria.registros == []


async def test_postgres_y_valkey_caidos_tras_rotar_siguen_siendo_503(
    token_service: JwtTokenService,
) -> None:
    uow, sesiones = FakeUnitOfWork(), FakeSesionesRenovacion()
    usuario = sembrar(uow)
    token = await sesion_de(sesiones, usuario)
    uow.caida = True
    sesiones.caida_al_revocar = True

    with pytest.raises(ServicioNoDisponibleError):
        await caso(uow, token_service, sesiones).execute(token, IP)


async def test_valkey_caido_falla_cerrado(token_service: JwtTokenService) -> None:
    uow = FakeUnitOfWork()

    with pytest.raises(ServicioNoDisponibleError):
        await caso(uow, token_service, FakeSesionesRenovacion(caida=True)).execute("t", IP)

    assert uow.auditoria.registros == []
