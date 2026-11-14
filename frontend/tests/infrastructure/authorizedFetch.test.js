import { describe, expect, it, vi } from 'vitest'
import { createAuthorizedFetch } from '../../src/infrastructure/auth/authorizedFetch.js'

const res = (status) => ({ status, ok: status < 400 })
const crear = ({ respuestas, token = 'a1', renovado = 'a2' }) => {
  const fetchFn = vi.fn()
  for (const r of respuestas) fetchFn.mockImplementationOnce(async () => (r instanceof Error ? Promise.reject(r) : res(r)))
  const tokens = { obtener: vi.fn(async () => token), renovarTras401: vi.fn(async () => renovado) }
  return { fetchFn, tokens, f: createAuthorizedFetch({ fetchFn, tokens }) }
}
const auth = (fetchFn, i) => fetchFn.mock.calls[i][1].headers.Authorization

describe('fetch autenticado', () => {
  it('pone el access token de la sesión y respeta el resto de la petición', async () => {
    const { f, fetchFn } = crear({ respuestas: [200] })
    await f('/api/bookings/mis-reservas', { method: 'GET', headers: { Accept: 'application/json', 'Idempotency-Key': 'k' }, body: '{"a":1}' })
    expect(fetchFn.mock.calls[0][0]).toBe('/api/bookings/mis-reservas')
    expect(fetchFn.mock.calls[0][1]).toMatchObject({ method: 'GET', body: '{"a":1}', headers: { Accept: 'application/json', 'Idempotency-Key': 'k', Authorization: 'Bearer a1' } })
  })

  it('sin sesión no manda Authorization y un 401 no intenta renovar (no hay con qué)', async () => {
    const { f, fetchFn, tokens } = crear({ respuestas: [401], token: null })
    expect((await f('/x')).status).toBe(401)
    expect(auth(fetchFn, 0)).toBeUndefined()
    expect(tokens.renovarTras401).not.toHaveBeenCalled()
  })

  it('una respuesta que no es 401 se entrega tal cual, sin renovar', async () => {
    for (const status of [200, 201, 400, 403, 404, 409, 500]) {
      const { f, tokens } = crear({ respuestas: [status] })
      expect((await f('/x')).status).toBe(status)
      expect(tokens.renovarTras401).not.toHaveBeenCalled()
    }
  })

  it('ante un 401 renueva UNA vez con el token que falló y repite la petición con el nuevo', async () => {
    const { f, fetchFn, tokens } = crear({ respuestas: [401, 200] })
    expect((await f('/x', { method: 'POST', body: '{"m":"hola"}' })).status).toBe(200)
    expect(tokens.renovarTras401).toHaveBeenCalledTimes(1)
    expect(tokens.renovarTras401).toHaveBeenCalledWith('a1')
    expect(fetchFn).toHaveBeenCalledTimes(2)
    expect(auth(fetchFn, 1)).toBe('Bearer a2')
    expect(fetchFn.mock.calls[1][1].body).toBe('{"m":"hola"}') // el cuerpo viaja igual en el reintento
  })

  it('si tras renovar vuelve a dar 401, devuelve ese 401 y no insiste (una sola repetición)', async () => {
    const { f, fetchFn, tokens } = crear({ respuestas: [401, 401] })
    expect((await f('/x')).status).toBe(401)
    expect(fetchFn).toHaveBeenCalledTimes(2)
    expect(tokens.renovarTras401).toHaveBeenCalledTimes(1)
  })

  it('si ya no se puede renovar (null) devuelve el 401 original sin repetir', async () => {
    const { f, fetchFn } = crear({ respuestas: [401], renovado: null })
    expect((await f('/x')).status).toBe(401)
    expect(fetchFn).toHaveBeenCalledTimes(1)
  })

  it('un fallo pasajero al renovar se propaga (no se confunde con "sesión vencida")', async () => {
    const { f, tokens } = crear({ respuestas: [401] })
    tokens.renovarTras401.mockRejectedValueOnce(new Error('sin red'))
    await expect(f('/x')).rejects.toThrow('sin red')
  })

  it('si el fetch falla (sin red) el error se propaga igual', async () => {
    const { f } = crear({ respuestas: [new TypeError('Failed to fetch')] })
    await expect(f('/x')).rejects.toThrow('Failed to fetch')
  })
})

describe('qué 401 se renuevan', () => {
  // Una respuesta con cuerpo JSON legible (clone().json()), como la del servicio real
  const con401 = (cuerpo) => ({ status: 401, ok: false, clone: () => ({ json: async () => { if (cuerpo === undefined) throw new SyntaxError('sin JSON'); return cuerpo } }) })
  const armar = (primera) => {
    const fetchFn = vi.fn().mockImplementationOnce(async () => primera).mockImplementationOnce(async () => ({ status: 200, ok: true }))
    const tokens = { obtener: vi.fn(async () => 'a1'), renovarTras401: vi.fn(async () => 'a2') }
    return { fetchFn, tokens, f: createAuthorizedFetch({ fetchFn, tokens }) }
  }

  it('TOKEN_INVALIDO (iam) renueva y repite', async () => {
    const { f, fetchFn, tokens } = armar(con401({ code: 'TOKEN_INVALIDO' }))
    expect((await f('/x')).status).toBe(200)
    expect(tokens.renovarTras401).toHaveBeenCalledTimes(1)
    expect(fetchFn).toHaveBeenCalledTimes(2)
  })
  it('NO_AUTENTICADO (catalog y booking, campo `error`) renueva y repite', async () => {
    const { f, tokens } = armar(con401({ error: 'NO_AUTENTICADO', message: 'x' }))
    expect((await f('/x')).status).toBe(200)
    expect(tokens.renovarTras401).toHaveBeenCalledTimes(1)
  })
  it('CREDENCIALES_INVALIDAS (contraseña mal al borrar la cuenta) NO gasta una rotación ni repite la petición', async () => {
    const { f, fetchFn, tokens } = armar(con401({ code: 'CREDENCIALES_INVALIDAS', detail: 'La contraseña no es correcta.' }))
    const r = await f('/api/iam/perfil', { method: 'DELETE', body: '{"password":"mala"}' })
    expect(r.status).toBe(401)
    expect(tokens.renovarTras401).not.toHaveBeenCalled()
    expect(fetchFn).toHaveBeenCalledTimes(1) // un DELETE irreversible no se repite
  })
  it('un 401 sin cuerpo legible (un proxy, un cuerpo vacío) se trata como token vencido, como antes', async () => {
    const { f, tokens } = armar(con401(undefined))
    expect((await f('/x')).status).toBe(200)
    expect(tokens.renovarTras401).toHaveBeenCalledTimes(1)
  })
})
