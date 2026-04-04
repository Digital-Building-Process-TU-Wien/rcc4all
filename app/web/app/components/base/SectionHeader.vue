<template>
  <div class="flex flex-wrap items-start justify-between gap-6">
    <div class="text-left">
      <slot name="title" class="mt-3 text-3xl font-semibold text-dark" />
      <slot name="description" class="mt-3 max-w-2xl text-sm text-slate-600" />
    </div>
    <slot name="actions" class="flex flex-wrap gap-3" />
  </div>
</template>
