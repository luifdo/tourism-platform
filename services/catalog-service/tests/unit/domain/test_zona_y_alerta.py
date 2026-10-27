from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.alerta_oficial import AlertaOficial
from app.domain.entities.zona import Zona
from app.domain.errors import AlertaRetirada, DatoInvalido, VersionDistinta, ZonaEnUso
from app.domain.value_objects.catalogos import NivelAlerta
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import PoligonoGeoJSON
from app.domain.value_objects.texto_traducido import TextoTraducido

AHORA = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)


def poligono(desplazamiento: float = 0.0) -> PoligonoGeoJSON:
    x = -74.2 + desplazamiento
    anillo = [[x, 11.1], [x + 0.1, 11.1], [x + 0.1, 11.2], [x, 11.2], [x, 11.1]]
    return PoligonoGeoJSON.desde_geojson({"type": "Polygon", "coordinates": [anillo]})


def zona() -> Zona:
    return Zona.crear(CodigoZona("minca"), TextoTraducido(es="Minca"), poligono())


class TestZona:
    def test_editar_informa_si_cambio_el_poligono(self) -> None:
        z = zona()
        assert z.editar(1, z.codigo, TextoTraducido(es="Minca", en="Minca"), poligono()) is False
        assert z.editar(2, z.codigo, z.nombre, poligono(0.05)) is True
        assert z.version == 3

    def test_editar_con_version_vieja(self) -> None:
        z = zona()
        z.editar(1, z.codigo, z.nombre, poligono())
        with pytest.raises(VersionDistinta):
            z.editar(1, z.codigo, z.nombre, poligono())

    def test_no_se_desactiva_con_alertas_vigentes(self) -> None:
        z = zona()
        with pytest.raises(ZonaEnUso):
            z.desactivar(1, alertas_vigentes=2)
        assert z.activa

    def test_desactivar(self) -> None:
        z = zona()
        assert z.desactivar(1, alertas_vigentes=0) is True
        assert not z.activa and z.version == 2
        assert z.desactivar(2, alertas_vigentes=3) is False  # repetido: sin efecto ni error
        assert z.version == 2


class TestAlertaOficial:
    def publicar(self, **cambios: object) -> AlertaOficial:
        base = {
            "nivel": NivelAlerta.PREVENTIVA,
            "mensaje": TextoTraducido(
                es="Sendero cerrado por lluvias", en="Trail closed due to rain"
            ),
            "entidad_usuario_id": uuid4(),
            "fecha_expiracion": AHORA + timedelta(days=2),
            "ahora": AHORA,
            "zona_id": uuid4(),
        }
        return AlertaOficial.publicar(**(base | cambios))  # type: ignore[arg-type]

    def test_publicar_por_zona(self) -> None:
        alerta = self.publicar()
        assert alerta.vigente(AHORA) and alerta.servicio_id is None

    def test_publicar_por_servicio(self) -> None:
        alerta = self.publicar(zona_id=None, servicio_id=uuid4())
        assert alerta.zona_id is None

    @pytest.mark.parametrize(
        "cambios",
        [{"zona_id": None}, {"servicio_id": uuid4()}],
        ids=["ninguno", "ambos"],
    )
    def test_exactamente_un_destino(self, cambios: dict) -> None:
        with pytest.raises(DatoInvalido):
            self.publicar(**cambios)

    def test_expiracion_futura(self) -> None:
        with pytest.raises(DatoInvalido):
            self.publicar(fecha_expiracion=AHORA)

    def test_vigencia(self) -> None:
        alerta = self.publicar()
        assert not alerta.vigente(AHORA + timedelta(days=3))
        alerta.desactivar()
        assert not alerta.vigente(AHORA)


class TestEdicionDeAlerta:
    def alerta(self) -> AlertaOficial:
        return AlertaOficial.publicar(
            nivel=NivelAlerta.PREVENTIVA,
            mensaje=TextoTraducido(es="Sendero cerrado"),
            entidad_usuario_id=uuid4(),
            fecha_expiracion=AHORA + timedelta(days=2),
            ahora=AHORA,
            zona_id=uuid4(),
        )

    def test_extender_y_cambiar_nivel(self) -> None:
        alerta = self.alerta()
        alerta.editar(1, NivelAlerta.CRITICA, alerta.mensaje, AHORA + timedelta(days=9), AHORA)
        assert (alerta.nivel, alerta.version) == (NivelAlerta.CRITICA, 2)
        assert alerta.vigente(AHORA + timedelta(days=8))

    def test_editar_con_version_vieja(self) -> None:
        alerta = self.alerta()
        alerta.editar(1, alerta.nivel, alerta.mensaje, alerta.fecha_expiracion, AHORA)
        with pytest.raises(VersionDistinta):
            alerta.editar(1, alerta.nivel, alerta.mensaje, alerta.fecha_expiracion, AHORA)

    def test_una_retirada_no_se_edita(self) -> None:
        alerta = self.alerta()
        assert alerta.desactivar() is True and alerta.desactivar() is False
        with pytest.raises(AlertaRetirada):
            alerta.editar(2, alerta.nivel, alerta.mensaje, alerta.fecha_expiracion, AHORA)

    @pytest.mark.parametrize("dias", [366, 1000])
    def test_vigencia_maxima_de_un_anio(self, dias: int) -> None:
        with pytest.raises(DatoInvalido, match="plazo_maximo"):
            AlertaOficial.publicar(
                nivel=NivelAlerta.INFORMATIVA,
                mensaje=TextoTraducido(es="Aviso"),
                entidad_usuario_id=uuid4(),
                fecha_expiracion=AHORA + timedelta(days=dias),
                ahora=AHORA,
                zona_id=uuid4(),
            )
