import { computed, reactive, readonly } from 'vue'
import { catalogUseCases } from '../composition'

/*
 * Estado reactivo del explorador para la interfaz. La lógica (normalizar la búsqueda, guardar la portada para
 * verla sin conexión) está en el caso de uso; aquí solo se guarda lo que se pinta. Compartido: la barra de
 * "sin conexión" muestra la misma fecha de actualización.
 */
const estado = reactive({
  items: [], total: 0, pagina: 1,
  cargando: false, cargandoMas: false,
  error: null, // código del error del catálogo
  desdeCache: false, actualizadoEn: null,
})
let solicitud = 0 // una búsqueda nueva descarta la respuesta de la anterior

export function useCatalog() {
  async function cargar(filtros, idioma) {
    const mia = ++solicitud
    estado.cargando = true; estado.cargandoMas = false; estado.error = null
    try {
      const r = await catalogUseCases.explorar({ ...filtros, pagina: 1 }, { idioma })
      if (mia !== solicitud) return
      Object.assign(estado, { items: r.items, total: r.total, pagina: 1, desdeCache: r.desdeCache, actualizadoEn: r.actualizadoEn })
    } catch (e) {
      if (mia !== solicitud) return
      Object.assign(estado, { items: [], total: 0, error: e.code ?? 'ERROR' })
    } finally {
      if (mia === solicitud) estado.cargando = false
    }
  }

  async function masResultados(filtros, idioma) {
    if (estado.cargando || estado.cargandoMas || estado.items.length >= estado.total) return
    const mia = solicitud
    estado.cargandoMas = true; estado.error = null
    try {
      const r = await catalogUseCases.explorar({ ...filtros, pagina: estado.pagina + 1 }, { idioma })
      if (mia !== solicitud) return
      estado.items = [...estado.items, ...r.items]; estado.pagina += 1; estado.total = r.total
    } catch (e) {
      if (mia === solicitud) estado.error = e.code ?? 'ERROR'
    } finally {
      if (mia === solicitud) estado.cargandoMas = false
    }
  }

  return { estado: readonly(estado), cargar, masResultados, updatedAt: computed(() => estado.actualizadoEn) }
}
