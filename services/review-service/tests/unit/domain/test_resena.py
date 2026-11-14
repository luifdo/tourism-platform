from datetime import date

import pytest

from app.domain.entities.resena import Resena
from app.domain.errors import (
    DatoInvalido,
    NoElegible,
    NoEncontrado,
    NoEsDueno,
    ResenaEnModeracion,
    ResenaPropia,
    VersionDistinta,
)
from app.domain.events.resena_ocultada import ResenaOcultada
from app.domain.events.resena_publicada import ResenaPublicada
from app.domain.value_objects.contenido_resena import ContenidoResena
from app.domain.value_objects.decision_moderacion import DecisionModeracion
from app.domain.value_objects.estado_resena import EstadoResena
from app.domain.value_objects.identidad import Rol
from tests.unit.domain.comun import (
    ADMIN,
    AHORA,
    DUENO,
    SERVICIO,
    TURISTA,
    dueno,
    elegibilidad,
    reporte,
    resena,
)

PUBLICAR, OCULTAR = DecisionModeracion.PUBLICAR, DecisionModeracion.OCULTAR


def en_estado(estado: EstadoResena) -> Resena:
    r = resena()
    if estado is EstadoResena.EN_REVISION:
        r.recibir_reporte(reporte(r, DUENO, Rol.PRESTADOR, es_dueno=True))
    elif estado is EstadoResena.OCULTA:
        r.moderar(ADMIN, r.version, OCULTAR, "Ofensiva", AHORA)
    return r


class TestEscribir:
    def test_queda_publicada_y_emite_el_evento(self) -> None:
        r, evento = Resena.escribir(TURISTA, SERVICIO, elegibilidad(), ContenidoResena(5), AHORA)
        assert (r.estado, r.version, r.mes_visita) == (EstadoResena.PUBLICADA, 1, "2026-11")
        assert evento == ResenaPublicada(
            resena_id=r.id,
            servicio_id=SERVICIO,
            turista_id=TURISTA,
            puntuacion=5,
            ocurrido_en=AHORA,
        )

    def test_sin_reserva_finalizada_no_es_elegible(self) -> None:
        with pytest.raises(NoElegible):
            Resena.escribir(TURISTA, SERVICIO, None, ContenidoResena(5), AHORA)


class TestEditar:
    def test_cambia_el_contenido_conserva_la_respuesta_y_publica(self) -> None:
        r = resena(puntuacion=2)
        r.responder(DUENO, dueno(), 1, "Gracias", AHORA)
        evento = r.editar(TURISTA, 2, ContenidoResena(4), elegibilidad(date(2027, 1, 3)), AHORA)

        assert evento.puntuacion == 4
        assert r.respuesta is not None and r.respuesta.texto == "Gracias"
        assert (r.version, r.editada_en, r.mes_visita) == (3, AHORA, "2027-01")

    def test_la_visita_no_retrocede(self) -> None:
        r = resena()
        r.editar(TURISTA, 1, ContenidoResena(3), elegibilidad(date(2026, 1, 1)), AHORA)
        assert r.mes_visita == "2026-11"

    def test_solo_el_autor(self) -> None:
        with pytest.raises(NoEsDueno):
            resena().editar(DUENO, 1, ContenidoResena(3), None, AHORA)

    def test_con_version_vieja(self) -> None:
        with pytest.raises(VersionDistinta):
            resena().editar(TURISTA, 7, ContenidoResena(3), None, AHORA)

    @pytest.mark.parametrize("estado", [EstadoResena.EN_REVISION, EstadoResena.OCULTA])
    def test_no_se_edita_en_moderacion(self, estado: EstadoResena) -> None:
        r = en_estado(estado)
        with pytest.raises(ResenaEnModeracion):
            r.editar(TURISTA, r.version, ContenidoResena(3), None, AHORA)


class TestResponder:
    def test_crea_y_reemplaza_la_respuesta(self) -> None:
        r = resena()
        r.responder(DUENO, dueno(), 1, "  Gracias  ", AHORA)
        r.responder(DUENO, dueno(), 2, "Gracias por venir", AHORA)
        assert r.respuesta is not None
        assert (r.respuesta.texto, r.version) == ("Gracias por venir", 3)

    def test_en_revision_si_se_responde(self) -> None:
        r = en_estado(EstadoResena.EN_REVISION)
        r.responder(DUENO, dueno(), r.version, "Nuestra versión", AHORA)
        assert r.respuesta is not None

    def test_oculta_no_se_responde(self) -> None:
        r = en_estado(EstadoResena.OCULTA)
        with pytest.raises(ResenaEnModeracion):
            r.responder(DUENO, dueno(), r.version, "Hola", AHORA)

    @pytest.mark.parametrize("con_proyeccion", [True, False])
    def test_solo_el_dueno_del_servicio(self, con_proyeccion: bool) -> None:
        with pytest.raises(NoEsDueno):
            resena().responder(TURISTA, dueno() if con_proyeccion else None, 1, "Hola", AHORA)

    def test_texto_vacio(self) -> None:
        with pytest.raises(DatoInvalido):
            resena().responder(DUENO, dueno(), 1, "   ", AHORA)


