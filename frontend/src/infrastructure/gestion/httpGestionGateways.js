import { createApiClient } from '../http/apiClient.js'
import { GestionError } from '../../domain/gestion/errors.js'

/*
 * Adaptadores HTTP de los puertos de gestión (application/gestion/ports.js). Hablan con iam, catalog y review a
 * través del Gateway; todas sus rutas exigen sesión salvo las públicas de reseñas (`fetchFn` es el fetch autenticado).
 */

/** UC4 perfil y UC37 documentos · iam-service */
export function createHttpAccountGateway({ baseUrl = '/api/iam', fetchFn } = {}) {
  const { request } = createApiClient({ baseUrl, fetchFn })
  const d = (p) => p.then((r) => r.data)
  return {
    perfil: () => d(request('GET', '/perfil')),
    editarPerfil: (cambios) => d(request('PATCH', '/perfil', { body: cambios })),
    cambiarContrasena: ({ actual, nueva }) => d(request('POST', '/perfil/contrasena', { body: { password_actual: actual, password_nueva: nueva } })),
    suprimirDatos: (password) => d(request('DELETE', '/perfil', { body: { password } })),
    misDocumentos: () => d(request('GET', '/prestador/documentos')),
    subirDocumento({ tipo, archivo, razonSocial }) {
      const form = new FormData()
      form.append('tipo', tipo)
      form.append('archivo', archivo)
      if (razonSocial) form.append('razon_social', razonSocial)
      return d(request('POST', '/prestador/documentos', { form }))
    },
  }
}

/** UC27, UC28, UC33 · iam-service (rol Admin) */
export function createHttpAdminGateway({ baseUrl = '/api/iam', fetchFn } = {}) {
  const { request } = createApiClient({ baseUrl, fetchFn })
  const d = (p) => p.then((r) => r.data)
  return {
    usuarios: (query) => d(request('GET', '/admin/usuarios', { query })),
    cambiarRol: (id, body) => d(request('PATCH', `/admin/usuarios/${id}/rol`, { body })),
    cambiarEstado: (id, body) => d(request('PATCH', `/admin/usuarios/${id}/estado`, { body })),
    bitacora: (query) => d(request('GET', '/admin/bitacora', { query })),
    prestadores: (query) => d(request('GET', '/admin/prestadores', { query })),
    documentosDePrestador: (id) => d(request('GET', `/admin/prestadores/${id}/documentos`)),
    urlDocumento: (documentoId) => d(request('GET', `/admin/documentos/${documentoId}/url`)),
    aprobarPrestador: (id) => d(request('POST', `/admin/prestadores/${id}/aprobar`)),
    rechazarPrestador: (id, documentos) => d(request('POST', `/admin/prestadores/${id}/rechazar`, { body: { documentos } })),
  }
}

/** UC15, UC21, UC29, UC39 · review-service. Las lecturas de un servicio son públicas pero el fetch autenticado también sirve. */
export function createHttpReviewGateway({ baseUrl = '/api/reviews', fetchFn } = {}) {
  const { request } = createApiClient({ baseUrl, fetchFn })
  const d = (p) => p.then((r) => r.data)
  const conVersion = (p) => p.then((r) => r.data)
  return {
    resumen: (servicioId) => d(request('GET', `/servicios/${servicioId}/resumen`)),
    resenasDeServicio: (servicioId, { idioma, ...query }) => d(request('GET', `/servicios/${servicioId}/resenas`, { query, idioma })),
    escribir: (cuerpo, clave) => d(request('POST', '/resenas', { body: cuerpo, headers: { 'Idempotency-Key': clave } })),
    editar: (id, cuerpo, version) => conVersion(request('PUT', `/resenas/${id}`, { body: cuerpo, version })),
    responder: (id, texto, version) => conVersion(request('PUT', `/resenas/${id}/respuesta`, { body: { texto }, version })),
    reportar: (id, cuerpo) => d(request('POST', `/resenas/${id}/reportes`, { body: cuerpo })),
    moderar: (id, cuerpo, version) => conVersion(request('POST', `/resenas/${id}/moderacion`, { body: cuerpo, version })),
    misResenas: ({ idioma, ...query }) => d(request('GET', '/turista/resenas', { query, idioma })),
    pendientes: () => d(request('GET', '/turista/pendientes')),
    resenasPrestador: ({ idioma, ...query }) => d(request('GET', '/prestador/resenas', { query, idioma })),
    colaModeracion: ({ idioma, ...query }) => d(request('GET', '/moderacion/resenas', { query, idioma })),
  }
}

