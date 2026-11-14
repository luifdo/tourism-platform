from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.application.use_cases.escritura_zona import EscrituraZona
from app.domain.entities.zona import Zona
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import PoligonoGeoJSON
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad
from app.domain.value_objects.texto_traducido import TextoTraducido


class CrearZona:
    """La Entidad agrega una zona; los servicios que caen dentro pasan a ella."""

    def __init__(
        self, unidad_de_trabajo: FabricaUnidadDeTrabajo, escritura: EscrituraZona, reloj: Reloj
    ) -> None:
        self._uow = unidad_de_trabajo
        self._escritura = escritura
        self._reloj = reloj

    async def execute(
        self,
        identidad: Identidad,
        codigo: CodigoZona,
        nombre: TextoTraducido,
        poligono: PoligonoGeoJSON,
    ) -> Zona:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        zona = Zona.crear(codigo, nombre, poligono)
        async with self._uow() as uow:
            await self._escritura.guardar_y_auditar(
                uow, zona, identidad, "ZONA_CREADA", self._reloj.ahora(), reasignar=True
            )
            await uow.confirmar()
        await self._escritura.despues_de_confirmar()
        return zona
