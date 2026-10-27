"""Textos fijos de la plataforma que la ficha muestra en el idioma pedido.

La regla base de cancelación la aplica booking-service (Guía Técnica del Módulo de Reservas
§4.3); aquí solo se muestra. Si booking cambia la regla, hay que cambiar este texto.
"""

from app.domain.value_objects.idioma import Idioma

REGLA_BASE_CANCELACION: dict[Idioma, str] = {
    Idioma.ES: (
        "Regla de la plataforma: puedes cancelar una reserva solicitada en cualquier momento "
        "y una confirmada hasta las 23:59 del día anterior a la fecha reservada. El prestador "
        "puede cancelar una reserva confirmada indicando el motivo. La política del prestador "
        "puede ser más flexible, nunca más estricta."
    ),
    Idioma.EN: (
        "Platform rule: you can cancel a requested booking at any time and a confirmed one "
        "until 23:59 on the day before the booked date. The provider may cancel a confirmed "
        "booking stating the reason. The provider's policy may be more flexible, never stricter."
    ),
}
