<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { entityUseCases } from '../../composition'
import { ultimosDias } from '../../domain/gestion/rules'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'

/* UC38 · Exportar el reporte de demanda en CSV (siempre en español, para Excel: separador ;, coma decimal y UTF-8 con BOM). Cada exportación queda en la bitácora. */
const { t, locale } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()
const enLinea = useOnline()

const f = reactive({ ...ultimosDias(new Date(), 30), zona: '' })
const zonas = ref([])
const enviando = ref(false)
const error = ref('')
const hecho = ref('')
onMounted(async () => { zonas.value = await entityUseCases.zonas(locale.value).catch(() => []) })

async function exportar() {
  enviando.value = true; error.value = ''; hecho.value = ''
  try {
    const { texto, nombre } = await entityUseCases.reporteCsv({ desde: f.desde, hasta: f.hasta, zona: f.zona || undefined })
    const url = URL.createObjectURL(new Blob([texto], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url; a.download = nombre
    document.body.appendChild(a); a.click(); a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 10_000)
    hecho.value = nombre
  } catch (e) { if (!sesionVencida(e)) error.value = camposDe(e).desde ?? mensaje(e, 'entidad') } finally { enviando.value = false }
}
</script>

<template>
  <section aria-labelledby="h-rep">
    <h2 id="h-rep" class="text-lg font-bold text-navy-darkest">{{ t('entidad.reportTitle') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('entidad.reportLead') }}</p>
    <form class="tarjeta mt-4 grid max-w-3xl gap-4 sm:grid-cols-3" @submit.prevent="exportar">
      <label><span class="campo-etiqueta">{{ t('gestion.from') }}</span><input v-model="f.desde" type="date" class="campo-input" required /></label>
      <label><span class="campo-etiqueta">{{ t('gestion.to') }}</span><input v-model="f.hasta" type="date" class="campo-input" required /></label>
      <label><span class="campo-etiqueta">{{ t('entidad.zone') }}</span><select v-model="f.zona" class="campo-input"><option value="">{{ t('entidad.allZones') }}</option><option v-for="z in zonas" :key="z.codigo" :value="z.codigo">{{ z.nombre }}</option></select></label>
      <div class="sm:col-span-3">
        <p class="text-xs text-muted">{{ t('entidad.reportNote') }}</p>
        <p v-if="error" class="campo-error" role="alert">{{ error }}</p>
        <p v-if="hecho" class="mt-2 text-sm text-ok" role="status">{{ t('entidad.reportDone', { nombre: hecho }) }}</p>
        <button type="submit" class="btn-primario mt-3" :disabled="enviando || !enLinea">{{ enviando ? t('gestion.sending') : t('entidad.download') }}</button>
      </div>
    </form>
  </section>
</template>
