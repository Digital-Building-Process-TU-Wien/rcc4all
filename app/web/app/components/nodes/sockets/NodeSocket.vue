<script setup lang="ts">
import type { NodeSocketProps } from '~/composables/useNodeSockets'
import { Handle } from '@vue-flow/core'

const props = withDefaults(defineProps<NodeSocketProps>(), {
  connectable: true,
  warning: false,
})
</script>

<template>
  <Handle
    :id="props.id"
    :type="props.type"
    :position="props.position"
    :connectable="props.connectable"
    :title="props.title"
    class="node-socket border-2! border-white! shadow-sm"
    :class="[
      props.warning
        ? 'bg-amber-500!'
        : props.type === 'target'
          ? 'bg-blue-600!'
          : 'bg-green-600!',
      $slots.default
        ? 'inline-flex! items-center! justify-center! w-auto! h-5! px-0.5!'
        : 'w-4! h-4!',
    ]"
  >
    <slot />
  </Handle>
</template>

<style scoped>
.node-socket {
  border-radius: 4px;
}

.node-socket.vue-flow__handle-left {
  left: -4px;
  transform: translate(-100%, -50%);
}

.node-socket.vue-flow__handle-right {
  right: -4px;
  transform: translate(100%, -50%);
}
</style>
