<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type GetNameNode = SchemaNodeType<'get_name'>

const props = defineProps<{
  node: GetNameNode
}>()

const node = useScopedNode<GetNameNode>(props.node.id)

if (!node.value.data.settings) {
  node.value.data.settings = { allow_missing: true, express_ids: [] }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      Get Name Node
    </div>
  </div>

  <div class="flex flex-col gap-2">
    <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Express IDs</label>
    <input
      v-model="node.data.settings!.express_ids"
      type="text"
      placeholder="e.g. 123, 456"
      class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
    >

    <div class="flex items-center gap-2 mt-1">
      <input
        id="allow-missing"
        v-model="node.data.settings!.allow_missing"
        type="checkbox"
        class="rounded bg-white border-slate-200 accent-blue-600 w-3 h-3"
      >
      <label for="allow-missing" class="text-[10px] text-slate-500 cursor-pointer font-medium">Allow Missing</label>
    </div>
  </div>
</template>
