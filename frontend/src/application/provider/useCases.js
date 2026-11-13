import { BookingError, CODIGOS } from '../../domain/booking/errors.js'
import {
  decisionConfirmar, decisionRechazar, validarDia, validarMotivo, validarRango,
} from '../../domain/booking/prestador.js'
import { assertProviderGateway } from './ports.js'

/*
 * Casos de uso del panel del prestador (UC19, UC20). Orquestan el dominio y el puerto; no saben de Vue ni de HTTP.
 * Las reglas se comprueban ANTES de llamar al servidor (ahorran una petición y dan el mismo mensaje), pero el
 * servidor sigue siendo la autoridad: puede responder 409 aunque aquí pareciera válido.
 */
const REINTENTABLES = new Set([CODIGOS.PETICION_EN_PROCESO, CODIGOS.IDEMPOTENCIA_NO_DISPONIBLE])
const ESPERAS_MS = [1500, 3000, 6000] // cuánto esperar entre reintentos con la MISMA Idempotency-Key

export function createProviderUseCases({ gateway, session, clock, esperar = (ms) => new Promise((r) => setTimeout(r, ms)) }) {
  assertProviderGateway(gateway)
  const ahora = () => clock.now()

  const exigirSesion = () => {
    if (!session.isAuthenticated()) throw new BookingError(CODIGOS.NO_AUTENTICADO, 'Inicia sesión para continuar.', { status: 401 })
  }
  const rechazar = (decision) => { throw new BookingError(decision.codigo, decision.mensaje, { status: 409 }) }
  const invalido = (errores, mensaje = 'Los datos no son válidos.') => {
    throw Object.assign(new BookingError(CODIGOS.VALIDACION, mensaje, { status: 400 }), { campos: errores })
  }

  /**
   * 409 PETICION_EN_PROCESO (la primera petición con esa clave sigue corriendo) y 503 IDEMPOTENCIA_NO_DISPONIBLE (no se
   * ejecutó nada) se reintentan con la misma clave unos segundos después. Una clave por intento del usuario, no por reintento.
   */
  async function conReintento(fn) {
    for (let intento = 0; ; intento++) {
      try { return await fn() } catch (e) {
        if (!(e instanceof BookingError) || !REINTENTABLES.has(e.code) || intento >= ESPERAS_MS.length) throw e
        await esperar(ESPERAS_MS[intento])
      }
    }
  }

  return {
    /** UC20 · por defecto las SOLICITADA, de la más urgente a la menos (lo ordena el servidor por `expira_en`). */
    async solicitudes({ estado = 'SOLICITADA', servicioId, desde, hasta, pagina = 1, tamano = 20 } = {}) {
      exigirSesion()
      return gateway.solicitudesPrestador({ estado: estado || undefined, servicio_id: servicioId, desde, hasta, pagina, tamano })
    },

    /** UC20 · solo SOLICITADA y antes de `expira_en`. */
    async confirmar(reserva) {
      exigirSesion()
      const d = decisionConfirmar(reserva, ahora())
      if (!d.permitido) rechazar(d)
      const { data, etag } = await gateway.confirmarReserva(reserva.id)
      return { reserva: data, etag }
    },

    /** UC20 · el motivo es obligatorio (3 a 500 caracteres); libera los cupos. */
    async rechazar(reserva, motivo) {
      exigirSesion()
      const m = validarMotivo(motivo)
      if (!m.ok) throw new BookingError(CODIGOS.MOTIVO_INVALIDO, 'El motivo debe tener entre 3 y 500 caracteres.', { status: 400 })
      const d = decisionRechazar(reserva)
      if (!d.permitido) rechazar(d)
      const { data, etag } = await gateway.rechazarReserva(reserva.id, m.motivo)
      return { reserva: data, etag }
    },

    /** UC19 · días del rango con totales, reservados, disponibles, tarifa y versión. */
    async calendario(servicioId, { desde, hasta }) {
      exigirSesion()
      return gateway.calendarioServicio(servicioId, desde, hasta)
    },

    /** UC19 · abre los días del rango que coincidan con `diasSemana`; informa cuáles ya existían. */
    async abrirRango(servicioId, { desde, hasta, diasSemana, cuposTotales, tarifaDia = null }, { idempotencyKey, aforo } = {}) {
      exigirSesion()
      const errores = validarRango({ desde, hasta, diasSemana, cuposTotales, tarifaDia }, { ahora: ahora(), aforo })
      if (errores.length) invalido(errores)
      const cuerpo = { desde, hasta, cupos_totales: cuposTotales, ...(diasSemana?.length ? { dias_semana: diasSemana } : {}), tarifa_dia: tarifaDia }
      return conReintento(() => gateway.abrirRangoCalendario(servicioId, cuerpo, idempotencyKey))
    },

    /**
     * UC19 · crea (sin `version`) o edita (con la `version` que el prestador vio) un día. Si el día cambió en el servidor
     * responde BookingError VERSION_DISTINTA con `data.actual`; para insistir se reenvía con `data.version_actual`.
     */
    async guardarDia(servicioId, fecha, { cuposTotales, tarifaDia = null }, { version = null, reservados = 0, aforo, idempotencyKey } = {}) {
      exigirSesion()
      const errores = validarDia({ cuposTotales, tarifaDia }, { reservados, aforo })
      if (errores.length) invalido(errores)
      const cuerpo = { cupos_totales: cuposTotales, tarifa_dia: tarifaDia }
      const { data, etag, creado } = await conReintento(() => gateway.guardarDiaCalendario(servicioId, fecha, cuerpo, { version, idempotencyKey }))
      return { dia: data, etag, creado }
    },
  }
}
