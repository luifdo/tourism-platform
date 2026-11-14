import uuid
from dataclasses import dataclass

from app.application.use_cases.registrar_usuario import NOMBRE_MAX, NOMBRE_MIN
from app.domain.entities.usuario import Usuario
from app.domain.exceptions import (
    NombreInvalidoError,
    UsuarioNoEncontradoError,
    VersionConflictoError,
)
from app.domain.ports.unit_of_work import UnitOfWork
from app.domain.value_objects.enums import Idioma, ResultadoAuditoria


@dataclass(frozen=True)
class EditarPerfilCommand:
    usuario_id: uuid.UUID
    nombre: str | None
    idioma: Idioma | None
    # None: el cliente no envió If-Match (en línea) o envió `*`.
    version_esperada: int | None
    ip_origen: str | None


class EditarPerfil:
    """UC4: nombre e idioma, con las reglas del registro (C-49, C-51).

    Sin cambios: 200 sin auditar ni subir la version. Esa comprobación va **antes** de la de
    la versión, y es lo que hace seguro repetir el PATCH sin `Idempotency-Key`: si se perdió la
    respuesta y la cola sin conexión lo reenvía con su If-Match ya viejo, encuentra los mismos
    valores y responde 200 en vez de un 409 falso.
    """

    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, cmd: EditarPerfilCommand) -> Usuario:
        nombre = _nombre_valido(cmd.nombre)
        async with self._uow as uow:
            usuario = await uow.usuarios.find_by_id_para_actualizar(cmd.usuario_id)
            if usuario is None or usuario.suprimido:
                raise UsuarioNoEncontradoError()
            nuevo_nombre = usuario.nombre_completo if nombre is None else nombre
            nuevo_idioma = usuario.idioma if cmd.idioma is None else cmd.idioma
            campos = []
            if nuevo_nombre != usuario.nombre_completo:
                campos.append("nombre")
            if nuevo_idioma is not usuario.idioma:
                campos.append("idioma")
            if not campos:
                return usuario
            if cmd.version_esperada is not None and cmd.version_esperada != usuario.version:
                raise VersionConflictoError()

            actualizado = await uow.usuarios.actualizar_perfil(
                cmd.usuario_id, nuevo_nombre, nuevo_idioma
            )
            # Los nombres de los campos, nunca sus valores: el nombre es un dato personal.
            await uow.auditoria.registrar(
                accion="PROFILE_UPDATE",
                resultado=ResultadoAuditoria.EXITO,
                usuario_id=cmd.usuario_id,
                ip_origen=cmd.ip_origen,
                detalles={"campos": campos},
            )
            await uow.commit()
        return actualizado


def _nombre_valido(nombre: str | None) -> str | None:
    if nombre is None:
        return None
    limpio = nombre.strip()
    if not NOMBRE_MIN <= len(limpio) <= NOMBRE_MAX:
        raise NombreInvalidoError()
    return limpio
