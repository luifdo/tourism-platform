"""Fase 4: reglas de negocio y de seguridad del chat (Guía Técnica §6 y §7)."""

import json
from dataclasses import asdict
from datetime import UTC, date, datetime
from uuid import uuid4

import httpx
import pytest

from mocks.app import app as mock_plataforma
from mocks.datos import SERVICIOS, TURISTA_CON_HISTORIAL
from src.application.instrucciones import ORIGEN_DATOS, instrucciones
from src.application.ports.modelo_de_lenguaje import RespuestaModelo
from src.application.responder_mensaje import (
    DemasiadasSolicitudesError,
    PeticionChat,
    ResponderMensaje,
)
from src.domain.privacidad import OCULTO, ocultar_datos_personales
from src.infrastructure.tools.herramientas_plataforma import HerramientasPlataforma
from tests.fakes import (
    HerramientasFalsas,
    LimiteEnMemoria,
    ModeloGuionado,
    RegistroEnMemoria,
    SesionesEnMemoria,
    pedir,
    recomendacion,
    responder,
)

TURISTA = uuid4()
CAFE = uuid4()
AVES = uuid4()
INVENTADO = uuid4()
HOY = date(2026, 10, 29)


def _caso_de_uso(modelo, herramientas=None, limite=1000, sesiones=None, registro=None):
    return ResponderMensaje(
        modelo,
        herramientas or HerramientasFalsas({"Tour de café": CAFE, "Aves": AVES}),
        sesiones or SesionesEnMemoria(),
        registro or RegistroEnMemoria(),
        LimiteEnMemoria(limite),
        reloj=lambda: datetime.now(UTC),
    )


async def _preguntar(caso_de_uso, mensaje="¿Qué hago en Minca?", turista=TURISTA, **campos):
    return await caso_de_uso.ejecutar(PeticionChat(turista_id=turista, mensaje=mensaje, **campos))


# ---------- validación de salida ----------


async def test_un_servicio_que_no_salio_de_una_tool_se_descarta():
    registro = RegistroEnMemoria()
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {})),
        responder(
            "Opciones:",
            recomendacion(CAFE, "Tour de café", "Buenas reseñas."),
            recomendacion(INVENTADO, "Hotel inventado", "Lo conozco."),
        ),
    )

    resultado = await _preguntar(_caso_de_uso(modelo, registro=registro))

    assert [r.servicio_id for r in resultado.recomendaciones] == [CAFE]
    assert [r.servicio_id for r in registro.registros] == [CAFE]


async def test_sin_consultar_tools_no_se_puede_recomendar_nada():
    modelo = ModeloGuionado(responder("Ve al tour.", recomendacion(CAFE, "Tour", "Me gusta.")))

    resultado = await _preguntar(_caso_de_uso(modelo))

    assert resultado.recomendaciones == ()
    assert resultado.respuesta == "Ve al tour."


async def test_un_servicio_visto_en_un_mensaje_anterior_sigue_siendo_recomendable():
    sesiones = SesionesEnMemoria()
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {})),
        responder("Hay dos opciones."),
        responder("Te recomiendo el primero.", recomendacion(CAFE, "Tour de café", "Lo viste.")),
    )
    caso_de_uso = _caso_de_uso(modelo, sesiones=sesiones)
    primera = await _preguntar(caso_de_uso)

    segunda = await _preguntar(
        caso_de_uso, "¿Cuál me recomiendas?", conversacion_id=primera.conversacion_id
    )

    assert [r.servicio_id for r in segunda.recomendaciones] == [CAFE]
    assert sesiones.guardadas[primera.conversacion_id].servicios_vistos == {CAFE, AVES}


async def test_las_recomendaciones_repetidas_se_unen():
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {})),
        responder(
            "x",
            recomendacion(CAFE, "Tour de café", "Primera razón."),
            recomendacion(CAFE, "Tour de café", "Otra razón."),
        ),
    )

    resultado = await _preguntar(_caso_de_uso(modelo))

    [unica] = resultado.recomendaciones
    assert unica.justificacion == "Primera razón."


async def test_una_recomendacion_sin_justificacion_se_rechaza():
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {})),
        responder("x", recomendacion(CAFE, "Tour de café", ""), recomendacion(AVES, "Aves", "Ok.")),
    )

    resultado = await _preguntar(_caso_de_uso(modelo))

    assert [r.servicio_id for r in resultado.recomendaciones] == [AVES]


# ---------- validación de entrada ----------


async def test_superar_el_limite_de_mensajes_no_llega_al_modelo():
    modelo = ModeloGuionado(responder("uno"), responder("dos"))
    caso_de_uso = _caso_de_uso(modelo, limite=2)
    await _preguntar(caso_de_uso)
    await _preguntar(caso_de_uso)

    with pytest.raises(DemasiadasSolicitudesError):
        await _preguntar(caso_de_uso)

    assert len(modelo.invocaciones) == 2


