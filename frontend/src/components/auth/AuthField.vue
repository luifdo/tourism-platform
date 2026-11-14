<script setup>
// Campo de texto con etiqueta, error asociado (aria-describedby / aria-invalid) y autocompletado correcto
defineProps({
  id: { type: String, required: true },
  label: { type: String, required: true },
  modelValue: { type: String, default: '' },
  type: { type: String, default: 'text' },
  autocomplete: String,
  error: String,
  inputmode: String,
})
defineEmits(['update:modelValue'])
</script>

<template>
  <div>
    <label :for="id" class="block text-sm font-medium text-ink-control">{{ label }}</label>
    <input
      :id="id" :type="type" :value="modelValue" :autocomplete="autocomplete" :inputmode="inputmode"
      autocapitalize="off" spellcheck="false"
      :aria-invalid="!!error" :aria-describedby="error ? `${id}-error` : undefined"
      class="mt-1 w-full rounded-xl border bg-white px-4 py-3 text-[15px] text-ink outline-none transition focus:border-teal focus:shadow-[0_0_0_3px_rgba(93,154,146,.18)]"
      :class="error ? 'border-danger' : 'border-border-input'"
      @input="$emit('update:modelValue', $event.target.value)"
    />
    <p v-if="error" :id="`${id}-error`" class="mt-1 text-sm text-danger">{{ error }}</p>
  </div>
</template>
