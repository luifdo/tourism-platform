<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { addDays, daysInMonth, monthKey, weekday } from '../domain/booking/dates'
import { estadoDia } from '../domain/booking/rules'
import { fmtDate } from '../ui/format'

// Calendario de un servicio: marca cada día con los cupos de GET /disponibilidad (UC10)
const props = defineProps({ days: { type: Array, default: () => [] }, modelValue: String, from: String, to: String })
const emit = defineEmits(['update:modelValue'])
const { t, locale } = useI18n()

const byDate = computed(() => new Map(props.days.map((d) => [d.fecha, d])))
const cursor = ref(monthKey(props.from))
watch(() => props.from, (f) => { cursor.value = monthKey(f) })

const first = computed(() => monthKey(props.from))
const last = computed(() => monthKey(props.to))
const title = computed(() => {
  const s = new Intl.DateTimeFormat(locale.value, { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${cursor.value}-01T12:00:00Z`))
  return s.charAt(0).toUpperCase() + s.slice(1)
})
const dow = computed(() => Array.from({ length: 7 }, (_, i) => fmtDate(addDays('2026-11-02', i), locale.value, { weekday: 'narrow' })))

const cells = computed(() => {
  const lead = weekday(`${cursor.value}-01`) - 1
  const out = Array.from({ length: lead }, () => null)
  for (let d = 1; d <= daysInMonth(cursor.value); d++) {
    const fecha = `${cursor.value}-${String(d).padStart(2, '0')}`
    const info = byDate.value.get(fecha)
    // La regla (fuera de rango / sin operación / agotado / disponible) vive en el dominio
    const state = { fuera: 'out', cerrado: 'closed', agotado: 'soldout', ok: 'ok' }[estadoDia(fecha, info, { desde: props.from, hasta: props.to })]
    out.push({ fecha, d, state, cupos: info?.cupos_disponibles ?? 0 })
  }
  return out
})

function shift(n) {
  const [y, m] = cursor.value.split('-').map(Number)
  const date = new Date(Date.UTC(y, m - 1 + n, 1))
  cursor.value = date.toISOString().slice(0, 7)
}
</script>

<template>
  <div>
    <div class="flex items-center justify-between">
      <button type="button" class="grid size-9 place-items-center rounded-full border border-border-input text-ink-control hover:border-teal disabled:opacity-30" :disabled="cursor <= first" aria-label="‹" @click="shift(-1)">‹</button>
      <p class="text-sm font-semibold text-navy-darkest">{{ title }}</p>
      <button type="button" class="grid size-9 place-items-center rounded-full border border-border-input text-ink-control hover:border-teal disabled:opacity-30" :disabled="cursor >= last" aria-label="›" @click="shift(1)">›</button>
    </div>
    <div class="mt-3 grid grid-cols-7 gap-1 text-center font-mono text-[10px] uppercase text-muted">
      <span v-for="(w, i) in dow" :key="i">{{ w }}</span>
    </div>
    <div class="mt-1 grid grid-cols-7 gap-1">
      <template v-for="(c, i) in cells" :key="i">
        <span v-if="!c" />
        <button
          v-else type="button"
          :disabled="c.state !== 'ok'"
          @click="emit('update:modelValue', c.fecha)"
          :aria-pressed="modelValue === c.fecha"
          :aria-label="`${fmtDate(c.fecha, locale)} · ${c.state === 'ok' ? t('booking.cupos', { n: c.cupos }) : c.state === 'soldout' ? t('booking.soldOut') : t('booking.closed')}`"
          class="flex aspect-square flex-col items-center justify-center rounded-xl border text-sm transition"
          :class="[
            modelValue === c.fecha ? 'border-navy bg-navy text-white shadow-cta' : '',
            c.state === 'ok' && modelValue !== c.fecha ? 'border-border-input bg-white text-ink hover:border-teal' : '',
            c.state === 'soldout' ? 'border-transparent bg-danger-bg/60 text-danger/70' : '',
            c.state === 'closed' || c.state === 'out' ? 'border-transparent text-muted/40' : '',
          ]"
        >
          <span class="font-medium leading-none">{{ c.d }}</span>
          <span v-if="c.state === 'ok'" class="mt-0.5 font-mono text-[9px] leading-none" :class="modelValue === c.fecha ? 'text-white/80' : c.cupos <= 3 ? 'text-warn' : 'text-ok'">{{ c.cupos }}</span>
        </button>
      </template>
    </div>
  </div>
</template>
