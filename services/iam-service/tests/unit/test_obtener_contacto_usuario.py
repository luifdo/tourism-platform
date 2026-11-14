import uuid

import pytest

from app.application.use_cases.obtener_contacto_usuario import ObtenerContactoUsuario
from app.domain.exceptions import UsuarioNoEncontradoError
from tests.api.conftest import usuario
from tests.fakes import FakeUnitOfWork


async def test_devuelve_el_usuario() -> None:
    uow = FakeUnitOfWork()
    sembrado = uow.usuarios.sembrar(usuario())
    assert sembrado.id is not None

    assert await ObtenerContactoUsuario(uow).execute(sembrado.id) == sembrado
    assert uow.commits == 0  # solo lectura


async def test_inexistente_es_usuario_no_encontrado() -> None:
    with pytest.raises(UsuarioNoEncontradoError):
        await ObtenerContactoUsuario(FakeUnitOfWork()).execute(uuid.uuid4())
