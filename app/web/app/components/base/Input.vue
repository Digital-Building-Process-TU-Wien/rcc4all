<script setup lang="ts">
const model = defineModel<string>()
</script>

<template>
  <input
    v-model="model"
    class="w-full rounded-2xl px-4 py-3 text-sm focus:outline outline-accent border border-slate-200 bg-white text-slate-700 placeholder:text-slate-400 disabled:bg-slate-100 disabled:text-slate-400 disabled:cursor-not-allowed"
  >
</template>
