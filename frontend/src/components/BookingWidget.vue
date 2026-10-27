<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { bookingUseCases, isMockBackend as isMock } from '../composition'
import { BookingError } from '../domain/booking/errors'
import { maxPersonas, tarifaDia } from '../domain/booking/rules'
import { queue } from '../lib/offlineQueue'
import { fmtDate } from '../ui/format'
import BookingCalendar from './BookingCalendar.vue'
import Countdown from './Countdown.vue'

/*
 * Reserva en 4 pasos (RNF-11, ESC-07): 1 Fecha · 2 Personas · 3 Resumen · 4 Enviar.
 * Sin pagos: la solicitud es gratuita y el pago es directo al prestador (SRS §1.2.1).
 * Requiere conexión (SRS §3.6.6): sin red el widget se deshabilita.
 *
 * Capa UI: solo presenta y llama a los casos de uso; las reglas viven en domain/booking.
 */
const props = defineProps({ service: { type: Object, required: true } })
const { t, n, locale, te, tm, rt } = useI18n()
const stepName = computed(() => rt(tm('booking.steps')[step.value - 1]))

const step = ref(1)
const days = ref([])
const loading = ref(false)
const loadError = ref('')
const date = ref('')
const people = ref(1)
const sending = ref(false)
const error = ref('')
const result = ref(null)

const { desde: from, hasta: to } = bookingUseCases.ventana()

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)
// Una clave por intento: un doble clic o un reintento devuelve la misma reserva, no una nueva
let idemKey = uid()
watch([date, people], () => { idemKey = uid() })

const day = computed(() => days.value.find((d) => d.fecha === date.value))
const maxPeople = computed(() => maxPersonas(day.value))
const rate = computed(() => tarifaDia(day.value, props.service.fee))
const cop = (v) => n(v, { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })

const errKey = (e) => {
  const k = e instanceof BookingError ? e.code : 'generic'
  return `booking.errors.${te(`booking.errors.${k}`) ? k : 'generic'}`
}

async function load() {
  loading.value = true; loadError.value = ''
  try { days.value = (await bookingUseCases.consultarDisponibilidad(props.service.id)).dias }
  catch (e) { loadError.value = t(errKey(e)) }
  finally { loading.value = false }
}
onMounted(load)
watch(() => queue.online, (on) => { if (on && !days.value.length) load() })

function pickDate(d) {
  date.value = d
  if (people.value > maxPeople.value) people.value = maxPeople.value
}
const canNext = computed(() => (step.value === 1 ? !!date.value : step.value === 2 ? people.value >= 1 && people.value <= maxPeople.value : true))

async function send() {
  error.value = ''
  sending.value = true
  try {
    const { reserva } = await bookingUseCases.solicitarReserva({
      servicioId: props.service.id, fecha: date.value, personas: people.value, maxPersonas: maxPeople.value, idempotencyKey: idemKey,
    })
    result.value = reserva
  } catch (e) {
    error.value = e instanceof BookingError && e.code === 'NO_AUTENTICADO' ? t('booking.needLogin') : t(errKey(e))
    if (e instanceof BookingError && ['CUPOS_INSUFICIENTES', 'DIA_NO_DISPONIBLE'].includes(e.code)) { await load(); step.value = 1; date.value = '' }
  } finally { sending.value = false }
}

function again() {
  result.value = null; step.value = 1; date.value = ''; people.value = 1; error.value = ''; idemKey = uid(); load()
}
</script>

