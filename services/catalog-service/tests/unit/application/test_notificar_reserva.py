"""Correos de reservas con dobles: a quién va cada uno, plantillas es/en, escapado, idempotencia
y el adaptador de iam."""

from datetime import UTC, date, datetime
from types import TracebackType
from typing import Self
from uuid import UUID, uuid4

import httpx
import pytest

from app.application.dto.contacto_usuario import ContactoUsuario
from app.application.dto.correo import Correo
from app.application.dto.datos_correo_reserva import DatosCorreoReserva
from app.application.dto.plantilla_correo import PlantillaCorreo
from app.application.dto.reserva_notificada import ReservaNotificada
from app.application.dto.resultado_consumo import ResultadoConsumo
from app.application.dto.servicio_editable import ServicioEditable
from app.application.errores import DependenciaNoDisponible
from app.application.use_cases.notificar_reserva import NotificarReserva
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.entities.reserva_proyeccion import TipoEventoReserva
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.atributos.bloque_pagos import BloquePagos
from app.domain.value_objects.atributos.valores import (
    MedioPago,
    RecomendacionDinero,
    SenalInternet,
)
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.identidad import Rol
from app.domain.value_objects.idioma import Idioma
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.clients.directorio_usuarios_iam import DirectorioUsuariosIam
from app.infrastructure.notificaciones.redactor_correos_jinja import RedactorCorreosJinja

AHORA = datetime(2026, 10, 24, 15, 0, tzinfo=UTC)
T = TipoEventoReserva
PAGOS = BloquePagos(
    senal_internet=SenalInternet.SIN_SENAL,
    medios_pago=(MedioPago.EFECTIVO,),
    recomendacion_dinero=RecomendacionDinero.EFECTIVO,
)


def perfil() -> PrestadorPerfil:
    p = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Sierra Viva")
    p.editar(1, "3001234567", "Vereda Pozo Azul", TextoTraducido(es="Gratis 24 h antes"))
    return p


PERFIL = perfil()
SERVICIO = AtractivoServicio.registrar(
    PERFIL,
    DatosServicio(
        nombre=TextoTraducido(es="Pozo Azul", en="Blue Pool"),
        descripcion=TextoTraducido(es="Entrada"),
        tipo=TipoServicio.RESERVA_PARQUE,
        ubicacion=Coordenada(lat=11.14, lon=-74.11),
        tarifa_base=Tarifa(10000),  # type: ignore[arg-type]
        unidad_tarifa=UnidadTarifa.POR_PERSONA,
        capacidad_aforo_diario=20,
        atributos=AtributosServicio(entrada=BloqueEntrada(), pagos=PAGOS),
    ),
    "https://s3/",
    AHORA,
)
TURISTA = uuid4()


class Catalogo:
    async def servicio(self, servicio_id: UUID) -> ServicioEditable | None:
        return ServicioEditable(SERVICIO, None) if servicio_id == SERVICIO.id else None

    async def perfil_de_usuario(self, usuario_id: UUID) -> PrestadorPerfil | None:
        return PERFIL if usuario_id == PERFIL.usuario_id else None


class Directorio:
    def __init__(self, conocidos: set[UUID] | None = None) -> None:
        self.conocidos = conocidos if conocidos is not None else {TURISTA, PERFIL.usuario_id}

    async def contacto(self, usuario_id: UUID) -> ContactoUsuario | None:
        if usuario_id not in self.conocidos:
            return None
        quien = "turista" if usuario_id == TURISTA else "prestador"
        return ContactoUsuario(usuario_id, quien.title(), f"{quien}@correo.test", Idioma.ES)


class Enviador:
    def __init__(self, falla: bool = False) -> None:
        self.enviados: list[Correo] = []
        self.falla = falla

    async def enviar(self, correo: Correo) -> None:
        if self.falla:
            raise ConnectionError("SMTP no responde")
        self.enviados.append(correo)


