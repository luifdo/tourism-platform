"""Carga del login de iam-service detrás de Traefik, en un k3d temporal (F-09, C-53).

ENTORNO DE PRUEBA, NO DE PRODUCCIÓN. Prepara el clúster con `scripts.e2e_k3d.preparar`, pero con
el overlay `e2e/overlay-carga`: en k3d todos los clientes llegan con la misma IP (F-08) y el
límite real de 5 logins por minuto cortaría la carga en el sexto. El middleware sigue en la cadena.

Uso: uv run python -m scripts.carga_k3d [--conservar] [--sin-preparar] [--crudo RUTA]
     uv run python -m scripts.carga_k3d --solo-reporte RUTA   (regenera desde un crudo)

El generador es de lazo abierto: cada petición sale a su hora aunque las anteriores no hayan
terminado, para que la cola del servidor se vea en la latencia y no en una tasa más baja.
"""

import argparse
import asyncio
import contextlib
import csv
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from scripts.e2e_k3d import CLAVE, GATEWAY, SERVICIO, borrar, esperar, kubectl, preparar

OVERLAY = SERVICIO / "e2e" / "overlay-carga"
REPORTE = SERVICIO / "docs" / "evidencias" / "carga-k3d.txt"
MUESTRAS = SERVICIO / "docs" / "evidencias" / "carga-k3d.csv"
SELECTOR = "app.kubernetes.io/name=iam-service,app.kubernetes.io/component=api"
NS = ("-n", "turismo-app")

DURACION = 120  # s por fase
VENTANA = 5  # s entre muestras
TRAMOS = (2, 4, 8, 12, 16)  # logins/s de la búsqueda del pico
VERIFICAR = 50  # verificar/s en la referencia y en la mezcla
USUARIOS = 20
TOPE = 10.0  # s: un login más lento que esto es ruptura, salvo el 503 diseñado (C-53)
DRENAJE = 35  # s de espera para las peticiones en vuelo al terminar una fase


# ---------- Medición ----------


@dataclass
class Respuesta:
    tipo: str  # login | verificar
    inicio: float  # s desde el inicio de la fase
    fin: float
    codigo: str  # "200", "503-OCUPADO", "503", "429", nombre de la excepción...
    retry_after: str | None = None

    @property
    def latencia(self) -> float:
        return self.fin - self.inicio


@dataclass
class Muestra:
    t: float
    deseadas: int | None
    listas: int | None
    hpa_cpu: int | None
    cpu: dict[str, int]


@dataclass
class Fase:
    nombre: str
    logins: float
    verificar: float
    duracion: int
    respuestas: list[Respuesta] = field(default_factory=list)
    muestras: list[Muestra] = field(default_factory=list)
    hitos: dict[str, float] = field(default_factory=dict)
    cpu_reposo: dict[str, int] = field(default_factory=dict)
    retraso_max: float = 0.0