<template>
  <section class="rounded-panel border border-sand/30 bg-white p-5 shadow-elevated sm:p-6" :aria-label="t('booking.title')">
    <!-- Paso final: confirmación en estado SOLICITADA -->
    <div v-if="result" class="text-center" role="status">
      <span class="mx-auto grid size-14 place-items-center rounded-full bg-ok-bg text-ok">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12l5 5 9-10" /></svg>
      </span>
      <h2 class="mt-3 text-xl font-bold text-navy-darkest">{{ t('booking.done') }}</h2>
      <p class="mt-1 text-sm text-muted">{{ t('booking.doneBody') }}</p>
      <p class="mt-3 text-sm font-medium text-ink">{{ fmtDate(result.fecha_reserva, locale) }} · {{ t('my.people', { n: result.numero_personas }, result.numero_personas) }}</p>
      <div class="mt-4 rounded-card border border-warn/30 bg-warn-bg px-4 py-3">
        <p class="font-mono text-[10px] uppercase tracking-[.14em] text-warn">{{ t('booking.left') }}</p>
        <p class="mt-1 text-2xl font-bold text-warn"><Countdown :until="result.expira_en" /></p>
      </div>
      <div class="mt-5 flex flex-col gap-2">
        <RouterLink :to="{ name: 'my-bookings' }" class="rounded-full bg-navy px-5 py-3 text-sm font-semibold text-white shadow-cta hover:bg-blue">{{ t('booking.mine') }}</RouterLink>
        <button type="button" class="rounded-full px-5 py-2.5 text-sm font-medium text-navy hover:bg-cream" @click="again">{{ t('booking.another') }}</button>
      </div>
    </div>

    <template v-else>
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-bold text-navy-darkest">{{ t('booking.title') }}</h2>
        <span class="font-mono text-[11px] text-muted">{{ t('booking.step', { n: step }) }}</span>
      </div>
      <ol class="mt-3 flex gap-1.5" aria-hidden="true">
        <li v-for="i in 4" :key="i" class="h-1.5 flex-1 rounded-full transition-colors" :class="i <= step ? 'bg-teal' : 'bg-border-input'" />
      </ol>
      <p class="mt-3 text-sm font-semibold text-navy">{{ step }}. {{ stepName }}</p>

      <p v-if="!queue.online" class="mt-3 rounded-xl bg-warn-bg px-3 py-2 text-sm text-warn">{{ t('booking.needOnline') }}</p>

      <fieldset :disabled="!queue.online || sending" class="mt-4 min-w-0">
        <!-- 1. Fecha -->
        <div v-if="step === 1">
          <p class="mb-3 text-sm text-muted">{{ t('booking.pickDate') }}. {{ t('booking.fromTomorrow') }}</p>
          <p v-if="loading" class="py-10 text-center text-sm text-muted">{{ t('booking.loading') }}</p>
          <p v-else-if="loadError" class="py-6 text-center text-sm text-danger">{{ loadError }}</p>
          <BookingCalendar v-else :days="days" :model-value="date" :from="from" :to="to" @update:model-value="pickDate" />
          <p v-if="day" class="mt-3 font-mono text-xs text-ink-control">{{ fmtDate(date, locale) }} · {{ t('booking.cupos', { n: day.cupos_disponibles }) }} · {{ cop(rate) }}</p>
        </div>

        <!-- 2. Personas -->
        <div v-else-if="step === 2">
          <p class="text-sm text-ink-control">{{ t('booking.people') }}</p>
          <div class="mt-3 flex items-center justify-center gap-5">
            <button type="button" class="grid size-12 place-items-center rounded-full border border-border-input text-2xl text-ink-control hover:border-teal disabled:opacity-30" :disabled="people <= 1" aria-label="−" @click="people--">−</button>
            <output class="w-16 text-center text-4xl font-bold tabular-nums text-navy-darkest" aria-live="polite">{{ people }}</output>
            <button type="button" class="grid size-12 place-items-center rounded-full border border-border-input text-2xl text-ink-control hover:border-teal disabled:opacity-30" :disabled="people >= maxPeople" aria-label="+" @click="people++">+</button>
          </div>
          <p class="mt-3 text-center text-xs text-muted">{{ t('booking.maxPeople', { n: maxPeople }) }}</p>
          <p class="mt-4 rounded-xl bg-cream px-4 py-3 text-center text-sm text-ink-control">{{ t('booking.refTotal') }}: <b class="tabular-nums">{{ cop(rate * people) }}</b></p>
        </div>

        <!-- 3. Resumen -->
        <div v-else-if="step === 3">
          <p class="text-sm font-semibold text-ink">{{ t('booking.summary') }}</p>
          <dl class="mt-3 divide-y divide-sand/30 rounded-card border border-sand/30 bg-cream text-sm">
            <div class="flex justify-between gap-3 px-4 py-2.5"><dt class="text-muted">{{ t('booking.date') }}</dt><dd class="text-right font-medium first-letter:uppercase">{{ fmtDate(date, locale) }}</dd></div>
            <div class="flex justify-between gap-3 px-4 py-2.5"><dt class="text-muted">{{ t('booking.persons') }}</dt><dd class="font-medium">{{ people }}</dd></div>
            <div class="flex justify-between gap-3 px-4 py-2.5"><dt class="text-muted">{{ t('booking.rate') }}</dt><dd class="font-medium tabular-nums">{{ cop(rate) }}</dd></div>
          </dl>
          <ul class="mt-3 space-y-1.5 text-[13px] leading-snug text-ink-control">
            <li><b>{{ t('booking.free') }}</b> {{ t('booking.payDirect') }}</li>
            <li>{{ t('booking.respond') }}</li>
          </ul>
        </div>

        <!-- 4. Enviar -->
        <div v-else>
          <p class="text-sm font-semibold text-ink">{{ fmtDate(date, locale) }} · {{ t('my.people', { n: people }, people) }}</p>
          <p class="mt-2 text-[13px] leading-snug text-muted">{{ t('booking.payDirect') }}</p>
          <p v-if="isMock" class="mt-2 font-mono text-[11px] text-muted/80">{{ t('my.demo') }}</p>
        </div>
      </fieldset>

      <p v-if="error" class="mt-3 rounded-xl bg-danger-bg px-3 py-2 text-sm text-danger" role="alert">{{ error }}</p>

      <div class="mt-5 flex gap-2">
        <button v-if="step > 1" type="button" class="rounded-full border border-border-input px-5 py-3 text-sm font-medium text-ink-control hover:border-teal" :disabled="sending" @click="step--; error = ''">{{ t('booking.back') }}</button>
        <button v-if="step < 4" type="button" class="flex-1 rounded-full bg-navy px-5 py-3 text-sm font-semibold text-white shadow-cta transition hover:bg-blue disabled:opacity-40 disabled:shadow-none" :disabled="!canNext || !queue.online" @click="step++">{{ t('booking.next') }}</button>
        <button v-else type="button" class="flex-1 rounded-full bg-navy px-5 py-3 text-sm font-semibold text-white shadow-cta transition hover:bg-blue disabled:opacity-40" :disabled="sending || !queue.online" @click="send">{{ sending ? t('booking.sending') : t('booking.send') }}</button>
      </div>
    </template>
  </section>
</template>
