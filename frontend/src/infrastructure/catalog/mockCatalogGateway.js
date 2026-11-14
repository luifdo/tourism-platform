import { CatalogError, CODIGOS } from '../../domain/catalog/errors.js'
import { ATRIBUTOS_DEMO, CATEGORIAS_DEMO, DEMO_SERVICIOS, REGLA_CANCELACION } from './demoCatalogo.js'

const normalizar = (s) => String(s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
const lang = (idioma) => (idioma === 'en' ? 'en' : 'es')
const UNIDAD = { es: 'por persona', en: 'per person' }

/** Servicio de la aplicación a partir de uno de demostración, en el idioma pedido. */
function aServicio(s, idioma) {
  const l = lang(idioma)
  return {
    id: s.id, nombre: s[l].nombre, tipo: s.tipo, tipoEtiqueta: s.tipoEtiqueta[l],
    categoria: s.categoria, categoriaEtiqueta: CATEGORIAS_DEMO[s.categoria][l],
    zona: s.zona, ubicacion: s.ubicacion, tarifaBase: s.tarifaBase, unidadTarifa: 'POR_PERSONA', unidadEtiqueta: UNIDAD[l],
    calificacion: s.calificacion, totalResenas: s.totalResenas,
    ocupacion: s.ocupacion, // el simulador sí lo conoce; el catálogo real no lo publica
  }
}

function aDetalle(s, idioma) {
  const l = lang(idioma)
  return {
    ...aServicio(s, idioma),
    descripcion: s[l].descripcion, capacidadDiaria: s.capacidadDiaria, imagenes: [],
    reglaCancelacion: REGLA_CANCELACION[l],
    prestador: { id: s.prestador.id, razonSocial: s.prestador.razonSocial, telefono: s.prestador.telefono, politicaCancelacion: s[l].politica },
    alertas: s.alertas.map((a) => ({ id: a.id, nivel: a.nivel, nivelEtiqueta: a.nivelEtiqueta[l], mensaje: a.mensaje[l], fechaExpiracion: a.fechaExpiracion })),
    etiquetas: [], avisoPagos: null,
    atributos: ATRIBUTOS_DEMO[s.id]?.[l]?.atributos ?? {}, etiquetasPorCodigo: ATRIBUTOS_DEMO[s.id]?.[l]?.etiquetas ?? {},
  }
}

/**
 * Adaptador simulado del puerto CatalogGateway: responde con el catálogo de demostración, con la misma forma que
 * el real, para desarrollar y probar la interfaz sin Gateway (VITE_API_MOCK=true).
 */
export function createMockCatalogGateway({ servicios = DEMO_SERVICIOS, verificarPrestador = async () => {}, esperaMs = 150, sleep = (ms) => new Promise((r) => setTimeout(r, ms)) } = {}) {
  const buscar = (id) => servicios.find((s) => s.id === id)

  return {
    async buscarServicios({ texto = '', categorias = [], zona, precioMin, precioMax, orden, pagina = 1, tamano = 12, idioma }) {
      await sleep(esperaMs)
      const l = lang(idioma)
      const q = normalizar(texto)
      const todos = servicios
        .filter((s) => !categorias.length || categorias.includes(s.categoria))
        .filter((s) => !q || normalizar(`${s[l].nombre} ${s[l].descripcion} ${s.zona.nombre}`).includes(q))
        .filter((s) => !zona || s.zona.codigo === zona)
        .filter((s) => (precioMin == null || s.tarifaBase >= precioMin) && (precioMax == null || s.tarifaBase <= precioMax))
      if (orden === 'precio') todos.sort((a, b) => a.tarifaBase - b.tarifaBase)
      else if (orden === 'calificacion') todos.sort((a, b) => b.calificacion - a.calificacion)
      const desde = (pagina - 1) * tamano
      return { items: todos.slice(desde, desde + tamano).map((s) => aServicio(s, idioma)), pagina, tamano, total: todos.length }
    },

    async zonas() {
      await sleep(esperaMs)
      return [...new Map(servicios.map((s) => [s.zona.codigo, { codigo: s.zona.codigo, nombre: s.zona.nombre }])).values()]
    },

    async obtenerServicio(id, idioma) {
      await sleep(esperaMs)
      const s = buscar(id)
      if (!s) throw new CatalogError(CODIGOS.NO_ENCONTRADO, 'Servicio no encontrado.', { status: 404 })
      return aDetalle(s, idioma)
    },

    async nombresServicios(ids, idioma) {
      await sleep(esperaMs)
      return ids.map(buscar).filter(Boolean).map((s) => ({ id: s.id, nombre: s[lang(idioma)].nombre, activo: true }))
    },

    async registrarIntencionVisita(id) {
      await sleep(esperaMs)
      if (!buscar(id)) throw new CatalogError(CODIGOS.NO_ENCONTRADO, 'Servicio no encontrado.', { status: 404 })
    },

    /** El simulador le da al prestador con sesión todos los servicios de demostración (no hay dueños distintos). */
    async serviciosPrestador({ pagina = 1, tamano = 100 } = {}, idioma) {
      await sleep(esperaMs)
      // Como el real: 403 PERFIL_INACTIVO si el prestador aún no está aprobado
      await verificarPrestador().catch((e) => { throw new CatalogError(e.code === 'PERFIL_INACTIVO' ? CODIGOS.PERFIL_INACTIVO : CODIGOS.ERROR, e.message, { status: e.status ?? 0 }) })
      const l = lang(idioma)
      const todos = servicios.map((s) => ({
        id: s.id, nombre: s[l].nombre, categoria: s.categoria, categoriaEtiqueta: CATEGORIAS_DEMO[s.categoria][l],
        zona: s.zona, activo: true, capacidadDiaria: s.capacidadDiaria, tarifaBase: s.tarifaBase,
      }))
      return { items: todos.slice((pagina - 1) * tamano, pagina * tamano), pagina, tamano, total: todos.length }
    },

    /** Zonas de ejemplo: un cuadrado alrededor de cada zona de los servicios de demostración, con el nivel que sale de su ocupación. */
    async mapaZonas({ idioma }) {
      await sleep(esperaMs)
      const l = lang(idioma)
      const porZona = new Map()
      for (const s of servicios) porZona.set(s.zona.codigo, [...(porZona.get(s.zona.codigo) ?? []), s])
      return [...porZona].map(([codigo, lista]) => {
        const ocu = Math.round(lista.reduce((a, s) => a + s.ocupacion, 0) / lista.length)
        const nivel = ocu < 60 ? 'BAJO' : ocu <= 85 ? 'MEDIO' : 'ALTO'
        const c = lista[0].ubicacion; const r = 0.04
        return {
          codigo, nombre: lista[0].zona.nombre, indice: ocu / 100, nivel, nivelEtiqueta: { es: { BAJO: 'Bajo', MEDIO: 'Medio', ALTO: 'Alto' }, en: { BAJO: 'Low', MEDIO: 'Medium', ALTO: 'High' } }[l][nivel],
          geometry: { type: 'MultiPolygon', coordinates: [[[[c.lon - r, c.lat - r], [c.lon + r, c.lat - r], [c.lon + r, c.lat + r], [c.lon - r, c.lat + r], [c.lon - r, c.lat - r]]]] },
        }
      })
    },

    async mapaAlertas({ idioma }) {
      await sleep(esperaMs)
      const l = lang(idioma)
      return servicios.flatMap((s) => s.alertas.map((a) => ({
        id: a.id, nivel: a.nivel, nivelEtiqueta: a.nivelEtiqueta[l], mensaje: a.mensaje[l], servicioId: s.id, zona: null,
        geometry: { type: 'Point', coordinates: [s.ubicacion.lon, s.ubicacion.lat] },
      })))
    },

    async mapaServicios({ bbox, categorias = [], idioma }) {
      await sleep(esperaMs)
      const [minLon, minLat, maxLon, maxLat] = bbox
      return servicios
        .filter((s) => !categorias.length || categorias.includes(s.categoria))
        .filter((s) => s.ubicacion.lon >= minLon && s.ubicacion.lon <= maxLon && s.ubicacion.lat >= minLat && s.ubicacion.lat <= maxLat)
        .map((s) => ({ tipo: 'servicio', id: s.id, nombre: s[lang(idioma)].nombre, categoria: s.categoria, calificacion: s.calificacion, lat: s.ubicacion.lat, lon: s.ubicacion.lon, ocupacion: s.ocupacion }))
    },
  }
}
