<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { NodeData } from '~/components/nodes/NodeWrapper.vue'

const props = defineProps<{
  node: NodeProps<NodeData>
}>()

const test = props.node.data.
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      Concat String Node {{ props.node.id }}
    </div>
  </div>

  <div class="flex flex-col gap-2">
    <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Separator</label>
    <input
      type="text"
      class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
    >
  </div>
</template>
