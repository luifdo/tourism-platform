#!/usr/bin/env python3
"""Prueba el gateway con un Traefik REAL y servicios falsos (no necesita Docker ni Kubernetes).

    pip install -r requirements.txt
    python probar_gateway.py                 # usa el `traefik` del PATH (brew install traefik)
    python probar_gateway.py --traefik /ruta/a/traefik

Qué comprueba (config/compose es la que usa infra/docker-compose.yml):
  1. Que cada operación de contracts/openapi/*.yaml sea pública o protegida en el gateway tal como lo declara su
     contrato (barrido completo): sin sesión, las protegidas dan 401 y no llegan al servicio.
  2. Que X-Usuario-Id y X-Usuario-Rol del cliente nunca lleguen a un servicio, ni en rutas públicas ni protegidas.
  3. El prefijo no se quita, /internal, /health y /metrics no se enrutan, X-Forwarded-For del cliente no se cree.
  4. Los límites de tasa (login y recuperar comparten cupo; refresh tiene el suyo) y el límite de 6 MB de documentos.
  5. SeaweedFS por nombre de host con CORS solo para la PWA, y que el token de /restablecer-contrasena no quede en los logs.
Termina con código distinto de cero si algo falla.
"""
import argparse
import http.client
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import servidores_falsos as falsos

RAIZ = Path(__file__).resolve().parents[2]
PUERTO = 18080
PUERTO_PING = 18081

# Los servicios del compose se sustituyen por los falsos locales; el resto de la configuración queda intacta.
REEMPLAZOS = {
    "http://iam-service:8001": f"http://127.0.0.1:{falsos.PUERTOS['iam']}",
    "http://catalog-service:8002": f"http://127.0.0.1:{falsos.PUERTOS['catalog']}",
    "http://booking-service:8003": f"http://127.0.0.1:{falsos.PUERTOS['booking']}",
    "http://review-service:8004": f"http://127.0.0.1:{falsos.PUERTOS['review']}",
    "http://recommendation-service:8005": f"http://127.0.0.1:{falsos.PUERTOS['recommendation']}",
    "http://frontend:8080": f"http://127.0.0.1:{falsos.PUERTOS['frontend']}",
    "http://seaweedfs:8333": f"http://127.0.0.1:{falsos.PUERTOS['almacenamiento']}",
}

# Opciones ESTÁTICAS de Traefik que el gateway necesita. Deben estar en el `command` del servicio traefik de
# infra/docker-compose.yml (la prueba lo comprueba); aquí solo se cambian el puerto y la carpeta.
BANDERAS_DEL_COMPOSE = [
    "--providers.file.watch=true",
    "--ping=true",
    "--accesslog=true",
    "--accesslog.format=json",
    "--accesslog.fields.names.RequestPath=drop",
    "--accesslog.fields.names.RequestLine=drop",
]

# Dominio público ficticio con el que se prueba la plantilla del CORS y el host s3.<dominio> (en el servidor es el de infra/.env)
DOMINIO_DE_PRUEBA = "ejemplo.test"

resultados = {"ok": 0, "fallos": []}


def verificar(nombre, condicion, detalle=""):
    if condicion:
        resultados["ok"] += 1
        print(f"  ✓ {nombre}")
    else:
        resultados["fallos"].append(nombre)
        print(f"  ✗ {nombre}" + (f"  → {detalle}" if detalle else ""))
    return condicion


def grupo(titulo):
    print(f"\n{titulo}")