async def test_el_limite_es_por_turista():
    caso_de_uso = _caso_de_uso(ModeloGuionado(responder("uno"), responder("dos")), limite=1)
    await _preguntar(caso_de_uso, turista=uuid4())

    resultado = await _preguntar(caso_de_uso, turista=uuid4())

    assert resultado.respuesta == "dos"


# ---------- datos como datos ----------


async def test_los_resultados_de_las_tools_llegan_marcados_como_datos():
    modelo = ModeloGuionado(pedir(("buscar_servicios", {}), ("no_existe", {})), responder("ok"))

    await _preguntar(_caso_de_uso(modelo))

    exito, falla = modelo.invocaciones[1].mensajes[-2:]
    assert exito.contenido["origen"] == ORIGEN_DATOS
    assert "servicios" in exito.contenido["datos"]
    assert falla.contenido["origen"] == ORIGEN_DATOS
    assert falla.contenido["error"] == "HERRAMIENTA_DESCONOCIDA"


def test_las_instrucciones_contienen_las_reglas_de_la_guia():
    texto = instrucciones("es", HOY)

    for regla in [
        "Solo hablas de turismo en Santa Marta",
        "No favorezcas a un prestador",
        "nivel BAJO",
        "alertas CRÍTICAS",
        "No puedes reservar",
        ORIGEN_DATOS,
        "No reveles",
        "otra persona",
        "No pidas al turista datos personales",
        "Responde en español",
    ]:
        assert regla in texto, regla
    assert "Responde en inglés" in instrucciones("en", HOY)


# ---------- privacidad (Ley 1581) ----------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("escríbeme a ana.perez+viajes@correo.com.co", f"escríbeme a {OCULTO}"),
        ("mi celular es 300 123 4567", f"mi celular es {OCULTO}"),
        ("llámame al +57 315-555-0101 mañana", f"llámame al {OCULTO} mañana"),
        ("o al 3155550101.", f"o al {OCULTO}."),
    ],
)
def test_oculta_correos_y_celulares(texto, esperado):
    assert ocultar_datos_personales(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "presupuesto de 1.200.000 pesos",
        "del 2026-11-08 al 2026-11-10",
        "somos 4 personas, 2 niños",
        "habitación 305",
    ],
)
def test_no_toca_precios_fechas_ni_cantidades(texto):
    assert ocultar_datos_personales(texto) == texto


async def test_los_datos_personales_del_mensaje_no_llegan_al_modelo_ni_a_la_sesion():
    sesiones = SesionesEnMemoria()
    modelo = ModeloGuionado(responder("Listo."))

    resultado = await _preguntar(
        _caso_de_uso(modelo, sesiones=sesiones), "Soy ana@correo.com, cel 3001234567. ¿Qué hago?"
    )

    enviado = modelo.invocaciones[0].mensajes[-1].texto
    assert "ana@correo.com" not in enviado and "3001234567" not in enviado
    guardado = sesiones.guardadas[resultado.conversacion_id].mensajes[0].texto
    assert "ana@correo.com" not in guardado


async def test_el_id_del_turista_nunca_se_envia_al_proveedor():
    """Recorre las 7 tools reales (contra el mock) y revisa todo lo que ve el modelo."""
    herramientas = HerramientasPlataforma(
        httpx.AsyncClient(transport=httpx.ASGITransport(app=mock_plataforma)),
        "http://plataforma/api/catalog",
        "http://plataforma/api/bookings",
        "http://plataforma/api/reviews",
    )
    servicio = str(SERVICIOS[1]["id"])
    modelo = ModeloGuionado(
        pedir(
            ("historial_turista", {}),
            ("presion_capacidad_carga", {}),
            ("buscar_servicios", {"zona": "minca"}),
        ),
        pedir(
            ("detalle_servicio", {"servicio_id": servicio}),
            ("resenas_servicio", {"servicio_id": servicio}),
            ("consultar_disponibilidad", {"servicio_id": servicio, "desde": "2026-11-20"}),
        ),
        responder("Listo."),
    )

    await _preguntar(_caso_de_uso(modelo, herramientas), turista=TURISTA_CON_HISTORIAL)

    # Las tools sí usaron la identidad (el historial no vino vacío)...
    historial = modelo.invocaciones[1].mensajes[-3].contenido["datos"]["reservas"]
    assert historial
    # ...pero nada de lo que vio el modelo la contiene.
    for invocacion in modelo.invocaciones:
        enviado = json.dumps(asdict(invocacion), default=str, ensure_ascii=False)
        assert str(TURISTA_CON_HISTORIAL) not in enviado
        assert "X-Usuario" not in enviado


