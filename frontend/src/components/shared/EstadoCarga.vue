<script setup>
import { useI18n } from 'vue-i18n'

// Tres estados que se repiten en cada lista: cargando (esqueleto), error (con reintento) y vacío. Si no es ninguno, pinta el contenido.
// `aviso` es un estado normal de la cuenta (p. ej. «disponible cuando el Admin apruebe tu cuenta»): se muestra en neutro, sin reintento.
defineProps({ cargando: Boolean, error: { type: String, default: '' }, aviso: { type: String, default: '' }, vacio: Boolean, textoVacio: { type: String, default: '' }, alto: { type: String, default: 'h-32' } })
defineEmits(['reintentar'])
const { t } = useI18n()
</script>

<template>
  <div v-if="cargando" class="animate-pulse rounded-panel bg-white" :class="alto" role="status" :aria-label="t('gestion.loading')" />
  <div v-else-if="error" class="rounded-panel border border-danger/30 bg-danger-bg p-5 text-sm text-danger" role="alert">
    <p>{{ error }}</p>
    <button type="button" class="mt-2 font-semibold underline" @click="$emit('reintentar')">{{ t('gestion.retry') }}</button>
  </div>
  <p v-else-if="aviso" class="rounded-panel border border-sand/40 bg-sand/10 p-5 text-sm leading-relaxed text-ink-control" role="status">{{ aviso }}</p>
  <p v-else-if="vacio" class="rounded-panel border border-dashed border-sand/50 bg-white/60 p-6 text-center text-sm text-muted">{{ textoVacio || t('gestion.empty') }}</p>
  <slot v-else />
</template>
