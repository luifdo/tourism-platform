"""Escenarios punta a punta de iam-service detrás de Traefik, en un k3d temporal.

ENTORNO DE PRUEBA, NO DE PRODUCCIÓN (ver e2e/README.md).
Uso: uv run python -m scripts.e2e_k3d [--conservar | --solo-borrar]

Las llaves JWT y el kubeconfig viven en una carpeta temporal que se borra al terminar. El reporte
no lleva tokens ni contraseñas.
"""

import argparse
import json
import os
import re
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import boto3
import httpx
from botocore.client import Config
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

SERVICIO = Path(__file__).resolve().parents[1]
REPORTE = SERVICIO / "docs" / "evidencias" / "e2e-k3d.txt"
CLUSTER = "iam-e2e"
IMAGEN = "iam-service:e2e"
CARPETA = Path(os.environ.get("E2E_DIR") or Path(tempfile.gettempdir()) / "iam-e2e")
KUBECONFIG = CARPETA / "kubeconfig"

GATEWAY = "http://127.0.0.1:18080"
HOST_DOCUMENTOS = "documentos.localhost:18080"
PUERTOS = {
    "postgres": (25433, 5432),
    "rabbitmq": (25673, 15672),
    "mailpit": (28025, 8025),
    "seaweedfs": (28333, 8333),
}
RABBIT = "http://127.0.0.1:25673/api"
AUTH_RABBIT = ("e2e", "solo-para-pruebas-e2e")
MAILPIT = "http://127.0.0.1:28025/api/v1"
CLAVE_FALSA = "solo-para-pruebas-e2e"
CLAVE = "SoloPruebasE2e123"
ADMIN_EMAIL = "admin.e2e@example.com"
BUCKET = "documentos-verificacion"
CONTACTO = "http://iam-service.turismo-app.svc:8001/internal/usuarios/{id}/contacto"
PDF = b"%PDF-1.7\n%documento de prueba e2e\n"


# ---------- Infraestructura ----------


def ejecutar(*cmd: str, entrada: str | None = None, timeout: int = 600) -> str:
    resultado = subprocess.run(
        cmd, input=entrada, capture_output=True, text=True, encoding="utf-8", timeout=timeout
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:4])}: {resultado.stderr.strip()[-400:]}")
    return resultado.stdout


def kubectl(*args: str, entrada: str | None = None, timeout: int = 400) -> str:
    return ejecutar(
        "kubectl", "--kubeconfig", str(KUBECONFIG), *args, entrada=entrada, timeout=timeout
    )


def esperar(condicion: Callable[[], Any], limite: float, paso: float = 0.5) -> Any:
    """Devuelve el primer valor verdadero de `condicion`, o None al agotar el tiempo."""
    fin = time.monotonic() + limite
    while time.monotonic() < fin:
        try:
            valor = condicion()
        except (httpx.HTTPError, OSError, RuntimeError):
            valor = None
        if valor:
            return valor
        time.sleep(paso)
    return None


