"""k3s local en Docker para probar infra/k8s/ y los servicios en un portátil (Windows, macOS o Linux).

Uso (desde la raíz del repositorio):
    python infra/k8s/k3s_local.py subir                    # crea o arranca el clúster y espera al nodo
    python infra/k8s/k3s_local.py imagenes [servicio ...]  # construye <servicio>:local y la importa
    python infra/k8s/k3s_local.py republicar <servicio>    # imagenes + reinicia sus Deployments
    python infra/k8s/k3s_local.py kubectl <args ...>       # kubectl del propio clúster (misma versión)
    python infra/k8s/k3s_local.py estado
    python infra/k8s/k3s_local.py bajar                    # borra el clúster y sus datos

Servicios: iam, catalog, booking, review, recommendation (o "todos").

La versión de k3s es la del clúster real (README: v1.32.9+k3s1, con Traefik 3.3). El gateway queda en
http://localhost:8081 y SeaweedFS público en http://s3.localhost:8081. El repositorio se monta en /repo
dentro del contenedor, así que `kubectl apply -k /repo/...` usa el kubectl y el kustomize de esa versión.
Para un kubectl del PC: KUBECONFIG=infra/k8s/local/k3s.kubeconfig (no se sube; lo escribe `subir`).
En Git Bash, anteponer MSYS_NO_PATHCONV=1 cuando un argumento empiece por /repo: si no, Git Bash lo
convierte en una ruta de Windows.
"""

import subprocess
import sys
import time
from pathlib import Path

VERSION_K3S = "v1.32.9-k3s1"  # cambiarla exige revisar el Traefik que trae (ver README)
CONTENEDOR = "turismo-k3s"
VOLUMEN = "turismo-k3s-datos"
PUERTO_GATEWAY = 8081  # el compose usa el 80; así pueden convivir
PUERTO_API = 16443  # no choca con el Kubernetes de Docker Desktop (6443)

RAIZ = Path(__file__).resolve().parents[2]
KUBECONFIG = RAIZ / "infra" / "k8s" / "local" / "k3s.kubeconfig"
SERVICIOS = ["iam", "catalog", "booking", "review", "recommendation"]
# Deployments de cada servicio en turismo-app (los que hay que reiniciar al republicar).
DEPLOYMENTS = {
    "iam": ["iam-service", "iam-worker"],
    "catalog": ["catalog-service", "catalog-worker"],
    "booking": ["booking-service"],
    "review": ["review-service", "review-worker"],
    "recommendation": ["recommendation-service"],
}


def docker(*argumentos: str, verificar: bool = True, capturar: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *argumentos], capture_output=capturar, text=True, check=verificar)


def existe() -> bool:
    return bool(docker("ps", "-a", "-q", "-f", f"name=^{CONTENEDOR}$").stdout.strip())


def corriendo() -> bool:
    return bool(docker("ps", "-q", "-f", f"name=^{CONTENEDOR}$").stdout.strip())


def kubectl(*argumentos: str, verificar: bool = True, capturar: bool = False) -> subprocess.CompletedProcess:
    return docker("exec", CONTENEDOR, "kubectl", *argumentos, verificar=verificar, capturar=capturar)


def subir() -> None:
    if not existe():
        print(f"Creando el clúster k3s {VERSION_K3S}...")
        docker(
            "run", "-d", "--name", CONTENEDOR, "--privileged",
            "--tmpfs", "/run", "--tmpfs", "/var/run",
            "-p", f"127.0.0.1:{PUERTO_API}:6443",
            "-p", f"{PUERTO_GATEWAY}:80",
            "-v", f"{VOLUMEN}:/var/lib/rancher/k3s",
            "-v", f"{RAIZ}:/repo:ro",
            f"rancher/k3s:{VERSION_K3S}",
            "server", "--tls-san", "127.0.0.1",
        )  # fmt: skip
    elif not corriendo():
        docker("start", CONTENEDOR)
    esperar_nodo()
    escribir_kubeconfig()
    print(f"Listo. Gateway: http://localhost:{PUERTO_GATEWAY}  ·  kubeconfig: {KUBECONFIG.relative_to(RAIZ)}")


