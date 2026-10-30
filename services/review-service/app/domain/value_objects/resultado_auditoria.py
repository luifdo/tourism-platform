from enum import StrEnum


class ResultadoAuditoria(StrEnum):
    """`resultado` de `auditoria.registrada.v1`."""

    EXITO = "EXITO"
    DENEGADO = "DENEGADO"
    ERROR = "ERROR"
