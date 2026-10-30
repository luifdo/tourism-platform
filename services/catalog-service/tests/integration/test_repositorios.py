import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities.alerta_oficial import AlertaOficial
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.calificacion_resena import CalificacionResena
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.entities.reserva_proyeccion import (
    EventoReserva,
    ReservaProyeccion,
    TipoEventoReserva,
)
from app.domain.entities.zona import Zona
from app.domain.errors import DatoInvalido
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.atributos.bloque_gastronomia import BloqueGastronomia
from app.domain.value_objects.atributos.valores import TipoCocina
from app.domain.value_objects.catalogos import Categoria, EstadoReserva, NivelAlerta, UnidadTarifa
from app.domain.value_objects.codigo_zona import CodigoZona
from app.domain.value_objects.geo import Coordenada, PoligonoGeoJSON
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

pytestmark = pytest.mark.integration

ORIGEN = "https://s3.turismo.local/catalogo-imagenes/"
AHORA = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
EN_MINCA = Coordenada(lat=11.1426, lon=-74.1178)
EN_EL_MAR = Coordenada(lat=11.40, lon=-74.40)
# Punto fuera de las zonas iniciales, para probar zonas creadas en la prueba.
LEJOS = Coordenada(lat=10.50, lon=-74.50)

Sesiones = async_sessionmaker[AsyncSession]


# Un tipo por categoría con su bloque principal mínimo (las pruebas filtran por categoría).
TIPO_DE = {
    Categoria.PLAYA: TipoServicio.ACCESO_PLAYA,
    Categoria.CULTURA: TipoServicio.MUSEO_SITIO,
    Categoria.NATURALEZA: TipoServicio.RESERVA_PARQUE,
    Categoria.GASTRONOMIA: TipoServicio.RESTAURANTE,
}


def atributos_de(tipo: TipoServicio) -> AtributosServicio:
    if tipo is TipoServicio.RESTAURANTE:
        return AtributosServicio(gastronomia=BloqueGastronomia(tipos_cocina=(TipoCocina.DE_MAR,)))
    return AtributosServicio(entrada=BloqueEntrada())


def datos(ubicacion: Coordenada = EN_MINCA) -> DatosServicio:
    return DatosServicio(
        nombre=TextoTraducido(es="Tour del café en Minca", en="Minca coffee tour"),
        descripcion=TextoTraducido(es="Recorrido por fincas cafeteras"),
        tipo=TIPO_DE[Categoria.NATURALEZA],
        unidad_tarifa=UnidadTarifa.POR_PERSONA,
        atributos=atributos_de(TIPO_DE[Categoria.NATURALEZA]),
        ubicacion=ubicacion,
        tarifa_base=Tarifa(Decimal("85000.50")),
        capacidad_aforo_diario=20,
        imagenes_urls=(f"{ORIGEN}a.webp",),
    )


def caja(lat: float, lon: float, lado: float) -> PoligonoGeoJSON:
    anillo = [
        [lon - lado, lat - lado],
        [lon + lado, lat - lado],
        [lon + lado, lat + lado],
        [lon - lado, lat + lado],
        [lon - lado, lat - lado],
    ]
    return PoligonoGeoJSON.desde_geojson({"type": "Polygon", "coordinates": [anillo]})


async def crear_prestador(sesiones: Sesiones) -> PrestadorPerfil:
    perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Café de la Sierra")
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        await uow.prestadores.guardar(perfil)
        await uow.confirmar()
    return perfil


async def crear_servicio(sesiones: Sesiones, ubicacion: Coordenada = EN_MINCA) -> AtractivoServicio:
    perfil = await crear_prestador(sesiones)
    servicio = AtractivoServicio.registrar(perfil, datos(ubicacion), ORIGEN, AHORA)
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        servicio.asignar_zona(await uow.zonas.zona_de(ubicacion))
        await uow.servicios.guardar(servicio)
        await uow.confirmar()
    return servicio


class TestPrestadores:
    async def test_ida_y_vuelta(self, sesiones: Sesiones) -> None:
        perfil = await crear_prestador(sesiones)
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            leido = await uow.prestadores.obtener_por_usuario(perfil.usuario_id)
            assert leido is not None
            leido.editar(1, "3001234567", "Minca", TextoTraducido(es="Gratis", en="Free"))
            await uow.prestadores.guardar(leido)
            await uow.confirmar()
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            final = await uow.prestadores.obtener(perfil.id)
        assert final is not None and final.version == 2
        assert final.politica_cancelacion == TextoTraducido(es="Gratis", en="Free")


