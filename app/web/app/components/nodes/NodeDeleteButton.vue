<script setup lang="ts">
import { useFlowStore } from '~/stores/flow'

interface Props {
  nodeId: string
}

const props = defineProps<Props>()
const store = useFlowStore()
const showConfirm = ref(false)

function handleDeleteClick() {
  showConfirm.value = true
}

function handleConfirmDelete() {
  store.removeNode(props.nodeId)
  showConfirm.value = false
}

function handleCancel() {
  showConfirm.value = false
}
</script>

<template>
  <div class="flex items-center justify-center">
    <template v-if="showConfirm">
      <button
        type="button"
        class="w-6 text-xs font-medium text-red-600 hover:text-red-700"
        @click.stop="handleConfirmDelete"
      >
        <UIcon name="i-heroicons-trash" class="size-4" />
      </button>
      <button
        type="button"
        class="w-6 text-xs text-slate-400 hover:text-slate-600"
        @click.stop="handleCancel"
      >
        <UIcon name="i-heroicons-x-mark" class="size-4" />
      </button>
    </template>
    <button
      v-else
      type="button"
      class="text-slate-400 opacity-0 transition-colors group-hover:opacity-100 hover:text-red-600"
      @click.stop="handleDeleteClick"
    >
      <UIcon name="i-heroicons-trash" class="size-4" />
    </button>
  </div>
</template>
