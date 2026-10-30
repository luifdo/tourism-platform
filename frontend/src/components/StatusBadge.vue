<script setup>
import { useI18n } from 'vue-i18n'

defineProps({ estado: { type: String, required: true } })
const { t } = useI18n()
const tone = {
  SOLICITADA: 'bg-warn-bg text-warn',
  CONFIRMADA: 'bg-ok-bg text-ok',
  RECHAZADA: 'bg-danger-bg text-danger',
  CANCELADA: 'bg-border-input/60 text-muted',
  FINALIZADA: 'bg-[#DFF2FE] text-[#005986]',
}
</script>

<template>
  <span class="inline-flex items-center rounded-full px-3 py-1 font-mono text-xs font-semibold uppercase tracking-wider" :class="tone[estado]">{{ t(`my.states.${estado}`) }}</span>
</template>
