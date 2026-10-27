"""Valkey solo para las pruebas de integración de booking-service, en Docker.

Uso (desde services/booking-service):
    python scripts/valkey_pruebas.py subir     # crea o arranca el contenedor y espera a que responda
    python scripts/valkey_pruebas.py estado
    python scripts/valkey_pruebas.py bajar     # lo detiene y lo borra (es desechable)

Usa el puerto 6380 para no chocar con el Valkey del docker-compose del equipo (6379).
"""

import subprocess
import sys
import time

CONTENEDOR = "booking-valkey-pruebas"
IMAGEN = "valkey/valkey:8"  # la misma del docker-compose del equipo
PUERTO = 6380
URL = f"redis://127.0.0.1:{PUERTO}/0"


def docker(*argumentos: str, verificar: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *argumentos], capture_output=True, text=True, check=verificar)


def existe() -> bool:
    return bool(docker("ps", "-a", "-q", "-f", f"name=^{CONTENEDOR}$").stdout.strip())


def corriendo() -> bool:
    return bool(docker("ps", "-q", "-f", f"name=^{CONTENEDOR}$").stdout.strip())


def esperar_listo(segundos: int = 30) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        listo = docker("exec", CONTENEDOR, "valkey-cli", "ping", verificar=False)
        if listo.returncode == 0 and listo.stdout.strip() == "PONG":
            return
        time.sleep(1)
    raise SystemExit(f"Valkey no respondió en {segundos} s. Revise: docker logs {CONTENEDOR}")


def subir() -> None:
    if corriendo():
        print(f"Ya está corriendo: {URL}")
        return
    if existe():
        docker("start", CONTENEDOR)
    else:
        docker("run", "-d", "--name", CONTENEDOR, "-p", f"127.0.0.1:{PUERTO}:6379", IMAGEN)
    esperar_listo()
    print(f"Listo: {URL}")


def bajar() -> None:
    if existe():
        docker("rm", "-f", CONTENEDOR)
        print("Contenedor borrado.")
    else:
        print("No existe.")


def estado() -> None:
    print("corriendo" if corriendo() else ("detenido" if existe() else "no existe"), "-", URL)


if __name__ == "__main__":
    acciones = {"subir": subir, "bajar": bajar, "estado": estado}
    if len(sys.argv) != 2 or sys.argv[1] not in acciones:
        raise SystemExit(__doc__)
    acciones[sys.argv[1]]()