class Gateway:
    def __init__(self, traefik, carpeta_config):
        self.traefik, self.carpeta_config = traefik, carpeta_config
        self.proceso = None
        self.tmp = Path(tempfile.mkdtemp(prefix="gateway-prueba-"))
        self.log_acceso = self.tmp / "acceso.log"
        self.log_traefik = self.tmp / "traefik.log"

    def _preparar_config(self):
        destino = self.tmp / "dinamica"
        shutil.rmtree(destino, ignore_errors=True)
        destino.mkdir()
        for archivo in sorted(self.carpeta_config.glob("*.yml")):
            texto = archivo.read_text()
            for origen, nuevo in REEMPLAZOS.items():
                texto = texto.replace(origen, nuevo)
            (destino / archivo.name).write_text(texto)
        return destino

    def arrancar(self):
        self.log_acceso.write_text("")
        banderas = [b for b in BANDERAS_DEL_COMPOSE if "watch" not in b]
        orden = [
            self.traefik, f"--providers.file.directory={self._preparar_config()}",
            f"--entrypoints.web.address=127.0.0.1:{PUERTO}", f"--entrypoints.traefik.address=127.0.0.1:{PUERTO_PING}",
            f"--accesslog.filepath={self.log_acceso}", "--log.level=ERROR", *banderas,
        ]
        entorno = {**os.environ, "DOMINIO_PUBLICO": DOMINIO_DE_PRUEBA}  # lo lee la plantilla del origen CORS de 00-middlewares.yml
        self.proceso = subprocess.Popen(orden, stdout=self.log_traefik.open("w"), stderr=subprocess.STDOUT, env=entorno)
        for _ in range(60):
            try:
                if pedir("GET", "/")[0] == 200:
                    return
            except OSError:
                pass
            if self.proceso.poll() is not None:
                break
            time.sleep(0.25)
        sys.exit(f"Traefik no arrancó:\n{self.log_traefik.read_text()}")

    def detener(self):
        if self.proceso and self.proceso.poll() is None:
            self.proceso.terminate()
            try:
                self.proceso.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proceso.kill()

    def reiniciar(self):  # reinicia también los contadores de los límites de tasa
        self.detener()
        self.arrancar()


def pedir(metodo, ruta, cabeceras=None, cuerpo=None, host=None):
    conexion = http.client.HTTPConnection("127.0.0.1", PUERTO, timeout=30)
    enviadas = dict(cabeceras or {})
    if host:
        enviadas["Host"] = host
    try:
        conexion.request(metodo, ruta, body=cuerpo, headers=enviadas)
    except (BrokenPipeError, ConnectionResetError):
        pass  # el gateway cortó antes de recibir todo el cuerpo (413): la respuesta ya está lista
    respuesta = conexion.getresponse()
    texto = respuesta.read().decode(errors="replace")
    resultado = (respuesta.status, {k.lower(): v for k, v in respuesta.getheaders()}, texto)
    conexion.close()
    return resultado


FALSA = {"X-Usuario-Id": "intruso", "X-Usuario-Rol": "Admin"}
TURISTA = {"Authorization": "Bearer ok-turista"}


def recibido(servicio, ruta):
    """Última petición real (no de ForwardAuth) que llegó a `servicio` para `ruta`."""
    candidatas = [r for r in falsos.vistos(servicio) if r["ruta"] == ruta and not r["forward_auth"]]
    return candidatas[-1] if candidatas else None


def llamadas_forward_auth():
    return [r for r in falsos.vistos("iam") if r["forward_auth"]]


# ---------------------------------------------------------------------------------------------------------------

