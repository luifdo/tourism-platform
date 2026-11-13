<script setup>
import { useI18n } from 'vue-i18n'

// Selector de 1 a 5 estrellas como grupo de radios: se opera con teclado (flechas) y se anuncia bien.
const props = defineProps({ modelValue: { type: Number, default: 0 }, etiqueta: { type: String, required: true }, opcional: Boolean, nombre: { type: String, required: true } })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
</script>

<template>
  <fieldset class="min-w-0">
    <legend class="font-mono text-[10px] font-medium uppercase tracking-[.12em] text-teal-hover">{{ etiqueta }}</legend>
    <div class="mt-1 flex items-center gap-1">
      <label v-for="i in 5" :key="i" class="cursor-pointer rounded p-0.5 text-warn focus-within:outline focus-within:outline-2 focus-within:outline-teal">
        <input type="radio" class="sr-only" :name="nombre" :value="i" :checked="props.modelValue === i" @change="emit('update:modelValue', i)" />
        <span class="sr-only">{{ t('reviews.starsOf', { n: i }) }}</span>
        <svg width="26" height="26" viewBox="0 0 24 24" :fill="i <= props.modelValue ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z" /></svg>
      </label>
      <button v-if="opcional && props.modelValue" type="button" class="ml-2 text-xs text-muted underline" @click="emit('update:modelValue', 0)">{{ t('reviews.clear') }}</button>
    </div>
  </fieldset>
</template>
