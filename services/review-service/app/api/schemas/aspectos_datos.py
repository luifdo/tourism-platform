from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from app.domain.value_objects.aspecto import Aspecto

PuntuacionDatos = Annotated[int, Field(strict=True, ge=1, le=5)]


class AspectosDatos(BaseModel):
    """Calificación opcional de 1 a 5 por aspecto (contrato `Aspectos`); un aspecto
    desconocido es un error de validación."""

    model_config = ConfigDict(extra="forbid")

    LIMPIEZA: PuntuacionDatos | None = None
    ATENCION: PuntuacionDatos | None = None
    CALIDAD_PRECIO: PuntuacionDatos | None = None
    SEGURIDAD: PuntuacionDatos | None = None
    GUIANZA: PuntuacionDatos | None = None

    def a_dominio(self) -> dict[Aspecto, int]:
        return {Aspecto(a): v for a, v in self.model_dump(exclude_none=True).items()}

    @classmethod
    def desde(cls, aspectos: dict[Aspecto, int]) -> "AspectosDatos":
        return cls(**{a.value: v for a, v in aspectos.items()})
