from app.application.dto.subida_imagen import SubidaImagen
from app.application.ports.almacen_imagenes import AlmacenImagenes
from app.application.ports.consulta_prestador import ConsultaPrestador
from app.application.use_cases.acceso_prestador import exigir_perfil
from app.domain.value_objects.identidad import Identidad, Rol
from app.domain.value_objects.imagen_solicitada import ImagenSolicitada


class SolicitarSubidaImagen:
    """URL firmada para que la PWA suba la imagen directo a SeaweedFS, sin pasar por aquí.

    La imagen queda bajo la carpeta del prestador; al guardar el servicio solo se aceptan
    URL de esa carpeta, así nadie puede usar imágenes de otro prestador.
    """

    def __init__(self, consulta: ConsultaPrestador, imagenes: AlmacenImagenes) -> None:
        self._consulta = consulta
        self._imagenes = imagenes

    async def execute(self, identidad: Identidad, imagen: ImagenSolicitada) -> SubidaImagen:
        identidad.exigir_rol(Rol.PRESTADOR)
        perfil = exigir_perfil(await self._consulta.perfil_de_usuario(identidad.usuario_id))
        perfil.exigir_activo()
        return self._imagenes.url_subida(perfil.id, imagen)
