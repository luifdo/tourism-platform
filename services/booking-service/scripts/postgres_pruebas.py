"""Postgres solo para las pruebas de integración de booking-service, en Docker.

Uso (desde services/booking-service):
    python scripts/postgres_pruebas.py subir     # crea o arranca el contenedor y espera a que responda
    python scripts/postgres_pruebas.py estado
    python scripts/postgres_pruebas.py bajar     # lo detiene y lo borra (los datos de prueba se pierden)

Usa el puerto 5433 para no chocar con un Postgres instalado en el PC (5432) ni con el
docker-compose del equipo. No guarda datos en un volumen: es desechable a propósito.
"""

import subprocess
import sys
import time

CONTENEDOR = "booking-postgres-pruebas"
IMAGEN = "postgres:16-alpine"  # misma versión mayor que el clúster (CloudNativePG 16); booking no usa PostGIS
PUERTO = 5433
USUARIO = CLAVE = "booking"
BASE = "booking_db"
URL = f"postgresql+asyncpg://{USUARIO}:{CLAVE}@127.0.0.1:{PUERTO}/{BASE}"


def docker(*argumentos: str, verificar: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *argumentos], capture_output=True, text=True, check=verificar)


def existe() -> bool:
    return bool(docker("ps", "-a", "-q", "-f", f"name=^{CONTENEDOR}$").stdout.strip())


def corriendo() -> bool:
    return bool(docker("ps", "-q", "-f", f"name=^{CONTENEDOR}$").stdout.strip())


def esperar_listo(segundos: int = 60) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        listo = docker("exec", CONTENEDOR, "pg_isready", "-U", USUARIO, "-d", BASE, verificar=False)
        if listo.returncode == 0:
            return
        time.sleep(1)
    raise SystemExit(f"Postgres no respondió en {segundos} s. Revise: docker logs {CONTENEDOR}")


def subir() -> None:
    if corriendo():
        print(f"Ya está corriendo: {URL}")
        return
    if existe():
        docker("start", CONTENEDOR)
    else:
        docker(
            "run", "-d", "--name", CONTENEDOR,
            "-e", f"POSTGRES_USER={USUARIO}", "-e", f"POSTGRES_PASSWORD={CLAVE}", "-e", f"POSTGRES_DB={BASE}",
            "-p", f"127.0.0.1:{PUERTO}:5432",
            IMAGEN,
        )
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
