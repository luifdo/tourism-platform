<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { providerUseCases } from '../../composition'
import { BookingError } from '../../domain/booking/errors'
import { addDays, today, tomorrow } from '../../domain/booking/dates'
import { DIAS_SEMANA, MAX_DIAS_RANGO, diasDelRango, resumenCalendario, validarDia, validarRango, ventanaCalendario } from '../../domain/booking/prestador'
import { useOnline } from '../../ui/useOnline'
import { useSession } from '../../ui/useSession'
import { fmtDate } from '../../ui/format'

/*
 * UC19 · Calendario de cupos y tarifas de un servicio. Un día que no existe (o tiene 0 cupos) no se ofrece al turista.
 * Editar un día lleva la versión que se vio (If-Match): si cambió en el servidor se muestra tu cambio frente a lo que hay ahora.
 * Necesita conexión. Capa UI: presenta y llama a los casos de uso; las reglas viven en domain/booking/prestador.js.
 */
const props = defineProps({ servicios: { type: Array, required: true } })
const { t, n, te, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { expirar } = useSession()
const enLinea = useOnline()

const servicioId = ref(props.servicios[0]?.id ?? '')
const servicio = computed(() => props.servicios.find((s) => s.id === servicioId.value))
const aforo = computed(() => servicio.value?.capacidadDiaria ?? undefined)
const ventana = reactive(ventanaCalendario(new Date(), 30))
const dias = ref([])
const cargando = ref(false)
const errorCarga = ref('')
const aviso = ref('')
const resumen = computed(() => resumenCalendario(dias.value))

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)
const textoError = (e) => {
  const c = e instanceof BookingError ? e.code : 'generic'
  return t(`provider.errors.${te(`provider.errors.${c}`) ? c : 'generic'}`, { aforo: aforo.value ?? '' })
}
// Error de un campo validado en el cliente: { campo, codigo } -> texto
const textoCampo = (e) => t(`provider.fieldErrors.${te(`provider.fieldErrors.${e.codigo}`) ? e.codigo : 'generic'}`, { aforo: aforo.value ?? '', max: MAX_DIAS_RANGO })

function sesionVencida(e) {
  if (!(e instanceof BookingError) || e.code !== 'NO_AUTENTICADO') return false
  expirar()
  router.replace({ name: 'login', query: { redirect: route.fullPath, expirada: '1' } })
  return true
}

async function cargar() {
  if (!servicioId.value) return
  cargando.value = true; errorCarga.value = ''
  try { dias.value = (await providerUseCases.calendario(servicioId.value, { desde: ventana.desde, hasta: ventana.hasta })).dias }
  catch (e) { if (!sesionVencida(e)) errorCarga.value = textoError(e) }
  finally { cargando.value = false }
}
onMounted(cargar)
watch([servicioId, () => ventana.desde, () => ventana.hasta], cargar)
const ampliar = () => { ventana.hasta = addDays(ventana.hasta, 30) }

/* ---------------- Editar (o crear) un día ---------------- */
const edicion = ref(null) // { fecha, cupos, tarifa, version|null, reservados, clave, guardando, errores, error, conflicto }
const nuevoDia = reactive({ fecha: tomorrow(new Date()) })

const abrirEdicion = (d) => {
  edicion.value = { fecha: d.fecha, cupos: d.cupos_totales, tarifa: d.tarifa_dia ?? '', version: d.version, reservados: d.cupos_reservados, clave: uid(), guardando: false, errores: [], error: '', conflicto: null }
  aviso.value = ''
}
const abrirCreacion = () => {
  if (!nuevoDia.fecha) return
  edicion.value = { fecha: nuevoDia.fecha, cupos: aforo.value ?? 1, tarifa: '', version: null, reservados: 0, clave: uid(), guardando: false, errores: [], error: '', conflicto: null }
  aviso.value = ''
}
const tarifaNum = (v) => (v === '' || v == null ? null : Number(v))

