from datetime import date

from app.application.dto.capacidad_zona import CapacidadZona
from app.application.dto.servicio_con_bandera import ServicioConBandera
from app.application.ports.consulta_capacidad import ConsultaCapacidad
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.services.calculadora_saturacion import CalculadoraSaturacion
from app.domain.value_objects.identidad import Identidad, Rol

ROLES_CAPACIDAD = (Rol.ENTIDAD, Rol.ADMIN, Rol.TURISTA)


class ConsultarCapacidad:
    """UC24: presión sobre la capacidad de carga por zona en un día (hoy por defecto).

    Índice = personas en reservas activas ÷ capacidad de carga. Se calcula al consultar
    (caché de 5 min), no con un CronJob. Las zonas sin capacidad (sin servicios) no salen.
    El turista solo ve el nivel; eso lo recorta el adaptador HTTP.
    """

    def __init__(self, consulta: ConsultaCapacidad, reloj: Reloj) -> None:
        self._consulta = consulta
        self._reloj = reloj
        self._calculadora = CalculadoraSaturacion()

    async def execute(
        self, identidad: Identidad, fecha: date | None = None, zona: str | None = None
    ) -> list[CapacidadZona]:
        identidad.exigir_rol(*ROLES_CAPACIDAD)
        fecha = fecha or self._reloj.hoy()
        cargas = await self._consulta.cargas(fecha, zona)
        if zona is not None and not cargas.zonas:
            raise NoEncontrado(recurso="zona", id=zona)
        resultado = []
        for de_zona in cargas.zonas:
            saturacion = self._calculadora.de_zona(s.carga for s in de_zona.servicios)
            if saturacion is None:
                continue
            banderas = []
            for servicio in de_zona.servicios:
                propio = self._calculadora.de_servicio(servicio.carga)
                if propio is not None and propio.bandera:
                    banderas.append(
                        ServicioConBandera(servicio.servicio_id, servicio.nombre, propio.indice)
                    )
            resultado.append(
                CapacidadZona(
                    zona_id=de_zona.zona_id,
                    zona=de_zona.zona,
                    fecha=fecha,
                    saturacion=saturacion,
                    servicios_con_bandera=tuple(
                        sorted(banderas, key=lambda b: b.indice, reverse=True)
                    ),
                    calculado_en=cargas.leido_en,
                )
            )
        # Las más presionadas primero: es lo que la Entidad necesita ver.
        return sorted(resultado, key=lambda c: c.saturacion.indice, reverse=True)
