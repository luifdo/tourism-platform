import { CatalogError, CODIGOS } from '../../domain/catalog/errors.js'

const CODIGO_POR_ESTADO = { 400: CODIGOS.VALIDACION, 404: CODIGOS.NO_ENCONTRADO }
const CONOCIDOS = new Set(Object.values(CODIGOS))

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/** ServicioResumen del contrato -> Servicio de la aplicación. */
const aServicio = (s) => ({
  id: s.id,
  nombre: s.nombre,
  tipo: s.tipo,
  tipoEtiqueta: s.tipo_etiqueta ?? s.tipo,
  categoria: s.categoria,
  categoriaEtiqueta: s.categoria_etiqueta ?? s.categoria,
  zona: s.zona?.nombre ? { codigo: s.zona.codigo, nombre: s.zona.nombre } : null,
  ubicacion: { lat: s.ubicacion?.lat, lon: s.ubicacion?.lon },
  tarifaBase: num(s.tarifa_base) ?? 0,
  unidadTarifa: s.unidad_tarifa,
  unidadEtiqueta: s.unidad_tarifa_etiqueta ?? '',
  calificacion: num(s.calificacion_promedio),
  totalResenas: num(s.total_resenas) ?? 0,
})

/** ServicioDetalle del contrato -> ServicioDetalle de la aplicación. */
const aDetalle = (s) => ({
  ...aServicio(s),
  descripcion: s.descripcion ?? '',
  capacidadDiaria: num(s.capacidad_aforo_diario),
  imagenes: (s.imagenes_urls ?? []).filter((u) => typeof u === 'string'),
  reglaCancelacion: s.regla_base_cancelacion ?? '',
  prestador: {
    id: s.prestador?.id,
    razonSocial: s.prestador?.razon_social ?? '',
    telefono: s.prestador?.telefono ?? null,
    politicaCancelacion: s.prestador?.politica_cancelacion ?? null,
  },
  alertas: (s.alertas ?? []).map((a) => ({ id: a.id, nivel: a.nivel, nivelEtiqueta: a.nivel_etiqueta ?? a.nivel, mensaje: a.mensaje, fechaExpiracion: a.fecha_expiracion })),
  etiquetas: Object.values(s.etiquetas ?? {}).filter((e) => typeof e === 'string'),
  avisoPagos: s.aviso_pagos ? { importante: !!s.aviso_pagos.importante, recomendacionDinero: s.aviso_pagos.recomendacion_dinero, mensaje: s.aviso_pagos.mensaje } : null,
})

/** Feature GeoJSON de /mapa/servicios -> PuntoMapa (GeoJSON trae [lon, lat]). */
const aPunto = (f) => {
  const p = f.properties ?? {}
  const [lon, lat] = f.geometry?.coordinates ?? []
  return { tipo: p.tipo, id: p.id, nombre: p.nombre, categoria: p.categoria, calificacion: num(p.calificacion_promedio), conteo: num(p.conteo), lat, lon }
}

/**
 * Adaptador HTTP del puerto CatalogGateway: habla con el catalog-service a través del Gateway (Traefik),
 * siguiendo contracts/openapi/catalog.yaml. Son rutas públicas: no lleva Authorization.
 */
