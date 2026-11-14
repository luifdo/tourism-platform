import asyncio
from dataclasses import dataclass

from src.application.ports.sonda import Sonda


@dataclass(frozen=True)
class EstadoSalud:
    base_de_datos: bool
    valkey: bool

    @property
    def sano(self) -> bool:
        return self.base_de_datos and self.valkey


class VerificarSalud:
    """No consulta al proveedor de IA: si este falla, el pod sigue sano (contrato, /health)."""

    def __init__(self, base_de_datos: Sonda, valkey: Sonda) -> None:
        self._base_de_datos = base_de_datos
        self._valkey = valkey

    async def ejecutar(self) -> EstadoSalud:
        base_de_datos, valkey = await asyncio.gather(
            self._base_de_datos.ping(), self._valkey.ping()
        )
        return EstadoSalud(base_de_datos=base_de_datos, valkey=valkey)
