<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { offerUseCases } from '../../composition'
import { useGestion } from '../../ui/useGestion'
import { useOnline } from '../../ui/useOnline'
import EstadoCarga from '../shared/EstadoCarga.vue'

/* Perfil comercial del prestador (catalog-service): teléfono, dirección y política de cancelación, que ven los turistas en cada ficha. */
const { t } = useI18n()
const { mensaje, camposDe, sesionVencida } = useGestion()
const enLinea = useOnline()

const perfil = ref(null)
const cargando = ref(true)
const errorCarga = ref('')
const f = reactive({ telefono: '', direccion: '', politica: { es: '', en: '' }, guardando: false, ok: false, error: '', campos: {} })

async function cargar() {
  cargando.value = true; errorCarga.value = ''
  try {
    perfil.value = await offerUseCases.perfilComercial()
    f.telefono = perfil.value.telefono ?? ''; f.direccion = perfil.value.direccion ?? ''
    f.politica = { es: perfil.value.politica_cancelacion?.es ?? '', en: perfil.value.politica_cancelacion?.en ?? '' }
  } catch (e) { if (!sesionVencida(e)) errorCarga.value = mensaje(e, 'negocio') } finally { cargando.value = false }
}
onMounted(cargar)

async function guardar() {
  f.guardando = true; f.ok = false; f.error = ''; f.campos = {}
  try {
    perfil.value = await offerUseCases.editarPerfilComercial({ telefono: f.telefono, direccion: f.direccion, politica: f.politica }, perfil.value.version)
    f.ok = true
  } catch (e) {
    if (sesionVencida(e)) return
    f.error = mensaje(e, 'negocio'); f.campos = camposDe(e)
    if (e.code === 'VERSION_DISTINTA') await cargar()
  } finally { f.guardando = false }
}
</script>

<template>
  <section aria-labelledby="h-negocio">
    <h2 id="h-negocio" class="text-lg font-bold text-navy-darkest">{{ t('negocio.title') }}</h2>
    <p class="mt-1 max-w-2xl text-sm text-muted">{{ t('negocio.lead') }}</p>
    <div class="mt-4">
      <EstadoCarga :cargando="cargando" :error="errorCarga" alto="h-48" @reintentar="cargar">
        <form v-if="perfil" class="tarjeta space-y-4" @submit.prevent="guardar">
          <p class="text-sm text-ink-control"><span class="campo-etiqueta">{{ t('negocio.businessName') }}</span><span class="mt-1 block">{{ perfil.razon_social }}</span></p>
          <div class="grid gap-4 sm:grid-cols-2">
            <label><span class="campo-etiqueta">{{ t('negocio.phone') }}</span><input v-model="f.telefono" class="campo-input" maxlength="30" autocomplete="tel" /></label>
            <label><span class="campo-etiqueta">{{ t('negocio.address') }}</span><input v-model="f.direccion" class="campo-input" maxlength="200" autocomplete="street-address" /></label>
          </div>
          <div class="grid gap-4 sm:grid-cols-2">
            <label><span class="campo-etiqueta">{{ t('negocio.policyEs') }}</span><textarea v-model="f.politica.es" class="campo-input min-h-24" /></label>
            <label><span class="campo-etiqueta">{{ t('negocio.policyEn') }}</span><textarea v-model="f.politica.en" class="campo-input min-h-24" /></label>
          </div>
          <p class="text-xs text-muted">{{ t('negocio.policyNote') }}</p>
          <p v-if="f.error" class="campo-error" role="alert">{{ f.error }}</p>
          <p v-if="f.ok" class="text-sm text-ok" role="status">{{ t('negocio.saved') }}</p>
          <button type="submit" class="btn-primario" :disabled="f.guardando || !enLinea">{{ f.guardando ? t('gestion.saving') : t('gestion.save') }}</button>
        </form>
      </EstadoCarga>
    </div>
  </section>
</template>
