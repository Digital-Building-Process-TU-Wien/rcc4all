<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
import { getNodeComponent, getAvailableNodes } from '~/utils/nodes'

const props = defineProps<{
  isOpen: boolean
  node: Node<NodeData>
}>()
const emit = defineEmits<{
  close: []
}>()

const component = computed(() => {
  if (!props.node.id)
    return null

  return getNodeComponent(props.node.data!.nodeName)
})

const nodeDocs = computed(() => {
  const availableNodes = getAvailableNodes()
  return availableNodes.find(n => n.nodeName === props.node.data?.nodeName)
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

            <div v-if="nodeDocs" class="mt-6 border-t border-default pt-4">
              <h3 class="text-sm font-semibold text-highlighted mb-2">
                Documentation
              </h3>
              <p v-if="nodeDocs.description" class="text-sm text-muted mb-3">
                {{ nodeDocs.description }}
              </p>
              <MDC
                v-if="nodeDocs.markdownDescription"
                :value="nodeDocs.markdownDescription"
                class="prose prose-sm dark:prose-invert max-w-none"
              />
            </div>
          </template>

          <div
            v-else-if="node"
            class="text-sm text-slate-500"
          >
            <p class="font-semibold mb-2">
              {{ node?.data?.label || 'Unknown Node' }}
            </p>
            <p>Node component not found: {{ node.data!.nodeName }}</p>
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
