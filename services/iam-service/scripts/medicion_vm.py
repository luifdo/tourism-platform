"""Comprobaciones puntuales de iam-service en la VM pública, por el gateway real con HTTPS.

NO es una prueba de carga: la VM tiene los datos de la demo y una sola réplica. Hace unas 25
peticiones en serie y como máximo 4 logins por minuto.

Comprueba lo que en k3d no se pudo: ESC-04 con IP real (F-08, C-56), el bucket privado (C-46), la
aprobación hasta catalog, el refresh (C-60), la supresión (C-27, C-63) y el certificado.

Uso (PowerShell, desde services/iam-service, con las variables ya definidas):
    uv run python -m scripts.medicion_vm

Variables: IAM_VM_URL, IAM_VM_ADMIN_EMAIL, IAM_VM_ADMIN_PASSWORD y MI_IP_PUBLICA.

Nunca escribe contraseñas, tokens, URL firmadas, correos completos ni la IP pública completa (el
repo es público y la IP es un dato personal; las privadas sí se muestran). Crea solo un Turista y un
Prestador propios, con contraseñas aleatorias que no guarda, y al terminar desactiva los que no se
suprimieron. El reporte queda en docs/evidencias/vm-aws.txt.
"""

import ipaddress
import os
import secrets
import socket
import ssl
import subprocess
import sys
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

SERVICIO = Path(__file__).resolve().parents[1]
REPORTE = SERVICIO / "docs" / "evidencias" / "vm-aws.txt"
VARIABLES = ("IAM_VM_URL", "IAM_VM_ADMIN_EMAIL", "IAM_VM_ADMIN_PASSWORD", "MI_IP_PUBLICA")
BUZON, DOMINIO = "laiadominomimente", "gmail.com"
PDF = b"%PDF-1.4\n%documento ficticio de la prueba del IAM, sin datos reales\n%%EOF\n"
MOTIVO = "Datos de prueba"
SEPARACION_LOGINS = 16.0  # s: menos de 4 logins por minuto
VIDA_TOKEN_ADMIN = 600.0  # s: se renueva con el refresh antes de los 15 min del access token
RUTA_PERFIL = "/api/iam/perfil"
RUTA_ADMIN = "/api/iam/admin/usuarios"


# ---------- Salida sin secretos ----------


def enmascarar(correo: str) -> str:
    local, _, dominio = correo.partition("@")
    return f"{local[:1]}***@{dominio}"


def enmascarar_ip(ip: str) -> str:
    """Una IP pública es un dato personal: solo los dos primeros octetos (o grupos en IPv6). Las
    privadas no identifican a nadie y se muestran enteras: son las que delatan F-08."""
    try:
        direccion = ipaddress.ip_address(ip)
    except ValueError:
        return "(no es una IP)"
    if direccion.is_private:
        return f"{ip} (privada)"
    if direccion.version == 4:
        return ".".join(ip.split(".")[:2] + ["x", "x"])
    return ":".join(direccion.exploded.split(":")[:2] + ["x"] * 6)


def resumen(respuesta: httpx.Response) -> str:
    """Código y `code` del error; nunca el cuerpo (el del login lleva tokens)."""
    try:
        codigo = respuesta.json().get("code") if respuesta.status_code >= 400 else None
    except ValueError:
        codigo = None
    return f"{respuesta.status_code}" + (f" {codigo}" if codigo else "")


def fallo(exc: BaseException) -> str:
    """Solo el tipo de error de httpx: su mensaje puede llevar la URL firmada."""
    return str(exc) if isinstance(exc, PasoFallidoError) else type(exc).__name__


class PasoFallidoError(Exception):
    """Mensaje escrito por el script, sin secretos."""


@dataclass
class Linea:
    numero: str
    descripcion: str
    estado: str  # OK | FALLA | PENDIENTE
    detalle: str = ""

    def texto(self) -> str:
        return f"{self.numero:<5} {self.estado:<9} {self.descripcion}" + (
            f"  -> {self.detalle}" if self.detalle else ""
        )


@dataclass
class Cuenta:
    rol: str
    email: str = field(repr=False)
    password: str = field(repr=False)
    id: str | None = None
    suprimida: bool = False
    access: str | None = field(default=None, repr=False)

    def auth(self) -> dict[str, str]:
        if not self.access:
            raise PasoFallidoError(f"el {self.rol} no tiene sesión")
        return {"Authorization": f"Bearer {self.access}"}


