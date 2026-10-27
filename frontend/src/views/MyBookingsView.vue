<script setup>
import { computed, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { bookingUseCases, isMockBackend as isMock } from '../composition'
import { BookingError } from '../domain/booking/errors'
import { addDays } from '../domain/booking/dates'
import { ACTIVOS, ESTADOS as estados, decisionCancelar, decisionModificar, lineaDeTiempo } from '../domain/booking/rules'
import { queue } from '../lib/offlineQueue'
import { findService } from '../data/mock'
import { fmtDate } from '../ui/format'
import StatusBadge from '../components/StatusBadge.vue'
import Countdown from '../components/Countdown.vue'

/*
 * UC13 (historial) + UC12 (modificar solo en SOLICITADA, cancelar). Modificar y cancelar requieren conexión.
 * Capa UI: presenta y llama a los casos de uso; las reglas viven en domain/booking.
 */
const { t, te, locale, d } = useI18n()

const filter = ref('')
const items = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)
const loadError = ref('')
const cachedAt = ref(null)
const notice = ref('')
const busy = ref('') // id de la reserva con una acción en curso
const rowError = ref({})
const editing = ref(null) // { id, fecha, personas }
const cancelling = ref(null) // { id, motivo }

const today = () => bookingUseCases.hoy()
const tomorrow = () => bookingUseCases.manana()
const name = (r) => { const s = findService(r.servicio_id); return s ? t(`items.${s.id}.name`) : r.servicio_id }
const errText = (e) => {
  const code = e instanceof BookingError ? e.code : 'generic'
  return t(`my.errors.${te(`my.errors.${code}`) ? code : 'generic'}`)
}

async function load(reset = true) {
  loading.value = reset; loadError.value = ''; cachedAt.value = null
  if (reset) page.value = 1
  try {
    const res = await bookingUseCases.listarMisReservas({ estado: filter.value || undefined, pagina: page.value })
    items.value = reset ? res.items : [...items.value, ...res.items]
    total.value = res.total
    cachedAt.value = res.copiaDe // sin conexión el caso de uso devuelve la última copia guardada
  } catch (e) { loadError.value = errText(e) }
  finally { loading.value = false }
}
onMounted(load)
const setFilter = (f) => { filter.value = f; load() }
const more = () => { page.value++; load(false) }

// Las reglas salen del dominio (modificar solo SOLICITADA; cancelar CONFIRMADA hasta el día anterior)
const canEdit = (r) => decisionModificar(r).permitido
const canCancel = (r) => ACTIVOS.includes(r.estado)
const tooLate = (r) => decisionCancelar(r, today()).codigo === 'FUERA_DE_PLAZO'

function replace(r) { items.value = items.value.map((x) => (x.id === r.id ? r : x)) }

async function run(r, fn, okMsg) {
  busy.value = r.id; rowError.value = { ...rowError.value, [r.id]: '' }; notice.value = ''
  try { replace((await fn()).reserva); notice.value = okMsg; editing.value = cancelling.value = null }
  catch (e) {
    rowError.value = { ...rowError.value, [r.id]: e.code === 'VERSION_DISTINTA' ? t('my.changed') : errText(e) }
    if (e.code === 'VERSION_DISTINTA' || e.code === 'TRANSICION_INVALIDA') load()
  } finally { busy.value = '' }
}

const startEdit = (r) => { editing.value = { id: r.id, fecha: r.fecha_reserva, personas: r.numero_personas }; cancelling.value = null }
const startCancel = (r) => { cancelling.value = { id: r.id, motivo: '' }; editing.value = null }
const save = (r) => run(r, () => bookingUseCases.modificarReserva(r, { fecha_reserva: editing.value.fecha, numero_personas: Number(editing.value.personas) }), t('my.modified'))
const confirmCancel = (r) => run(r, () => bookingUseCases.cancelarReserva(r, cancelling.value.motivo.trim() || undefined), t('my.cancelled'))

// Línea de tiempo (regla del dominio) adaptada a lo que pinta la plantilla
const timeline = (r) => lineaDeTiempo(r).map((p) => ({ s: p.estado, on: p.alcanzado, bad: p.negativo }))
const when = computed(() => (cachedAt.value ? d(cachedAt.value, { dateStyle: 'medium', timeStyle: 'short' }) : ''))
const hasMore = computed(() => items.value.length < total.value && !cachedAt.value)
</script>

