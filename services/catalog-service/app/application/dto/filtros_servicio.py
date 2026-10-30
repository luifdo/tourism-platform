import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.domain.errors import DatoInvalido
from app.domain.value_objects.atributos.valores import NivelFisico, OpcionDietaria
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.tipo_servicio import TipoServicio

_IDIOMA = re.compile(r"^[a-z]{2}$")


@dataclass(frozen=True, slots=True)
class FiltrosServicio:
    """Filtros de tipo, unidad y atributos que comparten la búsqueda (UC8) y el mapa (UC16).

    Así la lista y el mapa de la PWA muestran lo mismo con los mismos filtros. Un sí/no
    filtra por lo que el prestador informó: `accesible=False` trae los que dijeron que no,
    no los que no lo informaron.

    Con `fecha` se excluyen los servicios que, según booking, no tienen cupo para
    `personas` ese día (o lo tienen cerrado). Los que aún no tienen dato de ese día se
    muestran como "disponibilidad sin confirmar": no se esconden mientras booking no
    haya publicado su calendario.
    """

    tipos: tuple[TipoServicio, ...] = field(default_factory=tuple)
    unidad_tarifa: UnidadTarifa | None = None
    idioma_atencion: str | None = None
    accesible: bool | None = None
    mascotas: bool | None = None
    apto_ninos: bool | None = None
    opcion_dietaria: OpcionDietaria | None = None
    nivel_fisico: NivelFisico | None = None
    acepta_pago_digital: bool | None = None
    ofrece_credito: bool | None = None
    fecha: date | None = None
    personas: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "tipos", tuple(sorted(set(self.tipos))))
        if self.idioma_atencion is not None and not _IDIOMA.match(self.idioma_atencion):
            raise DatoInvalido(campo="idioma_atencion", regla="formato")
        if self.personas < 1:
            raise DatoInvalido(campo="personas", regla="minimo", minimo=1)
        if self.personas != 1 and self.fecha is None:
            raise DatoInvalido(campo="personas", regla="requiere", requiere="fecha")

    def filtro_atributos(self) -> dict[str, Any] | None:
        """Objeto para `atributos @> filtro` (índice GIN), o None si no hay filtros de atributos.

        Usa los mismos nombres que `AtributosServicio.a_json()`.
        """
        comunes = {
            clave: valor
            for clave, valor in (
                ("accesible", self.accesible),
                ("mascotas", self.mascotas),
                ("apto_ninos", self.apto_ninos),
            )
            if valor is not None
        }
        if self.idioma_atencion:
            comunes["idiomas_atencion"] = [self.idioma_atencion]
        filtro: dict[str, Any] = {"comunes": comunes} if comunes else {}
        if self.opcion_dietaria:
            filtro["gastronomia"] = {"opciones_dietarias": [self.opcion_dietaria.value]}
        if self.nivel_fisico:
            filtro["experiencia"] = {"nivel_fisico": self.nivel_fisico.value}
        pagos: dict[str, Any] = {}
        if self.acepta_pago_digital is not None:
            pagos["acepta_pago_digital"] = self.acepta_pago_digital
        if self.ofrece_credito is not None:
            pagos["credito"] = {"ofrece": self.ofrece_credito}
        if pagos:
            filtro["pagos"] = pagos
        return filtro or None
