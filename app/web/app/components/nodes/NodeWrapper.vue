<script lang="ts" setup>
import { Handle, Position } from '@vue-flow/core'

defineProps<{
  inputs?: string[]
  outputs?: string[]
}>()
</script>

<template>
  <div class="bg-white text-slate-900 border-2 border-slate-200 rounded-lg min-w-[180px] shadow-sm relative">
    <!-- Dynamic Target Handles (Left) -->
    <div v-if="inputs" class="absolute -left-2 top-0 bottom-0 flex flex-col justify-around py-4">
      <div v-for="input in inputs" :key="input" class="relative flex items-center group">
        <Handle
          :id="input"
          type="target"
          :position="Position.Left"
          class="!w-4 !h-4 !bg-blue-600 !border-2 !border-white !static shadow-sm"
        />
        <span class="absolute left-6 text-[10px] uppercase font-bold text-slate-400 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity bg-white border border-slate-200 px-1 rounded shadow-sm pointer-events-none z-30">
          {{ input }}
        </span>
      </div>
    </div>
    <!-- Fallback single handle if prop is undefined (not provided) -->
    <Handle
      v-else
      type="target"
      :position="Position.Left"
      class="!w-4 !h-4 !bg-blue-600 !border-2 !border-white !-left-2 shadow-sm"
    />

    <div class="p-4 flex flex-col gap-4">
      <slot />

      <!-- Settings Area -->
      <div v-if="$slots.settings" class="mt-2 pt-4 border-t border-slate-100 flex flex-col gap-3">
        <div class="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
          Settings
        </div>
        <slot name="settings" />
      </div>
    </div>

    <!-- Dynamic Source Handles (Right) -->
    <div v-if="outputs" class="absolute -right-2 top-0 bottom-0 flex flex-col justify-around py-4">
      <div v-for="output in outputs" :key="output" class="relative flex items-center group justify-end">
        <span class="absolute right-6 text-[10px] uppercase font-bold text-slate-400 whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity bg-white border border-slate-200 px-1 rounded shadow-sm pointer-events-none z-30">
          {{ output }}
        </span>
        <Handle
          :id="output"
          type="source"
          :position="Position.Right"
          class="!w-4 !h-4 !bg-green-600 !border-2 !border-white !static shadow-sm"
        />
      </div>
    </div>
    <!-- Fallback single handle if prop is undefined (not provided) -->
    <Handle
      v-else
      type="source"
      :position="Position.Right"
      class="!w-4 !h-4 !bg-green-600 !border-2 !border-white !-right-2 shadow-sm"
    />
  </div>
</template>

<style scoped>
.vue-flow__handle {
  border-radius: 4px;
}
</style>
