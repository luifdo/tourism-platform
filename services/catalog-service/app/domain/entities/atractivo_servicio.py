from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.entities.prestador_perfil import PrestadorPerfil
from app.domain.entities.versionado import Versionado
from app.domain.errors import DatoInvalido, NoEncontrado
from app.domain.value_objects.atributos.atributos_servicio import AtributosServicio
from app.domain.value_objects.catalogos import Categoria, UnidadTarifa
from app.domain.value_objects.geo import Coordenada
from app.domain.value_objects.tarifa import Tarifa
from app.domain.value_objects.texto_traducido import TextoTraducido
from app.domain.value_objects.tipo_servicio import TipoServicio

MAX_IMAGENES = 10


@dataclass(frozen=True, slots=True)
class DatosServicio:
    """Campos que el prestador escribe al registrar o editar una oferta.

    La categoría no se escribe: sale del tipo, así nunca se contradicen.
    """

    nombre: TextoTraducido
    descripcion: TextoTraducido
    tipo: TipoServicio
    ubicacion: Coordenada
    tarifa_base: Tarifa
    unidad_tarifa: UnidadTarifa
    capacidad_aforo_diario: int
    imagenes_urls: tuple[str, ...] = ()
    atributos: AtributosServicio = field(default_factory=AtributosServicio)

    @property
    def categoria(self) -> Categoria:
        return self.tipo.categoria

    def validar(self, origen_imagenes: str) -> None:
        if self.capacidad_aforo_diario < 1:
            raise DatoInvalido(campo="capacidad_aforo_diario", regla="minimo", minimo=1)
        self.atributos.validar_para(self.tipo)
        experiencia = self.atributos.experiencia
        if experiencia and (experiencia.grupo_maximo or 0) > self.capacidad_aforo_diario:
            raise DatoInvalido(
                campo="grupo_maximo", regla="mayor_que", otro="capacidad_aforo_diario"
            )
        if len(self.imagenes_urls) > MAX_IMAGENES:
            raise DatoInvalido(campo="imagenes_urls", regla="maximo", maximo=MAX_IMAGENES)
        for url in self.imagenes_urls:
            if not url.startswith(origen_imagenes):
                raise DatoInvalido(campo="imagenes_urls", regla="bucket_no_permitido", url=url)


@dataclass(kw_only=True)
class AtractivoServicio(Versionado):
    """Oferta turística georreferenciada de un prestador (ATRACTIVO_SERVICIO).

    No se borra: se desactiva, porque booking, review y la analítica la referencian. Una
    desactivación por suspensión del prestador se distingue de la que hace el propio
    prestador, para restaurar solo las primeras cuando iam lo vuelve a habilitar.
    """

    id: UUID
    prestador_id: UUID
    prestador_usuario_id: UUID
    datos: DatosServicio
    creado_en: datetime
    actualizado_en: datetime
    zona_id: UUID | None = None
    activo: bool = True
    desactivado_por_suspension: bool = False

    @classmethod
    def registrar(
        cls, perfil: PrestadorPerfil, datos: DatosServicio, origen_imagenes: str, ahora: datetime
    ) -> "AtractivoServicio":
        perfil.exigir_activo()
        datos.validar(origen_imagenes)
        return cls(
            id=uuid4(),
            prestador_id=perfil.id,
            prestador_usuario_id=perfil.usuario_id,
            datos=datos,
            creado_en=ahora,
            actualizado_en=ahora,
        )

    def exigir_dueno(self, perfil: PrestadorPerfil) -> None:
        """Un servicio ajeno se responde como inexistente, para no revelar que existe."""
        if perfil.id != self.prestador_id:
            raise NoEncontrado(recurso="servicio", id=str(self.id))

    def editar(
        self,
        perfil: PrestadorPerfil,
        version_esperada: int,
        datos: DatosServicio,
        origen_imagenes: str,
        ahora: datetime,
    ) -> None:
        self.exigir_dueno(perfil)
        perfil.exigir_activo()
        self._verificar_version(version_esperada)
        datos.validar(origen_imagenes)
        self.datos = datos
        self._registrar_cambio(ahora)

    def desactivar(self, perfil: PrestadorPerfil, version_esperada: int, ahora: datetime) -> bool:
        """Devuelve False si ya estaba inactivo (no hay nada que publicar)."""
        self.exigir_dueno(perfil)
        self._verificar_version(version_esperada)
        if not self.activo and not self.desactivado_por_suspension:
            return False
        # Si estaba apagado por una suspensión, la decisión del prestador gana: ya no se
        # restaurará cuando iam lo vuelva a habilitar.
        self.activo = False
        self.desactivado_por_suspension = False
        self._registrar_cambio(ahora)
        return True

    def reactivar(self, perfil: PrestadorPerfil, version_esperada: int, ahora: datetime) -> bool:
        """Devuelve False si ya estaba activo (no hay nada que publicar)."""
        self.exigir_dueno(perfil)
        perfil.exigir_activo()
        self._verificar_version(version_esperada)
        if self.activo:
            return False
        self.activo = True
        self.desactivado_por_suspension = False
        self._registrar_cambio(ahora)
        return True

    def desactivar_por_suspension(self, ahora: datetime) -> bool:
        if not self.activo:
            return False
        self.activo = False
        self.desactivado_por_suspension = True
        self._registrar_cambio(ahora)
        return True

    def restaurar_tras_suspension(self, ahora: datetime) -> bool:
        if not self.desactivado_por_suspension:
            return False
        self.activo = True
        self.desactivado_por_suspension = False
        self._registrar_cambio(ahora)
        return True

    def asignar_zona(self, zona_id: UUID | None) -> None:
        """La zona la calcula PostGIS; no cambia la versión porque no la edita el prestador."""
        self.zona_id = zona_id

    def _registrar_cambio(self, ahora: datetime) -> None:
        self._avanzar_version()
        self.actualizado_en = ahora
