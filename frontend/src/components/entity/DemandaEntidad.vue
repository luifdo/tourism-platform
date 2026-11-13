<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { entityUseCases } from '../../composition'
import { CATEGORIAS } from '../../domain/catalog/rules'
import { ultimosDias } from '../../domain/gestion/rules'
import { useGestion } from '../../ui/useGestion'
import EstadoCarga from '../shared/EstadoCarga.vue'
import SerieBarras from './SerieBarras.vue'

/* UC23 · Indicadores de demanda (personas por fecha de la visita, según el estado actual de su reserva) y las intenciones de visita ("Cómo llegar"), que son un indicador aparte. */
const { t, n, locale } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()

const f = reactive({ ...ultimosDias(new Date(), 30), zona: '', categoria: '', agrupacion: 'dia' })
const zonas = ref([])
const demanda = ref(null)
const intenciones = ref([])
const cargando = ref(true)
const error = ref('')

async function cargar() {
  cargando.value = true; error.value = ''
  try {
    const filtros = { desde: f.desde, hasta: f.hasta, zona: f.zona || undefined }
    const [d, i] = await Promise.all([entityUseCases.demanda({ ...filtros, categoria: f.categoria || undefined, agrupacion: f.agrupacion }), entityUseCases.intenciones(filtros)])
    demanda.value = d; intenciones.value = i
  } catch (e) { if (!sesionVencida(e)) error.value = camposDe(e).desde ?? mensaje(e, 'entidad') } finally { cargando.value = false }
}
onMounted(async () => { zonas.value = await entityUseCases.zonas(locale.value).catch(() => []); cargar() })

const sum = (k) => (demanda.value?.serie ?? []).reduce((s, p) => s + p[k], 0)
const porZona = computed(() => {
  const m = new Map()
  for (const i of intenciones.value) m.set(i.zona, (m.get(i.zona) ?? 0) + i.intenciones)
  return [...m].map(([zona, total]) => ({ zona: zonas.value.find((z) => z.codigo === zona)?.nombre ?? zona, total })).sort((a, b) => b.total - a.total)
})
const fecha = (iso) => new Intl.DateTimeFormat(locale.value, { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${iso}T12:00:00Z`))
</script>

<template>
  <section aria-labelledby="h-dem">
    <h2 id="h-dem" class="text-lg font-bold text-navy-darkest">{{ t('entidad.demandTitle') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('entidad.demandLead') }}</p>
    <form class="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5" @submit.prevent="cargar">
      <label><span class="campo-etiqueta">{{ t('gestion.from') }}</span><input v-model="f.desde" type="date" class="campo-input" required /></label>
      <label><span class="campo-etiqueta">{{ t('gestion.to') }}</span><input v-model="f.hasta" type="date" class="campo-input" required /></label>
      <label><span class="campo-etiqueta">{{ t('entidad.zone') }}</span><select v-model="f.zona" class="campo-input"><option value="">{{ t('entidad.allZones') }}</option><option v-for="z in zonas" :key="z.codigo" :value="z.codigo">{{ z.nombre }}</option></select></label>
      <label><span class="campo-etiqueta">{{ t('entidad.category') }}</span><select v-model="f.categoria" class="campo-input"><option value="">{{ t('gestion.all') }}</option><option v-for="c in CATEGORIAS" :key="c" :value="c">{{ t(`explorer.filters.${c}`) }}</option></select></label>
      <label><span class="campo-etiqueta">{{ t('entidad.groupBy') }}</span><select v-model="f.agrupacion" class="campo-input"><option v-for="a in ['dia', 'semana', 'mes']" :key="a" :value="a">{{ t(`entidad.groups.${a}`) }}</option></select></label>
      <div class="sm:col-span-2 lg:col-span-5"><button type="submit" class="btn-primario">{{ t('gestion.apply') }}</button></div>
    </form>

    <div class="mt-5">
      <EstadoCarga :cargando="cargando" :error="error" :vacio="!!demanda && !demanda.serie.length" alto="h-56" @reintentar="cargar">
        <template v-if="demanda">
          <dl class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div v-for="k in ['personas_solicitadas', 'personas_confirmadas', 'personas_finalizadas', 'personas_canceladas']" :key="k" class="tarjeta !p-4"><dt class="campo-etiqueta">{{ t(`entidad.series.${k}`) }}</dt><dd class="mt-1 text-3xl font-bold tabular-nums text-navy-darkest">{{ n(sum(k)) }}</dd></div>
          </dl>
          <div class="tarjeta mt-5"><SerieBarras :serie="demanda.serie" :agrupacion="f.agrupacion" /></div>

          <details class="mt-4 rounded-card border border-sand/30 bg-white">
            <summary class="cursor-pointer px-4 py-3 text-sm font-medium text-navy">{{ t('entidad.showTable') }}</summary>
            <div class="max-h-96 overflow-auto"><table class="w-full text-left text-sm">
              <thead class="sticky top-0 bg-cream font-mono text-[10px] uppercase tracking-[.12em] text-muted"><tr><th scope="col" class="px-4 py-2">{{ t('entidad.period') }}</th><th v-for="k in ['personas_solicitadas', 'personas_confirmadas', 'personas_finalizadas', 'personas_canceladas']" :key="k" scope="col" class="px-3 py-2 text-right">{{ t(`entidad.series.${k}`) }}</th></tr></thead>
              <tbody class="divide-y divide-sand/20"><tr v-for="p in demanda.serie" :key="p.periodo"><th scope="row" class="px-4 py-2 font-medium tabular-nums">{{ fecha(p.periodo) }}</th><td class="px-3 py-2 text-right tabular-nums">{{ p.personas_solicitadas }}</td><td class="px-3 py-2 text-right tabular-nums">{{ p.personas_confirmadas }}</td><td class="px-3 py-2 text-right tabular-nums">{{ p.personas_finalizadas }}</td><td class="px-3 py-2 text-right tabular-nums">{{ p.personas_canceladas }}</td></tr></tbody>
            </table></div>
          </details>

          <h3 class="mt-8 font-bold text-navy-darkest">{{ t('entidad.intentsTitle') }}</h3>
          <p class="text-xs text-muted">{{ t('entidad.intentsNote') }}</p>
          <p v-if="!porZona.length" class="mt-3 text-sm text-muted">{{ t('entidad.intentsEmpty') }}</p>
          <ul v-else class="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3"><li v-for="z in porZona" :key="z.zona" class="tarjeta flex items-center justify-between !p-3.5"><span class="font-medium text-navy-darkest">{{ z.zona }}</span><b class="tabular-nums">{{ n(z.total) }}</b></li></ul>
        </template>
      </EstadoCarga>
    </div>
  </section>
</template>
