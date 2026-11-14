from dataclasses import dataclass
from enum import StrEnum

from app.domain.value_objects.atributos.valores import BloqueAtributos as B
from app.domain.value_objects.catalogos import Categoria


@dataclass(frozen=True, slots=True)
class ReglaTipo:
    """Categoría del tipo y qué bloques de atributos usa.

    `principal` es obligatorio; `opcionales` se pueden agregar. Los comunes y los de pagos
    los admiten todos los tipos.
    """

    categoria: Categoria
    principal: B
    opcionales: frozenset[B] = frozenset()

    @property
    def permitidos(self) -> frozenset[B]:
        return self.opcionales | {self.principal, B.COMUNES, B.PAGOS}


class TipoServicio(StrEnum):
    """Qué es la oferta. Define su categoría y el formulario que llena el prestador.

    Un establecimiento con varias ofertas (un hostal con tour y restaurante) registra un
    servicio por cada una: cada uno tiene su tarifa, aforo, reservas y reseñas.
    """

    HOTEL = "HOTEL"
    HOSTAL = "HOSTAL"
    POSADA_ECOHOTEL = "POSADA_ECOHOTEL"
    GLAMPING_CAMPING = "GLAMPING_CAMPING"
    APARTAMENTO_TURISTICO = "APARTAMENTO_TURISTICO"
    RESTAURANTE = "RESTAURANTE"
    CAFE_BAR = "CAFE_BAR"
    EXPERIENCIA_GASTRONOMICA = "EXPERIENCIA_GASTRONOMICA"
    TOUR_GUIADO = "TOUR_GUIADO"
    SENDERISMO = "SENDERISMO"
    DEPORTE_ACUATICO = "DEPORTE_ACUATICO"
    AVISTAMIENTO = "AVISTAMIENTO"
    RESERVA_PARQUE = "RESERVA_PARQUE"
    ACCESO_PLAYA = "ACCESO_PLAYA"
    ALQUILER_EQUIPO = "ALQUILER_EQUIPO"
    TOUR_CULTURAL = "TOUR_CULTURAL"
    MUSEO_SITIO = "MUSEO_SITIO"
    EXPERIENCIA_COMUNITARIA = "EXPERIENCIA_COMUNITARIA"
    EVENTO_FESTIVAL = "EVENTO_FESTIVAL"
    TRANSPORTE_MARITIMO = "TRANSPORTE_MARITIMO"
    TRASLADO_TERRESTRE = "TRASLADO_TERRESTRE"

    @property
    def regla(self) -> ReglaTipo:
        return REGLAS[self]

    @property
    def categoria(self) -> Categoria:
        return REGLAS[self].categoria


_C = Categoria
REGLAS: dict[TipoServicio, ReglaTipo] = {
    TipoServicio.HOTEL: ReglaTipo(_C.ALOJAMIENTO, B.ALOJAMIENTO),
    TipoServicio.HOSTAL: ReglaTipo(_C.ALOJAMIENTO, B.ALOJAMIENTO),
    TipoServicio.POSADA_ECOHOTEL: ReglaTipo(_C.ALOJAMIENTO, B.ALOJAMIENTO),
    TipoServicio.GLAMPING_CAMPING: ReglaTipo(_C.ALOJAMIENTO, B.ALOJAMIENTO),
    TipoServicio.APARTAMENTO_TURISTICO: ReglaTipo(_C.ALOJAMIENTO, B.ALOJAMIENTO),
    TipoServicio.RESTAURANTE: ReglaTipo(_C.GASTRONOMIA, B.GASTRONOMIA),
    TipoServicio.CAFE_BAR: ReglaTipo(_C.GASTRONOMIA, B.GASTRONOMIA),
    TipoServicio.EXPERIENCIA_GASTRONOMICA: ReglaTipo(
        _C.GASTRONOMIA, B.EXPERIENCIA, frozenset({B.GASTRONOMIA})
    ),
    TipoServicio.TOUR_GUIADO: ReglaTipo(_C.AVENTURA, B.EXPERIENCIA),
    TipoServicio.SENDERISMO: ReglaTipo(_C.AVENTURA, B.EXPERIENCIA),
    TipoServicio.DEPORTE_ACUATICO: ReglaTipo(_C.AVENTURA, B.EXPERIENCIA),
    TipoServicio.AVISTAMIENTO: ReglaTipo(_C.NATURALEZA, B.EXPERIENCIA),
    TipoServicio.RESERVA_PARQUE: ReglaTipo(_C.NATURALEZA, B.ENTRADA),
    TipoServicio.ACCESO_PLAYA: ReglaTipo(_C.PLAYA, B.ENTRADA),
    TipoServicio.ALQUILER_EQUIPO: ReglaTipo(_C.PLAYA, B.ALQUILER),
    TipoServicio.TOUR_CULTURAL: ReglaTipo(_C.CULTURA, B.EXPERIENCIA),
    TipoServicio.MUSEO_SITIO: ReglaTipo(_C.CULTURA, B.ENTRADA),
    TipoServicio.EXPERIENCIA_COMUNITARIA: ReglaTipo(_C.CULTURA, B.EXPERIENCIA),
    TipoServicio.EVENTO_FESTIVAL: ReglaTipo(_C.CULTURA, B.ENTRADA, frozenset({B.EXPERIENCIA})),
    TipoServicio.TRANSPORTE_MARITIMO: ReglaTipo(_C.TRANSPORTE, B.TRANSPORTE),
    TipoServicio.TRASLADO_TERRESTRE: ReglaTipo(_C.TRANSPORTE, B.TRANSPORTE),
}
