<script setup lang="ts">
import type { AvailableNode } from '~/utils/nodes'

defineProps<{
  category: string
  nodes: AvailableNode[]
  isExpanded: boolean
  draggable?: boolean
}>()

const emit = defineEmits<{
  toggle: [category: string]
  add: [node: AvailableNode]
  dragStart: [event: DragEvent, node: AvailableNode]
  dragEnd: []
}>()
</script>

<template>
  <div class="mb-2">
    <button
      class="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted hover:bg-default hover:text-highlighted"
      @click="emit('toggle', category)"
    >
      <span class="flex items-center gap-2">
        <Icon
          :name="isExpanded ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
          class="size-4"
        />
        {{ category }}
      </span>
      <UBadge color="neutral" variant="soft" size="xs">
        {{ nodes.length }}
      </UBadge>
    </button>
    <div v-if="isExpanded" class="mt-1 flex flex-col gap-1 pl-2">
      <NodePaletteItem
        v-for="node in nodes"
        :key="node.nodeName"
        :node="node"
        :draggable="draggable"
        @drag-start="(e: DragEvent) => emit('dragStart', e, node)"
        @drag-end="emit('dragEnd')"
        @add="emit('add', node)"
      />
    </div>
  </div>
</template>
