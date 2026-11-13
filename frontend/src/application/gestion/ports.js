/*
 * PUERTOS de las pantallas de gestión. Los nombres siguen los contratos de contracts/openapi/ (iam, catalog, review).
 * Los errores se lanzan como GestionError (domain/gestion/errors.js). Las formas de datos son las del contrato.
 *
 * AccountGateway  (iam-service: perfil UC4 y documentos del prestador UC37)
 *   perfil() -> { id, email, nombre, rol, idioma, razon_social, creado_en }
 *   editarPerfil({ nombre?, idioma? }) -> Perfil
 *   cambiarContrasena({ actual, nueva }) -> void      (revoca todas las sesiones)
 *   suprimirDatos(password) -> void                   (irreversible; Ley 1581)
 *   misDocumentos() -> { usuario_id, razon_social, estado: incompleto|pendiente|rechazado|aprobado, documentos: Documento[] }
 *   subirDocumento({ tipo: 'RNT'|'RUT', archivo: File, razonSocial? }) -> Documento
 *
 * AdminGateway  (iam-service: UC27 usuarios, UC28 prestadores, UC33 bitácora)
 *   usuarios({ rol, activo, q, pagina, tamano }) -> Pagina<Usuario>
 *   cambiarRol(id, { rol, motivo? }) / cambiarEstado(id, { activo, motivo? }) -> Usuario
 *   bitacora({ usuario_id, accion, resultado, servicio_origen, desde, hasta, pagina, tamano }) -> Pagina<Evento>
 *   prestadores({ estado, pagina, tamano }) -> Pagina<PrestadorRevision>
 *   documentosDePrestador(id) -> { usuario_id, razon_social, estado, documentos }
 *   urlDocumento(documentoId) -> { url, expira_en }
 *   aprobarPrestador(id) -> Revision        rechazarPrestador(id, [{ tipo, motivo }]) -> Revision
 *
 * ReviewGateway  (review-service: UC15, UC21, UC29, UC39)
 *   resumen(servicioId) / resenasDeServicio(servicioId, { orden, pagina, tamano, idioma })
 *   escribir(cuerpo, idempotencyKey) -> Resena      editar(id, cuerpo, version) -> Resena
 *   responder(id, texto, version) -> Resena         reportar(id, cuerpo) -> void
 *   moderar(id, cuerpo, version) -> Resena          misResenas({ pagina, tamano, idioma }) / pendientes()
 *   resenasPrestador({ servicio_id, sin_respuesta, pagina, tamano, idioma }) / colaModeracion({ estado, pagina, tamano, idioma })
 *
 * OfferGateway  (catalog-service, rol Prestador: UC17, UC18, UC22)
 *   perfilComercial() -> Perfil{ version }   editarPerfilComercial(cuerpo, version, idempotencyKey)
 *   servicios({ pagina, tamano }) -> Pagina<ServicioEditable>
 *   crearServicio(cuerpo, idempotencyKey) -> ServicioEditable   editarServicio(id, cuerpo, version, idempotencyKey)
 *   desactivarServicio(id, version) / reactivarServicio(id, version) -> ServicioEditable
 *   subirImagen(archivo) -> url pública      (pide URL firmada y sube directo al almacenamiento)
 *   metricas({ desde, hasta }) -> { desde, hasta, servicios: Metrica[] }
 *   geocodificar(direccion) -> [{ lat, lon, etiqueta }]   zonas(idioma) -> Zona[]
 *
 * EntityGateway  (catalog-service, roles Entidad y Admin: UC23–UC26, UC38)
 *   alertas({ estado, pagina, tamano, idioma }) -> Pagina<Alerta>   crearAlerta(cuerpo) / editarAlerta(id, cuerpo, version) / retirarAlerta(id)
 *   zonas(idioma) -> Zona[]
 *   demanda({ desde, hasta, zona, categoria, agrupacion }) / capacidad({ zona, fecha, idioma }) / mapaCalor({ fecha, zoom, idioma })
 *   intenciones({ desde, hasta, zona }) / tablero({ desde, hasta, idioma })
 *   reporteCsv({ desde, hasta, zona }) -> { texto, nombre }
 */
export const ACCOUNT_METHODS = Object.freeze(['perfil', 'editarPerfil', 'cambiarContrasena', 'suprimirDatos', 'misDocumentos', 'subirDocumento'])
export const ADMIN_METHODS = Object.freeze(['usuarios', 'cambiarRol', 'cambiarEstado', 'bitacora', 'prestadores', 'documentosDePrestador', 'urlDocumento', 'aprobarPrestador', 'rechazarPrestador'])
export const REVIEW_METHODS = Object.freeze(['resumen', 'resenasDeServicio', 'escribir', 'editar', 'responder', 'reportar', 'moderar', 'misResenas', 'pendientes', 'resenasPrestador', 'colaModeracion'])
export const OFFER_METHODS = Object.freeze(['perfilComercial', 'editarPerfilComercial', 'servicios', 'crearServicio', 'editarServicio', 'desactivarServicio', 'reactivarServicio', 'subirImagen', 'metricas', 'geocodificar', 'zonas'])
export const ENTITY_METHODS = Object.freeze(['alertas', 'crearAlerta', 'editarAlerta', 'retirarAlerta', 'zonas', 'demanda', 'capacidad', 'mapaCalor', 'intenciones', 'tablero', 'reporteCsv'])

const verificar = (nombre, metodos) => (gateway) => {
  const faltan = metodos.filter((m) => typeof gateway?.[m] !== 'function')
  if (faltan.length) throw new TypeError(`El adaptador no implementa el puerto ${nombre}: faltan ${faltan.join(', ')}`)
  return gateway
}
export const assertAccountGateway = verificar('AccountGateway', ACCOUNT_METHODS)
export const assertAdminGateway = verificar('AdminGateway', ADMIN_METHODS)
export const assertReviewGateway = verificar('ReviewGateway', REVIEW_METHODS)
export const assertOfferGateway = verificar('OfferGateway', OFFER_METHODS)
export const assertEntityGateway = verificar('EntityGateway', ENTITY_METHODS)
