"""Publicador en memoria: guarda los sobres en una lista (pruebas y demo sin RabbitMQ)."""

from typing import Any


class PublicadorMemoria:
    def __init__(self) -> None:
        self.publicados: list[dict[str, Any]] = []

    async def publicar(self, sobres: list[dict[str, Any]]) -> None:
        self.publicados.extend(sobres)

    def tipos(self) -> list[str]:
        return [s["event_type"] for s in self.publicados]