def esperar_nodo(segundos: int = 180) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        listo = kubectl("get", "nodes", "--no-headers", verificar=False, capturar=True)
        if listo.returncode == 0 and " Ready " in listo.stdout:
            return
        time.sleep(3)
    sys.exit(f"El nodo no quedó Ready en {segundos} s. Revisar: docker logs {CONTENEDOR}")


def escribir_kubeconfig() -> None:
    config = docker("exec", CONTENEDOR, "cat", "/etc/rancher/k3s/k3s.yaml").stdout
    KUBECONFIG.write_text(config.replace("127.0.0.1:6443", f"127.0.0.1:{PUERTO_API}"), encoding="utf-8")


def servicios_pedidos(nombres: list[str]) -> list[str]:
    if not nombres or nombres == ["todos"]:
        return SERVICIOS
    desconocidos = [n for n in nombres if n not in SERVICIOS]
    if desconocidos:
        sys.exit(f"Servicios desconocidos: {', '.join(desconocidos)}. Válidos: {', '.join(SERVICIOS)}")
    return nombres


def imagenes(nombres: list[str]) -> None:
    if not corriendo():
        sys.exit("El clúster no está corriendo: python infra/k8s/k3s_local.py subir")
    for servicio in servicios_pedidos(nombres):
        imagen = f"{servicio}-service:local"
        print(f"Construyendo {imagen}...")
        docker("build", "-q", "-t", imagen, str(RAIZ / "services" / f"{servicio}-service"), capturar=False)
        print(f"Importando {imagen} al clúster...")
        guardar = subprocess.Popen(["docker", "save", imagen], stdout=subprocess.PIPE)
        importar = subprocess.run(
            ["docker", "exec", "-i", CONTENEDOR, "ctr", "-n", "k8s.io", "images", "import", "-"],
            stdin=guardar.stdout, capture_output=True, text=True,
        )  # fmt: skip
        guardar.stdout.close()
        if guardar.wait() != 0 or importar.returncode != 0:
            sys.exit(f"No se pudo importar {imagen}: {importar.stderr.strip()}")


def republicar(nombres: list[str]) -> None:
    if len(nombres) != 1 or nombres[0] not in SERVICIOS:
        sys.exit(f"Uso: republicar <servicio>. Válidos: {', '.join(SERVICIOS)}")
    servicio = nombres[0]
    imagenes([servicio])
    # Misma etiqueta :local: sin reiniciar, los pods seguirían con la imagen anterior.
    for deployment in DEPLOYMENTS[servicio]:
        kubectl("-n", "turismo-app", "rollout", "restart", f"deployment/{deployment}")
    for deployment in DEPLOYMENTS[servicio]:
        kubectl("-n", "turismo-app", "rollout", "status", f"deployment/{deployment}", "--timeout=5m")


def estado() -> None:
    if not corriendo():
        print("El clúster no está corriendo." if existe() else "No hay clúster.")
        return
    kubectl("get", "nodes", "-o", "wide")
    kubectl("get", "pods", "-A")


def bajar() -> None:
    docker("rm", "-f", CONTENEDOR, verificar=False)
    docker("volume", "rm", VOLUMEN, verificar=False)
    KUBECONFIG.unlink(missing_ok=True)
    print("Clúster borrado.")


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    orden, resto = sys.argv[1], sys.argv[2:]
    if orden == "subir":
        subir()
    elif orden == "imagenes":
        imagenes(resto)
    elif orden == "republicar":
        republicar(resto)
    elif orden == "kubectl":
        sys.exit(kubectl(*resto, verificar=False).returncode)
    elif orden == "estado":
        estado()
    elif orden == "bajar":
        bajar()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
