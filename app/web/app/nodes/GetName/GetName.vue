<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type GetNameNode = SchemaNodeType<'get_name'>

const props = defineProps<{
  node: GetNameNode
}>()

const node = useScopedNode<GetNameNode>(props.node.id)

if (!node.value.data.settings) {
  node.value.data.settings = { fail_on_missing: false }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      Get Name Node
    </div>
  </div>

  <div class="flex flex-col gap-2">
    <div class="flex items-center gap-2">
      <input
        id="fail-on-missing"
        v-model="node.data.settings!.fail_on_missing"
        type="checkbox"
        class="rounded bg-white border-slate-200 accent-blue-600 w-3 h-3"
      >
      <label for="fail-on-missing" class="text-[10px] text-slate-500 cursor-pointer font-medium">Fail on Missing</label>
    </div>
  </div>
</template>
