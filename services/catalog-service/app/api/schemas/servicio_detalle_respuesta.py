from typing import Any

from app.api.i18n.atributos_publicos import atributos_publicos
from app.api.i18n.textos_plataforma import REGLA_BASE_CANCELACION
from app.api.schemas.alerta_respuesta import AlertaRespuesta
from app.api.schemas.aviso_pagos_respuesta import AvisoPagosRespuesta
from app.api.schemas.prestador_publico_respuesta import PrestadorPublicoRespuesta
from app.api.schemas.servicio_resumen_respuesta import ServicioResumenRespuesta
from app.application.dto.servicio_detalle import ServicioDetalle
from app.domain.value_objects.idioma import Idioma


class ServicioDetalleRespuesta(ServicioResumenRespuesta):
    descripcion: str
    capacidad_aforo_diario: int
    imagenes_urls: list[str]
    prestador: PrestadorPublicoRespuesta
    # La que aplica booking; va junto a la política (informativa) del prestador.
    regla_base_cancelacion: str
    alertas: list[AlertaRespuesta]
    atributos: dict[str, Any]
    etiquetas: dict[str, str]
    aviso_pagos: AvisoPagosRespuesta | None

    @classmethod
    def desde(cls, detalle: ServicioDetalle, idioma: Idioma) -> "ServicioDetalleRespuesta":  # type: ignore[override]
        resumen = ServicioResumenRespuesta.desde(detalle.resumen, idioma)
        atributos, etiquetas = atributos_publicos(detalle.atributos, idioma)
        return cls(
            **resumen.model_dump(),
            descripcion=detalle.descripcion.en_idioma(idioma)[0],
            capacidad_aforo_diario=detalle.capacidad_aforo_diario,
            imagenes_urls=list(detalle.imagenes_urls),
            prestador=PrestadorPublicoRespuesta.desde(detalle.prestador, idioma),
            regla_base_cancelacion=REGLA_BASE_CANCELACION[idioma],
            alertas=[AlertaRespuesta.desde(a, idioma) for a in detalle.alertas],
            atributos=atributos,
            etiquetas=etiquetas,
            aviso_pagos=AvisoPagosRespuesta.desde(detalle.atributos.pagos, idioma),
        )
