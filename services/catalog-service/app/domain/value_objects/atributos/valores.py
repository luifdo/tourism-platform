"""Valores fijos de los atributos por tipo de servicio. Códigos estables; la PWA los traduce."""

from enum import StrEnum


class BloqueAtributos(StrEnum):
    """Grupos de atributos; cada tipo de servicio usa los que le corresponden."""

    COMUNES = "comunes"
    ALOJAMIENTO = "alojamiento"
    EXPERIENCIA = "experiencia"
    GASTRONOMIA = "gastronomia"
    ENTRADA = "entrada"
    ALQUILER = "alquiler"
    TRANSPORTE = "transporte"
    PAGOS = "pagos"


class NivelFisico(StrEnum):
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"


class TipoHabitacion(StrEnum):
    PRIVADA = "PRIVADA"
    COMPARTIDA = "COMPARTIDA"
    DORMITORIO = "DORMITORIO"
    SUITE = "SUITE"
    CABANA = "CABANA"
    CARPA = "CARPA"


class Amenidad(StrEnum):
    WIFI = "WIFI"
    AIRE_ACONDICIONADO = "AIRE_ACONDICIONADO"
    VENTILADOR = "VENTILADOR"
    AGUA_CALIENTE = "AGUA_CALIENTE"
    PISCINA = "PISCINA"
    PARQUEADERO = "PARQUEADERO"
    COCINA_COMPARTIDA = "COCINA_COMPARTIDA"
    LAVANDERIA = "LAVANDERIA"


class TipoCocina(StrEnum):
    CARIBENA = "CARIBENA"
    DE_MAR = "DE_MAR"
    COLOMBIANA = "COLOMBIANA"
    INTERNACIONAL = "INTERNACIONAL"
    VEGETARIANA = "VEGETARIANA"
    CAFE_Y_POSTRES = "CAFE_Y_POSTRES"
    COMIDA_RAPIDA = "COMIDA_RAPIDA"


class OpcionDietaria(StrEnum):
    VEGETARIANA = "VEGETARIANA"
    VEGANA = "VEGANA"
    SIN_GLUTEN = "SIN_GLUTEN"
    SIN_LACTOSA = "SIN_LACTOSA"


class TipoVisitante(StrEnum):
    GENERAL = "GENERAL"
    NACIONAL = "NACIONAL"
    EXTRANJERO = "EXTRANJERO"
    NINO = "NINO"
    ESTUDIANTE = "ESTUDIANTE"
    ADULTO_MAYOR = "ADULTO_MAYOR"


class ServicioEnSitio(StrEnum):
    BANOS = "BANOS"
    DUCHAS = "DUCHAS"
    SALVAVIDAS = "SALVAVIDAS"
    COMIDA = "COMIDA"
    PARQUEADERO = "PARQUEADERO"
    CASILLEROS = "CASILLEROS"


class SenalInternet(StrEnum):
    CON_SENAL = "CON_SENAL"
    INTERMITENTE = "INTERMITENTE"
    SIN_SENAL = "SIN_SENAL"


class MedioPago(StrEnum):
    EFECTIVO = "EFECTIVO"
    TARJETA = "TARJETA"
    TRANSFERENCIA = "TRANSFERENCIA"  # Nequi, Daviplata, Bre-B

    @property
    def digital(self) -> bool:
        return self is not MedioPago.EFECTIVO


class RecomendacionDinero(StrEnum):
    """Qué conviene llevar: dinero físico, virtual o cualquiera de los dos."""

    EFECTIVO = "EFECTIVO"
    DIGITAL = "DIGITAL"
    CUALQUIERA = "CUALQUIERA"
