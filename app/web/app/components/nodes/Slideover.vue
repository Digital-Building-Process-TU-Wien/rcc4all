<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
import { getNodeComponent } from '~/utils/nodes'

const props = defineProps<{
  isOpen: boolean
  node: NodeProps<NodeData>
}>()

const emit = defineEmits<{
  close: []
}>()

const component = computed(() => {
  if (!props.node?.data.nodeName)
    return null
  console.log('Finding component for nodeName:', props.node.data.nodeName, getNodeComponent(props.node.data.nodeName))
  console.log('Props', props)
  return getNodeComponent(props.node.data.nodeName)
})
</script>

<template>
  <USlideover
    title="Node Details"
    description="Configure and inspect node properties"
    @close="emit('close')"
  >
    <template #body>
      <div class="flex flex-col h-full">
        <div class="flex-1 overflow-y-auto p-4">
          <template v-if="node && component">
            <component
              :is="component"
              :node="node"
            />
          </template>

          <div
            v-else-if="node"
            class="text-sm text-slate-500"
          >
            test
            <p class="font-semibold mb-2">
              {{ node.data?.label }}
            </p>
            <p>Node component not found: {{ node.data?.nodeName }}</p>
          </div>

          <div
            v-else
            class="text-sm text-slate-400"
          >
            Select a node to view details
          </div>
        </div>
      </div>
    </template>
  </USlideover>
</template>