def generar_llaves() -> None:
    privada = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    (CARPETA / "private.pem").write_bytes(
        privada.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (CARPETA / "public.pem").write_bytes(
        privada.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )


def preparar() -> None:
    CARPETA.mkdir(parents=True, exist_ok=True)
    generar_llaves()
    print("Creando el clúster...", flush=True)
    ejecutar(
        "k3d", "cluster", "create", CLUSTER,
        "-p", "18080:80@loadbalancer",
        "--kubeconfig-update-default=false",
        "--wait", "--timeout", "300s",
    )  # fmt: skip
    KUBECONFIG.write_text(ejecutar("k3d", "kubeconfig", "get", CLUSTER), encoding="utf-8")

    print("Construyendo la imagen...", flush=True)
    ejecutar("docker", "build", "-q", "-t", IMAGEN, str(SERVICIO), timeout=900)
    ejecutar("k3d", "image", "import", IMAGEN, "-c", CLUSTER, timeout=600)

    print("Esperando a Traefik...", flush=True)
    if not esperar(lambda: kubectl("get", "crd", "ingressroutes.traefik.io"), 240, 3):
        raise RuntimeError("Los CRD de Traefik no aparecieron")
    kubectl(
        "-n",
        "kube-system",
        "wait",
        "--for=condition=Complete",
        "job/helm-install-traefik",
        "--timeout=240s",
    )
    kubectl("-n", "kube-system", "rollout", "status", "deploy/traefik", "--timeout=180s")

    print("Desplegando las dependencias...", flush=True)
    kubectl("apply", "-f", str(SERVICIO / "e2e" / "dependencias.yaml"))
    for nombre in ("postgres", "valkey", "rabbitmq", "mailpit", "seaweedfs"):
        kubectl("-n", "turismo-datos", "rollout", "status", f"deploy/{nombre}", "--timeout=300s")
    kubectl(
        "-n",
        "turismo-datos",
        "wait",
        "--for=condition=Complete",
        "job/seaweedfs-buckets",
        "--timeout=180s",
    )

    print("Desplegando iam-service...", flush=True)
    kubectl("create", "namespace", "turismo-app")
    kubectl(
        "-n", "turismo-app", "create", "secret", "generic", "iam-jwt-keys",
        f"--from-file=private.pem={CARPETA / 'private.pem'}",
        f"--from-file=public.pem={CARPETA / 'public.pem'}",
    )  # fmt: skip
    manifiestos = kubectl("kustomize", str(SERVICIO / "e2e" / "overlay"))
    kubectl("apply", "-f", "-", entrada=manifiestos)
    for nombre in ("iam-service", "iam-worker", "whoami"):
        kubectl("-n", "turismo-app", "rollout", "status", f"deploy/{nombre}", "--timeout=300s")


class PuertosReenviados:
    """`kubectl port-forward` hacia las dependencias, solo para preparar y comprobar."""

    def __init__(self) -> None:
        self._procesos: list[subprocess.Popen[bytes]] = []

    def __enter__(self) -> "PuertosReenviados":
        for servicio, (local, remoto) in PUERTOS.items():
            self._procesos.append(
                subprocess.Popen(
                    [
                        "kubectl",
                        "--kubeconfig",
                        str(KUBECONFIG),
                        "-n",
                        "turismo-datos",
                        "port-forward",
                        f"svc/{servicio}",
                        f"{local}:{remoto}",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )  # fmt: skip
            )
            if not esperar(lambda p=local: socket.create_connection(("127.0.0.1", p), 1), 30):
                raise RuntimeError(f"Sin port-forward hacia {servicio}")
        return self

    def __exit__(self, *_: object) -> None:
        for proceso in self._procesos:
            proceso.terminate()
            proceso.wait(timeout=10)


def sembrar_admin() -> None:
    url = f"postgresql+asyncpg://iam_user:{CLAVE_FALSA}@127.0.0.1:{PUERTOS['postgres'][0]}/iam_db"
    entorno = {
        **os.environ,
        "DATABASE_URL": url,
        "ADMIN_EMAIL": ADMIN_EMAIL,
        "ADMIN_PASSWORD": CLAVE,
        "ADMIN_NOMBRE": "Admin e2e",
    }
    resultado = subprocess.run(
        [sys.executable, "-m", "scripts.seed_admin"], cwd=SERVICIO, env=entorno, capture_output=True
    )
    if resultado.returncode != 0:
        raise RuntimeError(f"seed_admin: {resultado.stderr.decode(errors='replace')[-400:]}")


def borrar() -> None:
    subprocess.run(["k3d", "cluster", "delete", CLUSTER], capture_output=True)
    subprocess.run(["docker", "rmi", IMAGEN], capture_output=True)
    shutil.rmtree(CARPETA, ignore_errors=True)


# ---------- Reporte ----------


@dataclass
class Escenario:
    nombre: str
    lineas: list[str] = field(default_factory=list)
    fallos: int = 0

    def check(self, descripcion: str, condicion: bool, detalle: object = "") -> bool:
        self.lineas.append(
            f"  {'OK   ' if condicion else 'FALLO'} {descripcion}"
            + (f"  -> {detalle}" if detalle != "" else "")
        )
        self.fallos += 0 if condicion else 1
        return condicion

    def dato(self, descripcion: str) -> None:
        self.lineas.append(f"  DATO  {descripcion}")


def texto(respuesta: httpx.Response) -> str:
    return f"{respuesta.status_code} {respuesta.text[:200]}"


# ---------- Clientes ----------


class Plataforma:
    """Todo lo que usa el usuario pasa por el gateway. El rate limiting del login se respeta."""

    def __init__(self) -> None:
        self.http = httpx.Client(base_url=GATEWAY, timeout=30)
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"http://127.0.0.1:{PUERTOS['seaweedfs'][0]}",
            aws_access_key_id="iam_access_e2e",
            aws_secret_access_key=CLAVE_FALSA,
            region_name="us-east-1",
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
        self._admin: tuple[str, float] | None = None

    def post_limitado(self, ruta: str, cuerpo: dict[str, Any]) -> httpx.Response:
        """Login y recuperar comparten el límite por IP: se espera ante un 429 (no es el fallo
        que se prueba aquí; ese es el escenario i)."""
        for _ in range(12):
            respuesta = self.http.post(ruta, json=cuerpo)
            if respuesta.status_code != 429:
                return respuesta
            time.sleep(13)
        return respuesta

    def login(self, email: str, clave: str = CLAVE) -> str:
        respuesta = self.post_limitado("/api/iam/login", {"email": email, "password": clave})
        if respuesta.status_code != 200:
            raise RuntimeError(f"login: {respuesta.status_code}")
        return respuesta.json()["access_token"]

    def admin(self) -> dict[str, str]:
        if self._admin is None or time.monotonic() - self._admin[1] > 600:
            self._admin = (self.login(ADMIN_EMAIL), time.monotonic())
        return bearer(self._admin[0])

    def registrar(self, rol: str = "Turista", idioma: str = "es") -> tuple[str, str]:
        email = f"e2e.{uuid.uuid4().hex[:10]}@example.com"
        respuesta = self.http.post(
            "/api/iam/register",
            json={
                "email": email,
                "password": CLAVE,
                "nombre_completo": "Prueba e2e",
                "rol": rol,
                "habeas_data_aceptado": True,
                "es_mayor_de_edad": True,
                "idioma": idioma,
            },
        )
        if respuesta.status_code != 201:
            raise RuntimeError(f"registro: {texto(respuesta)}")
        return email, respuesta.json()["id"]

    def subir(
        self, cabeceras: dict[str, str], tipo: str, razon: str | None = None
    ) -> httpx.Response:
        datos = {"tipo": tipo} | ({"razon_social": razon} if razon else {})
        return self.http.post(
            "/api/iam/prestador/documentos",
            data=datos,
            files={"archivo": (f"{tipo}.pdf", PDF, "application/pdf")},
            headers=cabeceras,
        )

    def bitacora(self, **filtros: str) -> list[dict[str, Any]]:
        respuesta = self.http.get(
            "/api/iam/admin/bitacora", params={"tamano": "100", **filtros}, headers=self.admin()
        )
        respuesta.raise_for_status()
        return respuesta.json()["items"]

    def objetos(self, prefijo: str) -> list[str]:
        listado = self.s3.list_objects_v2(Bucket=BUCKET, Prefix=prefijo)
        return [o["Key"] for o in listado.get("Contents", [])]

    def verifica(self, token: str) -> int:
        return self.http.get("/api/iam/auth/verificar", headers=bearer(token)).status_code


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def encabezados_de_whoami(cuerpo: str) -> dict[str, list[str]]:
    resultado: dict[str, list[str]] = {}
    for linea in cuerpo.splitlines():
        nombre, separador, valor = linea.partition(": ")
        if separador:
            resultado.setdefault(nombre.lower(), []).append(valor)
    return resultado


class ColaDePrueba:
    """Cola temporal enlazada a una clave del exchange, por la API de gestión de RabbitMQ."""

    def __init__(self, clave: str) -> None:
        self.nombre = f"e2e.{clave}.{uuid.uuid4().hex[:6]}"
        httpx.put(
            f"{RABBIT}/queues/%2f/{self.nombre}",
            # Durable: RabbitMQ 4 ya no admite colas transitorias no exclusivas.
            json={"durable": True, "auto_delete": False},
            auth=AUTH_RABBIT,
        ).raise_for_status()
        httpx.post(
            f"{RABBIT}/bindings/%2f/e/turismo.eventos/q/{self.nombre}",
            json={"routing_key": clave},
            auth=AUTH_RABBIT,
        ).raise_for_status()

    def esperar_evento(
        self, condicion: Callable[[dict[str, Any]], bool], limite: float = 30
    ) -> Any:
        def buscar() -> dict[str, Any] | None:
            mensajes = leer_cola(self.nombre)
            for mensaje in mensajes:
                sobre = json.loads(mensaje["payload"])
                if condicion(sobre):
                    return sobre
            return None

        return esperar(buscar, limite, 1)


def leer_cola(nombre: str) -> list[dict[str, Any]]:
    respuesta = httpx.post(
        f"{RABBIT}/queues/%2f/{nombre}/get",
        json={"count": 200, "ackmode": "ack_requeue_true", "encoding": "auto"},
        auth=AUTH_RABBIT,
        timeout=15,
    )
    respuesta.raise_for_status()
    return respuesta.json()


def publicar(sobre: dict[str, Any] | str, clave: str = "auditoria.registrada") -> bool:
    cuerpo = sobre if isinstance(sobre, str) else json.dumps(sobre)
    respuesta = httpx.post(
        f"{RABBIT}/exchanges/%2f/turismo.eventos/publish",
        json={
            "routing_key": clave,
            "payload": cuerpo,
            "payload_encoding": "string",
            "properties": {"delivery_mode": 2, "content_type": "application/json"},
        },
        auth=AUTH_RABBIT,
    )
    respuesta.raise_for_status()
    return respuesta.json()["routed"]


def pod_de_prueba(nombre: str, etiquetas: str, usuario_id: str, encabezados: str = "{}") -> str:
    """Corre una petición al contacto interno desde un pod con esas etiquetas. Reintenta 20 s:
    kube-router tarda unos segundos en registrar un pod nuevo (C-54)."""
    codigo = f"""
import time, urllib.request, urllib.error
url = {CONTACTO.format(id=usuario_id)!r}
resultado = "SIN_CONEXION"
fin = time.monotonic() + 20
while time.monotonic() < fin:
    try:
        peticion = urllib.request.Request(url, headers={encabezados})
        resultado = str(urllib.request.urlopen(peticion, timeout=2).status)
        break
    except urllib.error.HTTPError as exc:
        resultado = str(exc.code)
        break
    except Exception:
        time.sleep(1)
print("RESULTADO=" + resultado)
"""
    pod = f"{nombre}-{uuid.uuid4().hex[:5]}"
    kubectl(
        "-n", "turismo-app", "run", pod, f"--image={IMAGEN}", "--image-pull-policy=Never",
        "--restart=Never", f"--labels={etiquetas}", "--command", "--", "python", "-c", codigo,
    )  # fmt: skip
    kubectl(
        "-n", "turismo-app", "wait", f"pod/{pod}",
        "--for=jsonpath={.status.phase}=Succeeded", "--timeout=90s",
    )  # fmt: skip
    salida = kubectl("-n", "turismo-app", "logs", pod)
    kubectl("-n", "turismo-app", "delete", "pod", pod, "--now")
    coincidencia = re.search(r"RESULTADO=(\S+)", salida)
    return coincidencia.group(1) if coincidencia else "SIN_SALIDA"


ETIQUETAS_WORKER = "app.kubernetes.io/name=catalog-service,app.kubernetes.io/component=worker"
ETIQUETAS_OTRO = "app.kubernetes.io/name=otro-servicio"


# ---------- Escenarios ----------


def prestador_con_documentos(p: Plataforma, razon: str) -> tuple[str, str, dict[str, str]]:
    email, usuario_id = p.registrar("Prestador", "en")
    cabeceras = bearer(p.login(email))
    for tipo, razon_tipo in (("RNT", None), ("RUT", razon)):
        respuesta = p.subir(cabeceras, tipo, razon_tipo)
        if respuesta.status_code != 201:
            raise RuntimeError(f"carga {tipo}: {texto(respuesta)}")
    return email, usuario_id, cabeceras


def documento_de(p: Plataforma, usuario_id: str) -> str:
    respuesta = p.http.get(f"/api/iam/admin/prestadores/{usuario_id}/documentos", headers=p.admin())
    respuesta.raise_for_status()
    return respuesta.json()["documentos"][0]["id"]


def abrir_firmada(url: str, firmada: bool = True) -> httpx.Response:
    """El host del enlace va dentro de la firma: se conecta al gateway y se conserva ese Host."""
    partes = urlsplit(url)
    destino = GATEWAY + partes.path + (f"?{partes.query}" if firmada else "")
    return httpx.get(destino, headers={"Host": partes.netloc}, timeout=15)


def escenario_a(p: Plataforma, e: Escenario) -> None:
    aprobados = ColaDePrueba("prestador.aprobado")
    suspendidos = ColaDePrueba("prestador.suspendido")
    razon = f"Turismo e2e {uuid.uuid4().hex[:6]}"

    email, usuario_id = p.registrar("Prestador", "en")
    e.check("Registro de Prestador con idioma en", True, usuario_id[:8])
    login = p.post_limitado("/api/iam/login", {"email": email, "password": CLAVE})
    e.check(
        "Login devuelve idioma en", login.json()["usuario"].get("idioma") == "en", login.status_code
    )
    cabeceras = bearer(login.json()["access_token"])

    r = p.subir(cabeceras, "RNT")
    e.check("Carga del RNT -> 201", r.status_code == 201, texto(r) if r.status_code != 201 else "")
    r = p.subir(cabeceras, "RUT", razon)
    e.check("Carga del RUT con razón social -> 201", r.status_code == 201, r.status_code)

    # Con curl: Traefik responde sin leer el cuerpo, y httpx no lee la respuesta hasta terminar
    # de enviar, así que se quedaría bloqueado escribiendo.
    grande = CARPETA / "grande.pdf"
    grande.write_bytes(b"%PDF-" + b"0" * 7_000_000)
    codigo = ejecutar(
        "curl", "-s", "-m", "30", "-o", os.devnull, "-w", "%{http_code}",
        "-H", f"Authorization: {cabeceras['Authorization']}", "-F", "tipo=RNT",
        "-F", f"archivo=@{grande};type=application/pdf",
        f"{GATEWAY}/api/iam/prestador/documentos",
    )  # fmt: skip
    grande.unlink()
    e.check("Cuerpo de 7 MB -> 413 en el gateway", codigo == "413", codigo)

    r = p.http.get("/api/iam/admin/prestadores", params={"estado": "pendiente"}, headers=p.admin())
    e.check(
        "El Admin lo ve en pendientes",
        any(i["usuario_id"] == usuario_id for i in r.json()["items"]),
        r.status_code,
    )

    documento = documento_de(p, usuario_id)
    r = p.http.get(f"/api/iam/admin/documentos/{documento}/url", headers=p.admin())
    e.check("URL firmada -> 200", r.status_code == 200, r.status_code)
    archivo = abrir_firmada(r.json()["url"])
    e.check(
        "La URL firmada abre el documento real",
        archivo.status_code == 200 and archivo.content == PDF,
        archivo.status_code,
    )
    e.check("Abrir el documento dejó DOCUMENT_VIEW", bool(p.bitacora(accion="DOCUMENT_VIEW")))

    r = p.http.post(f"/api/iam/admin/prestadores/{usuario_id}/aprobar", headers=p.admin())
    e.check("Aprobar -> 200", r.status_code == 200, r.status_code)
    sobre = aprobados.esperar_evento(lambda s: s["payload"].get("usuario_id") == usuario_id)
    e.check("prestador.aprobado llega a la cola de prueba", sobre is not None)
    if sobre:
        e.check(
            "prestador.aprobado lleva razon_social",
            sobre["payload"].get("razon_social") == razon,
            sobre["payload"].get("razon_social"),
        )
        e.check("prestador_id = usuario_id", sobre["payload"].get("prestador_id") == usuario_id)
        e.check("producer = iam-service", sobre.get("producer") == "iam-service")

    r = p.http.patch(
        f"/api/iam/admin/usuarios/{usuario_id}/estado",
        json={"activo": False, "motivo": "Motivo privado de la prueba"},
        headers=p.admin(),
    )
    e.check("Desactivar -> 200", r.status_code == 200, r.status_code)
    sobre = suspendidos.esperar_evento(lambda s: s["payload"].get("usuario_id") == usuario_id)
    e.check("prestador.suspendido llega a la cola de prueba", sobre is not None)
    if sobre:
        e.check("prestador.suspendido no lleva motivo", "motivo" not in sobre["payload"])


def escenario_b(p: Plataforma, e: Escenario) -> None:
    marca = uuid.uuid4().hex[:10]
    ruta = f"/otro-modulo/{marca}"

    r = p.http.get(ruta)
    e.check("Ruta protegida sin token -> 401", r.status_code == 401, r.status_code)
    filas = [
        f for f in p.bitacora(accion="ACCESS_DENIED") if (f["detalles"] or {}).get("uri") == ruta
    ]
    e.check("El 401 tiene su fila ACCESS_DENIED con la ruta", len(filas) == 1, len(filas))

    email, usuario_id = p.registrar()
    token = p.login(email)
    r = p.http.get(ruta, headers=bearer(token))
    e.check("Con token llega al otro módulo", r.status_code == 200, r.status_code)
    encabezados = encabezados_de_whoami(r.text)
    e.check("Llega X-Usuario-Id", encabezados.get("x-usuario-id") == [usuario_id])
    e.check("Llega X-Usuario-Rol", encabezados.get("x-usuario-rol") == ["Turista"])

    r = p.http.get(
        ruta,
        headers={**bearer(token), "X-Usuario-Rol": "Admin", "X-Usuario-Id": str(uuid.uuid4())},
    )
    encabezados = encabezados_de_whoami(r.text)
    e.check(
        "X-Usuario-Rol falso no llega (con ForwardAuth)",
        encabezados.get("x-usuario-rol") == ["Turista"],
        encabezados.get("x-usuario-rol"),
    )
    e.check(
        "X-Usuario-Id falso no llega (con ForwardAuth)",
        encabezados.get("x-usuario-id") == [usuario_id],
    )

    r = p.http.get("/modulo-publico/x", headers={"X-Usuario-Rol": "Admin", "X-Usuario-Id": "falso"})
    encabezados = encabezados_de_whoami(r.text)
    e.check(
        "X-Usuario-* falsos no llegan (ruta pública)",
        "x-usuario-rol" not in encabezados and "x-usuario-id" not in encabezados,
        encabezados.get("x-usuario-rol"),
    )

    r = p.http.get("/api/iam/admin/usuarios", headers=bearer(token))
    e.check(
        "Turista contra admin -> 403 ROL_INSUFICIENTE",
        r.status_code == 403 and r.json().get("code") == "ROL_INSUFICIENTE",
        r.status_code,
    )
    filas = p.bitacora(accion="ACCESS_DENIED", usuario_id=usuario_id)
    filas_403 = [f for f in filas if (f["detalles"] or {}).get("ruta") == "/api/iam/admin/usuarios"]
    e.check("El 403 tiene su fila con la ruta y el usuario", len(filas_403) == 1, len(filas_403))

    # IP: Traefik la pasa en X-Forwarded-For; un valor falso del cliente no debe ganar.
    falsa = "203.0.113.77"
    r = p.http.get(f"/modulo-publico/{marca}", headers={"X-Forwarded-For": falsa})
    ip_traefik = encabezados_de_whoami(r.text).get("x-real-ip", [""])[0]
    e.dato(f"IP con la que Traefik ve al cliente: {ip_traefik} (red de k3d, no una IP pública)")
    ruta_ip = f"/otro-modulo/{marca}-ip"
    p.http.get(ruta_ip, headers={"X-Forwarded-For": falsa})
    filas = [
        f for f in p.bitacora(accion="ACCESS_DENIED") if (f["detalles"] or {}).get("uri") == ruta_ip
    ]
    ip_fila = filas[0]["ip_origen"] if filas else None
    pods_traefik = kubectl(
        "-n", "kube-system", "get", "pods", "-l", "app.kubernetes.io/name=traefik",
        "-o", "jsonpath={.items[*].status.podIP}",
    ).split()  # fmt: skip
    e.check(
        "La IP de la fila es la que ve Traefik",
        bool(ip_fila) and ip_fila.split("/")[0] == ip_traefik,
        f"fila={ip_fila} traefik={ip_traefik}",
    )
    e.check("La IP de la fila no es la del pod de Traefik", ip_fila not in pods_traefik, ip_fila)
    e.check("Un X-Forwarded-For falso del cliente no se guarda", ip_fila != falsa, ip_fila)


def escenario_c(p: Plataforma, e: Escenario) -> None:
    email, _ = p.registrar()
    token = p.login(email)
    e.check("Token válido antes del logout", p.verifica(token) == 200)
    r = p.http.post("/api/iam/logout", headers=bearer(token))
    e.check("Logout -> 204", r.status_code == 204, r.status_code)
    e.check("Tras el logout, 401 de inmediato", p.verifica(token) == 401)

    email, usuario_id = p.registrar()
    token = p.login(email)
    e.check("Token válido antes de desactivar", p.verifica(token) == 200)
    r = p.http.patch(
        f"/api/iam/admin/usuarios/{usuario_id}/estado",
        json={"activo": False, "motivo": "prueba"},
        headers=p.admin(),
    )
    e.check("Desactivar -> 200", r.status_code == 200, r.status_code)
    e.check("Tras desactivar, 401 de inmediato", p.verifica(token) == 401)


def escenario_d(p: Plataforma, e: Escenario) -> None:
    accion = f"E2E_{uuid.uuid4().hex[:8].upper()}"
    sobre = {
        "event_id": str(uuid.uuid4()),
        "event_type": "auditoria.registrada",
        "version": 1,
        "occurred_at": datetime.now(UTC).isoformat(),
        "producer": "catalog-service",
        "correlation_id": "e2e-auditoria",
        "payload": {
            "usuario_id": None,
            "accion": accion,
            "resultado": "DENEGADO",
            "ip_origen": "190.24.10.5",
            "detalles": {"origen": "e2e"},
        },
    }
    e.check("Primera publicación enrutada", publicar(sobre))
    e.check("Segunda publicación enrutada (mismo event_id)", publicar(sobre))
    filas = esperar(lambda: p.bitacora(accion=accion), 20, 1)
    e.check("El evento llegó a la bitácora", bool(filas))
    time.sleep(5)  # margen para que el duplicado también se procese
    filas = p.bitacora(accion=accion)
    e.check("Dos publicaciones dejan una sola fila", len(filas) == 1, len(filas))
    if filas:
        e.check("servicio_origen = producer", filas[0]["servicio_origen"] == "catalog-service")

    invalido = {**sobre, "event_id": str(uuid.uuid4()), "payload": {"accion": "SIN_RESULTADO"}}
    e.check("Payload inválido enrutado", publicar(invalido))

    def en_dlq() -> bool:
        return any(
            json.loads(m["payload"]).get("event_id") == invalido["event_id"]
            for m in leer_cola("turismo.dead-letter")
        )

    e.check("El payload inválido termina en turismo.dead-letter", bool(esperar(en_dlq, 30, 1)))
    e.check("El payload inválido no deja fila", not p.bitacora(accion="SIN_RESULTADO"))


def escenario_e(p: Plataforma, e: Escenario) -> None:
    _, usuario_id = p.registrar()
    r = p.http.get(f"/internal/usuarios/{usuario_id}/contacto")
    e.check("Por Traefik -> 404", r.status_code == 404, r.status_code)
    resultado = pod_de_prueba("catalog-worker-prueba", ETIQUETAS_WORKER, usuario_id)
    e.check("Desde un pod con las etiquetas del worker -> 200", resultado == "200", resultado)
    resultado = pod_de_prueba(
        "catalog-worker-proxy", ETIQUETAS_WORKER, usuario_id, '{"X-Forwarded-For": "1.2.3.4"}'
    )
    e.check("Con X-Forwarded-For (defensa adicional) -> 404", resultado == "404", resultado)
    resultado = pod_de_prueba("otro-pod", ETIQUETAS_OTRO, usuario_id)
    e.check("Desde un pod sin esas etiquetas no conecta", resultado == "SIN_CONEXION", resultado)


def escenario_f(p: Plataforma, e: Escenario) -> None:
    email, _ = p.registrar()
    r = p.post_limitado("/api/iam/auth/recuperar", {"email": email})
    e.check("Recuperar -> 202", r.status_code == 202, r.status_code)

    def enlace() -> str | None:
        mensajes = httpx.get(f"{MAILPIT}/messages", timeout=5).json()["messages"]
        for mensaje in mensajes:
            if any(d["Address"] == email for d in mensaje["To"]):
                cuerpo = httpx.get(f"{MAILPIT}/message/{mensaje['ID']}", timeout=5).json()["Text"]
                encontrado = re.search(r"\?token=([\w-]+)", cuerpo)
                return encontrado.group(1) if encontrado else None
        return None

    token = esperar(enlace, 20, 0.5)
    e.check("El correo llega a Mailpit con el enlace", bool(token))
    if not token:
        return
    nueva = "RestablecidaE2e123"
    r = p.http.post("/api/iam/auth/restablecer", json={"token": token, "password": nueva})
    e.check("Restablecer -> 204", r.status_code == 204, r.status_code)
    r = p.http.post("/api/iam/auth/restablecer", json={"token": token, "password": nueva})
    e.check("El enlace no sirve dos veces -> 400", r.status_code == 400, r.status_code)
    r = p.post_limitado("/api/iam/login", {"email": email, "password": nueva})
    e.check("Login con la contraseña nueva -> 200", r.status_code == 200, r.status_code)
    r = p.post_limitado("/api/iam/login", {"email": email, "password": CLAVE})
    e.check("La contraseña vieja ya no sirve -> 401", r.status_code == 401, r.status_code)


def escenario_g(p: Plataforma, e: Escenario) -> None:
    _, usuario_id, cabeceras = prestador_con_documentos(p, "Empresa a suprimir")
    prefijo = f"{usuario_id}/"
    e.check("Antes hay objetos en SeaweedFS", len(p.objetos(prefijo)) == 2, len(p.objetos(prefijo)))
    r = p.http.request("DELETE", "/api/iam/perfil", json={"password": CLAVE}, headers=cabeceras)
    e.check("Supresión -> 204", r.status_code == 204, r.status_code)
    e.check("Los objetos desaparecen", p.objetos(prefijo) == [], p.objetos(prefijo))
    resultado = pod_de_prueba("catalog-worker-supresion", ETIQUETAS_WORKER, usuario_id)
    e.check("El contacto interno da 404", resultado == "404", resultado)


def escenario_h(p: Plataforma, e: Escenario) -> None:
    _, usuario_id, _ = prestador_con_documentos(p, "Empresa del bucket")
    documento = documento_de(p, usuario_id)
    url = p.http.get(f"/api/iam/admin/documentos/{documento}/url", headers=p.admin()).json()["url"]
    e.check("El enlace usa el host público", urlsplit(url).netloc == HOST_DOCUMENTOS)
    sin_firma = abrir_firmada(url, firmada=False)
    e.check("Sin firma -> 403", sin_firma.status_code == 403, sin_firma.status_code)
    con_firma = abrir_firmada(url)
    e.check("Con la URL firmada -> 200", con_firma.status_code == 200, con_firma.status_code)
    alterada = abrir_firmada(url.replace("X-Amz-Signature=", "X-Amz-Signature=0"))
    e.check("Con la firma alterada -> 403", alterada.status_code == 403, alterada.status_code)


def escenario_i(p: Plataforma, e: Escenario) -> None:
    e.dato("Se espera 65 s para partir con el cupo del límite completo")
    time.sleep(65)
    codigos = [
        p.http.post(
            "/api/iam/login", json={"email": "nadie.e2e@example.com", "password": "ClaveMala123"}
        ).status_code
        for _ in range(6)
    ]
    e.dato(f"Códigos: {codigos}")
    e.check("Los cinco primeros pasan al IAM (401)", codigos[:5] == [401] * 5, codigos[:5])
    e.check("El sexto login da 429", codigos[5] == 429, codigos[5])


@dataclass
class Bucle:
    """Llamadas continuas a verificar por el gateway, con conexiones nuevas en cada hilo."""

    token: str
    latencias: list[float] = field(default_factory=list)
    errores: dict[str, int] = field(default_factory=dict)
    alto: threading.Event = field(default_factory=threading.Event)

    def _hilo(self) -> None:
        with httpx.Client(base_url=GATEWAY, timeout=10) as cliente:
            while not self.alto.is_set():
                inicio = time.monotonic()
                try:
                    codigo = str(
                        cliente.get(
                            "/api/iam/auth/verificar", headers=bearer(self.token)
                        ).status_code
                    )
                except httpx.HTTPError as exc:
                    codigo = type(exc).__name__
                self.latencias.append(time.monotonic() - inicio)
                if codigo != "200":
                    self.errores[codigo] = self.errores.get(codigo, 0) + 1
                time.sleep(0.05)

    def __enter__(self) -> "Bucle":
        self._hilos = [threading.Thread(target=self._hilo) for _ in range(4)]
        for hilo in self._hilos:
            hilo.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.alto.set()
        for hilo in self._hilos:
            hilo.join()

    def resumen(self) -> str:
        ordenadas = sorted(self.latencias)
        p95 = ordenadas[int(len(ordenadas) * 0.95) - 1] * 1000
        return (
            f"peticiones={len(ordenadas)} mediana={statistics.median(ordenadas) * 1000:.0f} ms "
            f"p95={p95:.0f} ms max={ordenadas[-1] * 1000:.0f} ms "
            f"errores={self.errores or 'ninguno'}"
        )

    def errores_5xx(self) -> int:
        return sum(n for c, n in self.errores.items() if c.startswith("5"))


def replicas_listas() -> int:
    salida = kubectl(
        "-n", "turismo-app", "get", "deploy", "iam-service", "-o",
        "jsonpath={.status.readyReplicas}/{.status.updatedReplicas}",
    )  # fmt: skip
    return int(salida.split("/")[0] or 0)


def esperar_estable() -> None:
    kubectl("-n", "turismo-app", "rollout", "status", "deploy/iam-service", "--timeout=240s")
    esperar(lambda: replicas_listas() == 2, 120, 1)


def fijar_maximo_hpa(maximo: int) -> None:
    """Con más de 2 réplicas, reiniciar o borrar una no pondría nada a prueba: j y k corren con
    el mínimo. El bucle basta para que el HPA suba, porque el request de CPU es de 100m."""
    kubectl(
        "-n", "turismo-app", "patch", "hpa", "iam-service", "--type=merge",
        "-p", json.dumps({"spec": {"maxReplicas": maximo}}),
    )  # fmt: skip


def escenario_j(p: Plataforma, e: Escenario) -> None:
    fijar_maximo_hpa(2)
    esperar_estable()
    email, _ = p.registrar()
    token = p.login(email)
    with Bucle(token) as bucle:
        time.sleep(5)
        kubectl("-n", "turismo-app", "rollout", "restart", "deploy/iam-service")
        inicio = time.monotonic()
        kubectl("-n", "turismo-app", "rollout", "status", "deploy/iam-service", "--timeout=240s")
        duracion = time.monotonic() - inicio
        time.sleep(5)
    e.dato(bucle.resumen())
    e.dato(f"Duración del rollout: {duracion:.0f} s")
    e.check(
        "RNF-12: 0 respuestas 5xx durante el rollout", bucle.errores_5xx() == 0, bucle.errores_5xx()
    )
    otros = {c: n for c, n in bucle.errores.items() if not c.startswith("5")}
    e.check("Sin otros errores (conexión, 401...)", not otros, otros or "")


def escenario_k(p: Plataforma, e: Escenario) -> None:
    esperar_estable()
    email, _ = p.registrar()
    token = p.login(email)

    def borrar_una(*opciones: str) -> tuple[Bucle, float | None]:
        with Bucle(token) as bucle:
            time.sleep(3)
            pod = kubectl(
                "-n", "turismo-app", "get", "pods",
                "-l", "app.kubernetes.io/name=iam-service,app.kubernetes.io/component=api",
                "-o", "jsonpath={.items[0].metadata.name}",
            )  # fmt: skip
            inicio = time.monotonic()
            kubectl("-n", "turismo-app", "delete", "pod", pod, "--wait=false", *opciones)
            esperar(lambda: replicas_listas() < 2, 5, 0.2)
            listo = esperar(lambda: replicas_listas() == 2, 180, 0.5)
            duracion = time.monotonic() - inicio if listo else None
            time.sleep(3)
        return bucle, duracion

    bucle, duracion = borrar_una()
    e.dato(f"Borrado ordenado: {bucle.resumen()}")
    e.dato(f"Borrado ordenado: 2 réplicas listas a los {duracion and round(duracion)} s")
    e.check("Hay 2 réplicas listas de nuevo (borrado ordenado)", duracion is not None)
    e.check("Sin 5xx (borrado ordenado)", bucle.errores_5xx() == 0, bucle.errores_5xx())

    esperar_estable()
    bucle, duracion = borrar_una("--grace-period=0", "--force")
    e.dato(f"Borrado forzado (más cerca de una caída): {bucle.resumen()}")
    e.dato(f"Borrado forzado: 2 réplicas listas a los {duracion and round(duracion)} s")
    e.check("Hay 2 réplicas listas de nuevo (borrado forzado)", duracion is not None)
    otros = {c: n for c, n in bucle.errores.items() if not c.startswith("5")}
    e.dato(f"Borrado forzado: 5xx={bucle.errores_5xx()} otros errores={otros or 'ninguno'}")

    # Observación del HPA (Lab §5.1), no una prueba de capacidad: el mismo bucle, 2 minutos.
    fijar_maximo_hpa(4)
    with Bucle(token):
        time.sleep(120)
    hpa = kubectl("-n", "turismo-app", "get", "hpa", "iam-service", "--no-headers").split()
    e.dato(f"HPA tras 2 min del bucle (4 hilos): {' '.join(hpa[2:])}")
    e.check(
        "El HPA sube de 2 réplicas y no pasa de 4", 2 < replicas_listas() <= 4, replicas_listas()
    )


ESCENARIOS: list[tuple[str, Callable[[Plataforma, Escenario], None]]] = [
    ("a. Prestador: carga, aprobación y eventos", escenario_a),
    ("b. ESC-04: rechazos, X-Usuario-* y bitácora", escenario_b),
    ("c. Revocación: logout y desactivación", escenario_c),
    ("d. Auditoría: duplicado y DLQ", escenario_d),
    ("e. Contacto interno y NetworkPolicy", escenario_e),
    ("f. Recuperación por correo", escenario_f),
    ("g. Supresión", escenario_g),
    ("h. Seguridad del bucket", escenario_h),
    ("i. Rate limiting", escenario_i),
    ("j. RNF-12: rolling update bajo carga", escenario_j),
    ("k. ESC-01 aproximado: borrar una réplica", escenario_k),
]


def escribir_reporte(resultados: list[Escenario]) -> int:
    commit = subprocess.run(
        ["git", "describe", "--always", "--dirty"], cwd=SERVICIO, capture_output=True, text=True
    ).stdout.strip()
    version = kubectl("get", "nodes", "-o", "jsonpath={.items[0].status.nodeInfo.kubeletVersion}")
    fallos = sum(r.fallos for r in resultados)
    lineas = [
        "# Parte C: e2e de iam-service en k3d, detrás de Traefik (prueba, no producción)",
        f"# Fecha: {datetime.now(UTC):%Y-%m-%d %H:%M UTC}",
        f"# Commit: {commit}",
        f"# k3s: {version}",
        "",
    ]
    for resultado in resultados:
        estado = "OK" if resultado.fallos == 0 else f"FALLO ({resultado.fallos})"
        lineas += [f"[{estado}] {resultado.nombre}", *resultado.lineas, ""]
    lineas.append(
        f"# Resumen: {sum(r.fallos == 0 for r in resultados)} de {len(resultados)} escenarios OK, "
        f"{fallos} comprobaciones fallidas"
    )
    REPORTE.parent.mkdir(parents=True, exist_ok=True)
    REPORTE.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lineas))
    return 1 if fallos else 0