export function createHttpCatalogGateway({ baseUrl = '/api/catalog', fetchFn = (...a) => fetch(...a), authFetchFn = fetchFn } = {}) {
  // `authFetchFn` (fetch autenticado) solo lo usan las rutas del prestador; las públicas van sin Authorization
  async function http(method, path, { query = [], idioma = 'es', autenticada = false } = {}) {
    const qs = query.length ? '?' + new URLSearchParams(query.filter(([, v]) => v != null && v !== '')) : ''
    let res
    try { res = await (autenticada ? authFetchFn : fetchFn)(`${baseUrl}${path}${qs}`, { method, headers: { Accept: 'application/json', 'Accept-Language': idioma } }) }
    catch { throw new CatalogError(CODIGOS.SIN_CONEXION, 'No hay conexión con el servidor.') }
    if (res.status === 204) return null
    const data = await res.json().catch(() => null)
    if (!res.ok) {
      const code = CONOCIDOS.has(data?.error) ? data.error : CODIGO_POR_ESTADO[res.status] ?? CODIGOS.ERROR
      throw new CatalogError(code, data?.message ?? res.statusText, { status: res.status, correlationId: data?.correlation_id ?? null })
    }
    // Una ruta que el gateway no tiene cae en el frontend (HTML con 200): no es una respuesta del catálogo.
    if (data === null) throw new CatalogError(CODIGOS.RESPUESTA_INVALIDA, 'La respuesta del catálogo no tiene el formato esperado.', { status: res.status })
    return data
  }
  const invalida = () => new CatalogError(CODIGOS.RESPUESTA_INVALIDA, 'La respuesta del catálogo no tiene el formato esperado.')

  return {
    async buscarServicios({ texto, categorias = [], pagina = 1, tamano, idioma }) {
      const data = await http('GET', '/buscar', { idioma, query: [['texto', texto], ['categoria', categorias.join(',')], ['pagina', pagina], ['tamano', tamano]] })
      if (!Array.isArray(data.items)) throw invalida()
      return { items: data.items.map(aServicio), pagina: data.pagina ?? pagina, tamano: data.tamano ?? tamano, total: data.total ?? data.items.length }
    },

    async obtenerServicio(id, idioma) {
      const data = await http('GET', `/servicios/${encodeURIComponent(id)}`, { idioma })
      if (typeof data.id !== 'string' || typeof data.nombre !== 'string') throw invalida()
      return aDetalle(data)
    },

    async nombresServicios(ids, idioma) {
      const data = await http('GET', '/servicios/nombres', { idioma, query: ids.map((id) => ['ids', id]) })
      if (!Array.isArray(data.items)) throw invalida()
      return data.items.filter((n) => typeof n?.id === 'string').map((n) => ({ id: n.id, nombre: n.nombre, activo: n.activo !== false }))
    },

    async registrarIntencionVisita(id) {
      await http('POST', `/servicios/${encodeURIComponent(id)}/intencion-visita`)
    },

    /** UC18 · GET /prestador/servicios (Bearer): incluye inactivos; `nombre` viene en los dos idiomas ({ es, en }). */
    async serviciosPrestador({ pagina = 1, tamano = 100 } = {}, idioma = 'es') {
      const data = await http('GET', '/prestador/servicios', { idioma, autenticada: true, query: [['pagina', pagina], ['tamano', tamano]] })
      if (!Array.isArray(data.items)) throw invalida()
      const texto = (t) => (typeof t === 'string' ? t : t?.[idioma] ?? t?.es ?? t?.en ?? '')
      return {
        items: data.items.filter((s) => typeof s?.id === 'string').map((s) => ({
          id: s.id, nombre: texto(s.nombre), categoria: s.categoria, categoriaEtiqueta: s.categoria_etiqueta ?? s.categoria,
          zona: s.zona?.nombre ? { codigo: s.zona.codigo, nombre: s.zona.nombre } : null, activo: s.activo !== false,
          capacidadDiaria: num(s.capacidad_aforo_diario), tarifaBase: num(s.tarifa_base) ?? 0,
        })),
        pagina: data.pagina ?? pagina, tamano: data.tamano ?? tamano, total: data.total ?? data.items.length,
      }
    },

    async mapaServicios({ bbox, zoom, categorias = [], idioma }) {
      const data = await http('GET', '/mapa/servicios', { idioma, query: [['bbox', bbox.join(',')], ['zoom', Math.round(zoom)], ['categoria', categorias.join(',')]] })
      if (!Array.isArray(data.features)) throw invalida()
      return data.features.map(aPunto).filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon))
    },
  }
}
