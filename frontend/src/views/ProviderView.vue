<script setup>
import { onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { catalogUseCases } from '../composition'
import { useSession } from '../ui/useSession'
import SolicitudesPrestador from '../components/provider/SolicitudesPrestador.vue'
import CalendarioPrestador from '../components/provider/CalendarioPrestador.vue'

/*
 * Panel del prestador (UC19 calendario, UC20 solicitudes). Solo para el rol Prestador (la ruta lo exige).
 * Los servicios salen de GET /api/catalog/prestador/servicios; las solicitudes y el calendario, de booking-service.
 */
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { sesion, expirar } = useSession()

const pestana = ref('solicitudes')
const servicios = ref([])
const cargando = ref(true)
const error = ref('')

async function cargar() {
  cargando.value = true; error.value = ''
  try { servicios.value = await catalogUseCases.misServicios({ idioma: locale.value }) }
  catch (e) {
    if (e?.status === 401) { expirar(); router.replace({ name: 'login', query: { redirect: route.fullPath, expirada: '1' } }); return }
    error.value = t(e?.status === 403 ? 'provider.errors.ROL_NO_PERMITIDO' : 'provider.errors.generic')
  } finally { cargando.value = false }
}
onMounted(cargar)
watch(locale, cargar)
const pestanas = ['solicitudes', 'calendario']
</script>

<template>
  <div class="bg-cream px-[clamp(20px,5vw,64px)] py-8 sm:py-12">
    <div class="mx-auto max-w-[1000px]">
      <p class="kicker flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ sesion.usuario?.nombre_completo }}</p>
      <h1 class="mt-2 text-[clamp(30px,4vw,48px)] font-bold tracking-[-.02em] text-navy-darkest">{{ t('provider.title') }}</h1>
      <p class="mt-2 max-w-2xl text-muted">{{ t('provider.lead') }}</p>

      <div class="mt-6 flex gap-1 border-b border-sand/40" role="tablist" :aria-label="t('provider.title')">
        <button
          v-for="p in pestanas" :id="`tab-${p}`" :key="p" type="button" role="tab" :aria-selected="pestana === p" :aria-controls="`panel-${p}`"
          class="-mb-px border-b-2 px-5 py-3 text-sm font-semibold transition"
          :class="pestana === p ? 'border-navy text-navy' : 'border-transparent text-muted hover:text-navy'"
          @click="pestana = p"
        >{{ t(`provider.tabs.${p}`) }}</button>
      </div>

      <div v-if="cargando" class="mt-8 h-40 animate-pulse rounded-panel bg-white" role="status" :aria-label="t('provider.loading')" />
      <div v-else-if="error" class="mt-8 rounded-panel border border-danger/30 bg-danger-bg p-6 text-danger" role="alert">
        <p>{{ error }}</p>
        <button type="button" class="mt-3 font-semibold underline" @click="cargar">{{ t('provider.retry') }}</button>
      </div>
      <div v-else :id="`panel-${pestana}`" class="mt-6" role="tabpanel" :aria-labelledby="`tab-${pestana}`">
        <SolicitudesPrestador v-if="pestana === 'solicitudes'" :servicios="servicios" />
        <CalendarioPrestador v-else :servicios="servicios" />
      </div>
    </div>
  </div>
</template>
