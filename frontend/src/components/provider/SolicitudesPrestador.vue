<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { providerUseCases } from '../../composition'
import { BookingError } from '../../domain/booking/errors'
import { MOTIVO_MAX, MOTIVO_MIN, decisionConfirmar, urgencia, validarMotivo } from '../../domain/booking/prestador'
import { useOnline } from '../../ui/useOnline'
import { useSession } from '../../ui/useSession'
import { fmtDate } from '../../ui/format'
import StatusBadge from '../StatusBadge.vue'
import Countdown from '../Countdown.vue'

/*
 * UC20 · Solicitudes de los servicios del prestador. Por defecto las pendientes (SOLICITADA), de la más urgente a la menos.
 * Confirmar y rechazar necesitan conexión. Capa UI: presenta y llama a los casos de uso; las reglas viven en domain/booking.
 */
const props = defineProps({ servicios: { type: Array, required: true } })
const { t, te, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { expirar } = useSession()
const enLinea = useOnline()

const ESTADOS = ['SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'FINALIZADA']
const estado = ref('SOLICITADA')
const servicioId = ref('')
const items = ref([])
const total = ref(0)
const pagina = ref(1)
const cargando = ref(true)
const errorCarga = ref('')
const aviso = ref('')
const ocupado = ref('') // id de la solicitud con una acción en curso
const rechazando = ref(null) // { id, motivo }
const errorFila = ref({})

const nombre = (r) => props.servicios.find((s) => s.id === r.servicio_id)?.nombre ?? t('provider.serviceUnknown')
const textoError = (e) => {
  const c = e instanceof BookingError ? e.code : 'generic'
  return t(`provider.errors.${te(`provider.errors.${c}`) ? c : 'generic'}`)
}

function sesionVencida(e) {
  if (!(e instanceof BookingError) || e.code !== 'NO_AUTENTICADO') return false
  expirar()
  router.replace({ name: 'login', query: { redirect: route.fullPath, expirada: '1' } })
  return true
}

async function cargar(reiniciar = true) {
  cargando.value = reiniciar; errorCarga.value = ''
  if (reiniciar) pagina.value = 1
  try {
    const r = await providerUseCases.solicitudes({ estado: estado.value, servicioId: servicioId.value || undefined, pagina: pagina.value })
    items.value = reiniciar ? r.items : [...items.value, ...r.items]
    total.value = r.total
  } catch (e) { if (!sesionVencida(e)) errorCarga.value = textoError(e) }
  finally { cargando.value = false }
}
onMounted(cargar)
watch([estado, servicioId], () => cargar())
const masResultados = () => { pagina.value += 1; cargar(false) }
const hayMas = computed(() => items.value.length < total.value)

// Al confirmar o rechazar, la solicitud deja de estar pendiente: sale de la lista de pendientes y queda el aviso
async function ejecutar(r, accion, mensajeOk) {
  ocupado.value = r.id; errorFila.value = { ...errorFila.value, [r.id]: '' }; aviso.value = ''
  try {
    const { reserva } = await accion()
    items.value = estado.value === reserva.estado ? items.value.map((x) => (x.id === reserva.id ? reserva : x)) : items.value.filter((x) => x.id !== reserva.id)
    total.value = Math.max(0, total.value - (estado.value === reserva.estado ? 0 : 1))
    rechazando.value = null
    aviso.value = mensajeOk
  } catch (e) {
    if (sesionVencida(e)) return
    errorFila.value = { ...errorFila.value, [r.id]: textoError(e) }
    // La solicitud cambió (la cancelaron, venció el plazo): se recarga para ver cómo está ahora
    if (['TRANSICION_INVALIDA', 'PLAZO_VENCIDO', 'VERSION_DISTINTA', 'NO_ENCONTRADO'].includes(e?.code)) cargar()
  } finally { ocupado.value = '' }
}
const confirmar = (r) => ejecutar(r, () => providerUseCases.confirmar(r), t('provider.confirmed'))
const empezarRechazo = (r) => { rechazando.value = { id: r.id, motivo: '' }; errorFila.value = { ...errorFila.value, [r.id]: '' } }
const motivoValido = computed(() => (rechazando.value ? validarMotivo(rechazando.value.motivo).ok : false))
const enviarRechazo = (r) => ejecutar(r, () => providerUseCases.rechazar(r, rechazando.value.motivo), t('provider.rejected'))

const puedeConfirmar = (r) => decisionConfirmar(r, new Date()).permitido
const claseUrgencia = { vencida: 'text-danger', urgente: 'text-warn', normal: 'text-muted' }
</script>

<template>
  <div>
    <div class="flex flex-wrap items-end gap-3">
      <div class="flex flex-wrap gap-2" role="group" :aria-label="t('provider.filterState')">
        <button
          v-for="e in ESTADOS" :key="e" type="button" :aria-pressed="estado === e"
          class="rounded-full border px-4 py-2 text-sm font-medium transition"
          :class="estado === e ? 'border-navy bg-navy text-white shadow-cta' : 'border-sand/40 bg-white text-ink-control hover:border-teal'"
          @click="estado = e"
        >{{ t(`my.states.${e}`) }}</button>
      </div>
      <label v-if="servicios.length > 1" class="ml-auto text-sm">
        <span class="sr-only">{{ t('provider.filterService') }}</span>
        <select v-model="servicioId" class="rounded-xl border border-border-input bg-white px-3 py-2 text-sm text-ink-control">
          <option value="">{{ t('provider.allServices') }}</option>
          <option v-for="s in servicios" :key="s.id" :value="s.id">{{ s.nombre }}</option>
        </select>
      </label>
    </div>

    <p v-if="!enLinea" class="mt-4 rounded-xl bg-warn-bg px-4 py-2.5 text-sm text-warn" role="status">{{ t('provider.offline') }}</p>
    <p v-if="aviso" class="mt-4 rounded-xl bg-ok-bg px-4 py-2.5 text-sm text-ok" role="status">{{ aviso }}</p>

    <div v-if="cargando" class="mt-6 flex flex-col gap-4" role="status" :aria-label="t('provider.loading')">
      <div v-for="k in 3" :key="k" class="h-28 animate-pulse rounded-panel bg-white" />
    </div>
    <div v-else-if="errorCarga" class="mt-6 rounded-panel border border-danger/30 bg-danger-bg p-6 text-danger" role="alert">
      <p>{{ errorCarga }}</p>
      <button type="button" class="mt-3 font-semibold underline" @click="cargar()">{{ t('provider.retry') }}</button>
    </div>
    <p v-else-if="!items.length" class="mt-8 rounded-panel border border-sand/30 bg-white p-8 text-center text-muted shadow-card">{{ estado === 'SOLICITADA' ? t('provider.emptyPending') : t('provider.emptyState') }}</p>

    <ul v-else class="mt-6 flex flex-col gap-4">
      <li v-for="r in items" :key="r.id" class="rounded-panel border bg-white p-5 shadow-card sm:p-6" :class="urgencia(r) === 'urgente' ? 'border-warn/50' : 'border-sand/30'">
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="text-lg font-bold leading-snug tracking-tight text-navy-darkest">{{ nombre(r) }}</p>
            <p class="mt-1 text-sm text-ink-control first-letter:uppercase">{{ fmtDate(r.fecha_reserva, locale) }} · {{ t('my.people', { n: r.numero_personas }, r.numero_personas) }}</p>
          </div>
          <StatusBadge :estado="r.estado" />
        </div>

        <p v-if="r.estado === 'SOLICITADA' && r.expira_en" class="mt-3 text-sm" :class="claseUrgencia[urgencia(r)]">
          {{ t('provider.answerIn') }}: <Countdown :until="r.expira_en" @expired="cargar()" />
          <span v-if="urgencia(r) === 'urgente'" class="ml-2 font-semibold">· {{ t('provider.urgent') }}</span>
        </p>
        <p v-if="r.motivo" class="mt-3 rounded-xl bg-cream px-3.5 py-2.5 text-sm text-ink-control">
          <b>{{ t('provider.reason') }}:</b> {{ r.motivo }}
        </p>

        <div v-if="r.estado === 'SOLICITADA'" class="mt-4">
          <div v-if="rechazando?.id !== r.id" class="flex flex-wrap gap-2.5">
            <button type="button" class="rounded-full bg-navy px-5 py-2.5 text-sm font-medium text-white shadow-cta transition hover:bg-blue disabled:opacity-50" :disabled="!enLinea || ocupado === r.id || !puedeConfirmar(r)" @click="confirmar(r)">{{ ocupado === r.id ? t('provider.working') : t('provider.confirm') }}</button>
            <button type="button" class="rounded-full border border-danger/50 px-5 py-2.5 text-sm font-medium text-danger transition hover:bg-danger-bg disabled:opacity-50" :disabled="!enLinea || ocupado === r.id" @click="empezarRechazo(r)">{{ t('provider.reject') }}</button>
          </div>
          <form v-else class="flex flex-col gap-2.5" @submit.prevent="enviarRechazo(r)">
            <label class="text-sm font-medium text-navy-darkest" :for="`motivo-${r.id}`">{{ t('provider.reasonLabel') }}</label>
            <textarea :id="`motivo-${r.id}`" v-model="rechazando.motivo" rows="2" :maxlength="MOTIVO_MAX" class="rounded-xl border border-border-input bg-white px-3.5 py-2.5 text-sm outline-none focus-visible:ring-2 focus-visible:ring-teal" :placeholder="t('provider.reasonPh')" />
            <p class="text-xs text-muted">{{ t('provider.reasonHint', { min: MOTIVO_MIN, max: MOTIVO_MAX }) }}</p>
            <div class="flex flex-wrap gap-2.5">
              <button type="submit" class="rounded-full bg-danger px-5 py-2.5 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50" :disabled="!enLinea || ocupado === r.id || !motivoValido">{{ ocupado === r.id ? t('provider.working') : t('provider.rejectConfirm') }}</button>
              <button type="button" class="rounded-full border border-navy px-5 py-2.5 text-sm font-medium text-navy hover:bg-cream" @click="rechazando = null">{{ t('provider.cancel') }}</button>
            </div>
          </form>
        </div>
        <p v-if="errorFila[r.id]" class="mt-3 rounded-xl bg-danger-bg px-3.5 py-2.5 text-sm text-danger" role="alert">{{ errorFila[r.id] }}</p>
      </li>
    </ul>

    <div v-if="hayMas && !cargando" class="mt-6 text-center">
      <button type="button" class="rounded-full border border-navy px-8 py-3 font-medium text-navy hover:bg-white" @click="masResultados">{{ t('provider.more') }}</button>
    </div>
  </div>
</template>
