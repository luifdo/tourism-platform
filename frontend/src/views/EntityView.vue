<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from '../ui/useSession'
import TabsNav from '../components/shared/TabsNav.vue'
import TableroEntidad from '../components/entity/TableroEntidad.vue'
import DemandaEntidad from '../components/entity/DemandaEntidad.vue'
import AlertasEntidad from '../components/entity/AlertasEntidad.vue'
import ReporteEntidad from '../components/entity/ReporteEntidad.vue'

/* Panel de la Entidad (la oficina de turismo): UC25 tablero, UC23 demanda, UC26 alertas oficiales y UC38 reportes. Roles Entidad y Admin (la ruta lo exige). */
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { sesion } = useSession()

const IDS = ['tablero', 'demanda', 'alertas', 'reportes']
const pestana = ref(IDS.includes(route.hash.slice(1)) ? route.hash.slice(1) : 'tablero')
watch(pestana, (p) => router.replace({ hash: `#${p}` }))
watch(() => route.hash, (h) => { if (IDS.includes(h.slice(1))) pestana.value = h.slice(1) }) // un enlace con #resenas abre esa pestaña
const pestanas = computed(() => IDS.map((id) => ({ id, label: t(`entidad.tabs.${id}`) })))
</script>

<template>
  <div class="bg-cream px-[clamp(20px,5vw,64px)] py-8 sm:py-12">
    <div class="mx-auto max-w-[1100px]">
      <p class="kicker flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ sesion.usuario?.nombre_completo }}</p>
      <h1 class="mt-2 text-[clamp(30px,4vw,48px)] font-bold tracking-[-.02em] text-navy-darkest">{{ t('entidad.title') }}</h1>
      <p class="mt-2 max-w-2xl text-muted">{{ t('entidad.lead') }}</p>
      <TabsNav v-model="pestana" :tabs="pestanas" :etiqueta="t('entidad.title')" prefijo="ent" />
      <div :id="`ent-panel-${pestana}`" class="mt-6" role="tabpanel" :aria-labelledby="`ent-${pestana}`">
        <TableroEntidad v-if="pestana === 'tablero'" />
        <DemandaEntidad v-else-if="pestana === 'demanda'" />
        <AlertasEntidad v-else-if="pestana === 'alertas'" />
        <ReporteEntidad v-else />
      </div>
    </div>
  </div>
</template>
