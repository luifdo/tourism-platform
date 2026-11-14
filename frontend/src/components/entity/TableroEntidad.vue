<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { entityUseCases } from '../../composition'
import { ultimosDias } from '../../domain/gestion/rules'
import { useGestion } from '../../ui/useGestion'
import EstadoCarga from '../shared/EstadoCarga.vue'
import MapaCalor from './MapaCalor.vue'

/* UC25 tablero de planificación (reúne UC23 y UC24) y RF-07 mapa de calor. Los datos de capacidad se calculan al consultar y llevan su hora (`calculado_en`). */
const { t, n, locale } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()

const rango = reactive(ultimosDias(new Date(), 30))
const datos = ref(null)
const calor = ref(null)
const cargando = ref(true)
const error = ref('')

async function cargar() {
  cargando.value = true; error.value = ''
  try {
    const [d, c] = await Promise.all([entityUseCases.tablero({ ...rango, idioma: locale.value }), entityUseCases.mapaCalor({ idioma: locale.value })])
    datos.value = d; calor.value = c
  } catch (e) { if (!sesionVencida(e)) error.value = camposDe(e).desde ?? mensaje(e, 'entidad') } finally { cargando.value = false }
}
onMounted(cargar)

const NIVEL = { BAJO: 'bg-ok-bg text-ok', MEDIO: 'bg-warn-bg text-warn', ALTO: 'bg-danger-bg text-danger' }
const BARRA = { BAJO: 'bg-ok', MEDIO: 'bg-warn', ALTO: 'bg-danger' }
const totalPersonas = computed(() => (datos.value ? datos.value.totales.personas_solicitadas + datos.value.totales.personas_confirmadas + datos.value.totales.personas_finalizadas : 0))
const hora = computed(() => { const c = datos.value?.capacidad_hoy?.find((x) => x.calculado_en)?.calculado_en; return c ? new Intl.DateTimeFormat(locale.value, { timeStyle: 'short' }).format(new Date(c)) : '' })
</script>

<template>
  <section aria-labelledby="h-tab">
    <h2 id="h-tab" class="text-lg font-bold text-navy-darkest">{{ t('entidad.dashboardTitle') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('entidad.dashboardLead') }}</p>
    <form class="mt-4 flex flex-wrap items-end gap-3" @submit.prevent="cargar">
      <label><span class="campo-etiqueta">{{ t('gestion.from') }}</span><input v-model="rango.desde" type="date" class="campo-input" required /></label>
      <label><span class="campo-etiqueta">{{ t('gestion.to') }}</span><input v-model="rango.hasta" type="date" class="campo-input" required /></label>
      <button type="submit" class="btn-primario">{{ t('gestion.apply') }}</button>
    </form>

    <div class="mt-5">
      <EstadoCarga :cargando="cargando" :error="error" alto="h-56" @reintentar="cargar">
        <template v-if="datos">
          <dl class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div class="tarjeta !p-4"><dt class="campo-etiqueta">{{ t('entidad.kpi.people') }}</dt><dd class="mt-1 text-3xl font-bold tabular-nums text-navy-darkest">{{ n(totalPersonas) }}</dd></div>
            <div class="tarjeta !p-4"><dt class="campo-etiqueta">{{ t('entidad.kpi.confirmed') }}</dt><dd class="mt-1 text-3xl font-bold tabular-nums text-navy-darkest">{{ n(datos.totales.personas_confirmadas) }}</dd></div>
            <div class="tarjeta !p-4"><dt class="campo-etiqueta">{{ t('entidad.kpi.cancelled') }}</dt><dd class="mt-1 text-3xl font-bold tabular-nums text-navy-darkest">{{ n(datos.totales.personas_canceladas) }}</dd></div>
            <div class="tarjeta !p-4"><dt class="campo-etiqueta">{{ t('entidad.kpi.alerts') }}</dt><dd class="mt-1 text-3xl font-bold tabular-nums text-navy-darkest">{{ datos.alertas_vigentes }}</dd></div>
          </dl>

          <div class="mt-6 grid gap-6 lg:grid-cols-2">
            <div>
              <h3 class="font-bold text-navy-darkest">{{ t('entidad.capacityToday') }}</h3>
              <p class="text-xs text-muted">{{ t('entidad.capacityNote', { hora }) }}</p>
              <ul class="mt-3 space-y-2.5">
                <li v-for="c in datos.capacidad_hoy" :key="c.zona.codigo" class="tarjeta !p-3.5">
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <span class="font-semibold text-navy-darkest">{{ c.zona.nombre }}</span>
                    <span class="pildora" :class="NIVEL[c.nivel]">{{ c.nivel_etiqueta ?? c.nivel }}</span>
                  </div>
                  <div v-if="c.indice != null" class="mt-2 flex items-center gap-3 text-xs text-muted">
                    <span class="h-2 flex-1 overflow-hidden rounded-full bg-cream"><span class="block h-full rounded-full" :class="BARRA[c.nivel]" :style="{ width: Math.min(100, Math.round(c.indice * 100)) + '%' }" /></span>
                    <span class="tabular-nums">{{ Math.round(c.indice * 100) }} % · {{ c.personas_activas }}/{{ c.capacidad }}</span>
                  </div>
                  <p v-if="c.servicios_con_bandera?.length" class="mt-1.5 text-xs text-warn">{{ t('entidad.flagged', { lista: c.servicios_con_bandera.map((s) => s.nombre).join(', ') }) }}</p>
                </li>
              </ul>
            </div>
            <div>
              <h3 class="font-bold text-navy-darkest">{{ t('entidad.topZones') }}</h3>
              <ol class="mt-3 space-y-2">
                <li v-for="(z, i) in datos.zonas_mas_demandadas" :key="z.zona.codigo" class="tarjeta flex items-center gap-3 !p-3.5">
                  <span class="grid size-7 shrink-0 place-items-center rounded-full bg-navy text-xs font-bold text-white" aria-hidden="true">{{ i + 1 }}</span>
                  <span class="min-w-0 flex-1 truncate font-medium text-navy-darkest">{{ z.zona.nombre }}</span>
                  <span class="text-right text-xs text-muted"><b class="block text-sm tabular-nums text-ink">{{ n(z.personas) }}</b>{{ t('entidad.intents', { n: z.intenciones_visita ?? 0 }) }}</span>
                </li>
              </ol>
            </div>
          </div>

          <h3 class="mt-8 font-bold text-navy-darkest">{{ t('entidad.heatMap') }}</h3>
          <p class="mb-3 text-xs text-muted">{{ t('entidad.heatMapNote') }}</p>
          <MapaCalor :geojson="calor" />
        </template>
      </EstadoCarga>
    </div>
  </section>
</template>
