import { CatalogError, CODIGOS } from '../../domain/catalog/errors.js'
import { MAX_IDS_NOMBRES, hayFiltros, normalizarBusqueda, trocear } from '../../domain/catalog/rules.js'
import { assertCatalogGateway } from './ports.js'

/*
 * Casos de uso del catálogo. Orquestan el dominio y los puertos; no saben de Vue ni de HTTP ni de IndexedDB.
 */
export function createCatalogUseCases({ gateway, cache, clock }) {
  assertCatalogGateway(gateway)
  const ahora = () => clock.now().getTime()

  return {
    /**
     * UC7/UC8 · pública. La portada (primera página, sin filtros) se guarda para verla sin conexión (RNF-13);
     * si no hay red o el catálogo no responde (5xx) se devuelve esa copia con la fecha en que se guardó.
     */
    async explorar(filtros, { idioma = 'es' } = {}) {
      const f = normalizarBusqueda(filtros)
      const esPortada = !hayFiltros(f) && f.pagina === 1
      try {
        const r = await gateway.buscarServicios({ ...f, idioma })
        if (esPortada) await cache?.write({ items: r.items, total: r.total, at: ahora() }).catch(() => {})
        return { ...r, desdeCache: false, actualizadoEn: ahora() }
      } catch (e) {
        // Sin red, o con el catálogo caído (5xx, p. ej. el 502 de Traefik): mejor la última copia que una pantalla de error
        const sinServicio = e instanceof CatalogError && (e.code === CODIGOS.SIN_CONEXION || e.status >= 500)
        if (sinServicio && esPortada) {
          const copia = await cache?.read().catch(() => null)
          if (copia?.items?.length) return { items: copia.items, pagina: 1, tamano: copia.items.length, total: copia.total, desdeCache: true, actualizadoEn: copia.at }
        }
        throw e
      }
    },

    /** Zonas activas para el filtro del explorador (pública). */
    zonas: (idioma = 'es') => gateway.zonas(idioma),

    /** UC9 · pública. NO_ENCONTRADO si el servicio no existe o está inactivo. */
    ficha(id, { idioma = 'es' } = {}) {
      if (!id) return Promise.reject(new CatalogError(CODIGOS.NO_ENCONTRADO, 'Servicio no encontrado.', { status: 404 }))
      return gateway.obtenerServicio(id, idioma)
    },

    /**
     * Nombres de varios servicios con una sola ronda de llamadas (booking-service/INTEGRACION.md §2.6): las
     * reservas y reseñas solo guardan `servicio_id`. Devuelve { porId: { [id]: { nombre, activo } }, incompleto }. Un id que
     * falta en `porId` ya no existe: quien llama muestra "Servicio no disponible". Pero si `incompleto` es true,
     * alguna llamada falló (sin red, 5xx) y la ausencia no quiere decir que no exista. Un fallo nunca impide ver las reservas.
     */
    async nombres(ids, { idioma = 'es' } = {}) {
      const unicos = [...new Set((ids ?? []).filter(Boolean))]
      const porId = {}
      let incompleto = false
      const tandas = await Promise.all(
        trocear(unicos, MAX_IDS_NOMBRES).map((tanda) => gateway.nombresServicios(tanda, idioma).catch(() => { incompleto = true; return [] })),
      )
      for (const n of tandas.flat()) porId[n.id] = { nombre: n.nombre, activo: n.activo }
      return { porId, incompleto }
    },

    /** "Cómo llegar": cuenta la intención de visita. Es un indicador aparte: si falla no se le avisa al turista. */
    async comoLlegar(id) {
      try { await gateway.registrarIntencionVisita(id); return true } catch { return false }
    },

    /** UC18 · los servicios del prestador con sesión (incluye los inactivos). Los lee todos, de a 100, para el selector del panel. */
    async misServicios({ idioma = 'es' } = {}) {
      const items = []
      for (let pagina = 1; pagina <= 20; pagina++) {
        const r = await gateway.serviciosPrestador({ pagina, tamano: 100 }, idioma)
        items.push(...r.items)
        if (items.length >= r.total || !r.items.length) break
      }
      return items
    },

    /** UC16 · pública. Servicios (y grupos de servicios) que caen en la vista del mapa. */
    puntosDelMapa({ bbox, zoom, categorias = [] }, { idioma = 'es' } = {}) {
      return gateway.mapaServicios({ bbox, zoom, categorias: normalizarBusqueda({ categorias }).categorias, idioma })
    },

    /** UC16 · pública. Polígonos de las zonas en la vista (con su nivel de saturación si el catálogo lo publica). */
    zonasDelMapa({ bbox, zoom }, { idioma = 'es' } = {}) {
      return gateway.mapaZonas({ bbox, zoom, idioma })
    },

    /** UC16/UC26 · pública. Alertas oficiales vigentes en la vista del mapa. */
    alertasDelMapa({ bbox }, { idioma = 'es' } = {}) {
      return gateway.mapaAlertas({ bbox, idioma })
    },
  }
}
