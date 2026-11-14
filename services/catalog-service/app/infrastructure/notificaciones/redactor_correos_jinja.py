"""Correos de reservas con plantillas Jinja en español e inglés (implementa RedactorCorreos).

* Plantillas en `plantillas/{plantilla}.{es|en}.{html|txt}`; el HTML hereda de `base.html`.
* Escapado automático en el HTML: el nombre del servicio o el motivo los escribe un usuario.
* `StrictUndefined`: una variable que falte rompe la prueba, no llega vacía al correo.
* El aviso de pagos y la regla base de cancelación son los mismos textos de la ficha.
"""

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.api.i18n.aviso_pagos import es_importante, mensaje_aviso
from app.api.i18n.textos_plataforma import REGLA_BASE_CANCELACION
from app.application.dto.correo import Correo
from app.application.dto.datos_correo_reserva import DatosCorreoReserva
from app.application.dto.plantilla_correo import PlantillaCorreo
from app.domain.value_objects.idioma import Idioma
from app.infrastructure.notificaciones.formato_fechas import fecha_larga, fecha_y_hora

PLANTILLAS = Path(__file__).parent / "plantillas"
_P, _ES, _EN = PlantillaCorreo, Idioma.ES, Idioma.EN

ASUNTOS: dict[PlantillaCorreo, dict[Idioma, str]] = {
    _P.SOLICITUD: {
        _ES: "Nueva solicitud de reserva: {servicio}",
        _EN: "New booking request: {servicio}",
    },
    _P.MODIFICACION: {
        _ES: "Solicitud modificada: {servicio}",
        _EN: "Booking request changed: {servicio}",
    },
    _P.CONFIRMACION: {
        _ES: "Reserva confirmada: {servicio}",
        _EN: "Booking confirmed: {servicio}",
    },
    _P.RECHAZO: {
        _ES: "Tu solicitud no fue aceptada: {servicio}",
        _EN: "Your request was not accepted: {servicio}",
    },
    _P.CANCELACION: {
        _ES: "Reserva cancelada: {servicio}",
        _EN: "Booking cancelled: {servicio}",
    },
}


class RedactorCorreosJinja:
    def __init__(self, directorio: Path = PLANTILLAS) -> None:
        self._entorno = Environment(
            loader=FileSystemLoader(directorio),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def redactar(self, plantilla: PlantillaCorreo, datos: DatosCorreoReserva) -> Correo:
        idioma = datos.destinatario.idioma
        contexto = _contexto(datos, idioma)
        nombre = f"{plantilla.value}.{idioma.value}"
        return Correo(
            destinatario=datos.destinatario.email,
            asunto=ASUNTOS[plantilla][idioma].format(servicio=contexto["servicio"]),
            html=self._entorno.get_template(f"{nombre}.html").render(contexto),
            texto=self._entorno.get_template(f"{nombre}.txt").render(contexto),
        )


def _contexto(datos: DatosCorreoReserva, idioma: Idioma) -> dict[str, Any]:
    perfil, pagos = datos.prestador, datos.pagos
    politica = perfil.politica_cancelacion
    return {
        "idioma": idioma.value,
        "nombre": datos.destinatario.nombre,
        "servicio": datos.servicio.en_idioma(idioma)[0],
        "fecha": fecha_larga(datos.fecha_reserva, idioma),
        "personas": datos.numero_personas,
        "prestador": perfil.razon_social or "",
        "telefono": perfil.telefono,
        "direccion": perfil.direccion,
        "politica": politica.en_idioma(idioma)[0] if politica else None,
        "regla_base": REGLA_BASE_CANCELACION[idioma],
        "aviso_pagos": mensaje_aviso(pagos, idioma) if pagos else None,
        "aviso_importante": es_importante(pagos) if pagos else False,
        "motivo": datos.motivo,
        "cancelada_por_turista": datos.cancelada_por_turista,
        "fecha_anterior": fecha_larga(datos.fecha_anterior, idioma)
        if datos.fecha_anterior
        else None,
        "personas_anterior": datos.numero_personas_anterior,
        "expira": fecha_y_hora(datos.expira_en, idioma) if datos.expira_en else None,
    }
