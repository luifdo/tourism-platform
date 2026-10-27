from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.errors import DatoInvalido, NoEncontrado, PerfilInactivo, VersionDistinta
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio

ORIGEN = "https://s3.turismo.local/catalogo-imagenes/"
AHORA = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)


def datos(**cambios: object) -> DatosServicio:
    base = {
        "nombre": TextoTraducido(es="Tour cafetero", en="Coffee tour"),
        "descripcion": TextoTraducido(es="Recorrido por fincas de Minca"),
        "tipo": TipoServicio.RESERVA_PARQUE,
        "unidad_tarifa": UnidadTarifa.POR_PERSONA,
        "atributos": AtributosServicio(entrada=BloqueEntrada()),
        "ubicacion": Coordenada(lat=11.1426, lon=-74.1178),
        "tarifa_base": Tarifa(Decimal("85000")),
        "capacidad_aforo_diario": 20,
        "imagenes_urls": (f"{ORIGEN}a.webp",),
    }
    return DatosServicio(**(base | cambios))  # type: ignore[arg-type]


def perfil(activo: bool = True) -> PrestadorPerfil:
    p = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Café de la Sierra")
    if not activo:
        p.suspender()
    return p


def servicio_de(p: PrestadorPerfil) -> AtractivoServicio:
    return AtractivoServicio.registrar(p, datos(), ORIGEN, AHORA)


class TestPrestadorPerfil:
    def test_aprobar_crea_perfil_activo(self) -> None:
        p = perfil()
        assert p.activo and p.version == 1

    def test_suspender_y_reaprobar(self) -> None:
        p = perfil()
        assert p.suspender() is True
        assert p.suspender() is False  # repetido: sin efecto
        assert p.reaprobar("Café de la Sierra") is True
        assert p.reaprobar("Café de la Sierra") is False
        assert p.activo and p.version == 3

    def test_reaprobar_actualiza_razon_social(self) -> None:
        p = perfil()
        p.reaprobar("Café de la Sierra S.A.S.")
        assert p.razon_social == "Café de la Sierra S.A.S." and p.version == 2

    def test_editar_exige_version_y_perfil_activo(self) -> None:
        p = perfil()
        p.editar(1, "3001234567", "Minca", TextoTraducido(es="Gratis hasta 24 h"))
        assert p.version == 2
        with pytest.raises(VersionDistinta) as error:
            p.editar(1, None, None, None)
        assert error.value.version_actual == 2
        p.suspender()
        with pytest.raises(PerfilInactivo):
            p.editar(p.version, None, None, None)


class TestRegistrarServicio:
    def test_registra_con_dueno_y_version_1(self) -> None:
        p = perfil()
        s = servicio_de(p)
        assert s.prestador_id == p.id and s.prestador_usuario_id == p.usuario_id
        assert s.activo and s.version == 1 and s.zona_id is None

    def test_exige_perfil_activo(self) -> None:
        with pytest.raises(PerfilInactivo):
            servicio_de(perfil(activo=False))

    @pytest.mark.parametrize(
        "cambios",
        [
            {"capacidad_aforo_diario": 0},
            {"imagenes_urls": ("https://otro-sitio.com/a.png",)},
            {"imagenes_urls": tuple(f"{ORIGEN}{i}.png" for i in range(11))},
        ],
        ids=["capacidad_cero", "imagen_fuera_del_bucket", "mas_de_10_imagenes"],
    )
    def test_datos_invalidos(self, cambios: dict) -> None:
        with pytest.raises(DatoInvalido):
            AtractivoServicio.registrar(perfil(), datos(**cambios), ORIGEN, AHORA)


class TestEditarServicio:
    def test_editar_sube_version_y_fecha(self) -> None:
        p = perfil()
        s = servicio_de(p)
        despues = AHORA + timedelta(hours=1)
        s.editar(p, 1, datos(capacidad_aforo_diario=30), ORIGEN, despues)
        assert s.version == 2 and s.actualizado_en == despues
        assert s.datos.capacidad_aforo_diario == 30

    def test_version_distinta(self) -> None:
        p = perfil()
        s = servicio_de(p)
        s.editar(p, 1, datos(), ORIGEN, AHORA)
        with pytest.raises(VersionDistinta):
            s.editar(p, 1, datos(), ORIGEN, AHORA)

    def test_servicio_ajeno_se_responde_como_inexistente(self) -> None:
        s = servicio_de(perfil())
        with pytest.raises(NoEncontrado):
            s.editar(perfil(), 1, datos(), ORIGEN, AHORA)

    def test_prestador_suspendido_no_edita(self) -> None:
        p = perfil()
        s = servicio_de(p)
        p.suspender()
        with pytest.raises(PerfilInactivo):
            s.editar(p, 1, datos(), ORIGEN, AHORA)

    def test_asignar_zona_no_cambia_version(self) -> None:
        s = servicio_de(perfil())
        s.asignar_zona(uuid4())
        assert s.version == 1


class TestActivacion:
    def test_desactivar_y_reactivar(self) -> None:
        p = perfil()
        s = servicio_de(p)
        assert s.desactivar(p, 1, AHORA) is True and not s.activo
        assert s.desactivar(p, 2, AHORA) is False  # ya inactivo: nada que publicar
        assert s.reactivar(p, 2, AHORA) is True and s.activo
        assert s.version == 3

    def test_no_reactiva_con_perfil_suspendido(self) -> None:
        p = perfil()
        s = servicio_de(p)
        s.desactivar(p, 1, AHORA)
        p.suspender()
        with pytest.raises(PerfilInactivo):
            s.reactivar(p, 2, AHORA)

    def test_suspension_restaura_solo_lo_que_ella_apago(self) -> None:
        p = perfil()
        apagado_por_prestador = servicio_de(p)
        apagado_por_prestador.desactivar(p, 1, AHORA)
        activo = servicio_de(p)

        assert apagado_por_prestador.desactivar_por_suspension(AHORA) is False
        assert activo.desactivar_por_suspension(AHORA) is True and not activo.activo

        assert apagado_por_prestador.restaurar_tras_suspension(AHORA) is False
        assert not apagado_por_prestador.activo
        assert activo.restaurar_tras_suspension(AHORA) is True and activo.activo
        assert activo.restaurar_tras_suspension(AHORA) is False

    def test_prestador_que_apaga_durante_la_suspension_gana(self) -> None:
        p = perfil()
        s = servicio_de(p)
        s.desactivar_por_suspension(AHORA)
        assert s.desactivar(p, s.version, AHORA) is True
        assert s.desactivado_por_suspension is False
        assert s.restaurar_tras_suspension(AHORA) is False and not s.activo
