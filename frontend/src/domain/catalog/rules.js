/** Categorías del catálogo (contrato: esquema `Categoria`). Son códigos estables; la interfaz los traduce. */
export const CATEGORIAS = Object.freeze(['PLAYA', 'NATURALEZA', 'CULTURA', 'GASTRONOMIA', 'AVENTURA', 'ALOJAMIENTO', 'TRANSPORTE'])

export const TAMANO_PAGINA = 12
export const MAX_TEXTO = 200 // contrato: `texto` hasta 200 caracteres
export const MAX_IDS_NOMBRES = 100 // contrato: /servicios/nombres admite de 1 a 100 ids por llamada

/** Umbrales de saturación de DESIGN.md: < 60 % seguro, 60–85 % moderado, > 85 % saturado. */
export const nivelOcupacion = (pct) => (pct < 60 ? 'ok' : pct <= 85 ? 'mid' : 'high')

export const ORDENES = Object.freeze(['relevancia', 'precio', 'calificacion'])
const ISO = /^\d{4}-\d{2}-\d{2}$/
const aNumero = (v) => { if (v === '' || v == null) return null; const n = Number(v); return Number.isFinite(n) && n >= 0 ? n : null }

/**
 * Deja la búsqueda como la acepta el servicio: texto recortado, categorías válidas y sin repetir, página ≥ 1, y los filtros
 * opcionales (zona, rango de precio, fecha, personas, orden) solo si traen algo válido. Un precio mínimo mayor que el máximo se
 * intercambia (el servicio respondería 400). Sin filtro, el campo queda `null`.
 */
export function normalizarBusqueda({ texto = '', categorias = [], pagina = 1, tamano = TAMANO_PAGINA, zona, precioMin, precioMax, fecha, personas, orden } = {}) {
  let min = aNumero(precioMin)
  let max = aNumero(precioMax)
  if (min != null && max != null && min > max) [min, max] = [max, min]
  const p = Math.floor(Number(personas))
  return {
    texto: String(texto ?? '').trim().slice(0, MAX_TEXTO),
    categorias: [...new Set(categorias)].filter((c) => CATEGORIAS.includes(c)),
    pagina: Math.max(1, Math.floor(Number(pagina)) || 1),
    tamano: Math.min(100, Math.max(1, Math.floor(Number(tamano)) || TAMANO_PAGINA)),
    zona: typeof zona === 'string' && zona.trim() ? zona.trim() : null,
    precioMin: min, precioMax: max,
    fecha: typeof fecha === 'string' && ISO.test(fecha) ? fecha : null,
    // contrato: `personas` distinto de 1 exige `fecha` (si no, 400): sin fecha no se manda
    personas: Number.isFinite(p) && p >= 1 && typeof fecha === 'string' && ISO.test(fecha) ? p : null,
    orden: ORDENES.includes(orden) && orden !== 'relevancia' ? orden : null,
  }
}

/** ¿La búsqueda trae algo más que la página? La portada (sin filtros) es la única que se guarda para verla sin conexión. */
export const hayFiltros = (f) => !!(f.texto || f.categorias.length || f.zona || f.precioMin != null || f.precioMax != null || f.fecha || f.personas || f.orden)

/** Parte una lista en tandas de a `n` (el servicio de nombres admite hasta 100 ids por llamada). */
export function trocear(lista, n) {
  const tandas = []
  for (let i = 0; i < lista.length; i += n) tandas.push(lista.slice(i, i + n))
  return tandas
}