class Procesados:
    def __init__(self) -> None:
        self.ids: set[UUID] = set()

    async def registrar(self, event_id: UUID, consumidor: str) -> bool:
        nuevo = event_id not in self.ids
        self.ids.add(event_id)
        return nuevo

    async def ya_procesado(self, event_id: UUID, consumidor: str) -> bool:
        return event_id in self.ids


class Unidad:
    def __init__(self) -> None:
        self.eventos_procesados = Procesados()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self, t: type[BaseException] | None, e: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    async def confirmar(self) -> None:
        pass


def reserva(tipo: TipoEventoReserva, **extra: object) -> ReservaNotificada:
    return ReservaNotificada(
        event_id=uuid4(),
        tipo=tipo,
        reserva_id=uuid4(),
        servicio_id=SERVICIO.id,
        turista_id=TURISTA,
        fecha_reserva=date(2026, 11, 5),
        numero_personas=2,
        **extra,  # type: ignore[arg-type]
    )


def caso(
    uow: Unidad | None = None,
    enviador: Enviador | None = None,
    directorio: Directorio | None = None,
) -> tuple[NotificarReserva, Unidad, Enviador]:
    uow, enviador = uow or Unidad(), enviador or Enviador()
    notificar = NotificarReserva(
        lambda: uow, Catalogo(), directorio or Directorio(), RedactorCorreosJinja(), enviador
    )
    return notificar, uow, enviador


@pytest.mark.parametrize(
    ("tipo", "extra", "destinatario"),
    [
        (T.SOLICITADA, {}, "prestador@correo.test"),
        (
            T.MODIFICADA,
            {"fecha_anterior": date(2026, 11, 2), "numero_personas_anterior": 4},
            "prestador@correo.test",
        ),
        (T.CONFIRMADA, {}, "turista@correo.test"),
        (T.RECHAZADA, {"motivo": "Plazo de respuesta vencido"}, "turista@correo.test"),
        (T.CANCELADA, {"cancelada_por": Rol.TURISTA}, "prestador@correo.test"),
        (T.CANCELADA, {"cancelada_por": Rol.PRESTADOR, "motivo": "Lluvias"}, "turista@correo.test"),
    ],
    ids=[
        "solicitada",
        "modificada",
        "confirmada",
        "rechazada",
        "cancela_turista",
        "cancela_prestador",
    ],
)
async def test_a_quien_va_cada_correo(
    tipo: TipoEventoReserva, extra: dict, destinatario: str
) -> None:
    notificar, uow, enviador = caso()
    evento = reserva(tipo, **extra)
    assert await notificar.execute(evento) is ResultadoConsumo.APLICADO
    [correo] = enviador.enviados
    assert correo.destinatario == destinatario
    assert evento.event_id in uow.eventos_procesados.ids  # se registra después de enviar


async def test_finalizada_no_envia() -> None:
    notificar, _, enviador = caso()
    assert await notificar.execute(reserva(T.FINALIZADA)) is ResultadoConsumo.IGNORADO
    assert enviador.enviados == []


async def test_un_duplicado_no_reenvia() -> None:
    notificar, _, enviador = caso()
    evento = reserva(T.CONFIRMADA)
    await notificar.execute(evento)
    assert await notificar.execute(evento) is ResultadoConsumo.DUPLICADO
    assert len(enviador.enviados) == 1


async def test_si_el_correo_falla_no_se_registra_y_se_reintenta() -> None:
    uow = Unidad()
    notificar, _, _ = caso(uow, Enviador(falla=True))
    evento = reserva(T.CONFIRMADA)
    with pytest.raises(ConnectionError):
        await notificar.execute(evento)
    assert evento.event_id not in uow.eventos_procesados.ids
    reintento, _, enviador = caso(uow)
    assert await reintento.execute(evento) is ResultadoConsumo.APLICADO
    assert len(enviador.enviados) == 1


async def test_usuario_sin_contacto_no_se_envia_pero_se_registra() -> None:
    notificar, uow, enviador = caso(directorio=Directorio(set()))
    evento = reserva(T.CONFIRMADA)
    assert await notificar.execute(evento) is ResultadoConsumo.IGNORADO
    assert enviador.enviados == [] and evento.event_id in uow.eventos_procesados.ids