@dataclass
class Medicion:
    url: str
    mi_ip: str
    admin_email: str = field(repr=False)
    admin_password: str = field(repr=False)
    inicio: datetime = field(default_factory=lambda: datetime.now(UTC))
    lineas: list[Linea] = field(default_factory=list)
    cuentas: list[Cuenta] = field(default_factory=list)
    limpieza: list[str] = field(default_factory=list)
    consulta_sql: str = ""
    razon_social: str = ""
    _admin: tuple[str, str, float] | None = field(default=None, repr=False)
    _ultimo_login: float = float("-inf")

    def __post_init__(self) -> None:
        self.http = httpx.Client(
            base_url=self.url,
            timeout=20,
            follow_redirects=False,
            headers={"User-Agent": "medicion-vm-iam"},
        )

    def anotar(self, numero: str, descripcion: str, estado: str, detalle: object = "") -> bool:
        linea = Linea(numero, descripcion, estado, str(detalle) if detalle != "" else "")
        self.lineas.append(linea)
        print(linea.texto(), flush=True)
        return estado == "OK"

    def check(self, numero: str, descripcion: str, condicion: bool, detalle: object = "") -> bool:
        return self.anotar(numero, descripcion, "OK" if condicion else "FALLA", detalle)

    # ----- Logins limitados -----

    def login(self, email: str, password: str) -> httpx.Response:
        """Como máximo 4 por minuto; ante un 429, espera según Retry-After y reintenta una vez."""
        espera = self._ultimo_login + SEPARACION_LOGINS - time.monotonic()
        if espera > 0:
            print(f"      (espera {espera:.0f} s por el límite de logins)", flush=True)
            time.sleep(espera)
        cuerpo = {"email": email, "password": password}
        respuesta = self.http.post("/api/iam/login", json=cuerpo)
        self._ultimo_login = time.monotonic()
        if respuesta.status_code == 429:
            retry = respuesta.headers.get("retry-after", "")
            segundos = int(retry) if retry.isdigit() else 60
            print(f"      (429: espera {segundos} s y reintenta una vez)", flush=True)
            time.sleep(segundos)
            respuesta = self.http.post("/api/iam/login", json=cuerpo)
            self._ultimo_login = time.monotonic()
        return respuesta

    def iniciar_sesion(self, cuenta: Cuenta) -> httpx.Response:
        respuesta = self.login(cuenta.email, cuenta.password)
        cuenta.access = (
            respuesta.json().get("access_token") if respuesta.status_code == 200 else None
        )
        return respuesta

    # ----- Admin de prueba -----

    def admin(self) -> dict[str, str]:
        if self._admin is None:
            r = self.login(self.admin_email, self.admin_password)
            if r.status_code != 200:
                raise PasoFallidoError(f"login del Admin de prueba: {resumen(r)}")
            datos = r.json()
            self._admin = (datos["access_token"], datos["refresh_token"], time.monotonic())
        elif time.monotonic() - self._admin[2] > VIDA_TOKEN_ADMIN:
            r = self.http.post("/api/iam/auth/refresh", json={"refresh_token": self._admin[1]})
            if r.status_code != 200:
                raise PasoFallidoError(f"refresh del Admin de prueba: {resumen(r)}")
            datos = r.json()
            self._admin = (datos["access_token"], datos["refresh_token"], time.monotonic())
        return {"Authorization": f"Bearer {self._admin[0]}"}

    def bitacora(self, **filtros: str) -> list[dict[str, Any]]:
        params = {"tamano": "100", "desde": (self.inicio - timedelta(minutes=2)).isoformat()}
        r = self.http.get("/api/iam/admin/bitacora", params=params | filtros, headers=self.admin())
        if r.status_code != 200:
            raise PasoFallidoError(f"bitácora: {resumen(r)}")
        return r.json()["items"]

    def buscar(
        self, condicion: Callable[[dict[str, Any]], bool], minimo: int, **filtros: str
    ) -> list[dict[str, Any]]:
        """La fila del rechazo se escribe en su propia transacción: espera hasta 15 s."""
        fin = time.monotonic() + 15
        while True:
            filas = [f for f in self.bitacora(**filtros) if condicion(f)]
            if len(filas) >= minimo or time.monotonic() > fin:
                return filas
            time.sleep(2)


# ---------- Preparación ----------


def nueva_cuenta(rol: str, marca: str) -> Cuenta:
    email = f"{BUZON}+prueba-iam-{rol.lower()}-{marca}@{DOMINIO}"
    # Política del registro: 8 a 128 caracteres, con letras y números.
    return Cuenta(rol, email, f"Pv{secrets.token_urlsafe(18)}7")


