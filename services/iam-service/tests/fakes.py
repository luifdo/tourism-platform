"""Dobles en memoria de los puertos, para probar sin base de datos."""

import asyncio
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any, Self

from redis.exceptions import ConnectionError as RedisConnectionError

from app.domain.entities.documento_verificacion import (
    DocumentoVerificacion,
    estado_verificacion,
)
from app.domain.entities.usuario import NOMBRE_SUPRIMIDO, Usuario, email_suprimido
from app.domain.events.evento_dominio import EventoDominio
from app.domain.exceptions import ServicioNoDisponibleError, UsuarioYaExisteError
from app.domain.ports.enviador_correo import Correo
from app.domain.value_objects.email import Email
from app.domain.value_objects.enums import (
    EstadoDocumento,
    Idioma,
    ResultadoAuditoria,
    Rol,
    TipoDocumento,
)
from app.domain.value_objects.evento_auditoria import EventoAuditoria
from app.domain.value_objects.filtro_bitacora import EntradaBitacora, FiltroBitacora, PaginaBitacora
from app.domain.value_objects.filtro_prestadores import (
    FiltroPrestadores,
    PaginaPrestadores,
    ResumenPrestador,
)
from app.domain.value_objects.filtro_usuarios import FiltroUsuarios, PaginaUsuarios
from app.infrastructure.observabilidad.contexto_correlacion import correlation_id_actual

AHORA = datetime(2026, 10, 23, 15, 0, tzinfo=UTC)


def reloj_fijo() -> datetime:
    return AHORA


class FakeUsuarioRepository:
    def __init__(self) -> None:
        self.por_email: dict[str, Usuario] = {}
        self.bloqueos_admins = 0

    async def add(self, usuario: Usuario) -> Usuario:
        if usuario.email in self.por_email:
            raise UsuarioYaExisteError()
        guardado = replace(usuario, id=uuid.uuid4(), creado_en=AHORA, actualizado_en=AHORA)
        self.por_email[usuario.email] = guardado
        return guardado

    async def find_by_email(self, email: Email) -> Usuario | None:
        return self.por_email.get(email.value)

    async def find_by_id(self, usuario_id: uuid.UUID) -> Usuario | None:
        return next((u for u in self.por_email.values() if u.id == usuario_id), None)

    async def actualizar_password_hash(self, usuario_id: uuid.UUID, password_hash: str) -> None:
        for email, usuario in self.por_email.items():
            if usuario.id == usuario_id:
                self.por_email[email] = replace(usuario, password_hash=password_hash)

    async def listar(self, filtro: FiltroUsuarios) -> PaginaUsuarios:
        q = (filtro.q or "").lower()
        items = [
            u
            for u in self.por_email.values()
            if (filtro.rol is None or u.rol is filtro.rol)
            and (filtro.activo is None or u.activo == filtro.activo)
            and (not q or q in u.nombre_completo.lower() or q in u.email)
        ]
        inicio = (filtro.pagina - 1) * filtro.tamano
        return PaginaUsuarios(
            items=items[inicio : inicio + filtro.tamano],
            total=len(items),
            pagina=filtro.pagina,
            tamano=filtro.tamano,
        )

    async def bloquear_admins_activos(self) -> int:
        self.bloqueos_admins += 1
        return sum(1 for u in self.por_email.values() if u.rol is Rol.ADMIN and u.activo)

    async def find_by_id_para_actualizar(self, usuario_id: uuid.UUID) -> Usuario | None:
        return await self.find_by_id(usuario_id)

    async def actualizar_razon_social(self, usuario_id: uuid.UUID, razon_social: str) -> None:
        usuario = await self.find_by_id(usuario_id)
        assert usuario is not None
        self.por_email[usuario.email] = replace(usuario, razon_social=razon_social)

    async def actualizar_rol_y_estado(
        self, usuario_id: uuid.UUID, rol: Rol, activo: bool
    ) -> Usuario:
        usuario = await self.find_by_id(usuario_id)
        assert usuario is not None
        actualizado = replace(usuario, rol=rol, activo=activo)
        self.por_email[usuario.email] = actualizado
        return actualizado

    async def actualizar_perfil(
        self, usuario_id: uuid.UUID, nombre_completo: str, idioma: Idioma
    ) -> Usuario:
        usuario = await self.find_by_id(usuario_id)
        assert usuario is not None
        actualizado = replace(
            usuario,
            nombre_completo=nombre_completo,
            idioma=idioma,
            version=usuario.version + 1,
        )
        self.por_email[usuario.email] = actualizado
        return actualizado

    async def suprimir_datos(
        self, usuario_id: uuid.UUID, password_hash: str, suprimido_en: datetime
    ) -> None:
        usuario = await self.find_by_id(usuario_id)
        assert usuario is not None
        del self.por_email[usuario.email]
        suprimido = replace(
            usuario,
            email=email_suprimido(usuario_id),
            nombre_completo=NOMBRE_SUPRIMIDO,
            razon_social=None,
            activo=False,
            password_hash=password_hash,
            datos_suprimidos_en=suprimido_en,
            version=usuario.version + 1,
        )
        self.por_email[suprimido.email] = suprimido

    def sembrar(self, usuario: Usuario) -> Usuario:
        """Guarda un usuario ya existente (sin pasar por el caso de uso de registro)."""
        guardado = replace(usuario, id=uuid.uuid4(), creado_en=AHORA, actualizado_en=AHORA)
        self.por_email[guardado.email] = guardado
        return guardado


