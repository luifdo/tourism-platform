"""Rutas y datos de la demo en Swagger (solo en modo memoria; no son parte del contrato).

Reemplazan lo que en el clúster hacen otros componentes: el evento servicio.publicado del
catálogo, los CronJobs de Kubernetes y la consola de RabbitMQ.
"""

from datetime import timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request

from application.calendario import AbrirRangoCalendario
from application.servicios import AplicarServicioPublicado
from application.tareas import ExpirarSolicitudes, FinalizarReservas
from domain.reglas import hoy_local
from infrastructure.messaging import esquemas

SERVICIO_DEMO = UUID("0b6f1a52-3c1e-4c8e-9f0a-7d2a91c4e5b3")
PERFIL_PRESTADOR_DEMO = UUID("9a1c3e5f-2b4d-4c6e-8f0a-1b3d5f7a9c2e")
USUARIO_PRESTADOR_DEMO = UUID("22222222-2222-4222-8222-222222222222")
USUARIO_TURISTA_DEMO = UUID("33333333-3333-4333-8333-333333333333")

DESCRIPCION = f"""
Contrato acordado: `contracts/openapi/booking.yaml`. Reglas: Guía Técnica del Módulo 3.

**Modo demo (memoria).** Sin Postgres ni RabbitMQ; los datos se pierden al reiniciar.
En el clúster, Traefik agrega `X-Usuario-Id` y `X-Usuario-Rol`; aquí se escriben a mano.

| Dato de ejemplo | Valor |
|---|---|
| Servicio (abierto 30 días desde mañana, 10 cupos) | `{SERVICIO_DEMO}` |
| Usuario prestador (`X-Usuario-Rol: Prestador`) | `{USUARIO_PRESTADOR_DEMO}` |
| Usuario turista (`X-Usuario-Rol: Turista`) | `{USUARIO_TURISTA_DEMO}` |

Las rutas **Demo** simulan el evento del catálogo, los CronJobs y el paso del tiempo.
"""

router = APIRouter(prefix="/dev", tags=["Demo (solo modo memoria)"])


class ServicioPublicado(esquemas.ServicioPublicado):
    """El mismo payload que valida el consumidor; en la demo `activo` es opcional."""

    activo: bool = True


def _contenedor(request: Request):
    return request.app.state.contenedor


async def cargar_datos_demo(contenedor: Any) -> None:
    ctx = contenedor.ctx
    await AplicarServicioPublicado(ctx)({
        "servicio_id": str(SERVICIO_DEMO),
        "prestador_id": str(PERFIL_PRESTADOR_DEMO),
        "prestador_usuario_id": str(USUARIO_PRESTADOR_DEMO),
        "capacidad_aforo_diario": 20,
        "tarifa_base": 85000,
        "activo": True,
        "version": 1,
    })
    manana = hoy_local(ctx.reloj.ahora()) + timedelta(days=1)
    await AbrirRangoCalendario(ctx)(USUARIO_PRESTADOR_DEMO, SERVICIO_DEMO, manana, manana + timedelta(days=29), 10)


@router.post("/servicios", summary="Simular el evento servicio.publicado del catálogo")
async def publicar_servicio(request: Request, evento: ServicioPublicado):
    aplicado = await AplicarServicioPublicado(_contenedor(request).ctx)(evento.model_dump(mode="json"))
    return {"aplicado": aplicado, "nota": None if aplicado else "Ignorado: la versión no es mayor que la guardada."}


@router.post("/tareas/expirar", summary="Ejecutar el CronJob expirar-solicitudes")
async def expirar(request: Request):
    return {"expiradas": await ExpirarSolicitudes(_contenedor(request).ctx)()}


@router.post("/tareas/finalizar", summary="Ejecutar el CronJob finalizar-reservas")
async def finalizar(request: Request):
    return {"finalizadas": await FinalizarReservas(_contenedor(request).ctx)()}


@router.post("/reloj/avanzar", summary="Adelantar el reloj del servicio (p. ej. 48 h para ver una expiración)")
async def avanzar_reloj(request: Request, horas: Annotated[float, Query(gt=0, le=24 * 400)]):
    reloj = _contenedor(request).ctx.reloj
    reloj.avanzar(hours=horas)
    return {"ahora": reloj.ahora().isoformat()}


@router.get("/eventos", summary="Últimos eventos publicados (lo que vería RabbitMQ)")
async def eventos(request: Request, ultimos: Annotated[int, Query(ge=1, le=200)] = 20):
    return list(reversed(_contenedor(request).publicador.publicados[-ultimos:]))
