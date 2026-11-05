<script setup lang="ts">
import type { Connection, Edge, Node } from '@vue-flow/core'
import type { AvailableNode, NodeData } from '~/utils/nodes'
import { VueFlow } from '@vue-flow/core'
import { nanoid } from 'nanoid'
import { useFlowStore } from '~/stores/flow'
import { createNodeData } from '~/utils/nodes'

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
  nodeClick: [params: { node: Node<NodeData>, event: MouseEvent | TouchEvent }]
  nodeDoubleClick: [params: { node: Node<NodeData> }]
  selectionStart: []
  extract: [nodeIds: string[]]
}>()

const store = useFlowStore()
const { t } = useI18n()

interface SelectableNode {
  id: string
  selected?: boolean
}

type InteractionMode = 'select' | 'pan'

const vueFlowRef = ref<InstanceType<typeof VueFlow> | null>(null)
const isConnecting = ref(false)
const interactionMode = ref<InteractionMode>('pan')
const isSelectMode = computed(() => interactionMode.value === 'select')
const interactionHint = computed(() =>
  isSelectMode.value ? t('editor.hintSelect') : t('editor.hintPan'),
)
const selectedNodeIds = computed(() =>
  (props.nodes as SelectableNode[]).filter(node => node.selected).map(node => node.id),
)

function setInteractionMode(mode: InteractionMode) {
  interactionMode.value = mode
}

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

  store.addNodes({
    id: nanoid(),
    type: nodeName,
    position,
    data: createNodeData(availableNode),
  })
}
</script>

<template>
  <UDashboardPanel id="node-demo-panel" class="min-w-0">
    <div class="flex h-full min-h-0 flex-col">
      <UDashboardNavbar :toggle="false" :ui="{ root: 'h-10' }">
        <template #right>
          <span class="mr-3 hidden text-xs text-muted md:inline">
            {{ interactionHint }}
          </span>
          <div class="mr-3 flex items-center rounded-md border border-default p-0.5">
            <UButton
              icon="i-lucide-mouse-pointer-2"
              size="xs"
              :variant="isSelectMode ? 'soft' : 'ghost'"
              :color="isSelectMode ? 'primary' : 'neutral'"
              :aria-pressed="isSelectMode"
              :aria-label="t('editor.modeSelect')"
              :title="t('editor.modeSelect')"
              @click="setInteractionMode('select')"
            />
            <UButton
              icon="i-lucide-hand"
              size="xs"
              :variant="isSelectMode ? 'ghost' : 'soft'"
              :color="isSelectMode ? 'neutral' : 'primary'"
              :aria-pressed="!isSelectMode"
              :aria-label="t('editor.modePan')"
              :title="t('editor.modePan')"
              @click="setInteractionMode('pan')"
            />
          </div>
          <UBadge color="neutral" variant="soft">
            {{ t('editor.nodeCount', nodes.length) }}
          </UBadge>
        </template>
      </UDashboardNavbar>

      <div class="relative min-h-0 flex-1 bg-default" :class="{ 'is-connecting': isConnecting }">
        <VueFlow
          ref="vueFlowRef"
          :nodes="nodes"
          :edges="edges"
          :viewport="viewport"
          :node-types="nodeTypes"
          :selection-key-code="isSelectMode ? true : 'Shift'"
          :pan-on-drag="isSelectMode ? false : [0, 1, 2]"
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
          @node-double-click="emit('nodeDoubleClick', $event)"
          @selection-start="emit('selectionStart')"
          @dragover.prevent="handleDragOver"
          @drop.prevent="handleDrop"
        >
          <EmptyCanvasPrompt v-if="!hasNodes" />
        </VueFlow>

        <div
          v-if="selectedNodeIds.length > 0"
          class="absolute bottom-4 right-4 z-10 flex items-center gap-2 rounded-lg border border-default bg-elevated p-2 shadow-lg"
        >
          <UBadge color="neutral" variant="soft">
            {{ t('editor.selectionCount', { count: selectedNodeIds.length }) }}
          </UBadge>
          <UButton
            icon="i-lucide-package-plus"
            :label="t('editor.addToSubworkflow')"
            @click="emit('extract', selectedNodeIds)"
          />
        </div>
      </div>
    </div>
  </UDashboardPanel>
</template>

<style>
.vue-flow__node {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}

/* Node cards render their own chrome, so the flow theme cannot show selection. */
.vue-flow__node.selected > div {
  outline: 2px solid var(--ui-primary);
  outline-offset: 2px;
}

.vue-flow__selection,
.vue-flow__nodesselection-rect {
  background: color-mix(in oklab, var(--ui-primary) 8%, transparent) !important;
  border: 1px dashed var(--ui-primary) !important;
}

.vue-flow__pane.selection {
  cursor: crosshair;
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