class TestServicios:
    async def test_ida_y_vuelta_con_version(self, sesiones: Sesiones) -> None:
        servicio = await crear_servicio(sesiones)
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            leido = await uow.servicios.obtener(servicio.id)
        assert leido is not None
        assert leido.datos == servicio.datos
        assert leido.datos.tarifa_base.valor == Decimal("85000.50")
        assert leido.version == 1

    async def test_ubicacion_generada_mide_en_metros(self, sesiones: Sesiones) -> None:
        servicio = await crear_servicio(sesiones)
        async with sesiones() as s:
            metros = await s.scalar(
                text(
                    "SELECT ST_Distance(ubicacion, ST_MakePoint(-74.1178, 11.1516)::geography)"
                    " FROM atractivo_servicio WHERE id = :id"
                ),
                {"id": servicio.id},
            )
        assert 990 < metros < 1010  # 0,009° de latitud ≈ 1 km

    @pytest.mark.parametrize(
        ("columna", "consulta"),
        [
            ("busqueda_es", "to_tsquery('spanish', f_unaccent('cafe'))"),
            ("busqueda_es", "to_tsquery('spanish', f_unaccent('cafeteras'))"),
            ("busqueda_en", "to_tsquery('english', 'coffee')"),
        ],
    )
    async def test_busqueda_de_texto_sin_tildes(
        self, sesiones: Sesiones, columna: str, consulta: str
    ) -> None:
        servicio = await crear_servicio(sesiones)
        async with sesiones() as s:
            encontrado = await s.scalar(
                text(f"SELECT {columna} @@ {consulta} FROM atractivo_servicio WHERE id = :id"),
                {"id": servicio.id},
            )
        assert encontrado is True


class TestZonas:
    async def test_asigna_la_zona_que_cubre_el_punto(self, sesiones: Sesiones) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            minca = await uow.zonas.obtener_por_codigo(CodigoZona("minca"))
            assert minca is not None
            assert await uow.zonas.zona_de(EN_MINCA) == minca.id
            assert await uow.zonas.zona_de(EN_EL_MAR) is None

    async def test_la_zona_mas_especifica_gana(self, sesiones: Sesiones) -> None:
        grande = Zona.crear(
            CodigoZona("prueba-sierra"),
            TextoTraducido(es="Sierra"),
            caja(EN_MINCA.lat, EN_MINCA.lon, 0.2),
        )
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.zonas.guardar(grande)
            minca = await uow.zonas.obtener_por_codigo(CodigoZona("minca"))
            assert minca is not None
            assert await uow.zonas.zona_de(EN_MINCA) == minca.id
            await uow.confirmar()

    async def test_reasignar_al_crear_editar_y_desactivar(self, sesiones: Sesiones) -> None:
        servicio = await crear_servicio(sesiones, LEJOS)
        assert servicio.zona_id is None
        zona = Zona.crear(
            CodigoZona("prueba-lejos"), TextoTraducido(es="Lejos"), caja(LEJOS.lat, LEJOS.lon, 0.01)
        )

        async def zona_del_servicio() -> object:
            async with sesiones() as s:
                return await s.scalar(
                    text("SELECT zona_id FROM atractivo_servicio WHERE id = :id"),
                    {"id": servicio.id},
                )

        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.zonas.guardar(zona)
            await uow.zonas.reasignar_servicios(zona.id)
            await uow.confirmar()
        assert await zona_del_servicio() == zona.id

        async with SqlUnidadDeTrabajo(sesiones) as uow:
            leida = await uow.zonas.obtener(zona.id)
            assert leida is not None and leida.poligono == zona.poligono
            # El polígono se mueve y deja de cubrir el servicio.
            leida.editar(1, leida.codigo, leida.nombre, caja(LEJOS.lat + 0.5, LEJOS.lon, 0.01))
            await uow.zonas.guardar(leida)
            await uow.zonas.reasignar_servicios(leida.id)
            await uow.confirmar()
        assert await zona_del_servicio() is None

    async def test_poligono_invalido_lo_rechaza_postgis(self, sesiones: Sesiones) -> None:
        # Un "moño": el anillo se cruza a sí mismo. La forma es válida, la topología no.
        mono = PoligonoGeoJSON.desde_geojson(
            {
                "type": "Polygon",
                "coordinates": [
                    [[-74.5, 10.5], [-74.4, 10.6], [-74.4, 10.5], [-74.5, 10.6], [-74.5, 10.5]]
                ],
            }
        )
        zona = Zona.crear(CodigoZona("prueba-mono"), TextoTraducido(es="Moño"), mono)
        with pytest.raises(DatoInvalido, match="poligono_invalido"):
            async with SqlUnidadDeTrabajo(sesiones) as uow:
                await uow.zonas.guardar(zona)