async function guardar(versionForzada) {
  const e = edicion.value
  e.errores = []; e.error = ''
  const version = versionForzada ?? e.version
  const datos = { cuposTotales: Number(e.cupos), tarifaDia: tarifaNum(e.tarifa) }
  const errores = validarDia(datos, { reservados: e.reservados, aforo: aforo.value })
  if (errores.length) { e.errores = errores; return }
  e.guardando = true
  try {
    const { dia, creado } = await providerUseCases.guardarDia(servicioId.value, e.fecha, datos, { version, reservados: e.reservados, aforo: aforo.value, idempotencyKey: e.clave })
    dias.value = [...dias.value.filter((d) => d.fecha !== dia.fecha), dia].sort((a, b) => a.fecha.localeCompare(b.fecha))
    aviso.value = creado ? t('provider.dayCreated', { fecha: fmtDate(dia.fecha, locale.value) }) : t('provider.daySaved', { fecha: fmtDate(dia.fecha, locale.value) })
    edicion.value = null
  } catch (err) {
    if (sesionVencida(err)) return
    if (err instanceof BookingError && err.code === 'VERSION_DISTINTA' && err.data?.actual) e.conflicto = { version: err.data.version_actual, actual: err.data.actual, mio: datos }
    else if (err.campos) e.errores = err.campos
    else e.error = textoError(err)
    // Un intento nuevo (otra clave): la anterior ya devolvió su respuesta (conflicto o error)
    e.clave = uid()
  } finally { e.guardando = false }
}
// "Usar mi cambio": se reenvía con la versión que hay ahora en el servidor
const insistir = () => guardar(edicion.value.conflicto.version)
const aceptarActual = () => {
  const a = edicion.value.conflicto.actual
  dias.value = dias.value.map((d) => (d.fecha === a.fecha ? a : d))
  edicion.value = null
  aviso.value = t('provider.keptServer')
}

/* ---------------- Abrir un rango ---------------- */
const rango = reactive({ desde: tomorrow(new Date()), hasta: addDays(tomorrow(new Date()), 29), diasSemana: [...DIAS_SEMANA], cupos: aforo.value ?? 1, tarifa: '' })
watch(aforo, (a) => { if (a && (!rango.cupos || rango.cupos > a)) rango.cupos = a })
const alternarDia = (d) => { rango.diasSemana = rango.diasSemana.includes(d) ? rango.diasSemana.filter((x) => x !== d) : [...rango.diasSemana, d].sort() }
const previsualizacion = computed(() => diasDelRango({ desde: rango.desde, hasta: rango.hasta, diasSemana: rango.diasSemana.length === 7 ? undefined : rango.diasSemana }).length)
const rangoState = reactive({ guardando: false, errores: [], error: '', resultado: null, clave: uid() })
watch(rango, () => { rangoState.clave = uid() }, { deep: true }) // un intento nuevo del usuario = una clave nueva

async function abrirRango() {
  rangoState.errores = []; rangoState.error = ''; rangoState.resultado = null
  const datos = { desde: rango.desde, hasta: rango.hasta, diasSemana: rango.diasSemana.length === 7 ? undefined : rango.diasSemana, cuposTotales: Number(rango.cupos), tarifaDia: tarifaNum(rango.tarifa) }
  const errores = validarRango(datos, { aforo: aforo.value })
  if (errores.length) { rangoState.errores = errores; return }
  rangoState.guardando = true
  try {
    rangoState.resultado = await providerUseCases.abrirRango(servicioId.value, datos, { idempotencyKey: rangoState.clave, aforo: aforo.value })
    rangoState.clave = uid()
    cargar()
  } catch (e) {
    if (sesionVencida(e)) return
    if (e.campos) rangoState.errores = e.campos
    else rangoState.error = textoError(e)
  } finally { rangoState.guardando = false }
}
const errorDe = (lista, campo) => lista.find((x) => x.campo === campo)
const NOMBRES_DIA = computed(() => [1, 2, 3, 4, 5, 6, 7].map((d) => ({ d, texto: new Intl.DateTimeFormat(locale.value, { weekday: 'short', timeZone: 'UTC' }).format(new Date(`2026-11-0${d}T12:00:00Z`)) })))
const cop = (v) => (v == null ? t('provider.baseRate') : n(v, { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }))
const nombreDia = (iso) => new Intl.DateTimeFormat(locale.value, { weekday: 'short', timeZone: 'UTC' }).format(new Date(`${iso}T12:00:00Z`))
</script>

