<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { catalogUseCases } from '../composition'
import { useSession } from '../ui/useSession'
import SolicitudesPrestador from '../components/provider/SolicitudesPrestador.vue'
import CalendarioPrestador from '../components/provider/CalendarioPrestador.vue'
import MisServicios from '../components/provider/MisServicios.vue'
import ResenasPrestador from '../components/provider/ResenasPrestador.vue'
import MetricasPrestador from '../components/provider/MetricasPrestador.vue'
import VerificacionPrestador from '../components/provider/VerificacionPrestador.vue'
import PerfilComercial from '../components/provider/PerfilComercial.vue'
import TabsNav from '../components/shared/TabsNav.vue'

/*
 * Panel del prestador: UC20 solicitudes, UC19 calendario, UC17/UC18 servicios, UC21 reseñas, UC22 métricas y UC37 verificación. Solo para el rol Prestador (la ruta lo exige).
 * Los servicios salen de GET /api/catalog/prestador/servicios; las solicitudes y el calendario, de booking-service.
 */
const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const { sesion, expirar } = useSession()

const PESTANAS = ['solicitudes', 'calendario', 'servicios', 'resenas', 'metricas', 'negocio']
// La pestaña se recuerda en la dirección (#servicios): se puede enlazar y sobrevive a recargar
const inicial = PESTANAS.includes(route.hash.slice(1)) ? route.hash.slice(1) : 'solicitudes'
const pestana = ref(inicial)
watch(pestana, (p) => router.replace({ hash: `#${p}` }))
watch(() => route.hash, (h) => { if (PESTANAS.includes(h.slice(1))) pestana.value = h.slice(1) }) // un enlace con #servicios abre esa pestaña
const servicios = ref([])
const cargando = ref(true)
const error = ref('')
// El catálogo responde 403 PERFIL_INACTIVO mientras el Admin no apruebe el RNT y el RUT: no es una falla, es el paso 1 del alta
const sinVerificar = ref(false)
const hashPedido = PESTANAS.includes(route.hash.slice(1))

async function cargar() {
  cargando.value = true; error.value = ''; sinVerificar.value = false
  try { servicios.value = await catalogUseCases.misServicios({ idioma: locale.value }) }
  catch (e) {
    if (e?.status === 401) { expirar(); router.replace({ name: 'login', query: { redirect: route.fullPath, expirada: '1' } }); return }
    if (e?.code === 'PERFIL_INACTIVO') {
      sinVerificar.value = true
      if (!hashPedido) pestana.value = 'negocio' // lo único que puede hacer es subir el RNT y el RUT: se abre ahí
      return
    }
    error.value = t(e?.status === 403 ? 'provider.errors.ROL_NO_PERMITIDO' : 'provider.errors.generic')
  } finally { cargando.value = false }
}
onMounted(cargar)
watch(locale, cargar)
const pestanas = computed(() => PESTANAS.map((id) => ({ id, label: t(`provider.tabs.${id}`) })))
</script>

<template>
  <div class="bg-cream px-[clamp(20px,5vw,64px)] py-8 sm:py-12">
    <div class="mx-auto max-w-[1100px]">
      <p class="kicker flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ sesion.usuario?.nombre_completo }}</p>
      <h1 class="mt-2 text-[clamp(30px,4vw,48px)] font-bold tracking-[-.02em] text-navy-darkest">{{ t('provider.title') }}</h1>
      <p class="mt-2 max-w-2xl text-muted">{{ t('provider.lead') }}</p>

      <div v-if="sinVerificar" class="mt-6 rounded-card border border-warn/40 bg-warn-bg p-4 text-sm text-ink-control" role="status">
        <p class="font-semibold text-navy-darkest">{{ t('provider.unverified.title') }}</p>
        <p class="mt-1">{{ t('provider.unverified.body') }}</p>
        <button v-if="pestana !== 'negocio'" type="button" class="mt-2 font-semibold text-navy underline" @click="pestana = 'negocio'">{{ t('provider.unverified.go') }}</button>
      </div>
      <TabsNav v-model="pestana" :tabs="pestanas" :etiqueta="t('provider.title')" prefijo="tab" />

      <!-- Las pestañas que no dependen de la lista de servicios del calendario se pintan siempre: no esperan esa carga -->
      <div v-if="['servicios', 'resenas', 'metricas', 'negocio'].includes(pestana)" :id="`tab-panel-${pestana}`" class="mt-6" role="tabpanel" :aria-labelledby="`tab-${pestana}`">
        <MisServicios v-if="pestana === 'servicios'" @cambio="cargar" />
        <ResenasPrestador v-else-if="pestana === 'resenas'" :servicios="servicios" />
        <MetricasPrestador v-else-if="pestana === 'metricas'" />
        <div v-else class="space-y-10"><VerificacionPrestador /><PerfilComercial /></div>
      </div>
      <template v-else>
        <div v-if="cargando" class="mt-8 h-40 animate-pulse rounded-panel bg-white" role="status" :aria-label="t('provider.loading')" />
        <p v-else-if="sinVerificar" class="mt-8 rounded-panel border border-sand/40 bg-sand/10 p-5 text-sm leading-relaxed text-ink-control">{{ t('provider.unverified.tab') }}</p>
        <div v-else-if="error" class="mt-8 rounded-panel border border-danger/30 bg-danger-bg p-6 text-danger" role="alert">
          <p>{{ error }}</p>
          <button type="button" class="mt-3 font-semibold underline" @click="cargar">{{ t('provider.retry') }}</button>
        </div>
        <div v-else :id="`tab-panel-${pestana}`" class="mt-6" role="tabpanel" :aria-labelledby="`tab-${pestana}`">
          <SolicitudesPrestador v-if="pestana === 'solicitudes'" :servicios="servicios" />
          <CalendarioPrestador v-else :servicios="servicios" />
        </div>
      </template>
    </div>
  </div>
</template>