def registrar(m: Medicion, cuenta: Cuenta) -> None:
    r = m.http.post(
        "/api/iam/register",
        json={
            "email": cuenta.email,
            "password": cuenta.password,
            "nombre_completo": f"Prueba IAM {cuenta.rol}",
            "rol": cuenta.rol,
            "habeas_data_aceptado": True,
            "es_mayor_de_edad": True,
            "idioma": "es",
        },
    )
    if r.status_code == 201:
        cuenta.id = r.json()["id"]
        m.cuentas.append(cuenta)
    m.check(
        "0",
        f"Registro del {cuenta.rol} de prueba {enmascarar(cuenta.email)}",
        r.status_code == 201,
        resumen(r) if r.status_code != 201 else f"usuario_id={cuenta.id}",
    )


# ---------- Comprobaciones ----------


def esc04_e_ip(m: Medicion, turista: Cuenta) -> None:
    marca = uuid.uuid4().hex[:10]
    corr_sin, corr_mal = f"medicion-vm-401a-{marca}", f"medicion-vm-401b-{marca}"
    r = m.http.get(RUTA_PERFIL, headers={"X-Correlation-ID": corr_sin})
    m.check("1.1", "GET /api/iam/perfil sin token -> 401", r.status_code == 401, resumen(r))
    r = m.http.get(
        RUTA_PERFIL,
        headers={"X-Correlation-ID": corr_mal, "Authorization": "Bearer no-es-un-jwt"},
    )
    m.check(
        "1.2", "GET /api/iam/perfil con token mal formado -> 401", r.status_code == 401, resumen(r)
    )

    r = m.iniciar_sesion(turista)
    if not m.check("1.3", "Login del Turista", r.status_code == 200, resumen(r)):
        m.anotar("1.4", "Turista en /admin/usuarios -> 403", "PENDIENTE", "sin sesión del Turista")
        return
    r = m.http.get(RUTA_ADMIN, headers=turista.auth())
    m.check(
        "1.4",
        "Turista en GET /api/iam/admin/usuarios -> 403 ROL_INSUFICIENTE",
        r.status_code == 403 and resumen(r) == "403 ROL_INSUFICIENTE",
        resumen(r),
    )

    def es_401(f: dict[str, Any]) -> bool:
        return f["usuario_id"] is None and (f["detalles"] or {}).get("uri") == RUTA_PERFIL

    filas_401 = m.buscar(es_401, 2, accion="ACCESS_DENIED")
    por_correlacion = {
        c: [f for f in filas_401 if f.get("correlation_id") == c] for c in (corr_sin, corr_mal)
    }
    conservado = all(por_correlacion.values())
    if conservado:
        elegidas = [por_correlacion[corr_sin][0], por_correlacion[corr_mal][0]]
        como = "por su X-Correlation-ID"
    else:
        # El gateway reemplazó el X-Correlation-ID: por ruta, sin usuario, y las más recientes.
        elegidas = sorted(filas_401, key=lambda f: f["fecha"])[-2:]
        como = "por ruta y hora (el gateway no conservó el X-Correlation-ID enviado)"
    m.check(
        "1.5",
        "Bitácora: las dos filas ACCESS_DENIED de los 401",
        len(elegidas) == 2,
        f"{len(elegidas)} encontradas {como}",
    )

    def es_403(f: dict[str, Any]) -> bool:
        return (f["detalles"] or {}).get("ruta") == RUTA_ADMIN

    filas_403 = m.buscar(es_403, 1, accion="ACCESS_DENIED", usuario_id=turista.id or "")
    m.check(
        "1.6",
        "Bitácora: la fila ACCESS_DENIED del 403 con el usuario_id del Turista",
        len(filas_403) == 1,
        f"{len(filas_403)} encontradas",
    )

    filas = elegidas + filas_403[:1]
    if not filas:
        m.anotar("2.1", "ip_origen es MI_IP_PUBLICA", "PENDIENTE", "sin filas de la comprobación 1")
        return
    # La comparación es con la IP completa; la salida solo lleva la enmascarada.
    ips = [str(f["ip_origen"] or "").split("/")[0] for f in filas]
    m.check(
        "2.1",
        f"ip_origen de las {len(filas)} filas coincide con la IP pública de quien mide "
        f"({enmascarar_ip(m.mi_ip)})",
        all(ip == m.mi_ip for ip in ips),
        "quedó " + ", ".join("la misma" if ip == m.mi_ip else enmascarar_ip(ip) for ip in ips),
    )


