<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

// Estrellas de solo lectura. El valor se dice con palabras para lectores de pantalla ("4 de 5").
const props = defineProps({ valor: { type: Number, default: 0 }, tamano: { type: Number, default: 16 } })
const { t } = useI18n()
const redondeado = computed(() => Math.round(props.valor))
</script>

<template>
  <span class="inline-flex items-center gap-0.5 text-warn" role="img" :aria-label="t('reviews.starsOf', { n: valor })">
    <svg v-for="i in 5" :key="i" :width="tamano" :height="tamano" viewBox="0 0 24 24" :fill="i <= redondeado ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z" /></svg>
  </span>
</template>
