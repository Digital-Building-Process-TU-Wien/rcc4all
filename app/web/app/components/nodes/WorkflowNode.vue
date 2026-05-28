<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
import { Handle, Position } from '@vue-flow/core'

const props = defineProps<NodeProps<NodeData>>()
</script>

<template>
  <div
    class="bg-white text-slate-900 border-2 border-slate-200 rounded-lg min-w-45 shadow-sm relative cursor-pointer hover:shadow-md transition-shadow"
  >
    <Handle
      v-if="!props.data?.noInput"
      type="target"
      :position="Position.Left"
      class="w-4! h-4! bg-blue-600! border-2! border-white! -left-2! shadow-sm"
    />
    <div class="flex flex-col px-3 py-2">
      <span class="font-medium">{{ props.data.label }}</span>
    </div>
    <Handle
      type="source"
      :position="Position.Right"
      class="w-4! h-4! bg-green-600! border-2! border-white! -right-2! shadow-sm"
    />
  </div>
</template>

<style scoped>
.vue-flow__handle {
  border-radius: 4px;
}
</style>
