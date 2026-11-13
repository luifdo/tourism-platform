import { CODIGOS_GESTION as C, GestionError } from '../../domain/gestion/errors.js'

/**
 * Cliente JSON de los servicios de gestión (iam, catalog, review) a través del Gateway. `fetchFn` es el fetch
 * autenticado (authorizedFetch): pone el Bearer y renueva el token. Traduce los errores de cualquiera de los tres
 * servicios a GestionError (IAM manda `code` y `errores`; catalog y review mandan `error` y `message`).
 */
const TIEMPO_MAXIMO_MS = 30_000

const codigoPorEstado = (s) => (s === 401 ? C.NO_AUTENTICADO : s === 403 ? C.ROL_INSUFICIENTE : s === 404 ? C.NO_ENCONTRADO : s === 503 ? C.SERVICIO_NO_DISPONIBLE : s === 400 || s === 422 ? C.VALIDACION : C.ERROR)

export function createApiClient({ baseUrl, fetchFn = (...a) => fetch(...a), tiempoMaximoMs = TIEMPO_MAXIMO_MS } = {}) {
  /**
   * @param {string} method
   * @param {string} path
   * @param {{ query?: object, body?: object, form?: FormData, headers?: object, idioma?: string, version?: string|number, as?: 'json'|'text', aceptar?: string }} [op]
   * @returns {Promise<{ data: any, etag: string|null, status: number }>}
   */
  async function request(method, path, { query, body, form, headers = {}, idioma, version, as = 'json', aceptar } = {}) {
    const q = query ? Object.entries(query).filter(([, v]) => v != null && v !== '') : []
    const qs = q.length ? '?' + new URLSearchParams(q.map(([k, v]) => [k, String(v)])) : ''
    // un encabezado sin valor no se manda: fetch lo enviaría como el texto "undefined"
    const h = { Accept: aceptar ?? 'application/json', ...(idioma ? { 'Accept-Language': idioma } : {}), ...Object.fromEntries(Object.entries(headers).filter(([, v]) => v != null)) }
    if (version != null) h['If-Match'] = String(version)
    if (body !== undefined) h['Content-Type'] = 'application/json'
    let res
    try {
      res = await fetchFn(`${baseUrl}${path}${qs}`, { method, headers: h, body: body !== undefined ? JSON.stringify(body) : form, signal: AbortSignal.timeout(tiempoMaximoMs) })
    } catch { throw new GestionError(C.SIN_CONEXION, 'No hay conexión con el servidor.') }
    if (res.status === 204) return { data: null, etag: res.headers.get('ETag'), status: 204 }
    const data = as === 'text' && res.ok ? await res.text() : await res.json().catch(() => null)
    if (!res.ok) {
      const campos = (data?.errores ?? []).map((e) => ({ campo: e.campo, mensaje: e.mensaje }))
      throw new GestionError(data?.code ?? data?.error ?? codigoPorEstado(res.status), data?.detail ?? data?.message ?? res.statusText, {
        status: res.status, campos, data, correlationId: data?.correlation_id,
      })
    }
    return { data, etag: res.headers.get('ETag'), status: res.status }
  }
  return { request }
}
