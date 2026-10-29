from datetime import UTC, datetime
from uuid import uuid4

import pytest

from src.application.instrucciones import MENSAJE_LIMITE, MENSAJE_VACIO, RESPONDER
from src.application.ports.modelo_de_lenguaje import (
    MensajeAsistente,
    MensajeTurista,
    ModeloNoDisponibleError,
    RespuestaModelo,
    ResultadoLlamada,
)
from src.application.responder_mensaje import (
    AsistenteNoDisponibleError,
    ConversacionNoEncontradaError,
    PeticionChat,
    ResponderMensaje,
)
from src.domain.conversacion import Conversacion, Mensaje, Rol
from tests.fakes import (
    HerramientasFalsas,
    LimiteEnMemoria,
    ModeloCaido,
    ModeloGuionado,
    RegistroEnMemoria,
    SesionesEnMemoria,
    pedir,
    recomendacion,
    responder,
)

AHORA = datetime(2026, 10, 29, 15, 0, tzinfo=UTC)
TURISTA = uuid4()
CAFE = uuid4()
AVES = uuid4()


class Escenario:
    def __init__(self, modelo: ModeloGuionado, limite: int = 1000, **opciones) -> None:
        self.modelo = modelo
        self.herramientas = HerramientasFalsas({"Tour de café": CAFE, "Aves": AVES})
        self.sesiones = SesionesEnMemoria()
        self.registro = RegistroEnMemoria()
        self.limite = LimiteEnMemoria(limite)
        self.caso_de_uso = ResponderMensaje(
            modelo,
            self.herramientas,
            self.sesiones,
            self.registro,
            self.limite,
            reloj=lambda: AHORA,
            **opciones,
        )

    async def preguntar(self, mensaje="¿Qué hago en Minca?", **campos):
        campos.setdefault("turista_id", TURISTA)
        return await self.caso_de_uso.ejecutar(PeticionChat(mensaje=mensaje, **campos))


# ---------- flujo ----------


async def test_respuesta_directa_sin_tools():
    escenario = Escenario(ModeloGuionado(responder("¡Hola! ¿Qué te gustaría hacer?")))

    resultado = await escenario.preguntar("Hola")

    assert resultado.respuesta == "¡Hola! ¿Qué te gustaría hacer?"
    assert resultado.recomendaciones == ()
    assert escenario.herramientas.ejecutadas == []
    assert escenario.registro.registros == []


async def test_respuesta_en_texto_plano_sin_la_tool_final():
    escenario = Escenario(ModeloGuionado(RespuestaModelo(texto="  Claro, pregúntame.  ")))

    resultado = await escenario.preguntar("Hola")

    assert resultado.respuesta == "Claro, pregúntame."
    assert resultado.recomendaciones == ()


async def test_una_tool_y_su_resultado_vuelven_al_modelo():
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {"zona": "minca"})),
        responder(
            "Te recomiendo el tour de café.",
            recomendacion(CAFE, "Tour de café", "Minca tiene presión de capacidad baja."),
        ),
    )
    escenario = Escenario(modelo)

    resultado = await escenario.preguntar()

    assert [r.servicio_id for r in resultado.recomendaciones] == [CAFE]
    [(nombre, argumentos, contexto)] = escenario.herramientas.ejecutadas
    assert (nombre, argumentos) == ("buscar_servicios", {"zona": "minca"})
    assert contexto.turista_id == TURISTA
    # La segunda vuelta del modelo ve su pedido y el resultado de la tool.
    segunda = modelo.invocaciones[1].mensajes
    assert isinstance(segunda[-2], MensajeAsistente)
    assert isinstance(segunda[-1], ResultadoLlamada)
    assert segunda[-1].llamada_id == segunda[-2].llamadas[0].id
    assert segunda[-1].contenido["datos"]["servicios"][0]["nombre"] in {"Tour de café", "Aves"}