class TestAlertas:
    async def test_cuenta_solo_las_vigentes(self, sesiones: Sesiones) -> None:
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            minca = await uow.zonas.obtener_por_codigo(CodigoZona("minca"))
            assert minca is not None
            for dias in (1, 2):
                await uow.alertas.guardar(
                    AlertaOficial.publicar(
                        NivelAlerta.PREVENTIVA,
                        TextoTraducido(es="Lluvias"),
                        uuid4(),
                        AHORA + timedelta(days=dias),
                        AHORA,
                        zona_id=minca.id,
                    )
                )
            await uow.confirmar()
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            assert await uow.alertas.contar_vigentes_de_zona(minca.id, AHORA) == 2
            assert (
                await uow.alertas.contar_vigentes_de_zona(minca.id, AHORA + timedelta(days=1)) == 1
            )

    async def test_la_base_exige_un_solo_destino(self, sesiones: Sesiones) -> None:
        with pytest.raises(IntegrityError):
            async with sesiones() as s, s.begin():
                await s.execute(
                    text(
                        "INSERT INTO alerta_oficial (id, nivel, mensaje, entidad_usuario_id,"
                        " fecha_expiracion, creada_en) VALUES (gen_random_uuid(), 'CRITICA',"
                        " '{\"es\": \"x\"}', gen_random_uuid(), now() + interval '1 day', now())"
                    )
                )


