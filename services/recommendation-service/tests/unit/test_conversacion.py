from uuid import uuid4

from src.domain.conversacion import MAX_MENSAJES, Conversacion, Mensaje, Rol


def _mensaje(n: int) -> Mensaje:
    return Mensaje(rol=Rol.TURISTA, texto=f"mensaje {n}")


def test_conversacion_nueva_pertenece_al_turista_y_empieza_vacia():
    turista = uuid4()

    conversacion = Conversacion.nueva(turista)

    assert conversacion.pertenece_a(turista)
    assert not conversacion.pertenece_a(uuid4())
    assert conversacion.mensajes == []


def test_dos_conversaciones_nuevas_tienen_identificadores_distintos():
    turista = uuid4()

    assert Conversacion.nueva(turista).id != Conversacion.nueva(turista).id


def test_agregar_guarda_los_mensajes_en_orden():
    conversacion = Conversacion.nueva(uuid4())

    conversacion.agregar(Mensaje(rol=Rol.TURISTA, texto="¿Qué hago en Taganga?"))
    conversacion.agregar(Mensaje(rol=Rol.ASISTENTE, texto="Puedes bucear."))

    assert [m.rol for m in conversacion.mensajes] == [Rol.TURISTA, Rol.ASISTENTE]


def test_solo_conserva_los_ultimos_10_mensajes():
    conversacion = Conversacion.nueva(uuid4())

    for n in range(12):
        conversacion.agregar(_mensaje(n))

    assert len(conversacion.mensajes) == MAX_MENSAJES == 10
    assert conversacion.mensajes[0] == _mensaje(2)
    assert conversacion.mensajes[-1] == _mensaje(11)


def test_al_reconstruirla_con_mas_de_10_mensajes_se_recorta():
    conversacion = Conversacion(
        id=uuid4(), turista_id=uuid4(), mensajes=[_mensaje(n) for n in range(15)]
    )

    assert conversacion.mensajes == [_mensaje(n) for n in range(5, 15)]
