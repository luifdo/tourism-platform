<script setup>
import { useI18n } from 'vue-i18n'

// dark: logo para fondos oscuros (footer). large: tamaño del footer.
defineProps({ dark: Boolean, large: Boolean })
const { t } = useI18n()
const base = import.meta.env.BASE_URL
</script>

<template>
  <span class="flex items-center gap-2.5">
    <img
      :src="`${base}brand/${dark ? 'logo-dark' : 'logo-light'}.png`"
      alt="Samaland" width="364" height="400"
      class="w-auto shrink-0" :class="large ? 'h-32' : 'h-[58px]'"
    />
    <span class="flex flex-col leading-tight">
      <i class="font-semibold tracking-tight" :class="[large ? 'text-2xl' : 'text-[17px]', dark ? 'text-white' : 'text-navy-darkest']">{{ t('brand.alt') }}</i>
      <span class="mt-1 w-fit rounded px-1.5 font-mono text-[10px] uppercase tracking-widest" :class="dark ? 'bg-white/10 text-[#9fe3d4]' : 'bg-teal/15 text-teal'">{{ t('brand.tag') }}</span>
    </span>
  </span>
</template>