def bucket(m: Medicion, prestador: Cuenta, marca: str) -> bool:
    """Devuelve si el Prestador quedó con sus dos documentos (lo necesita la aprobación)."""
    r = m.iniciar_sesion(prestador)
    if not m.check("3.1", "Login del Prestador", r.status_code == 200, resumen(r)):
        return False
    m.razon_social = f"Prueba IAM {marca} SAS"
    codigos = []
    for tipo, razon in (("RNT", None), ("RUT", m.razon_social)):
        r = m.http.post(
            "/api/iam/prestador/documentos",
            data={"tipo": tipo} | ({"razon_social": razon} if razon else {}),
            files={"archivo": (f"{tipo.lower()}-prueba.pdf", PDF, "application/pdf")},
            headers=prestador.auth(),
        )
        codigos.append(resumen(r))
    subidos = codigos == ["201", "201"]
    m.check("3.2", "Carga del RNT y del RUT ficticios -> 201", subidos, " / ".join(codigos))
    if not subidos:
        return False

    r = m.http.get(f"/api/iam/admin/prestadores/{prestador.id}/documentos", headers=m.admin())
    if r.status_code != 200:
        raise PasoFallidoError(f"documentos del Prestador: {resumen(r)}")
    documento = r.json()["documentos"][0]["id"]
    r = m.http.get(f"/api/iam/admin/documentos/{documento}/url", headers=m.admin())
    if not m.check("3.3", "El Admin pide la URL firmada -> 200", r.status_code == 200, resumen(r)):
        return True
    firmada = r.json()["url"]
    partes = urlsplit(firmada)
    host = f"{partes.scheme}://{partes.netloc}"
    try:
        con_firma = httpx.get(firmada, timeout=20)
        m.check(
            "3.4",
            f"Con la firma -> 200 y el PDF subido (host {host})",
            con_firma.status_code == 200 and con_firma.content == PDF,
            con_firma.status_code,
        )
    except httpx.HTTPError as exc:
        m.check("3.4", f"Con la firma -> 200 (host {host})", False, fallo(exc))
    try:
        sin_firma = httpx.get(urlunsplit((partes.scheme, partes.netloc, partes.path, "", "")))
        m.check(
            "3.5",
            "La misma URL sin la query string -> 403 o 401",
            sin_firma.status_code in (401, 403),
            sin_firma.status_code,
        )
    except httpx.HTTPError as exc:
        m.check("3.5", "La misma URL sin la query string -> 403 o 401", False, fallo(exc))
    return True


def aprobacion(m: Medicion, prestador: Cuenta) -> None:
    r = m.http.post(f"/api/iam/admin/prestadores/{prestador.id}/aprobar", headers=m.admin())
    if not m.check("4.1", "El Admin aprueba al Prestador -> 200", r.status_code == 200, resumen(r)):
        m.anotar("4.2", "Perfil en catalog", "PENDIENTE", "sin aprobación")
        return
    inicio, ultimo = time.monotonic(), None
    while time.monotonic() - inicio < 30:
        ultimo = m.http.get("/api/catalog/prestador/perfil", headers=prestador.auth())
        if ultimo.status_code == 200 and ultimo.json().get("razon_social") == m.razon_social:
            break
        time.sleep(3)
    listo = ultimo is not None and ultimo.status_code == 200
    coincide = listo and ultimo.json().get("razon_social") == m.razon_social
    m.check(
        "4.2",
        "GET /api/catalog/prestador/perfil con la razón social (prestador.aprobado)",
        coincide,
        f"{resumen(ultimo) if ultimo else 'sin respuesta'} a los {time.monotonic() - inicio:.0f} s"
        + ("" if coincide or not listo else "; la razón social no coincide"),
    )


