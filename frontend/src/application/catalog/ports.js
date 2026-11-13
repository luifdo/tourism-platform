/*
 * PUERTOS del catálogo (UC7 listar/buscar, UC9 detalle, UC16 mapa). La aplicación solo conoce estas
 * interfaces; los adaptadores de infrastructure/ las implementan. Los nombres son los operationId de
 * contracts/openapi/catalog.yaml. Todos devuelven el MODELO de la aplicación (camelCase), no el JSON del servicio.
 *
 * CatalogGateway  (puerto de salida)
 *   buscarServicios({ texto, categorias, pagina, tamano, idioma }) -> { items: Servicio[], pagina, tamano, total }
 *   obtenerServicio(id, idioma)                 -> ServicioDetalle                 (CatalogError NO_ENCONTRADO si no existe)
 *   nombresServicios(ids, idioma)               -> { id, nombre, activo }[]        (los ids que no existen no vienen)
 *   registrarIntencionVisita(id)                -> void                            ("Cómo llegar")
 *   serviciosPrestador({ pagina, tamano }, idioma) -> { items: ServicioPrestador[], pagina, tamano, total }   (exige sesión de Prestador)
 *       ServicioPrestador { id, nombre, categoria, zona, activo, capacidadDiaria, tarifaBase }
 *   mapaServicios({ bbox, zoom, categorias, idioma }) -> PuntoMapa[]
 *   Los errores se lanzan como CatalogError (domain/catalog/errors.js).
 *
 *   Servicio       { id, nombre, tipo, tipoEtiqueta, categoria, categoriaEtiqueta, zona: {codigo,nombre}|null,
 *                    ubicacion: {lat,lon}, tarifaBase, unidadTarifa, unidadEtiqueta, calificacion|null, totalResenas,
 *                    ocupacion?: número 0-100 (solo si el adaptador lo conoce) }
 *   ServicioDetalle  Servicio + { descripcion, capacidadDiaria, imagenes: string[], reglaCancelacion,
 *                    prestador: { id, razonSocial, telefono|null, politicaCancelacion|null },
 *                    alertas: { id, nivel, nivelEtiqueta, mensaje, fechaExpiracion }[], etiquetas: string[],
 *                    avisoPagos: { importante, recomendacionDinero, mensaje }|null }
 *   PuntoMapa      { tipo: 'servicio'|'grupo', id?, nombre?, categoria?, calificacion?, conteo?, lat, lon, ocupacion? }
 *
 * CatalogCache (puerto de salida)  read() -> { items, total, at } | null   ·   write({ items, total, at })
 * Clock        (puerto de salida)  now() -> Date
 */
export const CATALOG_GATEWAY_METHODS = Object.freeze([
  'buscarServicios', 'obtenerServicio', 'nombresServicios', 'registrarIntencionVisita', 'mapaServicios', 'serviciosPrestador',
])

export function assertCatalogGateway(gateway) {
  const faltan = CATALOG_GATEWAY_METHODS.filter((m) => typeof gateway?.[m] !== 'function')
  if (faltan.length) throw new TypeError(`El adaptador del catálogo no implementa el puerto CatalogGateway: faltan ${faltan.join(', ')}`)
  return gateway
}