def grupo_compose():
    grupo("Opciones estáticas de Traefik en infra/docker-compose.yml")
    import yaml
    compose = yaml.safe_load((RAIZ / "infra/docker-compose.yml").read_text())
    comando = compose["services"]["traefik"]["command"]
    for bandera in BANDERAS_DEL_COMPOSE:
        verificar(f"el compose tiene {bandera}", bandera in comando, f"command = {comando}")
    volumenes = " ".join(compose["services"]["traefik"].get("volumes", []))
    verificar("el compose monta gateway/config/compose", "gateway/config/compose" in volumenes)
    verificar("el compose pasa DOMINIO_PUBLICO a Traefik (la plantilla del CORS lo lee)", "DOMINIO_PUBLICO" in compose["services"]["traefik"].get("environment", {}))

    grupo("HTTPS: infra/docker-compose.https.yml (se suma al compose base)")
    https = yaml.safe_load((RAIZ / "infra/docker-compose.https.yml").read_text())["services"]["traefik"]
    cmd = https["command"]
    # Compose REEMPLAZA `command`: el del archivo adicional debe llevar todos los flags del base
    faltan = [f for f in comando if f not in cmd]
    verificar("el command del archivo HTTPS incluye todos los flags del compose base", not faltan, f"faltan: {faltan}")
    for bandera, que in [
        ("--entrypoints.websecure.address=:443", "abre el 443"),
        ("--entrypoints.web.http.redirections.entrypoint.to=websecure", "el 80 redirige a HTTPS"),
        ("--entrypoints.websecure.http.tls.certresolver=le", "los routers de websecure usan Let's Encrypt"),
        ("--certificatesresolvers.le.acme.httpchallenge.entrypoint=web", "reto HTTP-01 por el puerto 80"),
        ("--certificatesresolvers.le.acme.storage=/letsencrypt/acme.json", "guarda el certificado en un volumen"),
        ("--entrypoints.websecure.http.middlewares=hsts@file", "HSTS en todas las respuestas HTTPS"),
    ]:
        verificar(f"HTTPS: {que}", bandera in cmd)
    dominios = [f for f in cmd if "tls.domains" in f]
    verificar("el certificado cubre DOMINIO_PUBLICO y s3.DOMINIO_PUBLICO", any("${DOMINIO_PUBLICO" in f for f in dominios) and any("sans=s3.${DOMINIO_PUBLICO}" in f for f in dominios), str(dominios))
    verificar("publica el 443", any(str(p).endswith("443:443") for p in https.get("ports", [])))
    verificar("el certificado va en un volumen (se pierde al recrear el contenedor si no)", any("/letsencrypt" in v for v in https.get("volumes", [])))
    verificar("la CA de Let's Encrypt se puede cambiar a staging con ACME_CA_SERVER", any("ACME_CA_SERVER" in f for f in cmd))

    grupo("Rutas sin entryPoints: sirven igual por HTTP (local) y por HTTPS (servidor)")
    import glob
    con_entrypoints = []
    for archivo in sorted(glob.glob(str(RAIZ / "gateway/config/compose/*.yml"))):
        for nombre, r in ((yaml.safe_load(open(archivo).read()).get("http", {}).get("routers")) or {}).items():
            if "entryPoints" in r:
                con_entrypoints.append(nombre)
    verificar("ninguna ruta fija entryPoints (con `web` fijo, nunca atenderían por HTTPS)", not con_entrypoints, str(con_entrypoints))


def grupo_publicas():
    grupo("Rutas públicas: llegan sin token, sin ForwardAuth, y sin el X-Usuario-* del cliente")
    casos = [
        ("POST", "/api/iam/register", "iam"), ("POST", "/api/iam/auth/restablecer", "iam"),
        ("GET", "/api/iam/.well-known/jwks.json", "iam"),
        ("GET", "/api/catalog/buscar?q=playa", "catalog"), ("GET", "/api/catalog/servicios/abc", "catalog"),
        ("POST", "/api/catalog/servicios/abc/intencion-visita", "catalog"),
        ("GET", "/api/bookings/disponibilidad?servicio_id=x", "booking"),
        ("GET", "/api/reviews/servicios/abc/resenas", "review"),
    ]
    for metodo, ruta, servicio in casos:
        falsos.limpiar()
        estado, _, _ = pedir(metodo, ruta, FALSA)
        r = recibido(servicio, ruta.split("?")[0])
        verificar(f"{metodo} {ruta}", estado == 200 and r is not None and not llamadas_forward_auth()
                  and "x-usuario-id" not in r["cabeceras"] and "x-usuario-rol" not in r["cabeceras"],
                  f"estado={estado} recibido={r and r['cabeceras'].get('x-usuario-id')}")