async def test_varias_tools_encadenadas_y_en_paralelo():
    modelo = ModeloGuionado(
        pedir(("presion_capacidad_carga", {}), ("alertas_oficiales", {})),
        pedir(("buscar_servicios", {"zona": "minca"})),
        responder("Listo."),
    )
    escenario = Escenario(modelo)

    await escenario.preguntar()

    assert [e[0] for e in escenario.herramientas.ejecutadas] == [
        "presion_capacidad_carga",
        "alertas_oficiales",
        "buscar_servicios",
    ]
    assert len(modelo.invocaciones) == 3


async def test_el_modelo_recibe_las_tools_de_la_plataforma_y_la_final():
    modelo = ModeloGuionado(responder("Hola"))

    await Escenario(modelo).preguntar("Hola", idioma="en")

    [invocacion] = modelo.invocaciones
    nombres = [h.nombre for h in invocacion.herramientas]
    assert nombres[-1] == RESPONDER
    assert "buscar_servicios" in nombres
    assert "inglés" in invocacion.instrucciones


async def test_una_tool_inexistente_vuelve_al_modelo_como_error():
    modelo = ModeloGuionado(pedir(("reservar", {"servicio_id": str(CAFE)})), responder("No puedo."))
    escenario = Escenario(modelo)

    resultado = await escenario.preguntar("Resérvame el tour")

    assert resultado.respuesta == "No puedo."
    resultado_tool = modelo.invocaciones[1].mensajes[-1]
    assert resultado_tool.contenido["error"] == "HERRAMIENTA_DESCONOCIDA"


async def test_al_superar_6_tools_corta_con_un_mensaje_claro():
    modelo = ModeloGuionado(
        *[pedir(("alertas_oficiales", {}))] * 6, pedir(("buscar_servicios", {}))
    )
    escenario = Escenario(modelo)

    resultado = await escenario.preguntar()

    assert resultado.respuesta == MENSAJE_LIMITE["es"]
    assert resultado.recomendaciones == ()
    assert len(escenario.herramientas.ejecutadas) == 6
    assert len(modelo.invocaciones) == 7


async def test_seis_tools_exactas_si_se_permiten():
    modelo = ModeloGuionado(
        pedir(*[("alertas_oficiales", {})] * 3),
        pedir(*[("buscar_servicios", {})] * 3),
        responder("Listo."),
    )
    escenario = Escenario(modelo)

    resultado = await escenario.preguntar()

    assert resultado.respuesta == "Listo."
    assert len(escenario.herramientas.ejecutadas) == 6


async def test_un_pedido_que_pasaria_el_limite_no_se_ejecuta_a_medias():
    modelo = ModeloGuionado(
        pedir(*[("alertas_oficiales", {})] * 5), pedir(*[("buscar_servicios", {})] * 2)
    )
    escenario = Escenario(modelo)

    resultado = await escenario.preguntar("Hola", idioma="en")

    assert resultado.respuesta == MENSAJE_LIMITE["en"]
    assert len(escenario.herramientas.ejecutadas) == 5


# ---------- fallas del modelo ----------


async def test_el_modelo_no_disponible_da_asistente_no_disponible():
    escenario = Escenario(ModeloCaido())

    with pytest.raises(AsistenteNoDisponibleError):
        await escenario.preguntar()

    assert escenario.sesiones.guardadas == {}


async def test_el_modelo_falla_despues_de_usar_una_tool():
    modelo = ModeloGuionado(pedir(("alertas_oficiales", {})), ModeloNoDisponibleError("caído"))

    with pytest.raises(AsistenteNoDisponibleError):
        await Escenario(modelo).preguntar()


async def test_el_modelo_no_responde_a_tiempo():
    escenario = Escenario(
        ModeloGuionado(responder("tarde"), demora_segundos=1), timeout_segundos=0.05
    )

    with pytest.raises(AsistenteNoDisponibleError):
        await escenario.preguntar()


# ---------- respuesta final ----------