def percentil(valores: list[float], p: float) -> float | None:
    """Rango más cercano: el valor que deja por debajo al p % de las observaciones."""
    if not valores:
        return None
    ordenados = sorted(valores)
    indice = max(0, min(len(ordenados) - 1, int(-(-p * len(ordenados) // 100)) - 1))
    return ordenados[indice]


def codigo_de(respuesta: httpx.Response) -> str:
    if respuesta.status_code != 503:
        return str(respuesta.status_code)
    try:
        code = respuesta.json().get("code")
    except ValueError:
        code = None
    return "503-OCUPADO" if code == "SERVICIO_OCUPADO" else "503"


# ---------- Clúster ----------


def estado_replicas() -> tuple[int | None, int | None, int | None]:
    """(réplicas del Deployment, listas, % de CPU que ve el HPA)."""

    def numero(texto: str) -> int | None:
        return int(texto) if texto.strip().isdigit() else None

    salida = kubectl(
        *NS, "get", "deploy/iam-service", "-o",
        "jsonpath={.spec.replicas}|{.status.readyReplicas}",
    )  # fmt: skip
    deseadas, listas = (numero(p) for p in salida.split("|"))
    try:  # entre fases el HPA está borrado
        hpa_cpu = numero(
            kubectl(
                *NS,
                "get",
                "hpa",
                "iam-service",
                "-o",
                "jsonpath={.status.currentMetrics[0].resource.current.averageUtilization}",
            )  # fmt: skip
        )
    except RuntimeError:
        hpa_cpu = None
    return deseadas, listas, hpa_cpu


def cpu_pods() -> dict[str, int]:
    salida = kubectl(*NS, "top", "pods", "-l", SELECTOR, "--no-headers")
    cpu: dict[str, int] = {}
    for linea in salida.splitlines():
        partes = linea.split()
        if len(partes) >= 2 and partes[1].endswith("m"):
            cpu[partes[0].removeprefix("iam-service-")] = int(partes[1][:-1])
    return cpu


def pods_api() -> int:
    salida = kubectl(
        *NS, "get", "pods", "-l", SELECTOR, "-o",
        "jsonpath={range .items[*]}{.metadata.deletionTimestamp}|{end}",
    )  # fmt: skip
    return salida.split("|")[:-1].count("")


def guardar_hpa() -> dict[str, Any]:
    hpa = json.loads(kubectl(*NS, "get", "hpa", "iam-service", "-o", "json"))
    return {
        "apiVersion": hpa["apiVersion"],
        "kind": hpa["kind"],
        "metadata": {"name": "iam-service", "namespace": "turismo-app"},
        "spec": hpa["spec"],
    }


def empezar_desde_dos(hpa: dict[str, Any]) -> dict[str, int]:
    """Borra el HPA (y con él su historial de 300 s para bajar), deja 2 réplicas en reposo y lo
    vuelve a crear con la misma especificación. Devuelve la CPU en reposo."""
    kubectl(*NS, "delete", "hpa", "iam-service", "--ignore-not-found")
    kubectl(*NS, "scale", "deploy/iam-service", "--replicas=2")
    kubectl(*NS, "rollout", "status", "deploy/iam-service", "--timeout=240s")
    if not esperar(lambda: pods_api() == 2 and estado_replicas()[1] == 2, 240, 2):
        raise RuntimeError("No quedaron 2 réplicas listas")

    def en_reposo() -> dict[str, int] | None:
        cpu = cpu_pods()
        return cpu if len(cpu) == 2 and max(cpu.values()) < 30 else None

    reposo = esperar(en_reposo, 240, 5)
    kubectl("apply", "-f", "-", entrada=json.dumps(hpa))
    if not esperar(lambda: estado_replicas()[2] is not None, 180, 3):
        raise RuntimeError("El HPA no leyó la CPU")
    return reposo or cpu_pods()


class Observador:
    """Dos hilos: réplicas cada segundo (hitos del HPA) y una muestra completa cada 5 s."""

    def __init__(self, fase: Fase, t0: float) -> None:
        self.fase, self.t0 = fase, t0
        self.alto = threading.Event()
        self.ultimo: tuple[int | None, int | None, int | None] = (None, None, None)

    def _hitos(self) -> None:
        while not self.alto.is_set():
            with contextlib.suppress(RuntimeError):
                self.ultimo = estado_replicas()
            t = time.monotonic() - self.t0
            deseadas, listas, _ = self.ultimo
            for n in (3, 4):
                if (deseadas or 0) >= n:
                    self.fase.hitos.setdefault(f"deseadas>={n}", t)
                if (listas or 0) >= n:
                    self.fase.hitos.setdefault(f"listas>={n}", t)
            self.alto.wait(1)

    def _muestras(self) -> None:
        k = 1
        while not self.alto.wait(max(0.0, self.t0 + k * VENTANA - time.monotonic())):
            try:
                cpu = cpu_pods()
            except RuntimeError:
                cpu = {}
            deseadas, listas, hpa_cpu = self.ultimo
            self.fase.muestras.append(Muestra(k * VENTANA, deseadas, listas, hpa_cpu, cpu))
            k += 1

    def __enter__(self) -> "Observador":
        self._hilos = [threading.Thread(target=f) for f in (self._hitos, self._muestras)]
        for hilo in self._hilos:
            hilo.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.alto.set()
        for hilo in self._hilos:
            hilo.join()


# ---------- Carga ----------


def cliente() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=GATEWAY,
        timeout=httpx.Timeout(30, pool=None),
        limits=httpx.Limits(max_connections=1000, max_keepalive_connections=200),
    )


async def calentar(http: httpx.AsyncClient, conexiones: int) -> None:
    """Abre las conexiones antes de medir. Abrir muchas a la vez por el puerto publicado de Docker
    Desktop es lento: sin esto, la primera ráfaga se encola y la cola no se recupera (el
    generador, no el IAM). Usa la ruta pública de whoami, que no pasa por el IAM."""
    await asyncio.gather(*(http.get("/modulo-publico/calentar") for _ in range(conexiones)))


async def generar(fase: Fase, emails: list[str], token: str | None) -> None:
    async with cliente() as logins, cliente() as verificaciones:
        await calentar(logins, 40 if fase.logins else 0)
        await calentar(verificaciones, 30 if fase.verificar else 0)
        tareas: list[asyncio.Task[None]] = []
        t0 = time.monotonic()  # después de crear y calentar los clientes

        async def login(i: int) -> None:
            inicio = time.monotonic()
            correo = emails[i % len(emails)]
            try:
                r = await logins.post("/api/iam/login", json={"email": correo, "password": CLAVE})
                codigo, retry = codigo_de(r), r.headers.get("retry-after")
            except Exception as exc:  # cualquier fallo del cliente cuenta como error
                codigo, retry = type(exc).__name__, None
            fase.respuestas.append(
                Respuesta("login", inicio - t0, time.monotonic() - t0, codigo, retry)
            )

        async def verificar(_: int) -> None:
            inicio = time.monotonic()
            try:
                r = await verificaciones.get(
                    "/otro-modulo/carga", headers={"Authorization": f"Bearer {token}"}
                )
                codigo = codigo_de(r)
            except Exception as exc:  # cualquier fallo del cliente cuenta como error
                codigo = type(exc).__name__
            fase.respuestas.append(
                Respuesta("verificar", inicio - t0, time.monotonic() - t0, codigo)
            )

        async def disparar(tasa: float, hacer: Any) -> None:
            for i in range(int(tasa * fase.duracion)):
                objetivo = t0 + i / tasa
                espera = objetivo - time.monotonic()
                if espera > 0:
                    await asyncio.sleep(espera)
                fase.retraso_max = max(fase.retraso_max, time.monotonic() - objetivo)
                tareas.append(asyncio.create_task(hacer(i)))

        flujos = [disparar(fase.logins, login)] if fase.logins else []
        flujos += [disparar(fase.verificar, verificar)] if fase.verificar else []
        with Observador(fase, t0):
            await asyncio.gather(*flujos)
            if tareas:
                await asyncio.wait(tareas, timeout=DRENAJE)


def correr_fase(fase: Fase, hpa: dict[str, Any], emails: list[str]) -> Fase:
    print(f"--- {fase.nombre}: preparando 2 réplicas en reposo", flush=True)
    fase.cpu_reposo = empezar_desde_dos(hpa)
    token = login_sincrono(emails[0]) if fase.verificar else None
    print(f"--- {fase.nombre}: {fase.logins} logins/s, {fase.verificar} verificar/s", flush=True)
    asyncio.run(generar(fase, emails, token))
    print(f"    {resumen_corto(fase)}", flush=True)
    return fase


def login_sincrono(email: str) -> str:
    def intento() -> str | None:
        r = httpx.post(f"{GATEWAY}/api/iam/login", json={"email": email, "password": CLAVE})
        return r.json()["access_token"] if r.status_code == 200 else None

    token = esperar(intento, 60, 2)
    if not token:
        raise RuntimeError("No se pudo iniciar sesión para verificar")
    return token


def crear_usuarios() -> list[str]:
    emails = []
    with httpx.Client(base_url=GATEWAY, timeout=30) as http:
        for _ in range(USUARIOS):
            email = f"carga.{uuid.uuid4().hex[:10]}@example.com"
            r = http.post(
                "/api/iam/register",
                json={
                    "email": email,
                    "password": CLAVE,
                    "nombre_completo": "Prueba de carga",
                    "rol": "Turista",
                    "habeas_data_aceptado": True,
                    "es_mayor_de_edad": True,
                    "idioma": "es",
                },
            )
            if r.status_code != 201:
                raise RuntimeError(f"registro: {r.status_code} {r.text[:200]}")
            emails.append(email)
    return emails


# ---------- Análisis ----------


def logins_de(fase: Fase) -> list[Respuesta]:
    return [r for r in fase.respuestas if r.tipo == "login"]


def verificaciones_de(fase: Fase) -> list[Respuesta]:
    return [r for r in fase.respuestas if r.tipo == "verificar"]


def es_ruptura(r: Respuesta) -> bool:
    """Error distinto del 503 diseñado, o un login que no es ese 503 y tarda más del tope."""
    return r.codigo not in ("200", "503-OCUPADO") or (
        r.codigo != "503-OCUPADO" and r.latencia > TOPE
    )


def ms(valor: float | None) -> str:
    return "-" if valor is None else f"{valor * 1000:.0f}"


def pct(parte: int, total: int) -> float:
    return 100 * parte / total if total else 0.0


def estadisticas(fase: Fase) -> dict[str, Any]:
    logins = logins_de(fase)
    ok = [r.latencia for r in logins if r.codigo == "200"]
    ocupados = [r for r in logins if r.codigo == "503-OCUPADO"]
    verif = verificaciones_de(fase)
    lat_v = [r.latencia for r in verif if r.codigo == "200"]
    cpu = [sum(m.cpu.values()) for m in fase.muestras if m.cpu and m.t <= fase.duracion]
    por_pod = [v for m in fase.muestras if m.t <= fase.duracion for v in m.cpu.values()]
    return {
        "logins": len(logins),
        "logins_200": len(ok),
        "ocupados": len(ocupados),
        "ocupados_pct": pct(len(ocupados), len(logins)),
        "retry_after": dict(Counter(r.retry_after for r in ocupados)),
        "codigos_login": dict(Counter(r.codigo for r in logins)),
        "rupturas": [asdict(r) for r in logins if es_ruptura(r)],
        "p50": percentil(ok, 50),
        "p95": percentil(ok, 95),
        "p99": percentil(ok, 99),
        "max_login": max((r.latencia for r in logins), default=None),
        "mas_de_tope_200": sum(1 for r in logins if r.codigo == "200" and r.latencia > TOPE),
        "verificar": len(verif),
        "verificar_p50": percentil(lat_v, 50),
        "verificar_p95": percentil(lat_v, 95),
        "verificar_p99": percentil(lat_v, 99),
        "codigos_verificar": dict(Counter(r.codigo for r in verif)),
        "cpu_total_media": sum(cpu) / len(cpu) if cpu else None,
        "cpu_pod_max": max(por_pod, default=None),
    }


def resumen_corto(fase: Fase) -> str:
    e = estadisticas(fase)
    return (
        f"logins={e['logins']} 200={e['logins_200']} 503={e['ocupados']} "
        f"({e['ocupados_pct']:.1f} %) p95={ms(e['p95'])} ms rupturas={len(e['rupturas'])} "
        f"verificar={e['verificar']} p95v={ms(e['verificar_p95'])} ms hitos={fase.hitos}"
    )


def filas_de_muestras(fase: Fase) -> list[dict[str, Any]]:
    filas = []
    for m in fase.muestras:
        ventana = [r for r in fase.respuestas if m.t - VENTANA < r.fin <= m.t]
        logins = [r for r in ventana if r.tipo == "login"]
        ok = [r.latencia for r in logins if r.codigo == "200"]
        verif = [r for r in ventana if r.tipo == "verificar"]
        otros = Counter(r.codigo for r in logins if r.codigo not in ("200", "503-OCUPADO"))
        filas.append(
            {
                "fase": fase.nombre,
                "t_s": int(m.t),
                "logins_por_s": round(len(ok) / VENTANA, 1),
                "logins_respondidos": len(logins),
                "login_p50_ms": ms(percentil(ok, 50)),
                "login_p95_ms": ms(percentil(ok, 95)),
                "login_p99_ms": ms(percentil(ok, 99)),
                "ocupado_503_pct": round(
                    pct(sum(r.codigo == "503-OCUPADO" for r in logins), len(logins)), 1
                ),
                "otros_errores_login": ";".join(f"{c}:{n}" for c, n in otros.items()),
                "verificar_respondidos": len(verif),
                "verificar_p95_ms": ms(
                    percentil([r.latencia for r in verif if r.codigo == "200"], 95)
                ),
                "verificar_errores": sum(r.codigo != "200" for r in verif),
                "replicas_deseadas": m.deseadas,
                "replicas_listas": m.listas,
                "hpa_cpu_pct": m.hpa_cpu,
                "cpu_pods_m": ";".join(f"{p}:{v}" for p, v in sorted(m.cpu.items())),
                "cpu_total_m": sum(m.cpu.values()) if m.cpu else "",
            }
        )
    return filas


# ---------- Reporte ----------


def maquina() -> dict[str, Any]:
    datos: dict[str, Any] = {"nucleos_logicos": os.cpu_count()}
    if sys.platform == "win32":

        class Memoria(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                *[(n, ctypes.c_ulonglong) for n in ("a", "b", "c", "d", "e", "f")],
            ]

        memoria = Memoria()
        memoria.dwLength = ctypes.sizeof(Memoria)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memoria))
        datos["ram_gib"] = round(memoria.ullTotalPhys / 2**30, 1)
    docker = subprocess.run(
        ["docker", "info", "--format", "{{.NCPU}}|{{.MemTotal}}"], capture_output=True, text=True
    ).stdout.strip()
    if "|" in docker:
        cpus, memoria_docker = docker.split("|")
        datos["docker_cpus"] = int(cpus)
        datos["docker_gib"] = round(int(memoria_docker) / 2**30, 1)
    return datos


def entorno() -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "describe", "--always", "--dirty"], cwd=SERVICIO, capture_output=True, text=True
    ).stdout.strip()
    k3s = kubectl("get", "nodes", "-o", "jsonpath={.items[0].status.nodeInfo.kubeletVersion}")
    traefik = kubectl(
        "-n", "kube-system", "get", "deploy", "traefik",
        "-o", "jsonpath={.spec.template.spec.containers[0].image}",
    )  # fmt: skip
    return {
        "fecha": f"{datetime.now(UTC):%Y-%m-%d %H:%M UTC}",
        "commit": commit,
        "k3s": k3s,
        "traefik": traefik,
        "maquina": maquina(),
    }


