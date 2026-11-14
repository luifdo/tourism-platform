"""Casos de uso del bloque 6 sin HTTP: lo que por la API no se puede provocar ni observar."""

import logging
import uuid
from dataclasses import replace

import pytest

from app.application.use_cases.cambiar_contrasena import (
    CambiarContrasena,
    CambiarContrasenaCommand,
)
from app.application.use_cases.editar_perfil import EditarPerfil, EditarPerfilCommand
from app.application.use_cases.obtener_perfil import ObtenerPerfil
from app.application.use_cases.restablecer_contrasena import (
    RestablecerContrasena,
    RestablecerContrasenaCommand,
)
from app.application.use_cases.revocacion_doble import RevocacionDoble
from app.application.use_cases.solicitar_recuperacion import (
    SolicitarRecuperacion,
    SolicitarRecuperacionCommand,
)
from app.application.use_cases.subir_documento import SubirDocumento, SubirDocumentoCommand
from app.application.use_cases.suprimir_datos import SuprimirDatos, SuprimirDatosCommand
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import (
    CuentaSuprimidaError,
    PasswordInvalidaError,
    ServicioNoDisponibleError,
    TokenRecuperacionInvalidoError,
    UsuarioNoEncontradoError,
)
from app.domain.value_objects.enums import Rol, TipoDocumento
from tests.fakes import (
    AHORA,
    FakeAlmacenDocumentos,
    FakeEnviadorCorreo,
    FakePasswordHasher,
    FakeRevocacion,
    FakeTokensRecuperacion,
    FakeUnitOfWork,
    reloj_fijo,
)
from tests.unit.test_documentos_dominio import PDF

CLAVE = "Actual12345"
EMAIL = "maria@example.com"


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def hasher() -> FakePasswordHasher:
    return FakePasswordHasher()


@pytest.fixture
def revocacion() -> FakeRevocacion:
    return FakeRevocacion()


@pytest.fixture
def tokens() -> FakeTokensRecuperacion:
    return FakeTokensRecuperacion()


@pytest.fixture
def enviador() -> FakeEnviadorCorreo:
    return FakeEnviadorCorreo()


@pytest.fixture
def almacen() -> FakeAlmacenDocumentos:
    return FakeAlmacenDocumentos()


@pytest.fixture
def cuenta(uow: FakeUnitOfWork, hasher: FakePasswordHasher) -> Usuario:
    return uow.usuarios.sembrar(
        Usuario(
            email=EMAIL,
            password_hash=hasher.hash(CLAVE),
            nombre_completo="María Pérez",
            rol=Rol.PRESTADOR,
            habeas_data_aceptado=True,
            habeas_data_aceptado_en=AHORA,
        )
    )


def marcar_suprimida(uow: FakeUnitOfWork, cuenta: Usuario) -> None:
    uow.usuarios.por_email[cuenta.email] = replace(cuenta, datos_suprimidos_en=AHORA, activo=False)


# ---------- Doble revocación ----------


async def test_revocacion_doble_antes_propaga_y_despues_solo_registra(
    revocacion: FakeRevocacion, caplog: pytest.LogCaptureFixture
) -> None:
    doble = RevocacionDoble(revocacion, reloj_fijo)
    revocacion.caida = True

    with pytest.raises(ServicioNoDisponibleError):
        await doble.antes_del_commit(uuid.uuid4(), AHORA)

    with caplog.at_level(logging.ERROR):
        await doble.despues_del_commit(uuid.uuid4())
    assert "No se pudo repetir la revocación" in caplog.text


# ---------- Perfil ----------


async def test_perfil_de_una_cuenta_suprimida_o_inexistente_404(
    uow: FakeUnitOfWork, cuenta: Usuario
) -> None:
    marcar_suprimida(uow, cuenta)

    for usuario_id in (cuenta.id, uuid.uuid4()):
        with pytest.raises(UsuarioNoEncontradoError):
            await ObtenerPerfil(uow).execute(usuario_id)  # type: ignore[arg-type]
        with pytest.raises(UsuarioNoEncontradoError):
            await EditarPerfil(uow).execute(
                EditarPerfilCommand(
                    usuario_id=usuario_id,  # type: ignore[arg-type]
                    nombre="Otro Nombre",
                    idioma=None,
                    version_esperada=None,
                    ip_origen=None,
                )
            )


