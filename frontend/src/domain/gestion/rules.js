/** Reglas comunes de las pantallas de gestión. Sin dependencias: funciones puras. */

export const MAX_DOCUMENTO_BYTES = 5 * 1024 * 1024 // contrato IAM: el archivo no supera 5 MB
export const TIPOS_DOCUMENTO_ARCHIVO = Object.freeze(['application/pdf', 'image/jpeg', 'image/png'])
export const MAX_IMAGEN_BYTES = 5 * 1024 * 1024 // contrato catalog: 1..5242880
export const TIPOS_IMAGEN = Object.freeze(['image/jpeg', 'image/png', 'image/webp'])
export const MAX_IMAGENES = 10

/** @returns {string|null} código de error o null si el archivo sirve como documento (RNT/RUT). */
export function validarArchivoDocumento(archivo) {
  if (!archivo) return 'ARCHIVO_REQUERIDO'
  if (!TIPOS_DOCUMENTO_ARCHIVO.includes(archivo.type)) return 'TIPO_ARCHIVO_NO_PERMITIDO'
  if (!(archivo.size > 0)) return 'ARCHIVO_REQUERIDO'
  if (archivo.size > MAX_DOCUMENTO_BYTES) return 'ARCHIVO_DEMASIADO_GRANDE'
  return null
}

/** @returns {string|null} código de error o null si la imagen sirve para la oferta. */
export function validarImagen(archivo) {
  if (!archivo) return 'ARCHIVO_REQUERIDO'
  if (!TIPOS_IMAGEN.includes(archivo.type)) return 'TIPO_IMAGEN_NO_PERMITIDO'
  if (!(archivo.size > 0)) return 'ARCHIVO_REQUERIDO'
  if (archivo.size > MAX_IMAGEN_BYTES) return 'IMAGEN_DEMASIADO_GRANDE'
  return null
}

/** Motivo de una decisión (rechazo, ocultar...): obligatorio entre `min` y `max` caracteres una vez recortado. */
export function validarMotivo(texto, { min = 1, max = 500 } = {}) {
  const t = String(texto ?? '').trim()
  if (t.length < min) return 'MOTIVO_REQUERIDO'
  if (t.length > max) return 'MOTIVO_LARGO'
  return null
}

const ISO_FECHA = /^\d{4}-\d{2}-\d{2}$/
export const esFechaIso = (s) => ISO_FECHA.test(String(s ?? '')) && !Number.isNaN(Date.parse(`${s}T00:00:00Z`))

/** Rango de fechas (YYYY-MM-DD) con `desde <= hasta` y, si se pide, no más largo que `maxDias`. */
export function validarRango(desde, hasta, { maxDias = 366 } = {}) {
  if (!esFechaIso(desde) || !esFechaIso(hasta)) return 'FECHA_INVALIDA'
  const dias = (Date.parse(`${hasta}T00:00:00Z`) - Date.parse(`${desde}T00:00:00Z`)) / 86_400_000
  if (dias < 0) return 'RANGO_INVERTIDO'
  if (dias + 1 > maxDias) return 'RANGO_LARGO'
  return null
}

/** YYYY-MM-DD de una fecha, en hora local (los rangos de los tableros son días calendario del usuario). */
export const aFechaIso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/** Últimos `dias` días hasta hoy, ambos incluidos. */
export function ultimosDias(hoy, dias) {
  const desde = new Date(hoy)
  desde.setDate(desde.getDate() - (dias - 1))
  return { desde: aFechaIso(desde), hasta: aFechaIso(hoy) }
}

/** Parte una lista en páginas (los mocks paginan en memoria). */
export const paginar = (lista, pagina = 1, tamano = 20) => ({ items: lista.slice((pagina - 1) * tamano, pagina * tamano), pagina, tamano, total: lista.length })
