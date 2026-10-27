<script setup>
import { useI18n } from 'vue-i18n'
import BrandLogo from './BrandLogo.vue'
const { t } = useI18n()
</script>

<template>
  <footer class="bg-navy-darkest px-[clamp(20px,6vw,96px)] pt-14 text-white" style="padding-bottom: calc(3.5rem + env(safe-area-inset-bottom))">
    <div class="mx-auto flex max-w-[1200px] flex-wrap items-center justify-between gap-6">
      <div class="max-w-xl">
        <BrandLogo dark large />
        <p class="mt-3 text-sm leading-relaxed text-white/65">{{ t('footer.about') }}</p>
      </div>
      <div class="flex flex-wrap items-center gap-3">
        <RouterLink :to="{ name: 'home', hash: '#catalogo' }" class="rounded-full bg-teal px-5 py-2.5 text-sm font-medium text-white transition hover:bg-teal-hover">{{ t('footer.explore') }}</RouterLink>
      </div>
    </div>
    <p class="mx-auto mt-10 max-w-[1200px] border-t border-white/10 pt-6 font-mono text-xs text-white/50">{{ t('footer.legal') }}</p>
  </footer>
</template>