async def test_el_cambio_de_contrasena_se_confirma_aunque_falle_la_segunda_revocacion(
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    revocacion: FakeRevocacion,
    cuenta: Usuario,
) -> None:
    llamadas = []

    def caer_en_la_segunda() -> None:
        llamadas.append(1)
        revocacion.caida = len(llamadas) == 2

    revocacion.al_revocar_usuario = caer_en_la_segunda

    await CambiarContrasena(uow, hasher, revocacion, reloj_fijo).execute(
        CambiarContrasenaCommand(cuenta.id, CLAVE, "Nueva12345", None)  # type: ignore[arg-type]
    )

    assert uow.commits == 1
    assert hasher.verify("Nueva12345", uow.usuarios.por_email[EMAIL].password_hash)


async def test_valkey_caido_deshace_el_cambio_de_contrasena(
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    revocacion: FakeRevocacion,
    cuenta: Usuario,
) -> None:
    revocacion.caida = True

    with pytest.raises(ServicioNoDisponibleError):
        await CambiarContrasena(uow, hasher, revocacion, reloj_fijo).execute(
            CambiarContrasenaCommand(cuenta.id, CLAVE, "Nueva12345", None)  # type: ignore[arg-type]
        )

    assert uow.commits == 0
    assert uow.rollbacks >= 1


# ---------- Recuperación ----------


def solicitar(uow, tokens, enviador) -> SolicitarRecuperacion:  # type: ignore[no-untyped-def]
    return SolicitarRecuperacion(uow, tokens, enviador, "https://pwa.example.com/")


async def test_el_enlace_usa_pwa_url_sin_doble_barra(
    uow: FakeUnitOfWork,
    tokens: FakeTokensRecuperacion,
    enviador: FakeEnviadorCorreo,
    cuenta: Usuario,
) -> None:
    resultado = await solicitar(uow, tokens, enviador).execute(
        SolicitarRecuperacionCommand(EMAIL, None)
    )

    assert resultado == "enviado"
    [token] = tokens.tokens
    assert (
        f"https://pwa.example.com/restablecer-contrasena?token={token}"
        in enviador.enviados[0].texto
    )


async def test_el_correo_escrito_en_mayusculas_encuentra_la_cuenta(
    uow: FakeUnitOfWork,
    tokens: FakeTokensRecuperacion,
    enviador: FakeEnviadorCorreo,
    cuenta: Usuario,
) -> None:
    resultado = await solicitar(uow, tokens, enviador).execute(
        SolicitarRecuperacionCommand(EMAIL.upper(), None)
    )

    assert resultado == "enviado"


