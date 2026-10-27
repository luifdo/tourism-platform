"""Aviso de dinero y pagos en el lugar para la ficha pública y el chatbot, en el idioma pedido.

Ejemplo: «Lleva efectivo: no hay señal de internet y no hay cajeros cerca (el más cercano:
Parque de Minca, a 8 km). El prestador ofrece crédito: si no tienes cómo pagar, le pagas
después (plazo: 3 días)…».
"""

from app.domain.value_objects.atributos.bloque_pagos import BloquePagos
from app.domain.value_objects.atributos.valores import (
    MedioPago,
    RecomendacionDinero,
    SenalInternet,
)
from app.domain.value_objects.idioma import Idioma

_ES, _EN = Idioma.ES, Idioma.EN

_RECOMENDACION = {
    RecomendacionDinero.EFECTIVO: {_ES: "Lleva efectivo", _EN: "Bring cash"},
    RecomendacionDinero.DIGITAL: {
        _ES: "Lleva tarjeta o billetera digital",
        _EN: "Bring a card or digital wallet",
    },
    RecomendacionDinero.CUALQUIERA: {
        _ES: "Puedes pagar en efectivo o con medios digitales",
        _EN: "You can pay in cash or digitally",
    },
}
_SENAL = {
    SenalInternet.SIN_SENAL: {_ES: "no hay señal de internet", _EN: "there is no internet signal"},
    SenalInternet.INTERMITENTE: {
        _ES: "la señal de internet es intermitente",
        _EN: "the internet signal is unreliable",
    },
}
_SOLO_EFECTIVO = {_ES: "solo se acepta efectivo", _EN: "only cash is accepted"}
_SIN_CAJEROS = {_ES: "no hay cajeros cerca", _EN: "there are no ATMs nearby"}
_CAJERO_MAS_CERCANO = {_ES: "el más cercano: {lugar}", _EN: "nearest one: {lugar}"}
_A_DISTANCIA = {_ES: "a {km} km", _EN: "{km} km away"}
_Y = {_ES: " y ", _EN: " and "}
_CREDITO = {
    _ES: "El prestador ofrece crédito: si no tienes cómo pagar, le pagas después",
    _EN: "The provider offers credit: if you can't pay on the spot, you pay them later",
}
_PLAZO = {_ES: "plazo: {dias} días", _EN: "within {dias} days"}
_ACUERDO = {
    _ES: "Es un acuerdo con el prestador; la plataforma no lo cobra ni lo garantiza.",
    _EN: "This is an agreement with the provider; the platform does not collect or guarantee it.",
}


def es_importante(pagos: BloquePagos) -> bool:
    """La ficha lo destaca si puede faltar con qué pagar: sin señal, solo efectivo o sin cajeros."""
    sin_cajeros = pagos.cajeros is not None and not pagos.cajeros.hay_cerca
    return (
        pagos.senal_internet is not SenalInternet.CON_SENAL
        or pagos.medios_pago == (MedioPago.EFECTIVO,)
        or sin_cajeros
    )


def mensaje_aviso(pagos: BloquePagos, idioma: Idioma) -> str:
    motivos: list[str] = []
    if pagos.senal_internet in _SENAL:
        motivos.append(_SENAL[pagos.senal_internet][idioma])
    if pagos.medios_pago == (MedioPago.EFECTIVO,):
        motivos.append(_SOLO_EFECTIVO[idioma])
    if pagos.cajeros is not None and not pagos.cajeros.hay_cerca:
        motivos.append(_SIN_CAJEROS[idioma] + _cajero_mas_cercano(pagos, idioma))

    frase = _RECOMENDACION[pagos.recomendacion_dinero][idioma]
    if motivos:
        frase += ": " + ", ".join(motivos[:-1]) + (_Y[idioma] if len(motivos) > 1 else "")
        frase += motivos[-1]
    partes = [frase + "."]

    credito = pagos.credito
    if credito.ofrece:
        texto = _CREDITO[idioma]
        if credito.plazo_dias:
            texto += f" ({_PLAZO[idioma].format(dias=credito.plazo_dias)})"
        partes.append(texto + ".")
        if credito.condiciones:
            partes.append(credito.condiciones.en_idioma(idioma)[0].rstrip(".") + ".")
        partes.append(_ACUERDO[idioma])
    return " ".join(partes)


def _cajero_mas_cercano(pagos: BloquePagos, idioma: Idioma) -> str:
    cajeros = pagos.cajeros
    if cajeros is None or (cajeros.referencia is None and cajeros.distancia_km is None):
        return ""
    detalles = []
    if cajeros.referencia:
        lugar = cajeros.referencia.en_idioma(idioma)[0]
        detalles.append(_CAJERO_MAS_CERCANO[idioma].format(lugar=lugar))
    if cajeros.distancia_km is not None:
        detalles.append(_A_DISTANCIA[idioma].format(km=f"{cajeros.distancia_km:g}"))
    return " (" + ", ".join(detalles) + ")"