def refresh(m: Medicion, turista: Cuenta) -> None:
    r = m.login(turista.email, turista.password)
    if not m.check("5.1", "Login del Turista (sesión nueva)", r.status_code == 200, resumen(r)):
        return
    viejo = r.json()
    renovar = "/api/iam/auth/refresh"
    r = m.http.post(renovar, json={"refresh_token": viejo["refresh_token"]})
    nuevo = r.json() if r.status_code == 200 else {}
    m.check(
        "5.2",
        "Refresh -> 200 con tokens nuevos",
        r.status_code == 200
        and nuevo.get("refresh_token") not in (None, viejo["refresh_token"])
        and nuevo.get("access_token") not in (None, viejo["access_token"]),
        resumen(r),
    )
    r = m.http.post(renovar, json={"refresh_token": viejo["refresh_token"]})
    m.check("5.3", "El refresh viejo otra vez -> 401", r.status_code == 401, resumen(r))
    filas = m.buscar(lambda _: True, 1, accion="REFRESH_REUTILIZADO", usuario_id=turista.id or "")
    m.check("5.4", "Bitácora: fila REFRESH_REUTILIZADO del Turista", len(filas) == 1, len(filas))
    if nuevo.get("refresh_token"):
        r = m.http.post(renovar, json={"refresh_token": nuevo["refresh_token"]})
        m.check(
            "5.5",
            "El refresh nuevo también -> 401 (familia revocada)",
            r.status_code == 401,
            resumen(r),
        )
    else:
        m.anotar("5.5", "El refresh nuevo también -> 401", "PENDIENTE", "sin refresh nuevo")


def supresion(m: Medicion, prestador: Cuenta) -> None:
    r = m.http.request(
        "DELETE", RUTA_PERFIL, json={"password": prestador.password}, headers=prestador.auth()
    )
    prestador.suprimida = r.status_code == 204
    m.check("6.1", "DELETE /api/iam/perfil del Prestador -> 204", prestador.suprimida, resumen(r))
    if not prestador.suprimida:
        return
    r = m.login(prestador.email, prestador.password)
    m.check("6.2", "Login del Prestador suprimido -> 401", r.status_code == 401, resumen(r))
    m.consulta_sql = (
        "SELECT usuario_id, razon_social, telefono, direccion, activo, estado_iam_en\n"
        "  FROM prestador_perfil\n"
        f" WHERE usuario_id = '{prestador.id}';\n"
        "-- Esperado: una fila con razon_social, telefono y direccion en NULL (C-63)."
    )
    m.anotar(
        "6.3",
        "catalog borró razon_social, telefono y direccion",
        "PENDIENTE",
        "no se ve desde fuera; Luis Fernando corre en la VM la consulta de abajo sobre catalog_db",
    )


def https(m: Medicion) -> None:
    partes = urlsplit(m.url)
    if partes.scheme != "https":
        m.check("7.1", "IAM_VM_URL usa https", False, partes.scheme)
        return
    host = partes.hostname or ""
    try:
        contexto = ssl.create_default_context()
        with (
            socket.create_connection((host, partes.port or 443), timeout=10) as conexion,
            contexto.wrap_socket(conexion, server_hostname=host) as tls,
        ):
            certificado = tls.getpeercert() or {}
        emisor = dict(par[0] for par in certificado.get("issuer", ()))
        nombre = f"{emisor.get('organizationName', '?')} / {emisor.get('commonName', '?')}"
        de_staging = any(p in nombre.upper() for p in ("STAGING", "FAKE"))
        m.check(
            "7.1",
            "Certificado válido y no de staging",
            not de_staging,
            f"emisor {nombre}, vence {certificado.get('notAfter', '?')}",
        )
    except (ssl.SSLError, OSError) as exc:
        m.check(
            "7.1",
            "Certificado válido y no de staging",
            False,
            getattr(exc, "verify_message", "") or type(exc).__name__,
        )
    try:
        r = httpx.get(f"http://{partes.netloc}/", timeout=10, follow_redirects=False)
        destino = r.headers.get("location", "")
        m.check(
            "7.2",
            "http:// redirige a https://",
            r.status_code in (301, 302, 307, 308) and destino.startswith(f"https://{host}"),
            f"{r.status_code} hacia {urlsplit(destino).scheme or '-'}://"
            f"{urlsplit(destino).netloc or '-'}",
        )
    except httpx.HTTPError as exc:
        m.check("7.2", "http:// redirige a https://", False, fallo(exc))


def desactivar_sobrantes(m: Medicion) -> None:
    for cuenta in m.cuentas:
        if cuenta.suprimida or not cuenta.id:
            continue
        nombre = f"{cuenta.rol} {enmascarar(cuenta.email)} ({cuenta.id})"
        try:
            r = m.http.patch(
                f"/api/iam/admin/usuarios/{cuenta.id}/estado",
                json={"activo": False, "motivo": MOTIVO},
                headers=m.admin(),
            )
            estado = "desactivado" if r.status_code == 200 else f"NO desactivado: {resumen(r)}"
        except (httpx.HTTPError, PasoFallidoError) as exc:
            estado = f"NO desactivado: {fallo(exc)}"
        m.limpieza.append(f"{nombre}: {estado}")
    for cuenta in m.cuentas:
        if cuenta.suprimida:
            m.limpieza.append(f"{cuenta.rol} {enmascarar(cuenta.email)} ({cuenta.id}): suprimido")
    for linea in m.limpieza:
        print(f"      limpieza: {linea}", flush=True)