def tabla(filas: list[dict[str, Any]]) -> list[str]:
    columnas = [
        ("t_s", "t(s)"), ("logins_por_s", "login/s"), ("login_p50_ms", "p50"),
        ("login_p95_ms", "p95"), ("login_p99_ms", "p99"), ("ocupado_503_pct", "503%"),
        ("otros_errores_login", "otros"), ("verificar_p95_ms", "verif p95"),
        ("replicas_deseadas", "rép.des"), ("replicas_listas", "rép.listas"),
        ("hpa_cpu_pct", "HPA%"), ("cpu_pods_m", "CPU por pod (m)"),
    ]  # fmt: skip
    datos = [[str(f[c] if f[c] not in (None, "") else "-") for c, _ in columnas] for f in filas]
    anchos = [max(len(t), *(len(d[i]) for d in datos)) for i, (_, t) in enumerate(columnas)]
    lineas = ["  " + "  ".join(t.rjust(a) for (_, t), a in zip(columnas, anchos, strict=True))]
    lineas += ["  " + "  ".join(v.rjust(a) for v, a in zip(d, anchos, strict=True)) for d in datos]
    return lineas


def umbrales(fases: list[Fase]) -> tuple[str, str]:
    solo_login = sorted((f for f in fases if f.logins and not f.verificar), key=lambda f: f.logins)
    saturacion = next((f for f in solo_login if estadisticas(f)["ocupados_pct"] > 1), None)
    ruptura = next((f for f in solo_login if estadisticas(f)["rupturas"]), None)
    maximo = max((f.logins for f in solo_login), default=0)
    return (
        f"{saturacion.logins:g} logins/s" if saturacion else f"no alcanzada hasta {maximo:g}/s",
        f"{ruptura.logins:g} logins/s" if ruptura else f"no alcanzada hasta {maximo:g}/s",
    )


