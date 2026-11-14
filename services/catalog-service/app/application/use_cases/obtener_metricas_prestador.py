from app.application.dto.metricas_prestador import MetricasPrestador
from app.application.dto.metricas_servicio import MetricasServicio
from app.application.dto.rango_fechas import RangoFechas
from app.application.ports.consulta_analitica import ConsultaAnalitica
from app.application.ports.consulta_prestador import ConsultaPrestador
from app.application.use_cases.acceso_prestador import exigir_perfil
from app.domain.value_objects.identidad import Identidad, Rol


class ObtenerMetricasPrestador:
    """UC22: rendimiento de cada oferta del prestador en un rango (por fecha de la visita).

    Un perfil suspendido también puede verlas, igual que puede leer su perfil y servicios.
    """

    def __init__(self, prestador: ConsultaPrestador, analitica: ConsultaAnalitica) -> None:
        self._prestador = prestador
        self._analitica = analitica

    async def execute(self, identidad: Identidad, rango: RangoFechas) -> MetricasPrestador:
        identidad.exigir_rol(Rol.PRESTADOR)
        perfil = exigir_perfil(await self._prestador.perfil_de_usuario(identidad.usuario_id))
        filas = await self._analitica.metricas_prestador(perfil.id, rango)
        servicios = tuple(
            MetricasServicio(
                servicio_id=f.servicio_id,
                nombre=f.nombre,
                reservas=f.reservas,
                personas_finalizadas=f.personas_finalizadas,
                # Sin tope: el aforo es la capacidad recomendada y se puede superar.
                ocupacion=round(
                    f.personas_finalizadas / (f.capacidad_aforo_diario * rango.dias), 4
                ),
                calificacion_promedio=f.calificacion_promedio,
                total_resenas=f.total_resenas,
                intenciones_visita=f.intenciones_visita,
            )
            for f in filas
        )
        return MetricasPrestador(rango=rango, servicios=servicios)
