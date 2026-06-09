<script setup lang="ts">
import type { AvailableNode } from '~/utils/nodes'

defineProps<{
  node: AvailableNode
  draggable?: boolean
}>()

const emit = defineEmits<{
  dragStart: [event: DragEvent, node: AvailableNode]
  dragEnd: []
  add: [node: AvailableNode]
}>()
</script>

<template>
  <UButton
    color="neutral"
    variant="ghost"
    size="sm"
    :block="true"
    icon="i-lucide-box"
    :label="node.label"
    :title="node.label"
    trailing-icon="i-lucide-plus"
    class="justify-start" :class="[draggable ? 'cursor-grab active:cursor-grabbing' : '']"
    :draggable="draggable"
    @dragstart="(e: DragEvent) => emit('dragStart', e, node)"
    @dragend="emit('dragEnd')"
    @click="emit('add', node)"
  />
</template>