def escribir(datos: dict[str, Any], fases: list[Fase]) -> None:
    filas = [fila for fase in fases for fila in filas_de_muestras(fase)]
    with MUESTRAS.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=list(filas[0]), lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(filas)

    m = datos["maquina"]
    lineas = [
        "# Carga del login de iam-service en k3d, detrás de Traefik (prueba, no producción)",
        f"# Fecha: {datos['fecha']}",
        f"# Commit: {datos['commit']}",
        f"# k3s: {datos['k3s']}  Traefik: {datos['traefik']}",
        f"# Máquina: {m.get('nucleos_logicos')} núcleos lógicos, {m.get('ram_gib')} GiB de RAM; "
        f"Docker Desktop con {m.get('docker_cpus')} CPU y {m.get('docker_gib')} GiB. "
        "El generador de carga corre en la misma máquina.",
        "#",
        "# Método:",
        "# - Overlay e2e/overlay-carga: el overlay e2e con el Middleware iam-rate-limit en "
        "100/s (burst 100)",
        "#   en lugar de 5/min. Sigue en la cadena de Traefik; en k3d todos los clientes "
        "comparten IP (F-08).",
        "# - Logins: POST /api/iam/login por el gateway, en rueda sobre "
        f"{USUARIOS} usuarios creados antes.",
        "# - Verificar: GET /otro-modulo/carga con Bearer, un ForwardAuth por petición (el caso "
        "real).",
        "# - Lazo abierto: cada petición sale a su hora aunque las anteriores no hayan terminado.",
        "# - Antes de cada fase: se borra el HPA (y su historial de 300 s para bajar), se escala",
        "#   a 2, se espera CPU < 30m por pod y se recrea con la misma especificación (2-4, 70 %).",
        f"# - Muestras cada {VENTANA} s: percentiles sobre los 200 que terminaron en la ventana; "
        "CPU con kubectl top",
        "#   (metrics-server, ventana propia de unos 15 s). Detalle en carga-k3d.csv.",
        "# - Ruptura: un error distinto de 503 SERVICIO_OCUPADO, o un login que no es ese 503 y "
        f"tarda más de {TOPE:g} s.",
        "",
    ]
    for fase in fases:
        e = estadisticas(fase)
        hitos = ", ".join(f"{k} a los {v:.0f} s" for k, v in fase.hitos.items()) or "sin cambios"
        lineas += [
            f"## {fase.nombre}: {fase.logins:g} logins/s y {fase.verificar:g} verificar/s, "
            f"{fase.duracion} s",
            f"  Logins: {e['logins']} enviados, {e['logins_200']} con 200, {e['ocupados']} con "
            f"503 SERVICIO_OCUPADO ({e['ocupados_pct']:.1f} %), códigos {e['codigos_login']}",
            f"  Login (200): p50 {ms(e['p50'])} ms, p95 {ms(e['p95'])} ms, p99 {ms(e['p99'])} ms; "
            f"máximo de cualquier respuesta {ms(e['max_login'])} ms",
            f"  Retry-After recibidos: {e['retry_after'] or 'ninguno'}; 200 de más de {TOPE:g} s: "
            f"{e['mas_de_tope_200']}; rupturas: {len(e['rupturas'])}",
        ]
        if e["verificar"]:
            lineas.append(
                f"  Verificar: {e['verificar']} enviados, p50 {ms(e['verificar_p50'])} ms, "
                f"p95 {ms(e['verificar_p95'])} ms, p99 {ms(e['verificar_p99'])} ms, "
                f"códigos {e['codigos_verificar']}"
            )
        lineas += [
            f"  HPA: {hitos}",
            f"  CPU en reposo antes de empezar (m): {fase.cpu_reposo}; media del total durante la "
            f"fase {e['cpu_total_media'] and round(e['cpu_total_media'])}m, máximo de un pod "
            f"{e['cpu_pod_max']}m",
            f"  Retraso máximo del generador: {fase.retraso_max * 1000:.0f} ms",
            *tabla(filas_de_muestras(fase)),
            "",
        ]
        for ruptura in e["rupturas"][:10]:
            lineas.insert(-1, f"  Ruptura: {ruptura}")

    saturacion, ruptura = umbrales(fases)
    referencia = next((f for f in fases if f.verificar and not f.logins), None)
    mezcla = next((f for f in fases if f.verificar and f.logins), None)
    lineas += ["## Conclusiones medidas", f"  Saturación (503 > 1 %): {saturacion}"]
    lineas.append(f"  Ruptura: {ruptura}")
    if referencia and mezcla:
        r, x = estadisticas(referencia), estadisticas(mezcla)
        lineas.append(
            f"  Verificar p95: {ms(r['verificar_p95'])} ms solo, {ms(x['verificar_p95'])} ms con "
            f"logins; p99 {ms(r['verificar_p99'])} y {ms(x['verificar_p99'])} ms; errores "
            f"{sum(n for c, n in x['codigos_verificar'].items() if c != '200')} en la mezcla"
        )
    REPORTE.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lineas))


