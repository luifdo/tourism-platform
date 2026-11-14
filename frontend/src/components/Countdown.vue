<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'

// Cuenta regresiva hasta `until` (ISO). Se actualiza cada segundo.
const props = defineProps({ until: { type: String, required: true } })
const emit = defineEmits(['expired'])

const now = ref(Date.now())
let fired = false
const id = setInterval(() => {
  now.value = Date.now()
  if (!fired && left.value <= 0) { fired = true; emit('expired') }
}, 1000)
onBeforeUnmount(() => clearInterval(id))

const left = computed(() => new Date(props.until).getTime() - now.value)
const text = computed(() => {
  const s = Math.max(0, Math.floor(left.value / 1000))
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
})
</script>

<template>
  <time :datetime="until" class="font-mono tabular-nums">{{ text }}</time>
</template>
