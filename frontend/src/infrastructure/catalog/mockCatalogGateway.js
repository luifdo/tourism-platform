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
export function createMockCatalogGateway({ servicios = DEMO_SERVICIOS, esperaMs = 150, sleep = (ms) => new Promise((r) => setTimeout(r, ms)) } = {}) {
  const buscar = (id) => servicios.find((s) => s.id === id)

  return {
    async buscarServicios({ texto = '', categorias = [], pagina = 1, tamano = 12, idioma }) {
      await sleep(esperaMs)
      const l = lang(idioma)
      const q = normalizar(texto)
      const todos = servicios
        .filter((s) => !categorias.length || categorias.includes(s.categoria))
        .filter((s) => !q || normalizar(`${s[l].nombre} ${s[l].descripcion} ${s.zona.nombre}`).includes(q))
      const desde = (pagina - 1) * tamano
      return { items: todos.slice(desde, desde + tamano).map((s) => aServicio(s, idioma)), pagina, tamano, total: todos.length }
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
      const l = lang(idioma)
      const todos = servicios.map((s) => ({
        id: s.id, nombre: s[l].nombre, categoria: s.categoria, categoriaEtiqueta: CATEGORIAS_DEMO[s.categoria][l],
        zona: s.zona, activo: true, capacidadDiaria: s.capacidadDiaria, tarifaBase: s.tarifaBase,
      }))
      return { items: todos.slice((pagina - 1) * tamano, pagina * tamano), pagina, tamano, total: todos.length }
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