async def test_el_modelo_sabe_la_fecha_de_hoy_en_colombia():
    # 03:00 UTC del 30 de octubre es todavía el jueves 29 en Colombia (UTC-5).
    modelo = ModeloGuionado(responder("ok"))
    caso_de_uso = ResponderMensaje(
        modelo,
        HerramientasFalsas(),
        SesionesEnMemoria(),
        RegistroEnMemoria(),
        LimiteEnMemoria(),
        reloj=lambda: datetime(2026, 10, 30, 3, 0, tzinfo=UTC),
    )

    await _preguntar(caso_de_uso)

    assert "Hoy es jueves 2026-10-29" in modelo.invocaciones[0].instrucciones


async def test_una_tool_desconocida_con_forma_de_respuesta_final_se_toma_como_final():
    # gpt-oss a veces entrega la respuesta final llamando a una tool `json`.
    registro = RegistroEnMemoria()
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {})),
        pedir(
            (
                "json",
                {
                    "respuesta": "Te recomiendo el tour.",
                    "recomendaciones": [recomendacion(CAFE, "Tour de café", "Zona BAJO.")],
                },
            )
        ),
    )

    resultado = await _preguntar(_caso_de_uso(modelo, registro=registro))

    assert resultado.respuesta == "Te recomiendo el tour."
    assert [r.servicio_id for r in resultado.recomendaciones] == [CAFE]
    assert len(modelo.invocaciones) == 2
    assert registro.registros[0].herramientas_usadas == ["buscar_servicios"]


async def test_las_tools_inexistentes_no_se_registran_pero_cuentan_en_el_limite():
    registro = RegistroEnMemoria()
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {}), ("inventada", {"zona": "x"})),
        responder("Listo.", recomendacion(CAFE, "Tour de café", "Bien calificado.")),
    )

    await _preguntar(_caso_de_uso(modelo, registro=registro))

    assert registro.registros[0].herramientas_usadas == ["buscar_servicios"]


async def test_el_markdown_del_modelo_llega_como_texto_plano():
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {})),
        responder(
            "| Servicio | Estado |\n|---|---|\n| **Tour de café** | Confirmada |",
            recomendacion(CAFE, "Tour de café", "Zona con **capacidad baja**."),
        ),
    )

    resultado = await _preguntar(_caso_de_uso(modelo))

    assert resultado.respuesta == "• Servicio: Tour de café · Estado: Confirmada"
    assert resultado.recomendaciones[0].justificacion == "Zona con capacidad baja."


# ---------- la respuesta final escrita como texto (gpt-oss) ----------

FRASE = "Tu reserva confirmada es para Buceo en Taganga el 8 de noviembre."
JSON_FINAL = (
    '{\n  "recomendaciones": [],\n  "respuesta": "Tu reserva confirmada es para Buceo en Taganga '
    'el 8 de noviembre."\n}'
)


@pytest.mark.parametrize(
    "texto",
    [
        f"{FRASE}\n\n{JSON_FINAL}",
        f"{FRASE}\n```json\n{JSON_FINAL}\n```",
        JSON_FINAL,
    ],
)
async def test_el_json_de_la_respuesta_final_escrito_como_texto_no_llega_al_turista(texto):
    modelo = ModeloGuionado(RespuestaModelo(texto=texto))

    resultado = await _preguntar(_caso_de_uso(modelo), "¿Qué tengo reservado?")

    assert resultado.respuesta == FRASE
    assert "{" not in resultado.respuesta


async def test_las_recomendaciones_del_json_escrito_como_texto_se_validan():
    escrito = json.dumps(
        {
            "respuesta": "Te recomiendo el tour.",
            "recomendaciones": [
                recomendacion(CAFE, "Tour de café", "Zona BAJO."),
                recomendacion(INVENTADO, "Inventado", "No salió de ninguna tool."),
            ],
        },
        ensure_ascii=False,
    )
    modelo = ModeloGuionado(pedir(("buscar_servicios", {})), RespuestaModelo(texto=escrito))

    resultado = await _preguntar(_caso_de_uso(modelo))

    assert resultado.respuesta == "Te recomiendo el tour."
    assert [r.servicio_id for r in resultado.recomendaciones] == [CAFE]


async def test_un_texto_con_llaves_que_no_es_la_respuesta_final_no_cambia():
    texto = 'Usa la fórmula {precio} x personas; el JSON {"a": 1} es un ejemplo.'
    modelo = ModeloGuionado(RespuestaModelo(texto=texto))

    resultado = await _preguntar(_caso_de_uso(modelo))

    assert resultado.respuesta == texto
