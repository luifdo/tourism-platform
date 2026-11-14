<script setup>
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from './ui/useSession'
import AppNavbar from './components/AppNavbar.vue'
import OfflineBar from './components/OfflineBar.vue'
import AppFooter from './components/AppFooter.vue'
import AssistantDrawer from './components/AssistantDrawer.vue'
import { descartarError, errorGlobal } from './lib/errorGlobal'
import { useI18n } from 'vue-i18n'

// El token dura 15 min y se renueva solo con el refresh token (7 días): solo si no se puede renovar se pide volver a ingresar
const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const { sesion } = useSession()
watch(() => sesion.expirada, (expirada) => {
  if (expirada && route.meta.requiresAuth && navigator.onLine)
    router.replace({ name: 'login', query: { redirect: route.fullPath, expirada: '1' } })
})
</script>

<template>
  <AppNavbar />
  <OfflineBar />
  <!-- Un error inesperado: se avisa en vez de dejar la pantalla a medias; la referencia sirve para reportarlo -->
  <div v-if="errorGlobal.hay" class="flex flex-wrap items-center justify-between gap-3 bg-danger-bg px-[clamp(16px,3vw,32px)] py-2.5 text-sm text-danger" role="alert">
    <p>{{ t('gestion.unexpected', { ref: errorGlobal.referencia }) }}</p>
    <span class="flex gap-4 font-semibold"><button type="button" class="underline" @click="$router.go(0)">{{ t('gestion.reload') }}</button><button type="button" class="underline" @click="descartarError">{{ t('gestion.dismiss') }}</button></span>
  </div>
  <main>
    <RouterView />
  </main>
  <AppFooter />
  <AssistantDrawer />
</template>
