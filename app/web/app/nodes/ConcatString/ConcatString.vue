<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { NodeData, NodeTypeFromSchema } from '~/utils/nodes'

const props = defineProps<{
  node: NodeProps<NodeTypeFromSchema<'concat_string'>>
}>()

const test = props.node.data
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      Concat String Node
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