def grupo_protegidas():
    grupo("Rutas protegidas: sin token 401; con token, la identidad es la del IAM y nunca la del cliente")
    casos = [
        ("GET", "/api/bookings/mis-reservas", "booking"), ("POST", "/api/bookings/", "booking"),
        ("GET", "/api/iam/perfil", "iam"), ("POST", "/api/iam/logout", "iam"),
        ("GET", "/api/catalog/analitica/tablero", "catalog"), ("POST", "/api/reviews/resenas", "review"),
        ("POST", "/api/recommendations/chat", "recommendation"),
    ]
    for metodo, ruta, servicio in casos:
        falsos.limpiar()
        estado, _, texto = pedir(metodo, ruta, FALSA)
        verificar(f"{metodo} {ruta} sin token → 401 y no llega al servicio",
                  estado == 401 and "TOKEN_INVALIDO" in texto and recibido(servicio, ruta) is None, f"estado={estado}")
        falsos.limpiar()
        estado, _, _ = pedir(metodo, ruta, {**FALSA, **TURISTA})
        r = recibido(servicio, ruta)
        verificar(f"{metodo} {ruta} con token → identidad del IAM (no la falsa), prefijo intacto",
                  estado == 200 and r is not None and r["cabeceras"].get("x-usuario-id") == "usuario-turista"
                  and r["cabeceras"].get("x-usuario-rol") == "Turista", f"estado={estado} id={r and r['cabeceras'].get('x-usuario-id')}")


def grupo_no_expuestos():
    grupo("Lo que no debe publicarse: /internal, /health y /metrics no llegan a ningún servicio")
    for ruta in ["/internal/usuarios/abc/contacto", "/health", "/metrics", "/health/live"]:
        falsos.limpiar()
        estado, _, _ = pedir("GET", ruta)
        servicios = {r["servicio"] for r in falsos.vistos() if r["servicio"] != "frontend"}
        verificar(f"GET {ruta} no llega a ningún servicio", not servicios, f"llegó a {servicios}")


def grupo_cabeceras():
    grupo("Correlación y dirección del cliente")
    falsos.limpiar()
    pedir("GET", "/api/catalog/buscar", {"X-Correlation-ID": "abc-123", "X-Forwarded-For": "6.6.6.6"})
    r = recibido("catalog", "/api/catalog/buscar")
    verificar("X-Correlation-ID llega al servicio", r and r["cabeceras"].get("x-correlation-id") == "abc-123")
    verificar("X-Forwarded-For del cliente no se acepta (Traefik pone el suyo)", r and "6.6.6.6" not in r["cabeceras"].get("x-forwarded-for", ""),
              r and r["cabeceras"].get("x-forwarded-for"))


def grupo_documentos():
    grupo("Carga de documentos: sesión primero, tope de 6 MB después")
    ruta = "/api/iam/prestador/documentos"
    falsos.limpiar()
    estado, _, _ = pedir("POST", ruta, cuerpo=b"x" * (7 * 1024 * 1024))
    verificar("7 MB sin token → 401 y no llega al IAM", estado == 401 and recibido("iam", ruta) is None, f"estado={estado}")
    falsos.limpiar()
    estado, _, _ = pedir("POST", ruta, TURISTA, cuerpo=b"x" * (1024 * 1024))
    r = recibido("iam", ruta)
    verificar("1 MB con token → llega al IAM", estado == 200 and r is not None and r["bytes"] == 1024 * 1024, f"estado={estado}")
    falsos.limpiar()
    estado, _, _ = pedir("POST", ruta, TURISTA, cuerpo=b"x" * (7 * 1024 * 1024))
    verificar("7 MB con token → 413 y no llega al IAM", estado == 413 and recibido("iam", ruta) is None, f"estado={estado}")


