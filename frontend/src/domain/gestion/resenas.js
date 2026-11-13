/** Reseñas (UC15, UC21, UC29, UC39). Códigos fijos del contrato review.yaml. */
export const ASPECTOS = Object.freeze(['LIMPIEZA', 'ATENCION', 'CALIDAD_PRECIO', 'SEGURIDAD', 'GUIANZA'])
export const MOTIVOS_REPORTE = Object.freeze(['OFENSIVO', 'SPAM', 'FALSO', 'DATOS_PERSONALES', 'OTRO'])
export const MAX_COMENTARIO = 2000
export const MAX_RESPUESTA = 1000
export const MAX_DETALLE_REPORTE = 500
export const MAX_MOTIVO_MODERACION = 500

const puntuacionValida = (n) => Number.isInteger(n) && n >= 1 && n <= 5

/**
 * Deja el cuerpo de la reseña como lo acepta review-service: puntuación 1..5 entera, solo los aspectos que el
 * turista calificó, comentario recortado (y ausente si queda vacío).
 * @returns {{ ok: true, cuerpo: object } | { ok: false, errores: Record<string,string> }}
 */
export function armarResena({ puntuacion, aspectos = {}, comentario = '' } = {}) {
  const errores = {}
  const p = Number(puntuacion)
  if (!puntuacionValida(p)) errores.puntuacion = 'PUNTUACION_INVALIDA'
  const asp = {}
  for (const a of ASPECTOS) {
    const v = aspectos?.[a]
    if (v == null || v === '' || v === 0) continue
    if (!puntuacionValida(Number(v))) errores.aspectos = 'PUNTUACION_INVALIDA'
    else asp[a] = Number(v)
  }
  const c = String(comentario ?? '').trim()
  if (c.length > MAX_COMENTARIO) errores.comentario = 'COMENTARIO_LARGO'
  if (Object.keys(errores).length) return { ok: false, errores }
  return { ok: true, cuerpo: { puntuacion: p, ...(Object.keys(asp).length ? { aspectos: asp } : {}), ...(c ? { comentario: c } : {}) } }
}

/** Texto de la respuesta del prestador: 1..1000 caracteres recortado. */
export function validarRespuesta(texto) {
  const t = String(texto ?? '').trim()
  if (!t) return { ok: false, error: 'RESPUESTA_REQUERIDA' }
  if (t.length > MAX_RESPUESTA) return { ok: false, error: 'RESPUESTA_LARGA' }
  return { ok: true, texto: t }
}

/** Reporte de una reseña: motivo del catálogo fijo y detalle opcional de hasta 500 caracteres. */
export function armarReporte({ motivo, detalle = '' } = {}) {
  if (!MOTIVOS_REPORTE.includes(motivo)) return { ok: false, error: 'MOTIVO_INVALIDO' }
  const d = String(detalle ?? '').trim()
  if (d.length > MAX_DETALLE_REPORTE) return { ok: false, error: 'DETALLE_LARGO' }
  return { ok: true, cuerpo: { motivo, ...(d ? { detalle: d } : {}) } }
}

/** Decisión del Admin sobre una reseña reportada: OCULTAR exige motivo (1..500). */
export function armarModeracion({ decision, motivo = '' } = {}) {
  if (decision !== 'PUBLICAR' && decision !== 'OCULTAR') return { ok: false, error: 'DECISION_INVALIDA' }
  const m = String(motivo ?? '').trim()
  if (decision === 'OCULTAR' && !m) return { ok: false, error: 'MOTIVO_REQUERIDO' }
  if (m.length > MAX_MOTIVO_MODERACION) return { ok: false, error: 'MOTIVO_LARGO' }
  return { ok: true, cuerpo: { decision, ...(m ? { motivo: m } : {}) } }
}