async def test_si_falla_la_bitacora_no_sale_el_correo_y_descarta_el_token(
    uow: FakeUnitOfWork,
    tokens: FakeTokensRecuperacion,
    enviador: FakeEnviadorCorreo,
    cuenta: Usuario,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def fallar(**_: object) -> None:
        raise ConnectionRefusedError("PostgreSQL caído")

    monkeypatch.setattr(uow.auditoria, "registrar", fallar)

    resultado = await solicitar(uow, tokens, enviador).execute(
        SolicitarRecuperacionCommand(EMAIL, None)
    )

    assert resultado == "fallo_base"
    assert enviador.enviados == []
    assert tokens.tokens == {}
    assert cuenta.id not in tokens.en_espera
    assert EMAIL not in caplog.text


async def test_si_valkey_cae_al_guardar_el_resultado_es_de_valkey_no_de_smtp(
    uow: FakeUnitOfWork,
    tokens: FakeTokensRecuperacion,
    enviador: FakeEnviadorCorreo,
    cuenta: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fallar(*_: object) -> None:
        raise ServicioNoDisponibleError()

    monkeypatch.setattr(tokens, "guardar", fallar)

    resultado = await solicitar(uow, tokens, enviador).execute(
        SolicitarRecuperacionCommand(EMAIL, None)
    )

    assert resultado == "fallo_valkey"
    assert enviador.enviados == []


def restablecer(uow, tokens, hasher, revocacion) -> RestablecerContrasena:  # type: ignore[no-untyped-def]
    return RestablecerContrasena(uow, tokens, hasher, revocacion, reloj_fijo)


async def test_token_falso_no_gasta_argon2(
    uow: FakeUnitOfWork,
    tokens: FakeTokensRecuperacion,
    revocacion: FakeRevocacion,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hasher = FakePasswordHasher()
    calculados: list[str] = []
    monkeypatch.setattr(hasher, "hash", lambda plain: calculados.append(plain) or "h")

    with pytest.raises(TokenRecuperacionInvalidoError):
        await restablecer(uow, tokens, hasher, revocacion).execute(
            RestablecerContrasenaCommand("falso", "Nueva12345", None)
        )

    assert calculados == []
    assert uow.entradas == 0


async def test_politica_antes_que_valkey(
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    revocacion: FakeRevocacion,
    tokens: FakeTokensRecuperacion,
) -> None:
    # Con Valkey caído, una contraseña débil sigue siendo 422: ni siquiera se consulta el token.
    tokens.caido = True

    with pytest.raises(PasswordInvalidaError):
        await restablecer(uow, tokens, hasher, revocacion).execute(
            RestablecerContrasenaCommand("t", "corta", None)
        )


async def test_enlace_de_una_cuenta_suprimida_es_invalido(
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    revocacion: FakeRevocacion,
    tokens: FakeTokensRecuperacion,
    cuenta: Usuario,
) -> None:
    await tokens.guardar("t", cuenta.id)  # type: ignore[arg-type]
    marcar_suprimida(uow, cuenta)

    with pytest.raises(TokenRecuperacionInvalidoError):
        await restablecer(uow, tokens, hasher, revocacion).execute(
            RestablecerContrasenaCommand("t", "Nueva12345", None)
        )

    assert revocacion.revocaciones_usuario == []
    assert uow.commits == 0


# ---------- Supresión ----------


def suprimir(uow, hasher, almacen, revocacion) -> SuprimirDatos:  # type: ignore[no-untyped-def]
    return SuprimirDatos(uow, hasher, almacen, revocacion, reloj_fijo)


async def test_se_confirma_aunque_falle_la_segunda_revocacion(
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
    revocacion: FakeRevocacion,
    cuenta: Usuario,
) -> None:
    llamadas = []

    def caer_en_la_segunda() -> None:
        llamadas.append(1)
        revocacion.caida = len(llamadas) == 2

    revocacion.al_revocar_usuario = caer_en_la_segunda

    await suprimir(uow, hasher, almacen, revocacion).execute(
        SuprimirDatosCommand(cuenta.id, CLAVE, None)  # type: ignore[arg-type]
    )

    assert uow.commits == 1


async def test_si_otra_peticion_termino_mientras_esperaba_el_bloqueo_no_hace_nada(
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
    revocacion: FakeRevocacion,
    cuenta: Usuario,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = uow.usuarios.find_by_id_para_actualizar

    async def suprimida_al_bloquear(usuario_id: uuid.UUID) -> Usuario | None:
        marcar_suprimida(uow, cuenta)
        return await original(usuario_id)

    monkeypatch.setattr(uow.usuarios, "find_by_id_para_actualizar", suprimida_al_bloquear)

    await suprimir(uow, hasher, almacen, revocacion).execute(
        SuprimirDatosCommand(cuenta.id, CLAVE, None)  # type: ignore[arg-type]
    )

    assert uow.commits == 0
    assert almacen.prefijos_borrados == []
    assert revocacion.revocaciones_usuario == []
    assert uow.auditoria.registros == []


async def test_el_hash_aleatorio_es_distinto_en_cada_supresion(
    uow: FakeUnitOfWork,
    hasher: FakePasswordHasher,
    almacen: FakeAlmacenDocumentos,
    revocacion: FakeRevocacion,
    cuenta: Usuario,
) -> None:
    await suprimir(uow, hasher, almacen, revocacion).execute(
        SuprimirDatosCommand(cuenta.id, CLAVE, None)  # type: ignore[arg-type]
    )

    final = await uow.usuarios.find_by_id(cuenta.id)  # type: ignore[arg-type]
    assert final is not None
    assert final.password_hash != cuenta.password_hash
    assert final.password_hash.startswith("fake-hash:")


async def test_carga_tras_la_supresion_si_no_se_puede_borrar_el_objeto_queda_en_el_log(
    uow: FakeUnitOfWork,
    almacen: FakeAlmacenDocumentos,
    cuenta: Usuario,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def suprimir_y_caer() -> None:
        marcar_suprimida(uow, cuenta)
        almacen.caido = True

    almacen.al_guardar = suprimir_y_caer

    with pytest.raises(CuentaSuprimidaError):
        await SubirDocumento(uow, almacen, reloj_fijo).execute(
            SubirDocumentoCommand(
                usuario_id=cuenta.id,  # type: ignore[arg-type]
                tipo=TipoDocumento.RNT,
                contenido=PDF,
                razon_social=None,
                ip_origen=None,
            )
        )

    assert "Objeto de una cuenta suprimida sin borrar" in caplog.text