<template>
  <div class="bg-cream px-[clamp(20px,5vw,64px)] py-8 sm:py-12">
    <div class="mx-auto max-w-[900px]">
      <h1 class="text-[clamp(30px,4vw,48px)] font-bold tracking-[-.02em] text-navy-darkest">{{ t('my.title') }}</h1>
      <p class="mt-2 text-muted">{{ t('my.lead') }}</p>
      <p v-if="isMock" class="mt-2 font-mono text-[11px] text-muted/80">{{ t('my.demo') }}</p>

      <div class="mt-6 flex flex-wrap gap-2" role="group" aria-label="Estado">
        <button
          v-for="f in ['', ...estados]" :key="f" type="button" :aria-pressed="filter === f"
          class="rounded-full border px-4 py-2 text-sm font-medium transition"
          :class="filter === f ? 'border-navy bg-navy text-white shadow-cta' : 'border-sand/40 bg-white text-ink-control hover:border-teal'"
          @click="setFilter(f)"
        >{{ f ? t(`my.states.${f}`) : t('my.all') }}</button>
      </div>

      <p v-if="cachedAt" class="mt-4 rounded-xl bg-navy-darkest px-4 py-2 text-sm text-white">{{ t('my.cached', { when }) }}</p>
      <p v-if="notice" class="mt-4 rounded-xl bg-ok-bg px-4 py-2 text-sm text-ok" role="status">{{ notice }}</p>

      <p v-if="loading" class="mt-10 text-center text-muted">…</p>
      <div v-else-if="loadError" class="mt-10 text-center">
        <p class="text-danger">{{ t('my.loadError') }} {{ loadError }}</p>
        <button type="button" class="mt-3 rounded-full bg-navy px-5 py-2.5 text-sm font-medium text-white" @click="load()">{{ t('my.retry') }}</button>
      </div>
      <div v-else-if="!items.length" class="mt-10 rounded-panel border border-sand/30 bg-white p-8 text-center shadow-card">
        <p class="text-muted">{{ filter ? t('my.emptyFilter') : t('my.empty') }}</p>
        <RouterLink :to="{ name: 'home', hash: '#catalogo' }" class="mt-4 inline-block rounded-full bg-navy px-6 py-3 text-sm font-semibold text-white shadow-cta hover:bg-blue">{{ t('my.explore') }}</RouterLink>
      </div>

      <ul v-else class="mt-6 flex flex-col gap-4">
        <li v-for="r in items" :key="r.id" class="rounded-panel border border-sand/30 bg-white p-5 shadow-card sm:p-6">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <RouterLink :to="{ name: 'service', params: { id: r.servicio_id } }" class="text-lg font-bold leading-snug tracking-tight text-navy-darkest hover:text-navy">{{ name(r) }}</RouterLink>
              <p class="mt-1 text-sm text-ink-control first-letter:uppercase">{{ fmtDate(r.fecha_reserva, locale) }} · <span>{{ t('my.people', { n: r.numero_personas }, r.numero_personas) }}</span></p>
            </div>
            <StatusBadge :estado="r.estado" />
          </div>

          <ol class="mt-4 flex items-center gap-2" :aria-label="t(`my.states.${r.estado}`)">
            <template v-for="(s, i) in timeline(r)" :key="s.s">
              <li class="flex items-center gap-1.5 font-mono text-[11px]" :class="s.on ? (s.bad ? 'text-danger' : 'text-ok') : 'text-muted/60'">
                <span class="size-2.5 rounded-full" :class="s.on ? (s.bad ? 'bg-danger' : 'bg-ok') : 'bg-border-input'" />{{ t(`my.states.${s.s}`) }}
              </li>
              <span v-if="i < 2" class="h-px flex-1 bg-border-input" />
            </template>
          </ol>

          <p class="mt-3 text-sm text-muted">{{ t(`my.help.${r.estado}`) }}</p>
          <div v-if="r.estado === 'SOLICITADA' && r.expira_en" class="mt-3 inline-flex items-center gap-2 rounded-xl bg-warn-bg px-3 py-2 text-sm text-warn">
            {{ t('my.expiresIn') }} <b><Countdown :until="r.expira_en" @expired="load()" /></b>
          </div>
          <p v-if="r.motivo" class="mt-3 text-sm text-ink-control"><b>{{ t('my.reasonLabel') }}:</b> {{ r.motivo }}<template v-if="r.cancelada_por"> · {{ t('my.cancelledBy', { who: r.cancelada_por }) }}</template></p>

          <!-- Edición (solo SOLICITADA) -->
          <form v-if="editing?.id === r.id" class="mt-4 grid gap-3 rounded-card border border-sand/30 bg-cream p-4 sm:grid-cols-2" @submit.prevent="save(r)">
            <label class="text-sm"><span class="block font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('my.newDate') }}</span>
              <input v-model="editing.fecha" type="date" :min="tomorrow()" :max="addDays(today(), 366)" required class="mt-1 w-full rounded-xl border border-border-input bg-white px-3 py-2" /></label>
            <label class="text-sm"><span class="block font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('my.newPeople') }}</span>
              <input v-model="editing.personas" type="number" min="1" required class="mt-1 w-full rounded-xl border border-border-input bg-white px-3 py-2" /></label>
            <div class="flex gap-2 sm:col-span-2">
              <button type="submit" class="rounded-full bg-navy px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40" :disabled="busy === r.id || !queue.online">{{ t('my.save') }}</button>
              <button type="button" class="rounded-full px-4 py-2.5 text-sm text-ink-control hover:bg-white" @click="editing = null">{{ t('my.discard') }}</button>
            </div>
          </form>

          <!-- Cancelación -->
          <form v-if="cancelling?.id === r.id" class="mt-4 rounded-card border border-danger/20 bg-danger-bg/50 p-4" @submit.prevent="confirmCancel(r)">
            <label class="text-sm"><span class="block font-mono text-[10px] uppercase tracking-[.12em] text-muted">{{ t('my.reason') }}</span>
              <textarea v-model="cancelling.motivo" maxlength="500" rows="2" class="mt-1 w-full rounded-xl border border-border-input bg-white px-3 py-2" /></label>
            <div class="mt-3 flex gap-2">
              <button type="submit" class="rounded-full bg-danger px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-40" :disabled="busy === r.id || !queue.online">{{ t('my.confirmCancel') }}</button>
              <button type="button" class="rounded-full px-4 py-2.5 text-sm text-ink-control hover:bg-white" @click="cancelling = null">{{ t('my.keep') }}</button>
            </div>
          </form>

          <p v-if="rowError[r.id]" class="mt-3 rounded-xl bg-danger-bg px-3 py-2 text-sm text-danger" role="alert">{{ rowError[r.id] }}</p>

          <div v-if="canEdit(r) || canCancel(r)" class="mt-4 flex flex-wrap items-center gap-2 border-t border-sand/30 pt-4">
            <button v-if="canEdit(r)" type="button" class="rounded-full border border-navy px-4 py-2 text-sm font-medium text-navy hover:bg-navy hover:text-white disabled:opacity-40" :disabled="!queue.online || !!busy" @click="startEdit(r)">{{ t('my.modify') }}</button>
            <button v-if="canCancel(r)" type="button" class="rounded-full border border-danger/40 px-4 py-2 text-sm font-medium text-danger hover:bg-danger-bg disabled:opacity-40" :disabled="!queue.online || !!busy || tooLate(r)" @click="startCancel(r)">{{ t('my.cancel') }}</button>
            <p v-if="!queue.online" class="w-full text-xs text-muted">{{ t('my.needOnline') }}</p>
            <p v-else-if="tooLate(r)" class="w-full text-xs text-muted">{{ t('my.tooLate') }}</p>
            <p v-else-if="r.estado === 'CONFIRMADA'" class="w-full text-xs text-muted">{{ t('my.onlyRequested') }}</p>
          </div>
        </li>
      </ul>

      <div v-if="hasMore" class="mt-6 text-center">
        <button type="button" class="rounded-full border border-navy px-6 py-2.5 text-sm font-medium text-navy hover:bg-navy hover:text-white" @click="more">{{ t('my.more') }}</button>
      </div>
    </div>
  </div>
</template>
