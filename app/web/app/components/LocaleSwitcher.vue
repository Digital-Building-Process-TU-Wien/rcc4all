<script setup lang="ts">
const { locale, setLocale, locales } = useI18n()
</script>

<template>
  <div class="flex items-center gap-2">
    <UButton
      v-for="option in locales"
      :key="option.code"
      color="neutral"
      :variant="option.code === locale ? 'soft' : 'ghost'"
      size="xs"
      @click="setLocale(option.code)"
    >
      {{ option.code.toUpperCase() }}
    </UButton>
  </div>
</template>