class FakePasswordHasher:
    """Hasher trivial que registra cada verify (para comprobar el verify de relleno).

    Como Argon2, el hash lleva sus "parámetros" (version): un hash de otra versión
    sigue verificando, pero needs_rehash() devuelve True.
    """

    def __init__(self, version: int = 1) -> None:
        self.version = version
        self.verificados: list[str] = []

    def hash(self, plain: str) -> str:
        return f"fake-hash:v{self.version}:{plain[::-1]}"

    def verify(self, plain: str, hashed: str) -> bool:
        self.verificados.append(hashed)
        prefijo, _, resto = hashed.partition(":")
        _, _, invertida = resto.partition(":")
        return prefijo == "fake-hash" and invertida == plain[::-1]

    async def hash_limitado(self, plain: str) -> str:
        return self.hash(plain)

    async def verify_limitado(self, plain: str, hashed: str) -> bool:
        return self.verify(plain, hashed)

    def needs_rehash(self, hashed: str) -> bool:
        return not hashed.startswith(f"fake-hash:v{self.version}:")


class FakeRevocacion:
    """Lista de revocación en memoria. caida=True simula Valkey sin responder.

    `al_revocar_usuario` se llama en cada revocar_usuario (antes de fallar o guardar): permite
    comprobar en qué momento de la transacción ocurre.
    """

    def __init__(self, caida: bool = False) -> None:
        self.revocados: dict[str, datetime] = {}
        self.revocados_desde: dict[uuid.UUID, int] = {}
        self.revocaciones_usuario: list[tuple[uuid.UUID, datetime]] = []
        self.al_revocar_usuario: Callable[[], None] | None = None
        self.caida = caida

    async def revocar(self, jti: str, expira_en: datetime) -> None:
        if self.caida:
            raise ServicioNoDisponibleError()
        self.revocados[jti] = expira_en

    async def revocar_usuario(self, usuario_id: uuid.UUID, desde: datetime) -> None:
        if self.al_revocar_usuario is not None:
            self.al_revocar_usuario()
        if self.caida:
            raise ServicioNoDisponibleError()
        self.revocaciones_usuario.append((usuario_id, desde))
        self.revocados_desde[usuario_id] = int(desde.timestamp())

    async def esta_revocado_token(self, jti: str, usuario_id: uuid.UUID, iat: datetime) -> bool:
        if self.caida:
            raise ServicioNoDisponibleError()
        desde = self.revocados_desde.get(usuario_id)
        return jti in self.revocados or (desde is not None and int(iat.timestamp()) <= desde)