/** UC17, UC18, UC22 · catalog-service (rol Prestador) */
export function createHttpOfferGateway({ baseUrl = '/api/catalog', fetchFn, subirFn = (...a) => fetch(...a) } = {}) {
  const { request } = createApiClient({ baseUrl, fetchFn })
  const d = (p) => p.then((r) => r.data)
  const idem = (clave) => ({ 'Idempotency-Key': clave })
  return {
    perfilComercial: () => request('GET', '/prestador/perfil').then((r) => r.data),
    editarPerfilComercial: (cuerpo, version, clave) => d(request('PUT', '/prestador/perfil', { body: cuerpo, version, headers: idem(clave) })),
    servicios: (query) => d(request('GET', '/prestador/servicios', { query })),
    crearServicio: (cuerpo, clave) => d(request('POST', '/servicios', { body: cuerpo, headers: idem(clave) })),
    editarServicio: (id, cuerpo, version, clave) => d(request('PUT', `/servicios/${id}`, { body: cuerpo, version, headers: idem(clave) })),
    desactivarServicio: (id, version) => d(request('POST', `/servicios/${id}/desactivar`, { version })),
    reactivarServicio: (id, version) => d(request('POST', `/servicios/${id}/reactivar`, { version })),
    /** Pide una URL firmada y sube el archivo directo al almacenamiento (la firma ya lleva tipo y tamaño exactos). */
    async subirImagen(archivo) {
      const { data } = await request('POST', '/prestador/imagenes', { body: { content_type: archivo.type, tamano_bytes: archivo.size } })
      let res
      try { res = await subirFn(data.subida_url, { method: 'PUT', headers: { 'Content-Type': archivo.type }, body: archivo }) }
      catch { throw new GestionError('SIN_CONEXION', 'No se pudo subir la imagen.') }
      if (!res.ok) throw new GestionError('SUBIDA_RECHAZADA', 'El almacenamiento rechazó la imagen.', { status: res.status })
      return data.url_publica
    },
    metricas: (query) => d(request('GET', '/prestador/metricas', { query })),
    geocodificar: (direccion) => d(request('GET', '/geocodificar', { query: { direccion } })),
    zonas: (idioma) => d(request('GET', '/zonas', { idioma })),
  }
}

/** UC23–UC26 y UC38 · catalog-service (roles Entidad y Admin) */
export function createHttpEntityGateway({ baseUrl = '/api/catalog', fetchFn } = {}) {
  const { request } = createApiClient({ baseUrl, fetchFn })
  const d = (p) => p.then((r) => r.data)
  return {
    alertas: ({ idioma, ...query }) => d(request('GET', '/entidad/alertas', { query, idioma })),
    crearAlerta: (cuerpo) => d(request('POST', '/alertas', { body: cuerpo })),
    editarAlerta: (id, cuerpo, version) => d(request('PUT', `/alertas/${id}`, { body: cuerpo, version })),
    retirarAlerta: (id) => d(request('POST', `/alertas/${id}/desactivar`)),
    zonas: (idioma) => d(request('GET', '/zonas', { idioma })),
    demanda: (query) => d(request('GET', '/analitica/demanda', { query })),
    capacidad: ({ idioma, ...query }) => d(request('GET', '/analitica/capacidad', { query, idioma })),
    mapaCalor: ({ idioma, ...query }) => d(request('GET', '/analitica/mapa-calor', { query, idioma })),
    intenciones: (query) => d(request('GET', '/analitica/intenciones-visita', { query })),
    tablero: ({ idioma, ...query }) => d(request('GET', '/analitica/tablero', { query, idioma })),
    async reporteCsv({ desde, hasta, zona }) {
      const { data } = await request('GET', '/analitica/reportes/demanda', { query: { desde, hasta, zona, formato: 'csv' }, as: 'text', aceptar: 'text/csv' })
      return { texto: data, nombre: `demanda_${desde}_${hasta}${zona ? `_${zona}` : ''}.csv` }
    },
  }
}
