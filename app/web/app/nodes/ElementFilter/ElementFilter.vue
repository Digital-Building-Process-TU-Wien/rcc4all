<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type ElementFilterNode = SchemaNodeType<'element_filter'>

const props = defineProps<{
  node: ElementFilterNode
}>()

const node = useScopedNode<ElementFilterNode>(props.node.id)

if (!node.value.data.settings) {
  node.value.data.settings = { entity_type: 'IFCWALL' }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      Element Filter Node
    </div>
  </div>

  <div class="flex flex-col gap-2">
    <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Entity Type</label>
    <input
      v-model="node.data.settings!.entity_type"
      type="text"
      placeholder="e.g. IFCWALL"
      class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
    >
  </div>
</template>
