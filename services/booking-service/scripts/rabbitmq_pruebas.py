"""RabbitMQ solo para las pruebas de integración de booking-service, en Docker.

Uso (desde services/booking-service):
    python scripts/rabbitmq_pruebas.py subir     # crea o arranca el contenedor y espera a que responda
    python scripts/rabbitmq_pruebas.py estado
    python scripts/rabbitmq_pruebas.py bajar     # lo detiene y lo borra

Usa el puerto 5673 para no chocar con el RabbitMQ del docker-compose del equipo (5672).
Misma versión mayor que el compose (4). Sin consola web ni volumen: es desechable a propósito.
"""

import subprocess
import sys
import time

CONTENEDOR = "booking-rabbitmq-pruebas"
IMAGEN = "rabbitmq:4-alpine"
PUERTO = 5673
USUARIO = CLAVE = "booking"  # el usuario guest solo entra desde localhost del contenedor
URL = f"amqp://{USUARIO}:{CLAVE}@127.0.0.1:{PUERTO}/"


def docker(*argumentos: str, verificar: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *argumentos], capture_output=True, text=True, check=verificar)


def existe() -> bool:
    return bool(docker("ps", "-a", "-q", "-f", f"name=^{CONTENEDOR}$").stdout.strip())


def corriendo() -> bool:
    return bool(docker("ps", "-q", "-f", f"name=^{CONTENEDOR}$").stdout.strip())


def esperar_listo(segundos: int = 90) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        # -u rabbitmq: como root, el diagnóstico crearía .erlang.cookie antes que el servidor y
        # este ya no podría leerlo (eacces) y se cerraría.
        listo = docker(
            "exec", "-u", "rabbitmq", CONTENEDOR, "rabbitmq-diagnostics", "-q", "check_port_connectivity", verificar=False
        )
        if listo.returncode == 0:
            return
        time.sleep(2)
    raise SystemExit(f"RabbitMQ no respondió en {segundos} s. Revise: docker logs {CONTENEDOR}")


def subir() -> None:
    if corriendo():
        print(f"Ya está corriendo: {URL}")
        return
    if existe():
        docker("start", CONTENEDOR)
    else:
        docker(
            "run", "-d", "--name", CONTENEDOR,
            "-e", f"RABBITMQ_DEFAULT_USER={USUARIO}", "-e", f"RABBITMQ_DEFAULT_PASS={CLAVE}",
            "-p", f"127.0.0.1:{PUERTO}:5672",
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
