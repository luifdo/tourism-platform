<script setup>
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSession } from './ui/useSession'
import AppNavbar from './components/AppNavbar.vue'
import OfflineBar from './components/OfflineBar.vue'
import AppFooter from './components/AppFooter.vue'
import AssistantDrawer from './components/AssistantDrawer.vue'

// El token dura 15 min y no hay refresh: si vence con una pantalla protegida abierta se pide volver a ingresar
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
  <main>
    <RouterView />
  </main>
  <AppFooter />
  <AssistantDrawer />
</template>
