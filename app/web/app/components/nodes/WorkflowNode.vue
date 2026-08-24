<script lang="ts" setup>
import type { NodeProps } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
import { Handle, Position } from '@vue-flow/core'
import { ref } from 'vue'
import { useFlowStore } from '~/stores/flow'

const props = defineProps<NodeProps<NodeData>>()
const store = useFlowStore()
const showConfirm = ref(false)

function handleDeleteClick() {
  showConfirm.value = true
}

function handleConfirmDelete() {
  store.removeNode(props.id)
  showConfirm.value = false
}

function handleCancel() {
  showConfirm.value = false
}
</script>

<template>
  <div
    class="bg-white text-slate-900 border-2 border-slate-200 rounded-lg min-w-45 shadow-sm relative cursor-pointer hover:shadow-md transition-shadow"
  >
    <Handle
      v-if="!props.data?.noInput"
      id="input-hitbox"
      type="target"
      :position="Position.Left"
      class="node-hitbox"
    />

    <Handle
      v-if="!props.data?.noInput"
      id="input"
      type="target"
      :position="Position.Left"
      :connectable="false"
      class="w-4! h-4! bg-blue-600! border-2! border-white! -left-2! shadow-sm"
    />
    <div class="group flex items-center justify-between gap-2 px-3 py-2">
      <span class="font-medium truncate">{{ props.data.label }}</span>
      <div v-if="showConfirm" class="flex items-center justify-center">
        <button
          type="button"
          class="text-xs text-red-600 hover:text-red-700 font-medium w-6"
          @click.stop="handleConfirmDelete"
        >
          <UIcon name="i-heroicons-trash" class="w-4 h-4" />
        </button>
        <button
          type="button"
          class="text-xs text-slate-400 hover:text-slate-600 w-6"
          @click.stop="handleCancel"
        >
          <UIcon name="i-heroicons-x-mark" class="w-4 h-4" />
        </button>
      </div>
      <button
        v-else
        type="button"
        class="text-slate-400 hover:text-red-600 transition-colors relative z-10 opacity-0 group-hover:opacity-100"
        @click.stop="handleDeleteClick"
      >
        <UIcon name="i-heroicons-trash" class="w-4 h-4" />
      </button>
    </div>
    <Handle
      v-if="data?.nodeName !== 'JsonOutput' && data?.nodeName !== 'bcf_output'"
      id="output"
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

.vue-flow__handle.node-hitbox {
  position: absolute;
  inset: 0;
  width: 100% !important;
  height: 100% !important;
  transform: none;
  border: none;
  background: transparent;
  opacity: 0;
  z-index: 1;
  pointer-events: none;
}
</style>