class TestReportar:
    def test_dos_reportes_no_la_ocultan_y_el_tercero_si(self) -> None:
        r = resena()
        assert r.recibir_reporte(reporte(r)) is False
        assert r.recibir_reporte(reporte(r)) is False
        # Sin cambio de estado no sube la versión: el autor puede seguir editando.
        assert (r.estado, r.version) == (EstadoResena.PUBLICADA, 1)

        assert r.recibir_reporte(reporte(r)) is True
        assert (r.estado, r.reportes_pendientes, r.version) == (EstadoResena.EN_REVISION, 3, 2)

    def test_el_reporte_del_dueno_la_pasa_a_revision(self) -> None:
        r = resena()
        assert r.recibir_reporte(reporte(r, DUENO, Rol.PRESTADOR, es_dueno=True)) is True
        assert r.estado is EstadoResena.EN_REVISION

    def test_el_autor_no_reporta_la_suya(self) -> None:
        r = resena()
        with pytest.raises(ResenaPropia):
            r.recibir_reporte(reporte(r, TURISTA))

    @pytest.mark.parametrize("estado", [EstadoResena.EN_REVISION, EstadoResena.OCULTA])
    def test_solo_se_reporta_una_publicada(self, estado: EstadoResena) -> None:
        r = en_estado(estado)
        with pytest.raises(NoEncontrado):
            r.recibir_reporte(reporte(r))


class TestModerar:
    def test_publicar_una_publicada_cierra_reportes_sin_evento(self) -> None:
        r = resena()
        r.recibir_reporte(reporte(r))

        assert r.moderar(ADMIN, 1, PUBLICAR, None, AHORA) is None
        assert (r.estado, r.reportes_pendientes, r.version) == (EstadoResena.PUBLICADA, 0, 2)

    def test_publicar_una_en_revision_no_emite_evento(self) -> None:
        r = en_estado(EstadoResena.EN_REVISION)
        assert r.moderar(ADMIN, r.version, PUBLICAR, None, AHORA) is None
        assert (r.estado, r.reportes_pendientes) == (EstadoResena.PUBLICADA, 0)

    def test_publicar_una_oculta_vuelve_a_contar(self) -> None:
        r = en_estado(EstadoResena.OCULTA)
        evento = r.moderar(ADMIN, r.version, PUBLICAR, None, AHORA)
        assert isinstance(evento, ResenaPublicada)
        assert r.estado is EstadoResena.PUBLICADA

    @pytest.mark.parametrize("estado", [EstadoResena.PUBLICADA, EstadoResena.EN_REVISION])
    def test_ocultar_la_quita_del_promedio(self, estado: EstadoResena) -> None:
        r = en_estado(estado)
        evento = r.moderar(ADMIN, r.version, OCULTAR, " Datos personales ", AHORA)

        assert evento == ResenaOcultada(
            resena_id=r.id,
            servicio_id=SERVICIO,
            turista_id=TURISTA,
            puntuacion=4,
            moderada_por=ADMIN,
            motivo="Datos personales",
            ocurrido_en=AHORA,
        )
        assert (r.estado, r.reportes_pendientes) == (EstadoResena.OCULTA, 0)

    def test_ocultar_una_oculta_no_cambia_nada(self) -> None:
        r = en_estado(EstadoResena.OCULTA)
        version = r.version
        assert r.moderar(ADMIN, version, OCULTAR, "Otra vez", AHORA) is None
        assert r.version == version

    @pytest.mark.parametrize("motivo", [None, "  "])
    def test_ocultar_exige_motivo(self, motivo: str | None) -> None:
        with pytest.raises(DatoInvalido):
            resena().moderar(ADMIN, 1, OCULTAR, motivo, AHORA)

    def test_con_version_vieja(self) -> None:
        with pytest.raises(VersionDistinta):
            resena().moderar(ADMIN, 9, PUBLICAR, None, AHORA)