class TestProyecciones:
    async def test_reserva_ida_y_vuelta(self, sesiones: Sesiones) -> None:
        evento = EventoReserva(
            tipo=TipoEventoReserva.CONFIRMADA,
            reserva_id=uuid4(),
            servicio_id=uuid4(),
            prestador_id=uuid4(),
            turista_id=uuid4(),
            fecha_reserva=date(2026, 11, 5),
            numero_personas=3,
            ocurrido_en=AHORA,
        )
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.reservas.guardar(ReservaProyeccion.desde_evento(evento))
            await uow.confirmar()
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            leida = await uow.reservas.obtener(evento.reserva_id)
        assert leida is not None and leida.estado is EstadoReserva.CONFIRMADA
        assert leida.ultimo_evento_en == AHORA

    async def test_calificacion_republicada_no_duplica(self, sesiones: Sesiones) -> None:
        resena, servicio = uuid4(), uuid4()
        for puntuacion in (4, 5):
            async with SqlUnidadDeTrabajo(sesiones) as uow:
                await uow.calificaciones.guardar(
                    CalificacionResena(
                        resena_id=resena, servicio_id=servicio, puntuacion=puntuacion
                    )
                )
                await uow.confirmar()
        async with sesiones() as s:
            filas = (
                await s.execute(
                    text("SELECT puntuacion FROM calificacion_resena WHERE servicio_id = :s"),
                    {"s": servicio},
                )
            ).all()
        assert filas == [(5,)]

    async def test_si_el_evento_viejo_confirma_ultimo_gana_el_nuevo(
        self, sesiones: Sesiones
    ) -> None:
        # Dos eventos de una reserva que aún no existe, procesados a la vez: ninguno tiene
        # fila que bloquear. Si el viejo (solicitada) confirma después del nuevo
        # (cancelada), la base no debe dejar que lo pise.
        reserva_id = uuid4()

        def evento(tipo: TipoEventoReserva, minutos: int) -> EventoReserva:
            return EventoReserva(
                tipo=tipo,
                reserva_id=reserva_id,
                servicio_id=uuid4(),
                prestador_id=uuid4(),
                turista_id=uuid4(),
                fecha_reserva=date(2026, 11, 5),
                numero_personas=2,
                ocurrido_en=AHORA + timedelta(minutes=minutos),
            )

        for e in (evento(TipoEventoReserva.CANCELADA, 5), evento(TipoEventoReserva.SOLICITADA, 0)):
            async with SqlUnidadDeTrabajo(sesiones) as uow:
                await uow.reservas.guardar(ReservaProyeccion.desde_evento(e))
                await uow.confirmar()
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            leida = await uow.reservas.obtener(reserva_id)
        assert leida is not None and leida.estado is EstadoReserva.CANCELADA

    async def test_lo_mismo_con_una_resena_ocultada_y_su_publicacion_vieja(
        self, sesiones: Sesiones
    ) -> None:
        resena = uuid4()
        for visible, minutos in ((False, 5), (True, 0)):
            async with SqlUnidadDeTrabajo(sesiones) as uow:
                await uow.calificaciones.guardar(
                    CalificacionResena.desde_evento(
                        resena, uuid4(), 1, visible, AHORA + timedelta(minutes=minutos)
                    )
                )
                await uow.confirmar()
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            leida = await uow.calificaciones.obtener(resena)
        assert leida is not None and leida.visible is False

    async def test_perfil_suspendido_no_lo_pisa_una_aprobacion_vieja_concurrente(
        self, sesiones: Sesiones
    ) -> None:
        prestador, usuario = uuid4(), uuid4()
        suspendido = PrestadorPerfil.aprobar(prestador, usuario, None)
        suspendido.suspender()
        suspendido.registrar_evento_iam(AHORA + timedelta(minutes=5))
        aprobado_viejo = PrestadorPerfil.aprobar(prestador, usuario, "Minca Viva")
        aprobado_viejo.registrar_evento_iam(AHORA)
        for perfil in (suspendido, aprobado_viejo):  # el viejo confirma último
            async with SqlUnidadDeTrabajo(sesiones) as uow:
                await uow.prestadores.guardar(perfil)
                await uow.confirmar()
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            leido = await uow.prestadores.obtener(prestador)
        assert leido is not None and not leido.activo

    async def test_editar_el_perfil_sigue_funcionando(self, sesiones: Sesiones) -> None:
        perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Minca Viva")
        perfil.registrar_evento_iam(AHORA)
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.prestadores.guardar(perfil)
            await uow.confirmar()
        perfil.editar(1, "3001234567", None, None)
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.prestadores.guardar(perfil)
            await uow.confirmar()
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            leido = await uow.prestadores.obtener(perfil.id)
        assert leido is not None and leido.telefono == "3001234567"


class TestTransacciones:
    async def test_eventos_procesados_detecta_duplicados(self, sesiones: Sesiones) -> None:
        event_id = uuid4()
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            assert await uow.eventos_procesados.registrar(event_id, "catalog.demanda") is True
            assert await uow.eventos_procesados.registrar(event_id, "catalog.demanda") is False
            assert (
                await uow.eventos_procesados.registrar(event_id, "catalog.notificaciones") is True
            )
            await uow.confirmar()

    async def test_sin_confirmar_no_se_guarda(self, sesiones: Sesiones) -> None:
        perfil = PrestadorPerfil.aprobar(uuid4(), uuid4(), "Sin confirmar")
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            await uow.prestadores.guardar(perfil)
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            assert await uow.prestadores.obtener(perfil.id) is None

    async def test_dos_ediciones_simultaneas_se_ordenan(self, sesiones: Sesiones) -> None:
        """Con varias réplicas, la segunda edición espera y ve la versión nueva (409)."""
        perfil = await crear_prestador(sesiones)

        async with SqlUnidadDeTrabajo(sesiones) as primera:
            leido = await primera.prestadores.obtener(perfil.id)
            assert leido is not None

            async def segunda_lectura() -> int:
                async with SqlUnidadDeTrabajo(sesiones) as segunda:
                    otro = await segunda.prestadores.obtener(perfil.id)
                    assert otro is not None
                    return otro.version

            tarea = asyncio.create_task(segunda_lectura())
            await asyncio.sleep(0.3)
            assert not tarea.done()  # bloqueada por SELECT ... FOR UPDATE

            leido.editar(1, "3000000000", None, None)
            await primera.prestadores.guardar(leido)
            await primera.confirmar()

        assert await asyncio.wait_for(tarea, timeout=5) == 2
