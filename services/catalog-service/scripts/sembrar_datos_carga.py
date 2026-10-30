"""Datos para las pruebas de carga con k6 (k6/README.md): servicios repartidos en las zonas.

Con la base vacía una búsqueda no mide nada: no hay filas que filtrar, ordenar ni paginar.
Crea prestadores aprobados y servicios activos en puntos al azar dentro de cada zona activa,
con calificaciones en la mayoría, y vacía la caché de búsquedas para que se vean de inmediato.

Uso (contra la base del compose de infra/, o la que diga DATABASE_URL):

    uv run python scripts/sembrar_datos_carga.py               # 2000 servicios
    uv run python scripts/sembrar_datos_carga.py --servicios 500
    uv run python scripts/sembrar_datos_carga.py --borrar      # quita lo sembrado

Lo sembrado se reconoce por la razón social "Carga k6 ..." de sus prestadores. No pasa por
el outbox: booking no se entera de estos servicios (solo sirven para medir el catálogo).
"""

import argparse
import asyncio
import random
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import text
from valkey.asyncio import Valkey

from app.config import get_settings
from app.domain.entities.atractivo_servicio import AtractivoServicio, DatosServicio
from app.domain.entities.calificacion_resena import CalificacionResena
from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.atributos.bloque_entrada import BloqueEntrada
from app.domain.value_objects.atributos.bloque_gastronomia import BloqueGastronomia
from app.domain.value_objects.atributos.valores import TipoCocina
from app.domain.value_objects.catalogos import UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio
from app.infrastructure.cache.cache_versionada import CacheVersionada
from app.infrastructure.persistence.database import build_engine, build_session_factory
from app.infrastructure.persistence.unidad_de_trabajo import SqlUnidadDeTrabajo

PREFIJO = "Carga k6"
PRESTADORES = 100
LOTE = 200
ORIGEN_IMAGENES = "https://imagenes.local/catalogo-imagenes/"
# Un tipo por categoría con su bloque principal mínimo, como en las pruebas de integración.
TIPOS = {
    TipoServicio.ACCESO_PLAYA: ("Playa", "Beach"),
    TipoServicio.MUSEO_SITIO: ("Museo", "Museum"),
    TipoServicio.RESERVA_PARQUE: ("Reserva", "Reserve"),
    TipoServicio.RESTAURANTE: ("Restaurante", "Restaurant"),
}


def atributos_de(tipo: TipoServicio) -> AtributosServicio:
    if tipo is TipoServicio.RESTAURANTE:
        return AtributosServicio(gastronomia=BloqueGastronomia(tipos_cocina=(TipoCocina.DE_MAR,)))
    return AtributosServicio(entrada=BloqueEntrada())


def servicio(
    perfil: PrestadorPerfil, numero: int, punto: Coordenada, azar: random.Random
) -> AtractivoServicio:
    tipo = azar.choice(list(TIPOS))
    es, en = TIPOS[tipo]
    datos = DatosServicio(
        nombre=TextoTraducido(es=f"{es} {numero}", en=f"{en} {numero}"),
        descripcion=TextoTraducido(es=f"Servicio de prueba de carga {numero}"),
        tipo=tipo,
        unidad_tarifa=UnidadTarifa.POR_PERSONA,
        atributos=atributos_de(tipo),
        ubicacion=punto,
        tarifa_base=Tarifa(Decimal(azar.randrange(10_000, 400_000, 1_000))),
        capacidad_aforo_diario=azar.randint(10, 300),
        imagenes_urls=(f"{ORIGEN_IMAGENES}{uuid4()}.webp",),
    )
    return AtractivoServicio.registrar(perfil, datos, ORIGEN_IMAGENES, datetime.now(UTC))


async def sembrar(cantidad: int) -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    sesiones = build_session_factory(engine)
    azar = random.Random(2026)
    async with engine.connect() as conn:
        zonas = (
            await conn.execute(
                text(
                    "SELECT ST_YMin(poligono), ST_YMax(poligono), ST_XMin(poligono),"
                    " ST_XMax(poligono) FROM zona WHERE activa"
                )
            )
        ).all()
    perfiles = [
        PrestadorPerfil.aprobar(uuid4(), uuid4(), f"{PREFIJO} {i}") for i in range(PRESTADORES)
    ]
    async with SqlUnidadDeTrabajo(sesiones) as uow:
        for perfil in perfiles:
            await uow.prestadores.guardar(perfil)
        await uow.confirmar()
    for inicio in range(0, cantidad, LOTE):
        async with SqlUnidadDeTrabajo(sesiones) as uow:
            for numero in range(inicio, min(inicio + LOTE, cantidad)):
                lat_min, lat_max, lon_min, lon_max = azar.choice(zonas)
                punto = Coordenada(
                    lat=round(azar.uniform(lat_min, lat_max), 6),
                    lon=round(azar.uniform(lon_min, lon_max), 6),
                )
                s = servicio(azar.choice(perfiles), numero, punto, azar)
                s.asignar_zona(await uow.zonas.zona_de(punto))
                await uow.servicios.guardar(s)
                for _ in range(azar.choice((0, 0, 1, 3, 8))):  # la mayoría con calificaciones
                    await uow.calificaciones.guardar(
                        CalificacionResena(
                            resena_id=uuid4(), servicio_id=s.id, puntuacion=azar.randint(1, 5)
                        )
                    )
            await uow.confirmar()
        print(f"{min(inicio + LOTE, cantidad)}/{cantidad} servicios")
    await engine.dispose()
    await vaciar_cache(settings.valkey_url)


async def borrar() -> None:
    settings = get_settings()
    engine = build_engine(settings.database_url)
    async with engine.begin() as conn:
        borrados = await conn.execute(
            text(
                "DELETE FROM atractivo_servicio WHERE prestador_id IN"
                " (SELECT id FROM prestador_perfil WHERE razon_social LIKE :p)"
            ),
            {"p": f"{PREFIJO} %"},
        )
        await conn.execute(
            text("DELETE FROM prestador_perfil WHERE razon_social LIKE :p"), {"p": f"{PREFIJO} %"}
        )
    await engine.dispose()
    print(f"{borrados.rowcount} servicios borrados")
    await vaciar_cache(settings.valkey_url)


async def vaciar_cache(url: str) -> None:
    valkey = Valkey.from_url(url, socket_timeout=2, socket_connect_timeout=2)
    try:
        await CacheVersionada(valkey).invalidar()
    except Exception as exc:  # sin Valkey las búsquedas igual se ven tras el TTL (5 min)
        print(f"No se pudo vaciar la caché ({exc}); los cambios se verán en 5 minutos")
    finally:
        await valkey.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--servicios", type=int, default=2000)
    parser.add_argument("--borrar", action="store_true", help="quita los datos sembrados")
    args = parser.parse_args()
    asyncio.run(borrar() if args.borrar else sembrar(args.servicios))


if __name__ == "__main__":
    main()
