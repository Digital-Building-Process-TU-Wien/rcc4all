<script setup lang="ts">
import type { Connection, Edge, Node } from '@vue-flow/core'
import type { AvailableNode, NodeData } from '~/utils/nodes'
import { VueFlow } from '@vue-flow/core'
import { nanoid } from 'nanoid'
import { useFlowStore } from '~/stores/flow'

interface Props {
  nodes: Node<NodeData>[]
  edges: Edge[]
  viewport: { x: number, y: number, zoom: number }
  nodeTypes: Record<string, any>
  hasNodes: boolean
  availableNodes: AvailableNode[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  connect: [params: Connection]
  nodeClick: [params: { node: Node<NodeData> }]
}>()

const store = useFlowStore()

const vueFlowRef = ref<InstanceType<typeof VueFlow> | null>(null)
const isConnecting = ref(false)

function handleDragOver(event: DragEvent) {
  event.preventDefault()
  event.dataTransfer!.dropEffect = 'copy'
}

function getCanvasCoordinates(event: DragEvent): { x: number, y: number } {
  const vueFlowElement = document.querySelector('.vue-flow')
  if (!vueFlowElement) {
    console.error('[getCanvasCoordinates] VueFlow element not found')
    return { x: 100, y: 100 }
  }

  const rect = vueFlowElement.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  const projected = vueFlowRef.value?.project({ x, y })

  return projected || { x, y }
}

function handleDrop(event: DragEvent) {
  event.preventDefault()
  event.stopPropagation()

  const nodeName = event.dataTransfer?.getData('application/node')

  if (!nodeName)
    return

  const availableNode = props.availableNodes.find(n => n.nodeName === nodeName)
  if (!availableNode)
    return

  const position = getCanvasCoordinates(event)

  const isFileInputNode = nodeName === 'FileInput'

  store.addNodes({
    id: nanoid(),
    type: 'custom',
    position,
    data: {
      label: availableNode.label,
      noInput: isFileInputNode,
      nodeName: availableNode.nodeName,
    },
  })
}
</script>

<template>
  <UDashboardPanel id="node-demo-panel" class="min-w-0">
    <template #header>
      <UDashboardNavbar title="BIM Node Editor Demo">
        <template #right>
          <UBadge color="neutral" variant="soft">
            {{ nodes.length }} {{ nodes.length === 1 ? 'node' : 'nodes' }}
          </UBadge>
        </template>
      </UDashboardNavbar>
    </template>

    <template #default>
      <div class="relative h-full bg-default" :class="{ 'is-connecting': isConnecting }">
        <VueFlow
          ref="vueFlowRef"
          :nodes="nodes"
          :edges="edges"
          :viewport="viewport"
          :node-types="nodeTypes"
          class="h-full bg-default"
          @update:nodes="(newNodes: Node[]) => {
            const newById: Record<string, Node> = {}
            newNodes.forEach((node: Node) => {
              newById[node.id] = node
            })
            store.nodesById = newById
          }"
          @update:edges="(newEdges: Edge[]) => {
            store.edges = newEdges
          }"
          @update:viewport="(newViewport: { x: number, y: number, zoom: number }) => {
            store.viewport = newViewport
          }"
          @connect="emit('connect', $event)"
          @connect-start="isConnecting = true"
          @connect-end="isConnecting = false"
          @node-click="emit('nodeClick', $event)"
          @dragover.prevent="handleDragOver"
          @drop.prevent="handleDrop"
        >
          <EmptyCanvasPrompt v-if="!hasNodes" />
        </VueFlow>
      </div>
    </template>
  </UDashboardPanel>
</template>

<style>
.vue-flow__node {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}

.vue-flow__edge-path {
  stroke: #cbd5e1 !important;
  stroke-width: 3;
}

.vue-flow__handle:not(.node-hitbox) {
  width: 12px !important;
  height: 12px !important;
}

.vue-flow__handle.node-hitbox {
  pointer-events: none !important;
}

.is-connecting .vue-flow__handle.node-hitbox {
  pointer-events: all !important;
}

/* Custom grid dots for light theme */
.vue-flow {
  background-image: radial-gradient(#e2e8f0 2px, transparent 1px);
  background-size: 48px 48px;
}

/* Drag and drop styles */
[draggable="true"] {
  user-select: none;
}

[draggable="true"]:active {
  cursor: grabbing;
}
</style>
