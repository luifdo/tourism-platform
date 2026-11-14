<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { refrescandoIdioma } from '../../lib/refrescoIdioma'

// Barra fina e indeterminada en el borde superior mientras llega el contenido en el idioma nuevo. Solo aparece si la espera
// pasa de 150 ms: una respuesta rápida no debe hacer parpadear nada. Con movimiento reducido queda fija (ver main.css).
const { t } = useI18n()
const visible = ref(false)
let temporizador = null
watch(refrescandoIdioma, (activo) => {
  clearTimeout(temporizador)
  if (activo) temporizador = setTimeout(() => { visible.value = true }, 150)
  else visible.value = false
}, { immediate: true })
onBeforeUnmount(() => clearTimeout(temporizador))
</script>

<template>
  <div class="pointer-events-none fixed inset-x-0 top-0 z-[60] h-0.5 overflow-hidden transition-opacity duration-200" :class="visible ? 'opacity-100' : 'opacity-0'" role="status" aria-live="polite">
    <span class="sr-only">{{ visible ? t('gestion.updating') : '' }}</span>
    <div v-if="visible" class="barra-refresco h-full w-1/3 rounded-full bg-teal" />
  </div>
</template>
