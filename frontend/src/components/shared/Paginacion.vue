<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({ pagina: { type: Number, required: true }, tamano: { type: Number, required: true }, total: { type: Number, required: true } })
const emit = defineEmits(['cambiar'])
const { t } = useI18n()
const paginas = computed(() => Math.max(1, Math.ceil(props.total / props.tamano)))
</script>

<template>
  <nav v-if="paginas > 1" class="mt-4 flex items-center justify-between gap-3 text-sm" :aria-label="t('gestion.pagination')">
    <button type="button" class="rounded-full border border-sand/40 bg-white px-4 py-2 font-medium text-navy transition hover:border-teal disabled:opacity-40" :disabled="pagina <= 1" @click="emit('cambiar', pagina - 1)">← {{ t('gestion.prev') }}</button>
    <span class="font-mono text-xs text-muted">{{ t('gestion.pageOf', { n: pagina, total: paginas }) }}</span>
    <button type="button" class="rounded-full border border-sand/40 bg-white px-4 py-2 font-medium text-navy transition hover:border-teal disabled:opacity-40" :disabled="pagina >= paginas" @click="emit('cambiar', pagina + 1)">{{ t('gestion.next') }} →</button>
  </nav>
</template>