def correr_escenarios() -> int:
    resultados: list[Escenario] = []
    with PuertosReenviados():
        sembrar_admin()
        plataforma = Plataforma()
        for nombre, funcion in ESCENARIOS:
            print(f"--- {nombre}", flush=True)
            escenario = Escenario(nombre)
            try:
                funcion(plataforma, escenario)
            except Exception as exc:  # noqa: BLE001 - un escenario roto no detiene los demás
                ultimo = traceback.extract_tb(exc.__traceback__)[-1]
                escenario.check(
                    "El escenario terminó",
                    False,
                    f"{type(exc).__name__} en la línea {ultimo.lineno}: {exc}",
                )
            resultados.append(escenario)
            # Se guarda el avance: la corrida puede interrumpirse.
            escribir_reporte(resultados)
    return escribir_reporte(resultados)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conservar", action="store_true", help="no borra el clúster al terminar")
    parser.add_argument("--solo-borrar", action="store_true", help="borra lo que haya quedado")
    parser.add_argument("--sin-preparar", action="store_true", help="usa un clúster ya preparado")
    args = parser.parse_args()
    if args.solo_borrar:
        borrar()
        return 0
    try:
        if not args.sin_preparar:
            preparar()
        return correr_escenarios()
    finally:
        if not args.conservar:
            borrar()


if __name__ == "__main__":
    sys.exit(main())
