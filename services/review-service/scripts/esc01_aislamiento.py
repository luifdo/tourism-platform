"""ESC-01: tumba la API de review y mide el tiempo de aislamiento (Plan §8.4).

Mientras k6 (k6/esc01.js) consulta catalog y review, este script provoca dos tipos de falla
y, para cada una, mide en el EndpointSlice del Service `review-service`:

* aislamiento: desde la falla hasta que la réplica deja de estar lista (Traefik y los demás
  clientes del Service ya no le mandan tráfico). Criterio: < 5 s;
* recuperación: hasta que vuelve a haber una réplica lista (solo se informa).

Fallas:

* `proceso`: el proceso de la API termina (SIGTERM al PID 1 desde dentro del contenedor; un
  SIGKILL no sirve porque el kernel protege al PID 1 de su propio espacio de nombres). El
  kubelet ve el contenedor caído y lo reinicia.
* `pod`: el pod desaparece de golpe (`kubectl delete pod --force --grace-period=0`), como si
  se perdiera el nodo. El Deployment crea otro.

Solo necesita `kubectl` apuntando al clúster. Uso:

    python scripts/esc01_aislamiento.py                  # 3 fallas, una por minuto
    python scripts/esc01_aislamiento.py --fallas proceso pod proceso --pausa 60
"""

import argparse
import json
import subprocess
import sys
import time

NAMESPACE = "turismo-app"
SERVICIO = "review-service"
SELECTOR_API = "app.kubernetes.io/name=review-service,app.kubernetes.io/component=api"
LIMITE_AISLAMIENTO_S = 5.0


def kubectl(*args: str) -> str:
    return subprocess.run(
        ["kubectl", "-n", NAMESPACE, *args], capture_output=True, text=True, check=True
    ).stdout


def listos() -> set[str]:
    """Pods de la API que el Service considera listos para recibir tráfico."""
    datos = json.loads(
        kubectl(
            "get", "endpointslices", "-l", f"kubernetes.io/service-name={SERVICIO}", "-o", "json"
        )
    )
    return {
        e["targetRef"]["name"]
        for s in datos["items"]
        for e in s.get("endpoints") or []
        if e.get("conditions", {}).get("ready") and e.get("targetRef")
    }


def esperar(condicion, limite_s: float) -> float | None:  # type: ignore[no-untyped-def]
    """Segundos hasta que se cumple `condicion()`; None si no se cumple en `limite_s`."""
    inicio = time.monotonic()
    while time.monotonic() - inicio < limite_s:
        if condicion():
            return time.monotonic() - inicio
        time.sleep(0.1)
    return None


def provocar(falla: str, pod: str) -> None:
    if falla == "proceso":
        kubectl(
            "exec",
            pod,
            "-c",
            "api",
            "--",
            "python",
            "-c",
            "import os, signal; os.kill(1, signal.SIGTERM)",
        )
    else:
        kubectl("delete", "pod", pod, "--force", "--grace-period=0", "--wait=false")


def una_falla(falla: str) -> tuple[float | None, float | None]:
    if esperar(lambda: bool(listos()), 180) is None:
        sys.exit("La API de review no tiene réplicas listas: no se puede empezar.")
    [pod] = sorted(listos())[:1]
    inicio = time.monotonic()
    provocar(falla, pod)
    orden = time.monotonic() - inicio  # lo que tardó kubectl en dar la orden
    aislado = esperar(lambda: pod not in listos(), 30)
    aislamiento = aislado if aislado is None else time.monotonic() - inicio
    vuelta = esperar(lambda: bool(listos()), 180)
    recuperacion = vuelta if vuelta is None else time.monotonic() - inicio
    print(f"  (la orden de kubectl tardó {orden:.1f} s)", flush=True)
    return aislamiento, recuperacion


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--fallas", nargs="+", choices=["proceso", "pod"], default=["proceso", "pod", "proceso"]
    )
    parser.add_argument("--pausa", type=float, default=60, help="segundos entre fallas")
    parser.add_argument(
        "--espera-inicial",
        type=float,
        default=30,
        help="segundos antes de la primera falla (k6 ya midiendo)",
    )
    args = parser.parse_args()

    time.sleep(args.espera_inicial)
    filas = []
    for i, falla in enumerate(args.fallas):
        if i:
            time.sleep(args.pausa)
        aislamiento, recuperacion = una_falla(falla)
        filas.append((falla, aislamiento, recuperacion))
        print(
            f"{time.strftime('%H:%M:%S')} {falla}: aislamiento "
            f"{'-' if aislamiento is None else f'{aislamiento:.1f} s'}, recuperación "
            f"{'-' if recuperacion is None else f'{recuperacion:.1f} s'}",
            flush=True,
        )

    bien = all(a is not None and a < LIMITE_AISLAMIENTO_S and r is not None for _, a, r in filas)
    peor = max((a for _, a, _ in filas if a is not None), default=float("nan"))
    print(
        f"Peor aislamiento: {peor:.1f} s (criterio < {LIMITE_AISLAMIENTO_S:.0f} s) -> "
        f"{'CUMPLE' if bien else 'NO CUMPLE'}"
    )
    sys.exit(0 if bien else 1)


if __name__ == "__main__":
    main()
