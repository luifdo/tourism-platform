/** Categorías del catálogo (contrato: esquema `Categoria`). Son códigos estables; la interfaz los traduce. */
export const CATEGORIAS = Object.freeze(['PLAYA', 'NATURALEZA', 'CULTURA', 'GASTRONOMIA', 'AVENTURA', 'ALOJAMIENTO', 'TRANSPORTE'])

export const TAMANO_PAGINA = 12
export const MAX_TEXTO = 200 // contrato: `texto` hasta 200 caracteres
export const MAX_IDS_NOMBRES = 100 // contrato: /servicios/nombres admite de 1 a 100 ids por llamada

/** Umbrales de saturación de DESIGN.md: < 60 % seguro, 60–85 % moderado, > 85 % saturado. */
export const nivelOcupacion = (pct) => (pct < 60 ? 'ok' : pct <= 85 ? 'mid' : 'high')

/** Deja la búsqueda como la acepta el servicio: texto recortado, categorías válidas y sin repetir, página ≥ 1. */
export function normalizarBusqueda({ texto = '', categorias = [], pagina = 1, tamano = TAMANO_PAGINA } = {}) {
  return {
    texto: String(texto ?? '').trim().slice(0, MAX_TEXTO),
    categorias: [...new Set(categorias)].filter((c) => CATEGORIAS.includes(c)),
    pagina: Math.max(1, Math.floor(Number(pagina)) || 1),
    tamano: Math.min(100, Math.max(1, Math.floor(Number(tamano)) || TAMANO_PAGINA)),
  }
}

/** Parte una lista en tandas de a `n` (el servicio de nombres admite hasta 100 ids por llamada). */
export function trocear(lista, n) {
  const tandas = []
  for (let i = 0; i < lista.length; i += n) tandas.push(lista.slice(i, i + n))
  return tandas
}
