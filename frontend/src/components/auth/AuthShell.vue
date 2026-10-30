<script setup>
defineProps({ title: String, lead: String })
</script>

<template>
  <div class="bg-cream px-[clamp(16px,5vw,64px)] py-8 sm:py-14">
    <div class="mx-auto w-full max-w-[460px]">
      <section class="rounded-panel border border-sand/30 bg-white p-6 shadow-elevated sm:p-8">
        <h1 class="text-[clamp(26px,4vw,32px)] font-bold tracking-[-.02em] text-navy-darkest">{{ title }}</h1>
        <p v-if="lead" class="mt-2 text-[15px] leading-relaxed text-muted">{{ lead }}</p>
        <div class="mt-6"><slot /></div>
      </section>
      <div class="mt-5 text-center text-sm text-ink-control"><slot name="footer" /></div>
    </div>
  </div>
</template>
