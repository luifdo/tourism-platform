"""Servicios falsos para probar el gateway: responden 200 y anotan lo que reciben.

El "iam" falso también hace de ForwardAuth (/api/iam/auth/verificar): reconoce unos tokens de prueba
y devuelve X-Usuario-Id y X-Usuario-Rol; con cualquier otro responde 401 como iam-service.
"""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKENS = {
    "ok-turista": ("usuario-turista", "Turista"),
    "ok-prestador": ("usuario-prestador", "Prestador"),
    "ok-admin": ("usuario-admin", "Admin"),
}
PUERTOS = {
    "iam": 18001, "catalog": 18002, "booking": 18003, "review": 18004, "recommendation": 18005,
    "frontend": 15173, "almacenamiento": 18333,
}

_REGISTRO = []
_CERROJO = threading.Lock()


def limpiar():
    with _CERROJO:
        _REGISTRO.clear()


def vistos(servicio=None):
    with _CERROJO:
        return [r for r in _REGISTRO if servicio is None or r["servicio"] == servicio]


def _manejador(servicio):
    class Manejador(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):  # sin ruido en la consola
            pass

        def _leer_cuerpo(self):
            restante = int(self.headers.get("Content-Length") or 0)
            total = 0
            while restante > 0:
                trozo = self.rfile.read(min(65536, restante))
                if not trozo:
                    break
                total += len(trozo)
                restante -= len(trozo)
            return total

        def _responder(self, estado, cuerpo, extra=None):
            datos = json.dumps(cuerpo).encode()
            self.send_response(estado)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(datos)))
            for clave, valor in (extra or {}).items():
                self.send_header(clave, valor)
            self.end_headers()
            self.wfile.write(datos)

        def _atender(self):
            ruta, _, consulta = self.path.partition("?")
            cabeceras = {k.lower(): v for k, v in self.headers.items()}
            bytes_recibidos = self._leer_cuerpo()
            with _CERROJO:
                _REGISTRO.append({
                    "servicio": servicio, "metodo": self.command, "ruta": ruta, "consulta": consulta,
                    "cabeceras": cabeceras, "bytes": bytes_recibidos,
                    # Traefik marca así sus llamadas de ForwardAuth
                    "forward_auth": "x-forwarded-uri" in cabeceras and ruta == "/api/iam/auth/verificar",
                })
            if servicio == "iam" and ruta == "/api/iam/auth/verificar":
                token = cabeceras.get("authorization", "").removeprefix("Bearer ").strip()
                if token in TOKENS:
                    usuario, rol = TOKENS[token]
                    return self._responder(200, {"ok": True}, {"X-Usuario-Id": usuario, "X-Usuario-Rol": rol})
                return self._responder(401, {"detail": "El token no es válido, expiró o fue revocado.", "code": "TOKEN_INVALIDO"},
                                       {"WWW-Authenticate": "Bearer"})
            return self._responder(200, {"servicio": servicio, "ruta": ruta})

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_HEAD = _atender

    return Manejador


def iniciar():
    servidores = []
    for servicio, puerto in PUERTOS.items():
        servidor = ThreadingHTTPServer(("127.0.0.1", puerto), _manejador(servicio))
        servidor.daemon_threads = True
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        servidores.append(servidor)
    return servidores