class FakeRedisClient:
    """Lo mínimo de redis.asyncio.Redis que usa ValkeyRevocacionTokens (sin expiración real)."""

    def __init__(self, caido: bool = False) -> None:
        self.valores: dict[str, str] = {}
        self.ttls: dict[str, int] = {}
        self.llamadas_mget = 0
        self.caido = caido

    def _comprobar(self) -> None:
        if self.caido:
            raise RedisConnectionError("Valkey caído")

    async def set(self, key: str, value: Any, ex: int) -> None:
        self._comprobar()
        self.valores[key] = str(value)
        self.ttls[key] = ex

    async def mget(self, *keys: str) -> list[str | None]:
        self._comprobar()
        self.llamadas_mget += 1
        return [self.valores.get(key) for key in keys]


@dataclass
class RegistroAuditoria:
    accion: str
    resultado: ResultadoAuditoria
    usuario_id: uuid.UUID | None
    ip_origen: str | None
    detalles: dict[str, Any]
    # Como el repositorio real, lo lee del ContextVar de la petición (C-05).
    correlation_id: str | None = None


class FakeAuditoriaRepository:
    """`registrar_evento` no simula el usuario inexistente (C-38): eso lo resuelve el SQL y
    se prueba en integración. `listar` tampoco filtra (eso es SQL): guarda el filtro recibido y
    pagina `entradas`.
    """

    def __init__(self) -> None:
        self.registros: list[RegistroAuditoria] = []
        self.eventos: dict[uuid.UUID, EventoAuditoria] = {}
        self.entradas: list[EntradaBitacora] = []
        self.filtros: list[FiltroBitacora] = []

    async def listar(self, filtro: FiltroBitacora) -> PaginaBitacora:
        self.filtros.append(filtro)
        inicio = (filtro.pagina - 1) * filtro.tamano
        return PaginaBitacora(
            items=self.entradas[inicio : inicio + filtro.tamano],
            total=len(self.entradas),
            pagina=filtro.pagina,
            tamano=filtro.tamano,
        )

    async def registrar_evento(self, evento: EventoAuditoria) -> bool:
        if evento.event_id in self.eventos:
            return False
        self.eventos[evento.event_id] = evento
        return True

    async def registrar(
        self,
        accion: str,
        resultado: ResultadoAuditoria,
        usuario_id: uuid.UUID | None,
        ip_origen: str | None,
        detalles: dict[str, Any],
    ) -> None:
        self.registros.append(
            RegistroAuditoria(
                accion, resultado, usuario_id, ip_origen, detalles, correlation_id_actual()
            )
        )


