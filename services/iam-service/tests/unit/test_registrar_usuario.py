from dataclasses import replace

import pytest

from app.application.use_cases.registrar_usuario import RegistrarUsuario, RegistrarUsuarioCommand
from app.domain.exceptions import (
    DominioValidationError,
    EmailInvalidoError,
    HabeasDataNoAceptadoError,
    MenorDeEdadError,
    NombreInvalidoError,
    PasswordInvalidaError,
    RolNoPermitidoError,
    UsuarioYaExisteError,
)
from app.domain.value_objects.enums import ResultadoAuditoria, Rol
from app.infrastructure.security.argon2_password_hasher import Argon2PasswordHasher
from tests.fakes import AHORA, FakeUnitOfWork, reloj_fijo

COMANDO = RegistrarUsuarioCommand(
    email="  Maria.Perez@Example.com ",
    password="Tayrona2026",
    nombre_completo="  María Pérez ",
    rol=Rol.TURISTA,
    habeas_data_aceptado=True,
    es_mayor_de_edad=True,
    ip_origen="190.0.0.1",
)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


@pytest.fixture
def registrar(uow: FakeUnitOfWork, hasher: Argon2PasswordHasher) -> RegistrarUsuario:
    return RegistrarUsuario(uow=uow, hasher=hasher, reloj=reloj_fijo)


@pytest.mark.parametrize("rol", [Rol.TURISTA, Rol.PRESTADOR])
async def test_registro_exitoso(registrar: RegistrarUsuario, uow: FakeUnitOfWork, rol: Rol) -> None:
    usuario = await registrar.execute(replace(COMANDO, rol=rol))

    assert usuario.id is not None
    assert usuario.email == "maria.perez@example.com"
    assert usuario.nombre_completo == "María Pérez"
    assert usuario.rol is rol
    assert usuario.activo is True
    assert usuario.email_verificado is False
    assert usuario.habeas_data_aceptado is True
    assert usuario.habeas_data_aceptado_en == AHORA

    assert uow.commits == 1
    [registro] = uow.auditoria.registros
    assert registro.accion == "USER_REGISTER"
    assert registro.resultado is ResultadoAuditoria.EXITO
    assert registro.usuario_id == usuario.id
    assert registro.ip_origen == "190.0.0.1"
    assert registro.detalles == {"rol": rol.value}


async def test_el_hash_guardado_no_es_la_contrasena(
    registrar: RegistrarUsuario, hasher: Argon2PasswordHasher
) -> None:
    usuario = await registrar.execute(COMANDO)

    assert usuario.password_hash != COMANDO.password
    assert COMANDO.password not in usuario.password_hash
    assert hasher.verify(COMANDO.password, usuario.password_hash)


async def test_email_duplicado(registrar: RegistrarUsuario, uow: FakeUnitOfWork) -> None:
    await registrar.execute(COMANDO)

    with pytest.raises(UsuarioYaExisteError):
        await registrar.execute(replace(COMANDO, email="MARIA.PEREZ@example.com"))

    assert uow.commits == 1  # solo el primer registro
    assert len(uow.auditoria.registros) == 1


@pytest.mark.parametrize(
    ("cambios", "error"),
    [
        ({"habeas_data_aceptado": False}, HabeasDataNoAceptadoError),
        ({"es_mayor_de_edad": False}, MenorDeEdadError),
        ({"rol": Rol.ADMIN}, RolNoPermitidoError),
        ({"rol": Rol.ENTIDAD}, RolNoPermitidoError),
        ({"email": "no-es-un-email"}, EmailInvalidoError),
        ({"password": "corta1"}, PasswordInvalidaError),
        ({"nombre_completo": " A "}, NombreInvalidoError),
        ({"nombre_completo": "x" * 151}, NombreInvalidoError),
    ],
)
async def test_reglas_de_validacion(
    registrar: RegistrarUsuario,
    uow: FakeUnitOfWork,
    cambios: dict[str, object],
    error: type[DominioValidationError],
) -> None:
    with pytest.raises(error):
        await registrar.execute(replace(COMANDO, **cambios))

    assert uow.commits == 0
    assert uow.usuarios.por_email == {}
    assert uow.auditoria.registros == []


async def test_habeas_data_se_valida_primero(
    registrar: RegistrarUsuario, uow: FakeUnitOfWork
) -> None:
    # Con todo inválido, el primer error es el de habeas data (UC6).
    invalido = replace(
        COMANDO,
        habeas_data_aceptado=False,
        es_mayor_de_edad=False,
        rol=Rol.ADMIN,
        email="x",
        password="x",
    )
    with pytest.raises(HabeasDataNoAceptadoError):
        await registrar.execute(invalido)
    assert uow.commits == 0
