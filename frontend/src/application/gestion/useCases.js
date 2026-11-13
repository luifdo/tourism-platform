import { GestionError, CODIGOS_GESTION as C } from '../../domain/gestion/errors.js'
import { evaluarPassword } from '../../domain/auth/rules.js'
import { nuevaClave as claveNueva, validarArchivoDocumento, validarImagen, validarMotivo, validarRango } from '../../domain/gestion/rules.js'
import { armarModeracion, armarReporte, armarResena, validarRespuesta } from '../../domain/gestion/resenas.js'
import { servicioAPayload, validarServicio } from '../../domain/gestion/servicio.js'
import { assertAccountGateway, assertAdminGateway, assertEntityGateway, assertOfferGateway, assertReviewGateway } from './ports.js'

/*
 * Casos de uso de las pantallas de gestión. Validan lo que se puede saber sin red (para no mandar peticiones que el
 * servicio va a rechazar) y delegan en el puerto. Cada fábrica recibe su gateway y un `nuevaClave` para las
 * Idempotency-Key (un reintento del mismo envío lleva la misma clave).
 */
const invalido = (campos) => new GestionError(C.VALIDACION, 'Revisa los datos.', { campos: Object.entries(campos).map(([campo, mensaje]) => ({ campo, mensaje })) })
const falla = (campo, codigo) => invalido({ [campo]: codigo })

/* ---- Perfil y documentos del prestador (UC4, UC37) ---- */
export function createAccountUseCases({ gateway }) {
  assertAccountGateway(gateway)
  return {
    perfil: () => gateway.perfil(),
    async editarPerfil({ nombre, idioma } = {}) {
      const cambios = {}
      if (nombre !== undefined) {
        const n = String(nombre).trim()
        if (n.length < 2 || n.length > 100) throw falla('nombre', 'NOMBRE_INVALIDO')
        cambios.nombre = n
      }
      if (idioma !== undefined) {
        if (!['es', 'en'].includes(idioma)) throw falla('idioma', 'IDIOMA_INVALIDO')
        cambios.idioma = idioma
      }
      if (!Object.keys(cambios).length) throw invalido({ nombre: 'SIN_CAMBIOS' })
      return gateway.editarPerfil(cambios)
    },
    async cambiarContrasena({ actual, nueva, confirmacion }) {
      if (!actual) throw falla('actual', 'REQUERIDO')
      if (!evaluarPassword(nueva).valida) throw falla('nueva', 'PASSWORD_INVALIDA')
      if (nueva !== confirmacion) throw falla('confirmacion', 'NO_COINCIDEN')
      if (nueva === actual) throw falla('nueva', 'IGUAL_A_LA_ACTUAL')
      return gateway.cambiarContrasena({ actual, nueva })
    },
    async suprimirDatos(password) {
      if (!password) throw falla('password', 'REQUERIDO')
      return gateway.suprimirDatos(password)
    },
    misDocumentos: () => gateway.misDocumentos(),
    async subirDocumento({ tipo, archivo, razonSocial }) {
      if (tipo !== 'RNT' && tipo !== 'RUT') throw falla('tipo', 'TIPO_INVALIDO')
      const e = validarArchivoDocumento(archivo)
      if (e) throw falla('archivo', e)
      const rs = String(razonSocial ?? '').trim()
      if (tipo === 'RUT' && (rs.length < 2 || rs.length > 200)) throw falla('razon_social', 'RAZON_SOCIAL_INVALIDA')
      return gateway.subirDocumento({ tipo, archivo, razonSocial: tipo === 'RUT' ? rs : undefined })
    },
  }
}