<template>
  <div>
    <p v-if="!servicios.length" class="rounded-panel border border-sand/30 bg-white p-8 text-center text-muted shadow-card">{{ t('provider.noServices') }}</p>

    <template v-else>
      <div class="flex flex-wrap items-end gap-4">
        <label class="text-sm font-medium text-navy-darkest">
          {{ t('provider.service') }}
          <select v-model="servicioId" class="mt-1 block min-w-[240px] rounded-xl border border-border-input bg-white px-3 py-2.5 text-sm font-normal text-ink-control">
            <option v-for="s in servicios" :key="s.id" :value="s.id">{{ s.nombre }}</option>
          </select>
        </label>
        <p v-if="aforo" class="text-sm text-muted">{{ t('provider.capacityOfficial', { n: aforo }) }}</p>
      </div>

      <p v-if="!enLinea" class="mt-4 rounded-xl bg-warn-bg px-4 py-2.5 text-sm text-warn" role="status">{{ t('provider.offline') }}</p>
      <p v-if="aviso" class="mt-4 rounded-xl bg-ok-bg px-4 py-2.5 text-sm text-ok" role="status">{{ aviso }}</p>

      <!-- Días -->
      <section class="mt-6 rounded-panel border border-sand/30 bg-white p-5 shadow-card sm:p-6" :aria-label="t('provider.days')">
        <div class="flex flex-wrap items-center justify-between gap-3">
          <h2 class="text-lg font-bold text-navy-darkest">{{ t('provider.days') }}</h2>
          <p class="font-mono text-xs text-muted">{{ fmtDate(ventana.desde, locale, { day: 'numeric', month: 'short' }) }} → {{ fmtDate(ventana.hasta, locale, { day: 'numeric', month: 'short' }) }}
            · {{ t('provider.summary', { abiertos: resumen.abiertos, cerrados: resumen.cerrados, reservados: resumen.reservados }) }}</p>
        </div>

        <div v-if="cargando" class="mt-4 h-40 animate-pulse rounded-xl bg-cream" role="status" :aria-label="t('provider.loading')" />
        <div v-else-if="errorCarga" class="mt-4 rounded-xl bg-danger-bg p-4 text-danger" role="alert">
          <p>{{ errorCarga }}</p>
          <button type="button" class="mt-2 font-semibold underline" @click="cargar">{{ t('provider.retry') }}</button>
        </div>
        <p v-else-if="!dias.length" class="mt-4 text-muted">{{ t('provider.noDays') }}</p>
        <div v-else class="mt-4 overflow-x-auto">
          <!-- En el teléfono la tarifa se oculta (se ve al editar el día) para que "Editar" quepa sin desplazar la tabla -->
          <table class="w-full text-left text-sm">
            <thead class="font-mono text-[10px] uppercase tracking-wider text-muted sm:text-[11px]">
              <tr><th class="py-2 pr-2">{{ t('provider.date') }}</th><th class="px-2">{{ t('provider.colTotal') }}</th><th class="px-2">{{ t('provider.reserved') }}</th><th class="px-2">{{ t('provider.free') }}</th><th class="hidden px-2 sm:table-cell">{{ t('provider.rate') }}</th><th /></tr>
            </thead>
            <tbody>
              <tr v-for="d in dias" :key="d.fecha" class="border-t border-sand/30" :class="d.cupos_totales === 0 ? 'text-muted' : 'text-ink-control'">
                <td class="py-2.5 pr-2 first-letter:uppercase"><span class="font-mono text-xs text-muted">{{ nombreDia(d.fecha) }}</span> {{ fmtDate(d.fecha, locale, { day: 'numeric', month: 'short' }) }}</td>
                <td class="px-2 tabular-nums">{{ d.cupos_totales === 0 ? t('provider.closed') : d.cupos_totales }}</td>
                <td class="px-2 tabular-nums">{{ d.cupos_reservados }}</td>
                <td class="px-2 tabular-nums">{{ d.cupos_disponibles }}</td>
                <td class="hidden px-2 tabular-nums sm:table-cell">{{ cop(d.tarifa_dia) }}</td>
                <td class="text-right"><button type="button" class="rounded-full border border-navy px-3.5 py-1.5 text-xs font-medium text-navy hover:bg-cream disabled:opacity-50" :disabled="!enLinea" @click="abrirEdicion(d)">{{ t('provider.edit') }}</button></td>
              </tr>
            </tbody>
          </table>
          <button v-if="ventana.hasta < addDays(ventana.desde, MAX_DIAS_RANGO - 1)" type="button" class="mt-3 text-sm font-medium text-navy underline" @click="ampliar">{{ t('provider.showMore') }}</button>
        </div>

        <!-- Editor de un día -->
        <form v-if="edicion" class="mt-5 rounded-xl border border-teal/40 bg-cream p-4" @submit.prevent="guardar()">
          <h3 class="font-semibold text-navy-darkest">{{ edicion.version == null ? t('provider.createDay') : t('provider.editDay') }}: <span class="first-letter:uppercase">{{ fmtDate(edicion.fecha, locale) }}</span></h3>
          <div class="mt-3 grid gap-3 sm:grid-cols-2">
            <label class="text-sm">
              {{ t('provider.total') }}
              <input v-model="edicion.cupos" type="number" min="0" :max="aforo" step="1" class="mt-1 w-full rounded-xl border border-border-input bg-white px-3 py-2" :aria-invalid="!!errorDe(edicion.errores, 'cuposTotales')" />
              <span v-if="errorDe(edicion.errores, 'cuposTotales')" class="mt-1 block text-xs text-danger" role="alert">{{ textoCampo(errorDe(edicion.errores, 'cuposTotales')) }}<template v-if="errorDe(edicion.errores, 'cuposTotales').codigo === 'CUPOS_COMPROMETIDOS'"> ({{ edicion.reservados }})</template></span>
              <span v-else-if="edicion.reservados" class="mt-1 block text-xs text-muted">{{ t('provider.alreadyReserved', { n: edicion.reservados }) }}</span>
            </label>
            <label class="text-sm">
              {{ t('provider.rateDay') }}
              <input v-model="edicion.tarifa" type="number" min="0" step="1000" :placeholder="t('provider.baseRate')" class="mt-1 w-full rounded-xl border border-border-input bg-white px-3 py-2" :aria-invalid="!!errorDe(edicion.errores, 'tarifaDia')" />
              <span v-if="errorDe(edicion.errores, 'tarifaDia')" class="mt-1 block text-xs text-danger" role="alert">{{ textoCampo(errorDe(edicion.errores, 'tarifaDia')) }}</span>
            </label>
          </div>
          <p class="mt-2 text-xs text-muted">{{ t('provider.zeroCloses') }}</p>

          <!-- Conflicto de versión: tu cambio frente a lo que hay ahora -->
          <div v-if="edicion.conflicto" class="mt-4 rounded-xl border border-warn/50 bg-warn-bg p-4 text-sm text-ink-control" role="alert">
            <p class="font-semibold text-warn">{{ t('provider.conflictTitle') }}</p>
            <dl class="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-2">
              <div><dt class="font-mono text-[11px] uppercase text-muted">{{ t('provider.yourChange') }}</dt><dd>{{ t('provider.conflictLine', { cupos: edicion.conflicto.mio.cuposTotales, tarifa: cop(edicion.conflicto.mio.tarifaDia) }) }}</dd></div>
              <div><dt class="font-mono text-[11px] uppercase text-muted">{{ t('provider.nowOnServer') }}</dt><dd>{{ t('provider.conflictLine', { cupos: edicion.conflicto.actual.cupos_totales, tarifa: cop(edicion.conflicto.actual.tarifa_dia) }) }}</dd></div>
            </dl>
            <div class="mt-3 flex flex-wrap gap-2.5">
              <button type="button" class="rounded-full bg-navy px-4 py-2 text-sm font-medium text-white hover:bg-blue disabled:opacity-50" :disabled="edicion.guardando || !enLinea" @click="insistir">{{ t('provider.useMine') }}</button>
              <button type="button" class="rounded-full border border-navy px-4 py-2 text-sm font-medium text-navy hover:bg-white" @click="aceptarActual">{{ t('provider.keepServer') }}</button>
            </div>
          </div>
          <p v-if="edicion.error" class="mt-3 rounded-xl bg-danger-bg px-3.5 py-2.5 text-sm text-danger" role="alert">{{ edicion.error }}</p>
          <div v-if="!edicion.conflicto" class="mt-3 flex flex-wrap gap-2.5">
            <button type="submit" class="rounded-full bg-navy px-5 py-2.5 text-sm font-medium text-white shadow-cta hover:bg-blue disabled:opacity-50" :disabled="edicion.guardando || !enLinea">{{ edicion.guardando ? t('provider.working') : t('provider.save') }}</button>
            <button type="button" class="rounded-full border border-navy px-5 py-2.5 text-sm font-medium text-navy hover:bg-white" @click="edicion = null">{{ t('provider.cancel') }}</button>
          </div>
        </form>

        <!-- Agregar un día suelto -->
        <form v-else class="mt-5 flex flex-wrap items-end gap-3 border-t border-sand/30 pt-4" @submit.prevent="abrirCreacion">
          <label class="text-sm">{{ t('provider.addDay') }}<input v-model="nuevoDia.fecha" type="date" :min="today(new Date())" class="mt-1 block rounded-xl border border-border-input bg-white px-3 py-2" /></label>
          <button type="submit" class="rounded-full border border-navy px-5 py-2.5 text-sm font-medium text-navy hover:bg-cream disabled:opacity-50" :disabled="!enLinea || !nuevoDia.fecha">{{ t('provider.add') }}</button>
        </form>
      </section>

      <!-- Abrir un rango -->
      <section class="mt-6 rounded-panel border border-sand/30 bg-white p-5 shadow-card sm:p-6" :aria-label="t('provider.openRange')">
        <h2 class="text-lg font-bold text-navy-darkest">{{ t('provider.openRange') }}</h2>
        <p class="mt-1 text-sm text-muted">{{ t('provider.openRangeHelp') }}</p>
        <form class="mt-4 grid gap-4 sm:grid-cols-2" @submit.prevent="abrirRango">
          <label class="text-sm">{{ t('provider.from') }}<input v-model="rango.desde" type="date" :min="today(new Date())" class="mt-1 w-full rounded-xl border border-border-input bg-white px-3 py-2" />
            <span v-if="errorDe(rangoState.errores, 'desde')" class="mt-1 block text-xs text-danger" role="alert">{{ textoCampo(errorDe(rangoState.errores, 'desde')) }}</span></label>
          <label class="text-sm">{{ t('provider.to') }}<input v-model="rango.hasta" type="date" class="mt-1 w-full rounded-xl border border-border-input bg-white px-3 py-2" />
            <span v-if="errorDe(rangoState.errores, 'hasta')" class="mt-1 block text-xs text-danger" role="alert">{{ textoCampo(errorDe(rangoState.errores, 'hasta')) }}</span></label>
          <fieldset class="sm:col-span-2">
            <legend class="text-sm">{{ t('provider.weekdays') }}</legend>
            <div class="mt-1.5 flex flex-wrap gap-2">
              <button v-for="x in NOMBRES_DIA" :key="x.d" type="button" :aria-pressed="rango.diasSemana.includes(x.d)" class="rounded-full border px-3.5 py-1.5 text-sm transition" :class="rango.diasSemana.includes(x.d) ? 'border-navy bg-navy text-white' : 'border-sand/40 bg-cream text-ink-control hover:border-teal'" @click="alternarDia(x.d)">{{ x.texto }}</button>
            </div>
            <span v-if="errorDe(rangoState.errores, 'diasSemana')" class="mt-1 block text-xs text-danger" role="alert">{{ textoCampo(errorDe(rangoState.errores, 'diasSemana')) }}</span>
          </fieldset>
          <label class="text-sm">{{ t('provider.total') }}<input v-model="rango.cupos" type="number" min="1" :max="aforo" step="1" class="mt-1 w-full rounded-xl border border-border-input bg-white px-3 py-2" />
            <span v-if="errorDe(rangoState.errores, 'cuposTotales')" class="mt-1 block text-xs text-danger" role="alert">{{ textoCampo(errorDe(rangoState.errores, 'cuposTotales')) }}</span></label>
          <label class="text-sm">{{ t('provider.rateDay') }}<input v-model="rango.tarifa" type="number" min="0" step="1000" :placeholder="t('provider.baseRate')" class="mt-1 w-full rounded-xl border border-border-input bg-white px-3 py-2" />
            <span v-if="errorDe(rangoState.errores, 'tarifaDia')" class="mt-1 block text-xs text-danger" role="alert">{{ textoCampo(errorDe(rangoState.errores, 'tarifaDia')) }}</span></label>
          <div class="flex flex-wrap items-center gap-4 sm:col-span-2">
            <button type="submit" class="rounded-full bg-navy px-6 py-3 text-sm font-medium text-white shadow-cta hover:bg-blue disabled:opacity-50" :disabled="rangoState.guardando || !enLinea">{{ rangoState.guardando ? t('provider.working') : t('provider.openDays', { n: previsualizacion }) }}</button>
            <p class="text-xs text-muted">{{ t('provider.skipExisting') }}</p>
          </div>
        </form>
        <p v-if="rangoState.error" class="mt-3 rounded-xl bg-danger-bg px-3.5 py-2.5 text-sm text-danger" role="alert">{{ rangoState.error }}</p>
        <p v-if="rangoState.resultado" class="mt-3 rounded-xl bg-ok-bg px-3.5 py-2.5 text-sm text-ok" role="status">{{ t('provider.rangeResult', { creados: rangoState.resultado.creados.length, omitidos: rangoState.resultado.omitidos.length }) }}</p>
      </section>
    </template>
  </div>
</template>
