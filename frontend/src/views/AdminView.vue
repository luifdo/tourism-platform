<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from '../ui/useSession'
import TabsNav from '../components/shared/TabsNav.vue'
import PrestadoresAdmin from '../components/admin/PrestadoresAdmin.vue'
import UsuariosAdmin from '../components/admin/UsuariosAdmin.vue'
import ModeracionResenas from '../components/admin/ModeracionResenas.vue'
import BitacoraAdmin from '../components/admin/BitacoraAdmin.vue'

/* Panel del Admin: UC28 prestadores, UC27 usuarios y roles, UC29 moderación de reseñas, UC33 bitácora. Solo rol Admin (la ruta lo exige). */
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { sesion } = useSession()

const IDS = ['prestadores', 'usuarios', 'resenas', 'bitacora']
const pestana = ref(IDS.includes(route.hash.slice(1)) ? route.hash.slice(1) : 'prestadores')
watch(pestana, (p) => router.replace({ hash: `#${p}` }))
watch(() => route.hash, (h) => { if (IDS.includes(h.slice(1))) pestana.value = h.slice(1) }) // un enlace con #resenas abre esa pestaña
const pestanas = computed(() => IDS.map((id) => ({ id, label: t(`admin.tabs.${id}`) })))
</script>

<template>
  <div class="bg-cream px-[clamp(20px,5vw,64px)] py-8 sm:py-12">
    <div class="mx-auto max-w-[1100px]">
      <p class="kicker flex items-center gap-2"><span class="size-1.5 rounded-full bg-teal" />{{ sesion.usuario?.nombre_completo }}</p>
      <h1 class="mt-2 text-[clamp(30px,4vw,48px)] font-bold tracking-[-.02em] text-navy-darkest">{{ t('admin.title') }}</h1>
      <p class="mt-2 max-w-2xl text-muted">{{ t('admin.lead') }}</p>
      <TabsNav v-model="pestana" :tabs="pestanas" :etiqueta="t('admin.title')" prefijo="adm" />
      <div :id="`adm-panel-${pestana}`" class="mt-6" role="tabpanel" :aria-labelledby="`adm-${pestana}`">
        <PrestadoresAdmin v-if="pestana === 'prestadores'" />
        <UsuariosAdmin v-else-if="pestana === 'usuarios'" />
        <ModeracionResenas v-else-if="pestana === 'resenas'" />
        <BitacoraAdmin v-else />
      </div>
    </div>
  </div>
</template>