def grupo_almacenamiento():
    grupo("SeaweedFS por nombre de host (URLs firmadas) y CORS solo para la PWA")
    falsos.limpiar()
    estado, _, _ = pedir("GET", "/catalogo-imagenes/foto.jpg", host="s3.localhost")
    verificar("Host s3.localhost → SeaweedFS", estado == 200 and falsos.vistos("almacenamiento") and not falsos.vistos("frontend"))
    estado, cab, _ = pedir("OPTIONS", "/documentos/x", {
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "PUT"}, host="s3.localhost")
    verificar("preflight desde la PWA permitido", cab.get("access-control-allow-origin") == "http://localhost:5173", str(cab))
    estado, cab, _ = pedir("OPTIONS", "/documentos/x", {
        "Origin": "https://sitio-malo.example", "Access-Control-Request-Method": "PUT"}, host="s3.localhost")
    verificar("preflight desde otro origen NO permitido", "access-control-allow-origin" not in cab, str(cab))
    falsos.limpiar()
    estado, _, _ = pedir("GET", "/catalogo-imagenes/foto.jpg", host=f"s3.{DOMINIO_DE_PRUEBA}")
    verificar(f"Host s3.<dominio> ({'s3.' + DOMINIO_DE_PRUEBA}) → SeaweedFS: el dominio no está escrito en la ruta", estado == 200 and falsos.vistos("almacenamiento") and not falsos.vistos("frontend"))
    estado, cab, _ = pedir("OPTIONS", "/documentos/x", {
        "Origin": f"https://{DOMINIO_DE_PRUEBA}", "Access-Control-Request-Method": "PUT"}, host=f"s3.{DOMINIO_DE_PRUEBA}")
    verificar("preflight desde la PWA con HTTPS (el DOMINIO_PUBLICO del entorno) permitido", cab.get("access-control-allow-origin") == f"https://{DOMINIO_DE_PRUEBA}", str(cab))
    estado, cab, _ = pedir("OPTIONS", "/documentos/x", {
        "Origin": f"http://{DOMINIO_DE_PRUEBA}", "Access-Control-Request-Method": "PUT"}, host=f"s3.{DOMINIO_DE_PRUEBA}")
    verificar("la PWA por HTTP plano en ese dominio NO está permitida", "access-control-allow-origin" not in cab, str(cab))
    falsos.limpiar()
    pedir("GET", "/catalogo-imagenes/foto.jpg")
    verificar("sin ese host, la misma ruta va al frontend (no a SeaweedFS)", not falsos.vistos("almacenamiento"))
    estado, _, _ = pedir("GET", "/catalogo-imagenes/foto.jpg", host="mis3.localhost")
    verificar("un host que solo CONTIENE s3 (mis3.localhost) no va a SeaweedFS", not falsos.vistos("almacenamiento"))


def grupo_frontend():
    grupo("Frontend: lo que no es de un servicio va a la PWA")
    for ruta in ["/", "/mis-reservas", "/restablecer-contrasena", "/servicios/abc"]:
        falsos.limpiar()
        estado, _, _ = pedir("GET", ruta)
        verificar(f"GET {ruta} → frontend", estado == 200 and falsos.vistos("frontend") and not falsos.vistos("iam"))


def comprobar_log(gateway):
    grupo("El token de /restablecer-contrasena no queda en el log de acceso")
    pedir("GET", "/restablecer-contrasena?token=TOKEN-SECRETO-123")
    pedir("GET", "/api/catalog/buscar?q=playa")
    time.sleep(1.5)
    texto = gateway.log_acceso.read_text()
    verificar("el token no aparece en ningún campo del log", "TOKEN-SECRETO-123" not in texto, texto[-600:])
    verificar("el log sigue registrando las peticiones (servicio, método y estado)",
              '"RequestMethod":"GET"' in texto and '"DownstreamStatus":200' in texto and "catalog" in texto, texto[-300:])


def grupo_limites(gateway):
    grupo("Límites de tasa (Traefik reiniciado para empezar con los contadores en cero)")
    gateway.reiniciar()
    login = [pedir("POST", "/api/iam/login", cuerpo=b"{}")[0] for _ in range(6)]
    verificar("login: 5 intentos pasan y el 6.º da 429", login[:5] == [200] * 5 and login[5] == 429, str(login))
    estado = pedir("POST", "/api/iam/auth/recuperar", cuerpo=b"{}")[0]
    verificar("recuperar comparte el cupo del login (ya agotado) → 429", estado == 429, str(estado))
    refresh = [pedir("POST", "/api/iam/auth/refresh", cuerpo=b"{}")[0] for _ in range(12)]
    verificar("refresh tiene su propio cupo: no lo gasta el login y aguanta una ráfaga de 10",
              refresh[:10] == [200] * 10, str(refresh))
    verificar("refresh también tiene tope (11.º–12.º pueden dar 429)", 429 in refresh, str(refresh))
    estado = pedir("POST", "/api/iam/register", cuerpo=b"{}")[0]
    verificar("el registro no entra en esos cupos", estado == 200, str(estado))


