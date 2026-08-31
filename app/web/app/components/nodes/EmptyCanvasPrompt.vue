<script setup lang="ts">
const { t } = useI18n()
</script>

<template>
  <div class="pointer-events-none absolute inset-x-0 top-6 z-20 flex justify-center px-4">
    <div class="max-w-md rounded-xl border border-dashed border-default bg-default/90 px-4 py-3 text-center shadow-sm backdrop-blur">
      <p class="mt-1 text-sm text-muted">
        {{ t('editor.emptyCanvas') }}
      </p>
    </div>
  </div>
</template>
