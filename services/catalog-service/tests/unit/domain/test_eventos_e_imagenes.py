from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.errors import DatoInvalido
from app.domain.events.servicio_publicado import ServicioPublicado
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.atributos.bloque_gastronomia import BloqueGastronomia
from app.domain.value_objects.atributos.valores import TipoCocina
from app.domain.value_objects.catalogos import Categoria, UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.imagen_solicitada import (
    MAX_BYTES_IMAGEN,
    ImagenSolicitada,
    TipoImagen,
)
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio

AHORA = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)


# Un tipo por categoría con su bloque principal mínimo (las pruebas filtran por categoría).
TIPO_DE = {
    Categoria.PLAYA: TipoServicio.ACCESO_PLAYA,
    Categoria.CULTURA: TipoServicio.MUSEO_SITIO,
    Categoria.NATURALEZA: TipoServicio.RESERVA_PARQUE,
    Categoria.GASTRONOMIA: TipoServicio.RESTAURANTE,
}


def atributos_de(tipo: TipoServicio) -> AtributosServicio:
    if tipo is TipoServicio.RESTAURANTE:
        return AtributosServicio(gastronomia=BloqueGastronomia(tipos_cocina=(TipoCocina.DE_MAR,)))
    return AtributosServicio(entrada=BloqueEntrada())


def test_servicio_publicado_cumple_el_contrato() -> None:
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Turismo Sierra")
    datos = DatosServicio(
        nombre=TextoTraducido(es="Tour"),
        descripcion=TextoTraducido(es="Recorrido"),
        tipo=TIPO_DE[Categoria.CULTURA],
        unidad_tarifa=UnidadTarifa.POR_PERSONA,
        atributos=atributos_de(TIPO_DE[Categoria.CULTURA]),
        ubicacion=Coordenada(lat=11.24, lon=-74.21),
        tarifa_base=Tarifa(Decimal("85000.50")),
        capacidad_aforo_diario=20,
    )
    servicio = AtractivoServicio.registrar(perfil, datos, "https://s3/", AHORA)
    evento = ServicioPublicado.de(servicio, AHORA)
    assert evento.tipo == "servicio.publicado" and evento.version_esquema == 1
    # Exactamente los campos de contracts/events/servicio.publicado.v1.json.
    assert evento.payload() == {
        "servicio_id": str(servicio.id),
        "prestador_id": str(perfil.id),
        "prestador_usuario_id": str(perfil.usuario_id),
        "capacidad_aforo_diario": 20,
        "tarifa_base": 85000.5,
        "activo": True,
        "version": 1,
    }


class TestImagen:
    @pytest.mark.parametrize("tamano", [0, MAX_BYTES_IMAGEN + 1])
    def test_tamano_fuera_de_rango(self, tamano: int) -> None:
        with pytest.raises(DatoInvalido) as exc:
            ImagenSolicitada(TipoImagen.PNG, tamano)
        assert exc.value.detalle["campo"] == "tamano_bytes"

    def test_cinco_megas_justos_se_aceptan(self) -> None:
        assert ImagenSolicitada(TipoImagen.WEBP, MAX_BYTES_IMAGEN).tipo.extension == "webp"

    def test_solo_tres_tipos(self) -> None:
        assert {t.value for t in TipoImagen} == {"image/jpeg", "image/png", "image/webp"}
