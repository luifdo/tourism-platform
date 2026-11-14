from uuid import UUID

from app.application.use_cases.acceso_prestador import FabricaUnidadDeTrabajo
from app.application.use_cases.escritura_zona import EscrituraZona
from app.domain.entities.zona import Zona
from app.domain.errors import NoEncontrado
from app.domain.ports.reloj import Reloj
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import PoligonoGeoJSON
from app.domain.value_objects.identidad import ROLES_ENTIDAD, Identidad
from app.domain.value_objects.texto_traducido import TextoTraducido


class EditarZona:
    """La Entidad corrige código, nombre o polígono con la versión que leyó (`If-Match`).

    Solo si cambió el polígono se reasignan los servicios; renombrar no los toca.
    """

    def __init__(
        self, unidad_de_trabajo: FabricaUnidadDeTrabajo, escritura: EscrituraZona, reloj: Reloj
    ) -> None:
        self._uow = unidad_de_trabajo
        self._escritura = escritura
        self._reloj = reloj

    async def execute(
        self,
        identidad: Identidad,
        zona_id: UUID,
        version_esperada: int,
        codigo: CodigoZona,
        nombre: TextoTraducido,
        poligono: PoligonoGeoJSON,
    ) -> Zona:
        identidad.exigir_rol(*ROLES_ENTIDAD)
        async with self._uow() as uow:
            zona = await uow.zonas.obtener(zona_id)
            if zona is None:
                raise NoEncontrado(recurso="zona", id=str(zona_id))
            cambio_poligono = zona.editar(version_esperada, codigo, nombre, poligono)
            await self._escritura.guardar_y_auditar(
                uow,
                zona,
                identidad,
                "ZONA_EDITADA",
                self._reloj.ahora(),
                reasignar=cambio_poligono,
                poligono_cambiado=cambio_poligono,
            )
            await uow.confirmar()
        await self._escritura.despues_de_confirmar()
        return zona