/* ---- Administración (UC27, UC28, UC33) ---- */
export function createAdminUseCases({ gateway }) {
  assertAdminGateway(gateway)
  return {
    usuarios: (filtros = {}) => gateway.usuarios({ pagina: 1, tamano: 20, ...filtros, q: filtros.q ? String(filtros.q).trim().slice(0, 100) : undefined }),
    async cambiarRol(id, { rol, motivo }) {
      if (!['Turista', 'Prestador', 'Entidad', 'Admin'].includes(rol)) throw falla('rol', 'ROL_INVALIDO')
      if (String(motivo ?? '').length > 2000) throw falla('motivo', 'MOTIVO_LARGO')
      return gateway.cambiarRol(id, { rol, ...(motivo ? { motivo: String(motivo).trim() } : {}) })
    },
    async cambiarEstado(id, { activo, motivo }) {
      if (typeof activo !== 'boolean') throw falla('activo', 'REQUERIDO')
      if (String(motivo ?? '').length > 2000) throw falla('motivo', 'MOTIVO_LARGO')
      return gateway.cambiarEstado(id, { activo, ...(motivo ? { motivo: String(motivo).trim() } : {}) })
    },
    async bitacora(filtros = {}) {
      if (filtros.desde && filtros.hasta && Date.parse(filtros.desde) >= Date.parse(filtros.hasta)) throw falla('desde', 'RANGO_INVERTIDO')
      return gateway.bitacora({ pagina: 1, tamano: 20, ...filtros })
    },
    prestadores: (filtros = {}) => gateway.prestadores({ pagina: 1, tamano: 20, ...filtros }),
    documentosDePrestador: (id) => gateway.documentosDePrestador(id),
    urlDocumento: (documentoId) => gateway.urlDocumento(documentoId),
    aprobarPrestador: (id) => gateway.aprobarPrestador(id),
    async rechazarPrestador(id, documentos) {
      if (!documentos?.length) throw falla('documentos', 'REQUERIDO')
      const errores = {}
      for (const d of documentos) {
        const e = validarMotivo(d.motivo, { min: 1, max: 500 })
        if (e) errores[`motivo_${d.tipo}`] = e
      }
      if (Object.keys(errores).length) throw invalido(errores)
      return gateway.rechazarPrestador(id, documentos.map((d) => ({ tipo: d.tipo, motivo: d.motivo.trim() })))
    },
  }
}

/* ---- Reseñas (UC15, UC21, UC29, UC39) ---- */
export function createReviewUseCases({ gateway, nuevaClave = claveNueva }) {
  assertReviewGateway(gateway)
  const armar = (datos) => { const r = armarResena(datos); if (!r.ok) throw invalido(r.errores); return r.cuerpo }
  return {
    resumen: (servicioId) => gateway.resumen(servicioId),
    resenasDeServicio: (servicioId, op = {}) => gateway.resenasDeServicio(servicioId, { orden: 'recientes', pagina: 1, tamano: 10, ...op }),
    // La clave de idempotencia la fija quien llama (una por envío del formulario), para que un reintento no duplique
    escribir: async (servicioId, datos, clave = nuevaClave()) => gateway.escribir({ servicio_id: servicioId, ...armar(datos) }, clave),
    editar: async (id, datos, version) => gateway.editar(id, armar(datos), version),
    async responder(id, texto, version) {
      const r = validarRespuesta(texto)
      if (!r.ok) throw falla('texto', r.error)
      return gateway.responder(id, r.texto, version)
    },
    async reportar(id, datos) {
      const r = armarReporte(datos)
      if (!r.ok) throw falla('motivo', r.error)
      return gateway.reportar(id, r.cuerpo)
    },
    async moderar(id, datos, version) {
      const r = armarModeracion(datos)
      if (!r.ok) throw falla('motivo', r.error)
      return gateway.moderar(id, r.cuerpo, version)
    },
    misResenas: (op = {}) => gateway.misResenas({ pagina: 1, tamano: 20, ...op }),
    pendientes: () => gateway.pendientes(),
    resenasPrestador: (op = {}) => gateway.resenasPrestador({ pagina: 1, tamano: 20, ...op }),
    colaModeracion: (op = {}) => gateway.colaModeracion({ pagina: 1, tamano: 20, ...op }),
  }
}

