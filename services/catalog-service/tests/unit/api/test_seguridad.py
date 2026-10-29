"""Cabeceras de identidad, If-Match e Idempotency-Key, sin base de datos."""

from uuid import UUID, uuid4

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse

from app.api.seguridad.idempotencia import CABECERA_REPETIDA, responder_idempotente
from app.api.seguridad.identidad_peticion import identidad_peticion
from app.api.seguridad.version_if_match import version_if_match
from app.application.dto.respuesta_guardada import RespuestaGuardada
from app.application.errores import FaltaIfMatch, NoAutenticado, SolicitudEnProceso
from app.domain.errors import DatoInvalido, RolNoPermitido
from app.domain.value_objects.identidad import Identidad, Rol

USUARIO = uuid4()


class TestIdentidad:
    def test_lee_las_cabeceras_de_traefik(self) -> None:
        assert identidad_peticion(str(USUARIO), "Prestador") == Identidad(USUARIO, Rol.PRESTADOR)

    @pytest.mark.parametrize(
        ("usuario", "rol"), [(None, "Prestador"), (str(USUARIO), None), ("no-es-uuid", "Turista")]
    )
    def test_sin_identidad_valida_es_401(self, usuario: str | None, rol: str | None) -> None:
        with pytest.raises(NoAutenticado):
            identidad_peticion(usuario, rol)

    def test_rol_desconocido_es_403_no_401(self) -> None:
        with pytest.raises(RolNoPermitido):
            identidad_peticion(str(USUARIO), "Moderador")


class TestIfMatch:
    @pytest.mark.parametrize("valor", ['"3"', 'W/"3"', "3", ' "3" '])
    def test_formatos_aceptados(self, valor: str) -> None:
        assert version_if_match(valor) == 3

    @pytest.mark.parametrize("valor", [None, "", "  "])
    def test_falta_es_428(self, valor: str | None) -> None:
        with pytest.raises(FaltaIfMatch):
            version_if_match(valor)

    @pytest.mark.parametrize("valor", ['"abc"', '"0"', '"-1"', "*"])
    def test_formato_invalido_es_400(self, valor: str) -> None:
        with pytest.raises(DatoInvalido):
            version_if_match(valor)


class AlmacenEnMemoria:
    def __init__(self) -> None:
        self.datos: dict[str, RespuestaGuardada | str] = {}

    async def reservar(self, clave: str) -> RespuestaGuardada | bool:
        actual = self.datos.get(clave)
        if actual is None:
            self.datos[clave] = "en_proceso"
            return True
        return False if actual == "en_proceso" else actual  # type: ignore[return-value]

    async def guardar(self, clave: str, respuesta: RespuestaGuardada) -> None:
        self.datos[clave] = respuesta

    async def liberar(self, clave: str) -> None:
        self.datos.pop(clave, None)


def peticion(ruta: str = "/api/catalog/servicios") -> Request:
    return Request(
        {"type": "http", "method": "POST", "path": ruta, "headers": [], "query_string": b""}
    )


class TestIdempotencia:
    async def test_el_reintento_devuelve_lo_mismo_sin_ejecutar(self) -> None:
        almacen, llamadas = AlmacenEnMemoria(), []
        identidad, clave = Identidad(USUARIO, Rol.PRESTADOR), uuid4()

        async def ejecutar() -> JSONResponse:
            llamadas.append(1)
            return JSONResponse({"id": "s1"}, status_code=201, headers={"ETag": '"1"'})

        primera = await responder_idempotente(almacen, peticion(), identidad, clave, ejecutar)
        segunda = await responder_idempotente(almacen, peticion(), identidad, clave, ejecutar)
        assert len(llamadas) == 1
        assert (segunda.status_code, segunda.body) == (201, primera.body)
        assert segunda.headers["etag"] == '"1"' and segunda.headers[CABECERA_REPETIDA] == "true"

    async def test_la_clave_es_por_usuario_y_por_ruta(self) -> None:
        almacen, llamadas = AlmacenEnMemoria(), []
        clave = uuid4()

        async def ejecutar() -> JSONResponse:
            llamadas.append(1)
            return JSONResponse({})

        await responder_idempotente(
            almacen, peticion(), Identidad(USUARIO, Rol.PRESTADOR), clave, ejecutar
        )
        await responder_idempotente(
            almacen, peticion(), Identidad(uuid4(), Rol.PRESTADOR), clave, ejecutar
        )
        await responder_idempotente(
            almacen,
            peticion("/api/catalog/prestador/perfil"),
            Identidad(USUARIO, Rol.PRESTADOR),
            clave,
            ejecutar,
        )
        assert len(llamadas) == 3

    async def test_si_falla_el_reintento_vuelve_a_ejecutar(self) -> None:
        almacen, identidad, clave = AlmacenEnMemoria(), Identidad(USUARIO, Rol.PRESTADOR), uuid4()

        async def falla() -> JSONResponse:
            raise DatoInvalido(campo="x", regla="formato")

        with pytest.raises(DatoInvalido):
            await responder_idempotente(almacen, peticion(), identidad, clave, falla)
        assert almacen.datos == {}

    async def test_mientras_sigue_el_primero_es_409(self) -> None:
        almacen, identidad, clave = AlmacenEnMemoria(), Identidad(USUARIO, Rol.PRESTADOR), uuid4()

        async def segundo_mientras_tanto() -> JSONResponse:
            with pytest.raises(SolicitudEnProceso):
                await responder_idempotente(
                    almacen, peticion(), identidad, clave, segundo_mientras_tanto
                )
            return JSONResponse({})

        await responder_idempotente(almacen, peticion(), identidad, clave, segundo_mientras_tanto)

    async def test_sin_clave_se_ejecuta_siempre(self) -> None:
        llamadas = []

        async def ejecutar() -> JSONResponse:
            llamadas.append(1)
            return JSONResponse({})

        for _ in range(2):
            await responder_idempotente(
                AlmacenEnMemoria(), peticion(), Identidad(USUARIO, Rol.PRESTADOR), None, ejecutar
            )
        assert len(llamadas) == 2 and isinstance(USUARIO, UUID)