async def test_las_recomendaciones_mal_formadas_se_descartan():
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {})),
        responder(
            "Opciones:",
            recomendacion(CAFE, "Tour de café", "Buenas reseñas."),
            recomendacion("no-es-uuid", "X", "motivo"),
            recomendacion(AVES, "Aves", "   "),
            {"nombre": "sin id", "justificacion": "motivo"},
        ),
    )

    resultado = await Escenario(modelo).preguntar()

    assert [r.servicio_id for r in resultado.recomendaciones] == [CAFE]


async def test_respuesta_final_sin_texto_usa_el_texto_del_modelo_o_un_mensaje():
    modelo = ModeloGuionado(
        pedir((RESPONDER, {"respuesta": "", "recomendaciones": "no-es-lista"}), texto="Aquí va."),
        pedir((RESPONDER, {})),
    )
    escenario = Escenario(modelo)

    primera = await escenario.preguntar()
    segunda = await escenario.preguntar()

    assert primera.respuesta == "Aquí va."
    assert primera.recomendaciones == ()
    assert segunda.respuesta == MENSAJE_VACIO["es"]


# ---------- registro y sesión ----------


async def test_registra_cada_recomendacion_con_las_tools_usadas():
    modelo = ModeloGuionado(
        pedir(("buscar_servicios", {}), ("presion_capacidad_carga", {})),
        pedir(("buscar_servicios", {"zona": "minca"})),
        responder(
            "Dos opciones.",
            recomendacion(CAFE, "Tour de café", "Zona con presión baja."),
            recomendacion(AVES, "Aves", "Muy bien calificado."),
        ),
    )
    escenario = Escenario(modelo)

    resultado = await escenario.preguntar()

    registros = escenario.registro.registros
    assert [r.servicio_id for r in registros] == [CAFE, AVES]
    for registro in registros:
        assert registro.conversacion_id == resultado.conversacion_id
        assert registro.turista_id == TURISTA
        assert registro.herramientas_usadas == ["buscar_servicios", "presion_capacidad_carga"]
        assert registro.modelo == "pruebas/guion"
        assert registro.fecha_generacion == AHORA
    assert registros[1].justificacion == "Muy bien calificado."


async def test_guarda_la_sesion_con_el_mensaje_y_la_respuesta():
    escenario = Escenario(ModeloGuionado(responder("Respuesta.")))

    resultado = await escenario.preguntar("Pregunta")

    sesion = escenario.sesiones.guardadas[resultado.conversacion_id]
    assert sesion.turista_id == TURISTA
    assert sesion.mensajes == [
        Mensaje(Rol.TURISTA, "Pregunta"),
        Mensaje(Rol.ASISTENTE, "Respuesta."),
    ]


async def test_continuar_una_conversacion_le_da_al_modelo_el_historial():
    modelo = ModeloGuionado(responder("Primera respuesta."), responder("Segunda respuesta."))
    escenario = Escenario(modelo)
    primera = await escenario.preguntar("Primera pregunta")

    segunda = await escenario.preguntar("Segunda pregunta", conversacion_id=primera.conversacion_id)

    assert segunda.conversacion_id == primera.conversacion_id
    assert modelo.invocaciones[1].mensajes == [
        MensajeTurista("Primera pregunta"),
        MensajeAsistente("Primera respuesta."),
        MensajeTurista("Segunda pregunta"),
    ]
    assert len(escenario.sesiones.guardadas[primera.conversacion_id].mensajes) == 4


async def test_una_conversacion_que_no_existe():
    escenario = Escenario(ModeloGuionado())

    with pytest.raises(ConversacionNoEncontradaError):
        await escenario.preguntar(conversacion_id=uuid4())


async def test_la_conversacion_de_otro_turista_no_se_puede_continuar():
    escenario = Escenario(ModeloGuionado())
    ajena = Conversacion.nueva(uuid4())
    await escenario.sesiones.guardar(ajena)

    with pytest.raises(ConversacionNoEncontradaError):
        await escenario.preguntar(conversacion_id=ajena.id)

    assert escenario.modelo.invocaciones == []
