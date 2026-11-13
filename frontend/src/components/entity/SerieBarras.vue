<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

/*
 * Barras apiladas de la demanda por periodo (UC23): solicitadas, confirmadas y finalizadas. Las canceladas no suman a la
 * presión sobre el destino y van solo en la tabla. Es un gráfico hecho a mano en SVG (sin librería) y va acompañado de la tabla.
 */
const props = defineProps({ serie: { type: Array, required: true }, agrupacion: { type: String, default: 'dia' } })
const { t, locale } = useI18n()
const CAPAS = [['personas_finalizadas', '#009767'], ['personas_confirmadas', '#006798'], ['personas_solicitadas', '#F99C00']]
const W = 720; const H = 220; const M = { t: 10, r: 8, b: 26, l: 40 }

const total = (p) => CAPAS.reduce((s, [k]) => s + p[k], 0)
const max = computed(() => Math.max(1, ...props.serie.map(total)))
const techo = computed(() => { const m = max.value; const p = 10 ** Math.floor(Math.log10(m)); return Math.ceil(m / p) * p })
const ancho = computed(() => (W - M.l - M.r) / Math.max(1, props.serie.length))
const y = (v) => M.t + (H - M.t - M.b) * (1 - v / techo.value)
const barras = computed(() => props.serie.map((p, i) => {
  let acum = 0
  return { p, x: M.l + i * ancho.value + ancho.value * 0.12, w: ancho.value * 0.76, capas: CAPAS.map(([k, c]) => { const v = p[k]; const r = { y: y(acum + v), h: y(acum) - y(acum + v), c }; acum += v; return r }) }
}))
const marcas = computed(() => [0, 0.5, 1].map((f) => Math.round(techo.value * f)))
const paso = computed(() => Math.max(1, Math.ceil(props.serie.length / 8)))
const rotulo = (iso) => new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(`${iso}T12:00:00Z`))
</script>

<template>
  <figure>
    <svg :viewBox="`0 0 ${W} ${H}`" class="h-auto w-full" role="img" :aria-label="t('entidad.chartLabel')">
      <g v-for="m in marcas" :key="m"><line :x1="M.l" :x2="W - M.r" :y1="y(m)" :y2="y(m)" stroke="#C7A781" stroke-opacity=".3" /><text :x="M.l - 6" :y="y(m) + 4" text-anchor="end" font-size="11" fill="#536F79">{{ m }}</text></g>
      <g v-for="(b, i) in barras" :key="b.p.periodo">
        <rect v-for="(c, j) in b.capas" :key="j" :x="b.x" :y="c.y" :width="b.w" :height="Math.max(0, c.h)" :fill="c.c"><title>{{ rotulo(b.p.periodo) }}: {{ total(b.p) }}</title></rect>
        <text v-if="i % paso === 0" :x="b.x + b.w / 2" :y="H - 8" text-anchor="middle" font-size="10.5" fill="#536F79">{{ rotulo(b.p.periodo) }}</text>
      </g>
    </svg>
    <figcaption class="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-control">
      <span v-for="[k, c] in [...CAPAS].reverse()" :key="k" class="inline-flex items-center gap-1.5"><span class="size-2.5 rounded-sm" :style="{ background: c }" />{{ t(`entidad.series.${k}`) }}</span>
    </figcaption>
  </figure>
</template>