class FakeDocumentoRepository:
    """Documentos en memoria. `listar_prestadores` necesita las cuentas: recibe el repositorio
    de usuarios de la misma unidad de trabajo."""

    def __init__(self, usuarios: FakeUsuarioRepository) -> None:
        self.documentos: dict[uuid.UUID, DocumentoVerificacion] = {}
        self._usuarios = usuarios
        self._orden = 0

    async def agregar(self, documento: DocumentoVerificacion) -> DocumentoVerificacion:
        self._orden += 1
        guardado = replace(
            documento, id=uuid.uuid4(), fecha_subida=AHORA + timedelta(seconds=self._orden)
        )
        self.documentos[guardado.id] = guardado  # type: ignore[index]
        return guardado

    async def vigentes(self, usuario_id: uuid.UUID) -> list[DocumentoVerificacion]:
        return sorted(
            (d for d in self.documentos.values() if d.usuario_id == usuario_id and d.vigente),
            key=lambda d: d.tipo_documento.value,
        )

    async def historial(self, usuario_id: uuid.UUID) -> list[DocumentoVerificacion]:
        return sorted(
            (d for d in self.documentos.values() if d.usuario_id == usuario_id),
            key=lambda d: d.fecha_subida,  # type: ignore[arg-type, return-value]
            reverse=True,
        )

    async def find_by_id(self, documento_id: uuid.UUID) -> DocumentoVerificacion | None:
        return self.documentos.get(documento_id)

    async def retirar_vigente(self, usuario_id: uuid.UUID, tipo: TipoDocumento) -> None:
        for d in await self.vigentes(usuario_id):
            if d.tipo_documento is tipo:
                self.documentos[d.id] = replace(d, vigente=False)  # type: ignore[index]

    async def marcar_revisado(
        self,
        documento_id: uuid.UUID,
        estado: EstadoDocumento,
        revisado_por: uuid.UUID,
        revisado_en: datetime,
        motivo_rechazo: str | None,
    ) -> DocumentoVerificacion:
        revisado = replace(
            self.documentos[documento_id],
            estado=estado,
            revisado_por=revisado_por,
            revisado_en=revisado_en,
            motivo_rechazo=motivo_rechazo,
        )
        self.documentos[documento_id] = revisado
        return revisado

    async def borrar_motivos_rechazo(self, usuario_id: uuid.UUID) -> None:
        for d in await self.historial(usuario_id):
            self.documentos[d.id] = replace(d, motivo_rechazo=None)  # type: ignore[index]

    async def listar_prestadores(self, filtro: FiltroPrestadores) -> PaginaPrestadores:
        resumenes = []
        for u in self._usuarios.por_email.values():
            if u.rol is not Rol.PRESTADOR or u.id is None or u.suprimido:
                continue
            vigentes = await self.vigentes(u.id)
            estado = estado_verificacion(vigentes)
            if filtro.estado is None or estado is filtro.estado:
                resumenes.append(
                    ResumenPrestador(
                        usuario_id=u.id,
                        nombre_completo=u.nombre_completo,
                        email=u.email,
                        activo=u.activo,
                        razon_social=u.razon_social,
                        estado=estado,
                        vigentes=vigentes,
                    )
                )
        inicio = (filtro.pagina - 1) * filtro.tamano
        return PaginaPrestadores(
            items=resumenes[inicio : inicio + filtro.tamano],
            total=len(resumenes),
            pagina=filtro.pagina,
            tamano=filtro.tamano,
        )

    def sembrar(
        self, usuario_id: uuid.UUID, tipo: TipoDocumento, estado: EstadoDocumento
    ) -> DocumentoVerificacion:
        """Guarda un documento vigente ya revisado (o pendiente) sin pasar por la carga."""
        self._orden += 1
        documento = DocumentoVerificacion(
            id=uuid.uuid4(),
            usuario_id=usuario_id,
            tipo_documento=tipo,
            objeto_s3=f"{usuario_id}/{tipo.value}/x.pdf",
            tipo_contenido="application/pdf",
            tamano_bytes=10,
            estado=estado,
            fecha_subida=AHORA + timedelta(seconds=self._orden),
        )
        self.documentos[documento.id] = documento  # type: ignore[index]
        return documento


