from dataclasses import dataclass
from datetime import date, datetime

from app.application.dto.contacto_usuario import ContactoUsuario
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.atributos.bloque_pagos import BloquePagos
from app.domain.value_objects.texto_traducido import TextoTraducido


@dataclass(frozen=True, slots=True)
class DatosCorreoReserva:
    """Todo lo que una plantilla de correo de reserva puede mostrar."""

    destinatario: ContactoUsuario
    servicio: TextoTraducido
    fecha_reserva: date
    numero_personas: int
    prestador: PrestadorPerfil
    pagos: BloquePagos | None = None
    motivo: str | None = None
    cancelada_por_turista: bool = False
    fecha_anterior: date | None = None
    numero_personas_anterior: int | None = None
    expira_en: datetime | None = None
