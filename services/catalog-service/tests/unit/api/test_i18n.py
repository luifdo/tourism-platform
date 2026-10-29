"""El sistema debe funcionar completo en español y en inglés: ningún texto puede faltar."""

import re
from pathlib import Path

import pytest

from app.api.errores.manejador_errores import ESTADO_POR_CODIGO
from app.api.i18n.etiquetas import ETIQUETAS, etiqueta
from app.api.i18n.mensajes_error import MENSAJES, VALIDACION, mensaje_error
from app.api.i18n.textos_plataforma import REGLA_BASE_CANCELACION
from app.application import errores
from app.application.dto.estado_alerta import EstadoAlerta
from app.domain import errors
from app.domain.errors import DatoInvalido, ErrorDominio, VersionDistinta, ZonaEnUso
from app.domain.value_objects.atributos import valores
from app.domain.value_objects.catalogos import Categoria, NivelAlerta, UnidadTarifa
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.saturacion import NivelSaturacion
from app.domain.value_objects.tipo_servicio import TipoServicio

APP = Path(__file__).resolve().parents[3] / "app"


def reglas_usadas_en_el_codigo() -> set[str]:
    reglas: set[str] = set()
    for archivo in APP.rglob("*.py"):
        reglas |= set(re.findall(r'regla="([a-z0-9_]+)"', archivo.read_text(encoding="utf-8")))
    return reglas


def test_cada_regla_de_validacion_tiene_mensaje() -> None:
    faltantes = reglas_usadas_en_el_codigo() - set(VALIDACION)
    assert not faltantes, f"Reglas sin mensaje: {faltantes}"


def test_cada_error_del_dominio_y_la_aplicacion_tiene_mensaje_y_estado() -> None:
    codigos = {
        clase.codigo
        for modulo in (errors, errores)
        for clase in vars(modulo).values()
        if isinstance(clase, type) and issubclass(clase, ErrorDominio) and clase is not ErrorDominio
    }
    sin_mensaje = codigos - set(MENSAJES) - {"VALIDACION"}
    assert not sin_mensaje
    assert codigos <= set(ESTADO_POR_CODIGO)


@pytest.mark.parametrize(
    "catalogo",
    [MENSAJES, VALIDACION, {"regla_base_cancelacion": REGLA_BASE_CANCELACION}],
    ids=["mensajes", "validacion", "textos_plataforma"],
)
def test_todos_los_textos_estan_en_ambos_idiomas(catalogo: dict) -> None:
    for clave, textos in catalogo.items():
        assert set(textos) == set(Idioma), clave
        assert all(t.strip() for t in textos.values()), clave


@pytest.mark.parametrize(
    "enum",
    [
        Categoria,
        NivelAlerta,
        NivelSaturacion,
        TipoServicio,
        UnidadTarifa,
        valores.NivelFisico,
        valores.TipoHabitacion,
        valores.Amenidad,
        valores.TipoCocina,
        valores.OpcionDietaria,
        valores.TipoVisitante,
        valores.ServicioEnSitio,
        valores.SenalInternet,
        valores.MedioPago,
        valores.RecomendacionDinero,
        EstadoAlerta,
    ],
)
def test_cada_valor_fijo_tiene_etiqueta_en_ambos_idiomas(enum: type) -> None:
    for valor in enum:
        assert set(ETIQUETAS[valor]) == set(Idioma), valor


def test_mensajes_con_datos() -> None:
    assert "3" in mensaje_error(VersionDistinta(version_actual=3), Idioma.EN)
    assert "2 alerta" in mensaje_error(ZonaEnUso(zona="minca", alertas_vigentes=2), Idioma.ES)
    texto = mensaje_error(
        DatoInvalido(campo="radio_m", regla="rango", minimo=100, maximo=50000), Idioma.EN
    )
    assert texto == "The field 'radio_m' must be between 100 and 50000."


def test_dato_faltante_en_la_plantilla_no_rompe() -> None:
    assert mensaje_error(DatoInvalido(regla="rango"), Idioma.ES)


def test_regla_desconocida_usa_mensaje_generico() -> None:
    assert "precio" in mensaje_error(DatoInvalido(campo="precio", regla="otra"), Idioma.ES)


def test_etiquetas() -> None:
    assert etiqueta(Categoria.GASTRONOMIA, Idioma.ES) == "Gastronomía"
    assert etiqueta(NivelAlerta.CRITICA, Idioma.EN) == "Critical"