def operaciones_de_los_contratos():
    import yaml
    for archivo in sorted((RAIZ / "contracts/openapi").glob("*.yaml")):
        contrato = yaml.safe_load(archivo.read_text())
        servidores = [s["url"] for s in contrato.get("servers", [])]
        base = servidores[0] if servidores and servidores[0].startswith("/") else ""
        if archivo.name == "iam-interno.yaml":
            continue  # llamadas internas entre pods: no pasan por el gateway
        seguridad_global = contrato.get("security")
        for ruta, item in contrato["paths"].items():
            if ruta in ("/health", "/metrics") or ruta.startswith("/internal"):
                continue
            for metodo, op in item.items():
                if metodo not in ("get", "post", "put", "patch", "delete"):
                    continue
                seguridad = op.get("security", seguridad_global)
                publica = seguridad == [] or seguridad is None
                url = re.sub(r"\{[^}]+\}", "x1", (base + ruta)).replace("//", "/")
                yield archivo.name, metodo.upper(), url.rstrip("/") if url != "/" else url, publica


def grupo_contratos():
    grupo("Barrido de los contratos OpenAPI: cada operación es pública o protegida como dice su contrato")
    servicio_de = {"iam.yaml": "iam", "catalog.yaml": "catalog", "booking.yaml": "booking", "review.yaml": "review",
                   "recommendation.yaml": "recommendation"}
    total = 0
    malas = []
    for contrato, metodo, ruta, publica in operaciones_de_los_contratos():
        total += 1
        servicio = servicio_de[contrato]
        cuerpo = b"{}" if metodo in ("POST", "PUT", "PATCH") else None
        cab = {**FALSA, "Content-Type": "application/json"}
        falsos.limpiar()
        estado, _, _ = pedir(metodo, ruta, cab, cuerpo)
        llego = recibido(servicio, ruta) is not None
        if publica:
            r = recibido(servicio, ruta)
            bien = (estado == 200 and llego and (ruta == "/api/iam/auth/verificar" or not llamadas_forward_auth())
                    and "x-usuario-id" not in r["cabeceras"])
        else:
            bien = estado == 401 and not llego
        if bien and not publica:
            falsos.limpiar()
            estado2, _, _ = pedir(metodo, ruta, {**cab, **TURISTA}, cuerpo)
            r = recibido(servicio, ruta)
            bien = estado2 == 200 and r is not None and r["cabeceras"].get("x-usuario-id") == "usuario-turista"
        if not bien:
            malas.append(f"{contrato} {metodo} {ruta} ({'pública' if publica else 'protegida'}) estado={estado}")
    verificar(f"las {total} operaciones de los contratos están enrutadas según su `security`", not malas, "; ".join(malas[:6]))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--traefik", default=shutil.which("traefik") or "traefik")
    parser.add_argument("--config", default=str(RAIZ / "gateway/config/compose"))
    args = parser.parse_args()

    falsos.iniciar()
    gateway = Gateway(args.traefik, Path(args.config))
    gateway.arrancar()
    try:
        print(subprocess.run([args.traefik, "version"], capture_output=True, text=True).stdout.splitlines()[0])
        grupo_compose()
        grupo_publicas()
        grupo_protegidas()
        grupo_no_expuestos()
        grupo_cabeceras()
        grupo_documentos()
        grupo_almacenamiento()
        grupo_frontend()
        grupo_contratos()
        comprobar_log(gateway)
        grupo_limites(gateway)
    finally:
        gateway.detener()
        shutil.rmtree(gateway.tmp, ignore_errors=True)

    print(f"\n{resultados['ok']} comprobaciones correctas, {len(resultados['fallos'])} con fallos")
    for f in resultados["fallos"]:
        print(f"  ✗ {f}")
    sys.exit(1 if resultados["fallos"] else 0)


if __name__ == "__main__":
    main()