# ---------- Reporte ----------


def escribir_reporte(m: Medicion) -> None:
    commit = subprocess.run(
        ["git", "describe", "--always", "--dirty"], cwd=SERVICIO, capture_output=True, text=True
    ).stdout.strip()
    estados = [linea.estado for linea in m.lineas]
    lineas = [
        "# Comprobaciones de iam-service en la VM pública, por el gateway con HTTPS",
        "# Puntuales, sin carga. Sin contraseñas, tokens, URL firmadas ni correos completos.",
        f"# Fecha: {m.inicio:%Y-%m-%d %H:%M:%S} UTC",
        f"# URL: {m.url}",
        f"# IP pública de quien mide: {enmascarar_ip(m.mi_ip)}",
        f"# Commit del script: {commit}",
        "",
        *(linea.texto() for linea in m.lineas),
        "",
        f"# Resumen: {estados.count('OK')} OK, {estados.count('FALLA')} FALLA, "
        f"{estados.count('PENDIENTE')} PENDIENTE",
        "",
        "# Cuentas de prueba al terminar:",
        *(f"  {linea}" for linea in m.limpieza or ["ninguna creada"]),
    ]
    if m.consulta_sql:
        lineas += ["", "# Consulta para catalog_db (Luis Fernando, en la VM):", m.consulta_sql]
    REPORTE.write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print(f"\nReporte: {REPORTE.relative_to(SERVICIO)}")


# ---------- Principal ----------


def paso(m: Medicion, numero: str, nombre: str, funcion: Callable[[], object]) -> object:
    """Un paso roto queda como FALLA y los demás siguen."""
    try:
        return funcion()
    except (httpx.HTTPError, PasoFallidoError, KeyError, ValueError) as exc:
        m.anotar(numero, f"{nombre}: el paso no terminó", "FALLA", fallo(exc))
        return None


def main() -> int:
    faltan = [v for v in VARIABLES if not os.environ.get(v)]
    if faltan:
        print(f"Faltan variables de entorno: {', '.join(faltan)}. Defínelas y vuelve a correr.")
        return 2
    m = Medicion(
        url=os.environ["IAM_VM_URL"].rstrip("/"),
        mi_ip=os.environ["MI_IP_PUBLICA"].strip(),
        admin_email=os.environ["IAM_VM_ADMIN_EMAIL"],
        admin_password=os.environ["IAM_VM_ADMIN_PASSWORD"],
    )
    marca = datetime.now().strftime("%Y%m%d%H%M")
    turista, prestador = nueva_cuenta("Turista", marca), nueva_cuenta("Prestador", marca)
    print(
        f"Midiendo {m.url} desde {enmascarar_ip(m.mi_ip)}. "
        "Sin carga: unas 25 peticiones en serie.\n"
    )
    try:
        if not paso(m, "0", "Login del Admin de prueba", lambda: m.admin() and True):
            return 1
        registrar(m, turista)
        registrar(m, prestador)
        if turista.id:
            paso(m, "1", "ESC-04 e IP real", lambda: esc04_e_ip(m, turista))
        else:
            m.anotar("1-2", "ESC-04 e IP real", "PENDIENTE", "no se registró el Turista")
        documentos = bool(prestador.id) and paso(
            m, "3", "Bucket privado", lambda: bucket(m, prestador, marca)
        )
        if documentos:
            paso(m, "4", "Aprobación y catalog", lambda: aprobacion(m, prestador))
        else:
            m.anotar("4", "Aprobación y catalog", "PENDIENTE", "el Prestador no tiene documentos")
        if turista.id:
            paso(m, "5", "Refresh", lambda: refresh(m, turista))
        if prestador.access:
            paso(m, "6", "Supresión", lambda: supresion(m, prestador))
        else:
            m.anotar("6", "Supresión", "PENDIENTE", "sin sesión del Prestador")
        paso(m, "7", "HTTPS", lambda: https(m))
    finally:
        desactivar_sobrantes(m)
        escribir_reporte(m)
        m.http.close()
    return 1 if any(linea.estado == "FALLA" for linea in m.lineas) else 0


if __name__ == "__main__":
    sys.exit(main())
