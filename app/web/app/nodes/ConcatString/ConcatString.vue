<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type ConcatStringNode = SchemaNodeType<'concat_string'>

const props = defineProps<{
  node: ConcatStringNode
}>()

const node = useScopedNode<ConcatStringNode>(props.node.id)

if (!node.value.data.settings) {
  node.value.data.settings = { separator: ' ' }
}
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
      v-model="node.data.settings!.separator"
      type="text"
      placeholder="e.g. ', '"
      class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
    >
  </div>
</template>