/* ---- Oferta del prestador (UC17, UC18, UC22) ---- */
export function createOfferUseCases({ gateway, nuevaClave = claveNueva }) {
  assertOfferGateway(gateway)
  const preparar = (form, atributosPrevios) => {
    const e = validarServicio(form)
    if (Object.keys(e).length) throw invalido(e)
    return servicioAPayload(form, atributosPrevios)
  }
  return {
    perfilComercial: () => gateway.perfilComercial(),
    async editarPerfilComercial({ telefono, direccion, politica }, version, clave = nuevaClave()) {
      const cuerpo = {}
      if (String(telefono ?? '').trim()) cuerpo.telefono = String(telefono).trim().slice(0, 30)
      if (String(direccion ?? '').trim()) cuerpo.direccion = String(direccion).trim().slice(0, 200)
      const es = String(politica?.es ?? '').trim()
      const en = String(politica?.en ?? '').trim()
      if (es) cuerpo.politica_cancelacion = { es, ...(en ? { en } : {}) }
      return gateway.editarPerfilComercial(cuerpo, version, clave)
    },
    servicios: (op = {}) => gateway.servicios({ pagina: 1, tamano: 50, ...op }),
    /** `clave`: una por intento de envío; el reintento tras un corte de red usa la misma. */
    crearServicio: async (form, clave = nuevaClave()) => gateway.crearServicio(preparar(form), clave),
    editarServicio: async (id, form, version, atributosPrevios, clave = nuevaClave()) => gateway.editarServicio(id, preparar(form, atributosPrevios), version, clave),
    desactivarServicio: (id, version) => gateway.desactivarServicio(id, version),
    reactivarServicio: (id, version) => gateway.reactivarServicio(id, version),
    async subirImagen(archivo) {
      const e = validarImagen(archivo)
      if (e) throw falla('imagen', e)
      return gateway.subirImagen(archivo)
    },
    async metricas({ desde, hasta }) {
      const e = validarRango(desde, hasta, { maxDias: 366 })
      if (e) throw falla('desde', e)
      return gateway.metricas({ desde, hasta })
    },
    async geocodificar(direccion) {
      const d = String(direccion ?? '').trim()
      if (d.length < 5 || d.length > 200) throw falla('direccion', 'DIRECCION_INVALIDA')
      return gateway.geocodificar(d)
    },
    zonas: (idioma) => gateway.zonas(idioma),
  }
}

/* ---- Entidad (UC23–UC26, UC38) ---- */
export function createEntityUseCases({ gateway }) {
  assertEntityGateway(gateway)
  const rango = (desde, hasta, maxDias = 366) => { const e = validarRango(desde, hasta, { maxDias }); if (e) throw falla('desde', e) }
  return {
    alertas: (op = {}) => gateway.alertas({ pagina: 1, tamano: 50, ...op }),
    async crearAlerta({ nivel, mensaje, servicioId, zona, fechaExpiracion }) {
      const errores = {}
      if (!['INFORMATIVA', 'PREVENTIVA', 'CRITICA'].includes(nivel)) errores.nivel = 'REQUERIDO'
      if (!String(mensaje?.es ?? '').trim()) errores.mensaje = 'REQUERIDO'
      if (!servicioId && !zona) errores.destino = 'DESTINO_REQUERIDO'
      if (servicioId && zona) errores.destino = 'DESTINO_UNICO'
      if (!fechaExpiracion || Number.isNaN(Date.parse(fechaExpiracion))) errores.fecha_expiracion = 'FECHA_INVALIDA'
      if (Object.keys(errores).length) throw invalido(errores)
      const en = String(mensaje.en ?? '').trim()
      return gateway.crearAlerta({
        nivel, mensaje: { es: mensaje.es.trim(), ...(en ? { en } : {}) }, ...(servicioId ? { servicio_id: servicioId } : { zona }), fecha_expiracion: new Date(fechaExpiracion).toISOString(),
      })
    },
    async editarAlerta(id, { nivel, mensaje, fechaExpiracion }, version) {
      const errores = {}
      if (!['INFORMATIVA', 'PREVENTIVA', 'CRITICA'].includes(nivel)) errores.nivel = 'REQUERIDO'
      if (!String(mensaje?.es ?? '').trim()) errores.mensaje = 'REQUERIDO'
      if (!fechaExpiracion || Number.isNaN(Date.parse(fechaExpiracion))) errores.fecha_expiracion = 'FECHA_INVALIDA'
      if (Object.keys(errores).length) throw invalido(errores)
      const en = String(mensaje.en ?? '').trim()
      return gateway.editarAlerta(id, { nivel, mensaje: { es: mensaje.es.trim(), ...(en ? { en } : {}) }, fecha_expiracion: new Date(fechaExpiracion).toISOString() }, version)
    },
    retirarAlerta: (id) => gateway.retirarAlerta(id),
    zonas: (idioma) => gateway.zonas(idioma),
    async demanda({ desde, hasta, ...resto }) { rango(desde, hasta); return gateway.demanda({ desde, hasta, agrupacion: 'dia', ...resto }) },
    capacidad: (op = {}) => gateway.capacidad(op),
    mapaCalor: (op = {}) => gateway.mapaCalor({ zoom: 10, ...op }),
    async intenciones({ desde, hasta, ...resto }) { rango(desde, hasta); return gateway.intenciones({ desde, hasta, ...resto }) },
    async tablero({ desde, hasta, ...resto }) { rango(desde, hasta); return gateway.tablero({ desde, hasta, ...resto }) },
    async reporteCsv({ desde, hasta, zona }) { rango(desde, hasta, 366); return gateway.reporteCsv({ desde, hasta, zona }) },
  }
}