def a_crudo(datos: dict[str, Any], fases: list[Fase]) -> dict[str, Any]:
    return {"entorno": datos, "fases": [asdict(f) for f in fases]}


def de_crudo(crudo: dict[str, Any]) -> tuple[dict[str, Any], list[Fase]]:
    fases = []
    for f in crudo["fases"]:
        fase = Fase(**{k: v for k, v in f.items() if k not in ("respuestas", "muestras")})
        fase.respuestas = [Respuesta(**r) for r in f["respuestas"]]
        fase.muestras = [Muestra(**m) for m in f["muestras"]]
        fases.append(fase)
    return crudo["entorno"], fases


# ---------- Principal ----------


def correr(crudo: Path | None) -> None:
    datos = entorno()
    hpa = guardar_hpa()
    print("Creando usuarios de prueba...", flush=True)
    emails = crear_usuarios()
    fases: list[Fase] = []

    def guardar() -> None:
        if crudo:
            crudo.write_text(json.dumps(a_crudo(datos, fases)), encoding="utf-8")

    fases.append(correr_fase(Fase("Base", 1, 0, DURACION), hpa, emails))
    guardar()
    for tasa in TRAMOS:
        fase = correr_fase(Fase(f"Pico {tasa}/s", tasa, 0, DURACION), hpa, emails)
        fases.append(fase)
        guardar()
        if estadisticas(fase)["rupturas"]:
            print(f"Ruptura a {tasa}/s: se detiene la búsqueda", flush=True)
            break
    fases.append(correr_fase(Fase("Referencia de verificar", 0, VERIFICAR, 60), hpa, emails))
    guardar()
    fases.append(correr_fase(Fase("Mezcla", 2, VERIFICAR, DURACION), hpa, emails))
    guardar()
    escribir(datos, fases)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conservar", action="store_true", help="no borra el clúster al terminar")
    parser.add_argument("--sin-preparar", action="store_true", help="usa un clúster ya preparado")
    parser.add_argument("--crudo", type=Path, help="guarda las respuestas y muestras en JSON")
    parser.add_argument("--solo-reporte", type=Path, help="regenera el reporte desde un crudo")
    args = parser.parse_args()
    if args.solo_reporte:
        escribir(*de_crudo(json.loads(args.solo_reporte.read_text(encoding="utf-8"))))
        return 0
    try:
        if not args.sin_preparar:
            preparar(OVERLAY)
        correr(args.crudo)
        return 0
    finally:
        if not args.conservar:
            borrar()


if __name__ == "__main__":
    sys.exit(main())
