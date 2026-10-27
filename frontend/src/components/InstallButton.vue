<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'

// Botón "Instalar app": solo aparece cuando el navegador ofrece instalar la PWA (Chrome, Edge, Android)
const { t } = useI18n()
const deferred = ref(null)
const installed = ref(false)

const onPrompt = (e) => { e.preventDefault(); deferred.value = e }
const onInstalled = () => { installed.value = true; deferred.value = null }

onMounted(() => {
  window.addEventListener('beforeinstallprompt', onPrompt)
  window.addEventListener('appinstalled', onInstalled)
})
onBeforeUnmount(() => {
  window.removeEventListener('beforeinstallprompt', onPrompt)
  window.removeEventListener('appinstalled', onInstalled)
})

async function install() {
  if (!deferred.value) return
  deferred.value.prompt()
  await deferred.value.userChoice
  deferred.value = null
}
</script>

<template>
  <button v-if="deferred && !installed" type="button" class="flex items-center gap-1.5 rounded-full border border-navy/30 px-3 py-1.5 text-[13px] font-medium text-navy transition hover:bg-navy hover:text-white" @click="install">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12M7 10l5 5 5-5M5 20h14" /></svg>
    <span class="hidden sm:inline">{{ t('nav.install') }}</span>
    <span class="sm:hidden">{{ t('nav.installShort') }}</span>
  </button>
</template>