def datos(idioma: Idioma, **cambios: object) -> DatosCorreoReserva:
    base = {
        "destinatario": ContactoUsuario(TURISTA, "Ana", "ana@correo.test", idioma),
        "servicio": SERVICIO.datos.nombre,
        "fecha_reserva": date(2026, 11, 5),
        "numero_personas": 2,
        "prestador": PERFIL,
        "pagos": PAGOS,
        "motivo": "Lluvias",
        "fecha_anterior": date(2026, 11, 2),
        "numero_personas_anterior": 4,
        "expira_en": datetime(2026, 11, 3, 19, 30, tzinfo=UTC),
    }
    return DatosCorreoReserva(**(base | cambios))  # type: ignore[arg-type]


@pytest.mark.parametrize("plantilla", list(PlantillaCorreo))
@pytest.mark.parametrize("idioma", list(Idioma))
def test_cada_plantilla_existe_en_ambos_idiomas(plantilla: PlantillaCorreo, idioma: Idioma) -> None:
    correo = RedactorCorreosJinja().redactar(plantilla, datos(idioma))
    assert correo.asunto and correo.html.startswith("<!doctype html>") and correo.texto.strip()
    assert ("Blue Pool" if idioma is Idioma.EN else "Pozo Azul") in correo.texto


def test_confirmacion_trae_contacto_aviso_de_pagos_y_regla_base() -> None:
    es = RedactorCorreosJinja().redactar(PlantillaCorreo.CONFIRMACION, datos(Idioma.ES))
    assert es.asunto == "Reserva confirmada: Pozo Azul"
    assert "jueves 5 de noviembre de 2026" in es.texto
    assert "3001234567" in es.texto and "Vereda Pozo Azul" in es.texto
    assert "Lleva efectivo" in es.texto and "#fff3cd" in es.html  # aviso destacado
    assert "Gratis 24 h antes" in es.texto and "Regla de la plataforma" in es.texto
    en = RedactorCorreosJinja().redactar(PlantillaCorreo.CONFIRMACION, datos(Idioma.EN))
    assert "Thursday, November 5, 2026" in en.texto and "Bring cash" in en.texto


def test_modificacion_con_plazo_en_hora_de_santa_marta() -> None:
    correo = RedactorCorreosJinja().redactar(PlantillaCorreo.MODIFICACION, datos(Idioma.ES))
    assert "lunes 2 de noviembre de 2026, 4 persona(s)" in correo.texto
    assert "martes 3 de noviembre de 2026, 14:30" in correo.texto  # 19:30 UTC = 14:30 en Bogotá


def test_lo_que_escribe_un_usuario_se_escapa_en_el_html() -> None:
    malicioso = datos(Idioma.ES, motivo='<script>alert("x")</script>')
    correo = RedactorCorreosJinja().redactar(PlantillaCorreo.RECHAZO, malicioso)
    assert "<script>" not in correo.html and "&lt;script&gt;" in correo.html


async def test_adaptador_de_iam() -> None:
    usuario = uuid4()

    def responder(peticion: httpx.Request) -> httpx.Response:
        if str(usuario) in peticion.url.path:
            return httpx.Response(
                200,
                json={
                    "usuario_id": str(usuario),
                    "nombre": "Ana",
                    "email": "ana@x.co",
                    "idioma": "en",
                },
            )
        if "caido" in peticion.url.path:
            return httpx.Response(503)
        return httpx.Response(404)

    cliente = httpx.AsyncClient(base_url="http://iam", transport=httpx.MockTransport(responder))
    iam = DirectorioUsuariosIam(cliente)
    contacto = await iam.contacto(usuario)
    assert contacto == ContactoUsuario(usuario, "Ana", "ana@x.co", Idioma.EN)
    assert await iam.contacto(uuid4()) is None
    caido = DirectorioUsuariosIam(
        httpx.AsyncClient(
            base_url="http://iam",
            transport=httpx.MockTransport(lambda _: httpx.Response(503)),
        )
    )
    with pytest.raises(DependenciaNoDisponible):
        await caido.contacto(uuid4())