class FakeAlmacenDocumentos:
    """Bucket en memoria. caido=True simula SeaweedFS sin responder.

    `al_guardar` se llama en cada guardar, ya con el objeto en el bucket: permite simular lo que
    ocurre mientras el archivo sube.
    """

    def __init__(self, caido: bool = False) -> None:
        self.objetos: dict[str, tuple[bytes, str]] = {}
        self.caido = caido
        self.prefijos_borrados: list[str] = []
        self.al_guardar: Callable[[], Any] | None = None

    async def borrar_prefijo(self, prefijo: str) -> int:
        if self.caido:
            raise ServicioNoDisponibleError()
        self.prefijos_borrados.append(prefijo)
        claves = [c for c in self.objetos if c.startswith(prefijo)]
        for clave in claves:
            del self.objetos[clave]
        return len(claves)

    async def guardar(self, clave: str, contenido: bytes, tipo_contenido: str) -> None:
        if self.caido:
            raise ServicioNoDisponibleError()
        self.objetos[clave] = (contenido, tipo_contenido)
        if self.al_guardar is not None:
            await self.al_guardar()

    def url_lectura(self, clave: str, tipo_contenido: str, nombre_archivo: str) -> str:
        return f"https://s3.prueba/{clave}?tipo={tipo_contenido}&nombre={nombre_archivo}"


class FakeTokensRecuperacion:
    """Tokens de UC3 en memoria, en claro (el SHA-256 se prueba en integración). caido=True
    simula Valkey sin responder. `en_espera` son los usuarios dentro de los 60 s."""

    def __init__(self, caido: bool = False) -> None:
        self.tokens: dict[str, uuid.UUID] = {}
        self.en_espera: set[uuid.UUID] = set()
        self.caido = caido

    def _comprobar(self) -> None:
        if self.caido:
            raise ServicioNoDisponibleError()

    async def reservar_envio(self, usuario_id: uuid.UUID) -> bool:
        self._comprobar()
        if usuario_id in self.en_espera:
            return False
        self.en_espera.add(usuario_id)
        return True

    async def guardar(self, token: str, usuario_id: uuid.UUID) -> None:
        self._comprobar()
        self.tokens = {t: u for t, u in self.tokens.items() if u != usuario_id}
        self.tokens[token] = usuario_id

    async def esta_vigente(self, token: str) -> bool:
        self._comprobar()
        return token in self.tokens

    async def consumir(self, token: str) -> uuid.UUID | None:
        self._comprobar()
        return self.tokens.pop(token, None)

    async def descartar(self, usuario_id: uuid.UUID) -> None:
        self._comprobar()
        self.tokens = {t: u for t, u in self.tokens.items() if u != usuario_id}
        self.en_espera.discard(usuario_id)


class FakeEnviadorCorreo:
    """Guarda los correos. caido=True simula el SMTP sin responder. `liberar` permite retener el
    envío para comprobar que la respuesta HTTP no lo espera."""

    def __init__(self, caido: bool = False) -> None:
        self.enviados: list[Correo] = []
        self.caido = caido
        self.liberar = threading.Event()
        self.liberar.set()

    async def enviar(self, correo: Correo) -> None:
        await asyncio.to_thread(self.liberar.wait, 10)
        if self.caido:
            raise ServicioNoDisponibleError()
        self.enviados.append(correo)


class FakeOutbox:
    def __init__(self) -> None:
        self.eventos: list[EventoDominio] = []

    async def agregar(self, evento: EventoDominio) -> None:
        self.eventos.append(evento)


class FakeUnitOfWork:
    """Cuenta entradas, commits y rollbacks. Los repositorios persisten entre usos, como una
    base real. caida=True simula PostgreSQL sin responder al abrir la transacción.
    """

    def __init__(self, caida: bool = False) -> None:
        self.usuarios = FakeUsuarioRepository()
        self.auditoria = FakeAuditoriaRepository()
        self.outbox = FakeOutbox()
        self.documentos = FakeDocumentoRepository(self.usuarios)
        self.entradas = 0
        self.commits = 0
        self.rollbacks = 0
        self.caida = caida
        self._committed = False

    async def __aenter__(self) -> Self:
        self.entradas += 1
        if self.caida:
            raise ConnectionRefusedError("PostgreSQL caído")
        self._committed = False
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if not self._committed:
            await self.rollback()

    async def commit(self) -> None:
        self.commits += 1
        self._committed = True

    async def rollback(self) -> None:
        self.rollbacks += 1
