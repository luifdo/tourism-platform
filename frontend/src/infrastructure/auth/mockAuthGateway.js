import { AuthError, CODIGOS_AUTH as C } from '../../domain/auth/errors.js'
import { emailValido, evaluarPassword, normalizarEmail, validarRegistro } from '../../domain/auth/rules.js'

/*
 * Adaptador SIMULADO del puerto AuthGateway: hace el papel de iam-service mientras no hay Gateway.
 * Reproduce sus respuestas (códigos, 201/401/409/422) y la política de contraseñas. Nunca guarda la
 * contraseña en claro: guarda un resumen SHA-256 con sal (solo para la demostración; el servicio real usa Argon2id).
 *
 * Cuenta de demostración (la del README de iam-service): maria.perez@example.com / Tayrona2026
 */
const USERS = 'mock.iam.users.v1'
const RESETS = 'mock.iam.reset.v1'
const TTL_TOKEN_S = 900 // igual que jwt_access_token_ttl_minutes = 15
const TTL_RESET_MS = 30 * 60_000

export const CUENTA_DEMO = Object.freeze({ email: 'maria.perez@example.com', password: 'Tayrona2026', nombre: 'María Pérez' })

async function resumen(password, sal) {
  const bytes = new TextEncoder().encode(`${sal}:${password}`)
  if (globalThis.crypto?.subtle) {
    const h = await crypto.subtle.digest('SHA-256', bytes)
    return [...new Uint8Array(h)].map((b) => b.toString(16).padStart(2, '0')).join('')
  }
  let x = 0 // sin crypto.subtle (HTTP no seguro): resumen débil, solo de demostración
  for (const b of bytes) x = (Math.imul(x, 31) + b) >>> 0
  return `d${x.toString(16)}`
}

export function createMockAuthGateway({
  storage = globalThis.localStorage,
  clock = { now: () => new Date() },
  delayMs = 250,
  newId = () => (globalThis.crypto?.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`),
  exponerEnlaceDeRecuperacion = true,
} = {}) {
  const ahora = () => clock.now()
  const espera = (v) => (delayMs ? new Promise((res) => setTimeout(() => res(v), delayMs)) : Promise.resolve(v))
  const leer = (k, def) => { try { return JSON.parse(storage?.getItem(k)) ?? def } catch { return def } }
  const guardar = (k, v) => { try { storage?.setItem(k, JSON.stringify(v)) } catch { /* sin almacenamiento */ } }
  const publico = ({ id, email, nombre_completo, rol, email_verificado, creado_en }) => ({ id, email, nombre_completo, rol, email_verificado, creado_en })

  async function usuarios() {
    let lista = leer(USERS, null)
    if (!lista) {
      const sal = 'demo'
      lista = [{
        id: newId(), email: CUENTA_DEMO.email, sal, hash: await resumen(CUENTA_DEMO.password, sal), nombre_completo: CUENTA_DEMO.nombre,
        rol: 'Turista', activo: true, email_verificado: false, creado_en: ahora().toISOString(),
      }]
      guardar(USERS, lista)
    }
    return lista
  }

  const falso = (payload) => {
    const b64 = (o) => btoa(JSON.stringify(o)).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_')
    return `${b64({ alg: 'none', typ: 'JWT' })}.${b64(payload)}.mock`
  }

  return {
    async registrar(datos) {
      const lista = await usuarios()
      // Mismo orden de comprobación que RegistrarUsuario: consentimiento, mayoría de edad, rol, correo, contraseña, nombre
      const errores = validarRegistro({
        email: datos.email, password: datos.password, nombre: datos.nombre_completo, rol: datos.rol,
        habeasDataAceptado: datos.habeas_data_aceptado, esMayorDeEdad: datos.es_mayor_de_edad,
      })
      const orden = [C.HABEAS_DATA_REQUERIDO, C.MAYORIA_DE_EDAD_REQUERIDA, C.ROL_NO_PERMITIDO, C.EMAIL_INVALIDO, C.PASSWORD_INVALIDA, C.NOMBRE_INVALIDO]
      const primero = [...errores].sort((a, b) => orden.indexOf(a.codigo) - orden.indexOf(b.codigo))[0]
      if (primero) throw new AuthError(primero.codigo, primero.mensaje, { status: 422 })
      const email = normalizarEmail(datos.email)
      if (lista.some((u) => u.email === email)) throw new AuthError(C.EMAIL_EN_USO, 'Ya existe una cuenta registrada con ese correo electrónico.', { status: 409 })
      const sal = newId()
      const usuario = {
        id: newId(), email, sal, hash: await resumen(datos.password, sal), nombre_completo: datos.nombre_completo.trim(),
        rol: datos.rol, activo: true, email_verificado: false, creado_en: ahora().toISOString(),
      }
      guardar(USERS, [...lista, usuario])
      return espera(publico(usuario))
    },

    async iniciarSesion({ email, password }) {
      const lista = await usuarios()
      const u = lista.find((x) => x.email === normalizarEmail(email))
      // Mismo mensaje y trabajo si el correo no existe o la contraseña no coincide (no revela cuentas)
      const hash = await resumen(password, u?.sal ?? 'x')
      if (!u || hash !== u.hash) throw new AuthError(C.CREDENCIALES_INVALIDAS, 'Correo o contraseña incorrectos.', { status: 401 })
      if (!u.activo) throw new AuthError(C.CUENTA_INACTIVA, 'La cuenta está desactivada. Contacte al administrador.', { status: 403 })
      const iat = Math.floor(ahora().getTime() / 1000)
      const access_token = falso({ sub: u.id, rol: u.rol, jti: newId(), iat, exp: iat + TTL_TOKEN_S, iss: 'iam-service' })
      return espera({ access_token, token_type: 'bearer', expires_in: TTL_TOKEN_S, usuario: publico(u) })
    },

    async cerrarSesion(token) {
      if (!token) throw new AuthError(C.TOKEN_INVALIDO, 'El token no es válido, expiró o fue revocado.', { status: 401 })
      return espera(undefined)
    },

    async solicitarRecuperacion(email) {
      const lista = await usuarios()
      const u = lista.find((x) => x.email === normalizarEmail(email))
      const respuesta = { enviado: true } // igual exista o no la cuenta
      if (u) {
        const token = newId()
        const resets = leer(RESETS, []).filter((r) => r.vence > ahora().getTime())
        guardar(RESETS, [...resets, { token, usuarioId: u.id, vence: ahora().getTime() + TTL_RESET_MS }])
        if (exponerEnlaceDeRecuperacion) respuesta.demo = { token } // no hay correo real: se muestra el enlace para probar
      }
      return espera(respuesta)
    },

    async restablecerPassword({ token, password }) {
      if (!evaluarPassword(password).valida) throw new AuthError(C.PASSWORD_INVALIDA, 'La contraseña no cumple la política.', { status: 422 })
      const resets = leer(RESETS, [])
      const r = resets.find((x) => x.token === token && x.vence > ahora().getTime())
      if (!r) throw new AuthError(C.TOKEN_INVALIDO, 'El enlace no es válido o expiró.', { status: 400 })
      const lista = await usuarios()
      const u = lista.find((x) => x.id === r.usuarioId)
      if (!u) throw new AuthError(C.TOKEN_INVALIDO, 'El enlace no es válido o expiró.', { status: 400 })
      const sal = newId()
      u.sal = sal
      u.hash = await resumen(password, sal)
      guardar(USERS, lista)
      guardar(RESETS, resets.filter((x) => x.token !== token)) // un enlace sirve una sola vez
      return espera(undefined)
    },
  }
}
