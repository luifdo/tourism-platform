from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.atributos.atributos_servicio_datos import AtributosServicioDatos
from app.api.schemas.coordenada_respuesta import CoordenadaRespuesta
from app.api.schemas.texto_traducido_datos import TextoTraducidoDatos
from app.domain.entities.atractivo_servicio import MAX_IMAGENES, DatosServicio
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.tipo_servicio import TipoServicio


class ServicioGuardar(BaseModel):
    """Cuerpo de UC17 (registrar) y UC18 (editar). Las reglas finas las valida el dominio.

    La categoría no se envía: sale de `tipo`.
    """

    model_config = ConfigDict(extra="forbid")

    nombre: TextoTraducidoDatos
    descripcion: TextoTraducidoDatos
    tipo: TipoServicio
    ubicacion: CoordenadaRespuesta
    tarifa_base: Decimal = Field(ge=0)
    unidad_tarifa: UnidadTarifa
    capacidad_aforo_diario: int = Field(ge=1)
    imagenes_urls: list[str] = Field(default_factory=list, max_length=MAX_IMAGENES)
    atributos: AtributosServicioDatos = Field(default_factory=AtributosServicioDatos)

    def a_dominio(self) -> DatosServicio:
        return DatosServicio(
            nombre=self.nombre.a_dominio(),
            descripcion=self.descripcion.a_dominio(),
            tipo=self.tipo,
            ubicacion=Coordenada(lat=self.ubicacion.lat, lon=self.ubicacion.lon),
            tarifa_base=Tarifa(self.tarifa_base),
            unidad_tarifa=self.unidad_tarifa,
            capacidad_aforo_diario=self.capacidad_aforo_diario,
            imagenes_urls=tuple(self.imagenes_urls),
            atributos=self.atributos.a_dominio(),
        )
