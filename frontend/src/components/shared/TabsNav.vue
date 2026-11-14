<script setup>
import { nextTick, onMounted, watch } from 'vue'
// Pestañas accesibles (role="tablist"): flechas, Inicio y Fin cambian de pestaña. El contenido lo pinta quien lo usa.
const props = defineProps({ tabs: { type: Array, required: true }, modelValue: { type: String, required: true }, etiqueta: { type: String, default: '' }, prefijo: { type: String, default: 'tab' } })
const emit = defineEmits(['update:modelValue'])

// En pantallas angostas la fila de pestañas se desplaza: la activa (p. ej. «Mi negocio», al final) no puede quedar cortada fuera de la vista
const verActiva = () => document.getElementById(`${props.prefijo}-${props.modelValue}`)?.scrollIntoView({ block: 'nearest', inline: 'center' })
onMounted(() => nextTick(verActiva))
watch(() => props.modelValue, () => nextTick(verActiva))

function teclado(e, i) {
  const n = props.tabs.length
  const destino = e.key === 'ArrowRight' ? (i + 1) % n : e.key === 'ArrowLeft' ? (i - 1 + n) % n : e.key === 'Home' ? 0 : e.key === 'End' ? n - 1 : null
  if (destino == null) return
  e.preventDefault()
  emit('update:modelValue', props.tabs[destino].id)
  document.getElementById(`${props.prefijo}-${props.tabs[destino].id}`)?.focus()
}
</script>

<template>
  <div class="mt-6 flex gap-1 overflow-x-auto border-b border-sand/40" role="tablist" :aria-label="etiqueta">
    <button
      v-for="(p, i) in tabs" :id="`${prefijo}-${p.id}`" :key="p.id" type="button" role="tab" :aria-selected="modelValue === p.id" :aria-controls="`${prefijo}-panel-${p.id}`" :tabindex="modelValue === p.id ? 0 : -1"
      class="-mb-px shrink-0 whitespace-nowrap border-b-2 px-4 py-3 text-sm font-semibold transition sm:px-5"
      :class="modelValue === p.id ? 'border-navy text-navy' : 'border-transparent text-muted hover:text-navy'"
      @click="emit('update:modelValue', p.id)" @keydown="teclado($event, i)"
    >{{ p.label }}</button>
  </div>
</template>
