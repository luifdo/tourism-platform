<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { offerUseCases } from '../../composition'
import { ultimosDias } from '../../domain/gestion/rules'
import { useGestion } from '../../ui/useGestion'
import EstadoCarga from '../shared/EstadoCarga.vue'
import Estrellas from '../reviews/Estrellas.vue'

/* UC22 · Métricas de mi oferta: reservas por estado, personas atendidas, ocupación, calificación e intenciones de visita ("Cómo llegar"). */
const { t, n } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()

const rango = reactive(ultimosDias(new Date(), 30))
const datos = ref(null)
const cargando = ref(true)
const error = ref('')

async function cargar() {
  cargando.value = true; error.value = ''
  try { datos.value = await offerUseCases.metricas({ desde: rango.desde, hasta: rango.hasta }) }
  catch (e) {
    if (sesionVencida(e)) return
    error.value = camposDe(e).desde ?? mensaje(e, 'metricas')
  } finally { cargando.value = false }
}
onMounted(cargar)
const atajo = (dias) => { Object.assign(rango, ultimosDias(new Date(), dias)); cargar() }
const pct = (v) => n(v, { style: 'percent', maximumFractionDigits: 0 })
const totales = computed(() => (datos.value?.servicios ?? []).reduce((a, s) => ({
  reservas: a.reservas + s.reservas.confirmadas + s.reservas.finalizadas, personas: a.personas + s.personas_finalizadas, intenciones: a.intenciones + s.intenciones_visita, pendientes: a.pendientes + s.reservas.solicitadas,
}), { reservas: 0, personas: 0, intenciones: 0, pendientes: 0 }))
const ESTADOS = ['solicitadas', 'confirmadas', 'finalizadas', 'canceladas', 'rechazadas']
</script>

<template>
  <section aria-labelledby="h-met">
    <h2 id="h-met" class="text-lg font-bold text-navy-darkest">{{ t('metricas.title') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('metricas.lead') }}</p>

    <form class="mt-4 flex flex-wrap items-end gap-3" @submit.prevent="cargar">
      <label><span class="campo-etiqueta">{{ t('gestion.from') }}</span><input v-model="rango.desde" type="date" class="campo-input" required /></label>
      <label><span class="campo-etiqueta">{{ t('gestion.to') }}</span><input v-model="rango.hasta" type="date" class="campo-input" required /></label>
      <button type="submit" class="btn-primario">{{ t('gestion.apply') }}</button>
      <div class="flex gap-2 text-sm"><button type="button" class="btn-secundario !py-1.5" @click="atajo(7)">7 {{ t('gestion.days') }}</button><button type="button" class="btn-secundario !py-1.5" @click="atajo(30)">30 {{ t('gestion.days') }}</button><button type="button" class="btn-secundario !py-1.5" @click="atajo(90)">90 {{ t('gestion.days') }}</button></div>
    </form>

    <div class="mt-5">
      <EstadoCarga :cargando="cargando" :error="error" :vacio="!!datos && !datos.servicios.length" :texto-vacio="t('metricas.empty')" alto="h-48" @reintentar="cargar">
        <template v-if="datos">
          <dl class="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <div class="tarjeta !p-4"><dt class="campo-etiqueta">{{ t('metricas.bookings') }}</dt><dd class="mt-1 text-3xl font-bold tabular-nums text-navy-darkest">{{ totales.reservas }}</dd></div>
            <div class="tarjeta !p-4"><dt class="campo-etiqueta">{{ t('metricas.people') }}</dt><dd class="mt-1 text-3xl font-bold tabular-nums text-navy-darkest">{{ totales.personas }}</dd></div>
            <div class="tarjeta !p-4"><dt class="campo-etiqueta">{{ t('metricas.pending') }}</dt><dd class="mt-1 text-3xl font-bold tabular-nums text-navy-darkest">{{ totales.pendientes }}</dd></div>
            <div class="tarjeta !p-4"><dt class="campo-etiqueta">{{ t('metricas.intents') }}</dt><dd class="mt-1 text-3xl font-bold tabular-nums text-navy-darkest">{{ totales.intenciones }}</dd></div>
          </dl>

          <div class="mt-5 overflow-x-auto rounded-card border border-sand/30 bg-white shadow-card">
            <table class="w-full min-w-[720px] text-left text-sm">
              <caption class="sr-only">{{ t('metricas.title') }}</caption>
              <thead class="bg-cream font-mono text-[10px] uppercase tracking-[.12em] text-muted">
                <tr>
                  <th scope="col" class="px-4 py-3">{{ t('metricas.service') }}</th>
                  <th v-for="e in ESTADOS" :key="e" scope="col" class="px-3 py-3 text-right">{{ t(`metricas.states.${e}`) }}</th>
                  <th scope="col" class="px-3 py-3 text-right">{{ t('metricas.occupancy') }}</th>
                  <th scope="col" class="px-3 py-3">{{ t('metricas.rating') }}</th>
                  <th scope="col" class="px-3 py-3 text-right">{{ t('metricas.intents') }}</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-sand/20">
                <tr v-for="s in datos.servicios" :key="s.servicio_id">
                  <th scope="row" class="px-4 py-3 font-medium text-navy-darkest">{{ s.nombre }}</th>
                  <td v-for="e in ESTADOS" :key="e" class="px-3 py-3 text-right tabular-nums">{{ s.reservas[e] }}</td>
                  <td class="px-3 py-3 text-right tabular-nums">{{ pct(s.ocupacion) }}</td>
                  <td class="px-3 py-3"><span v-if="s.calificacion_promedio" class="inline-flex items-center gap-1.5"><Estrellas :valor="s.calificacion_promedio" :tamano="13" /><span class="tabular-nums text-xs text-muted">{{ s.calificacion_promedio.toFixed(1) }} ({{ s.total_resenas }})</span></span><span v-else class="text-muted">—</span></td>
                  <td class="px-3 py-3 text-right tabular-nums">{{ s.intenciones_visita }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p class="mt-3 text-xs text-muted">{{ t('metricas.note') }}</p>
        </template>
      </EstadoCarga>
    </div>
  </section>
</template>
