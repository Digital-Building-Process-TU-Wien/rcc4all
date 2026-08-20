<script setup lang="ts">
import type { Connection, Edge, Node } from '@vue-flow/core'
import type { AvailableNode, NodeData, SupportedLocale } from '~/utils/nodes'
import { nanoid } from 'nanoid'
import { storeToRefs } from 'pinia'
import SlideOver from '~/components/nodes/Slideover.vue'
import WorkflowNode from '~/components/nodes/WorkflowNode.vue'
import { useFlowStore } from '~/stores/flow'
import { getAvailableNodes } from '~/utils/nodes'
import { getNodeInputs, getNodeOutputs } from '~/utils/schema-helpers'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

definePageMeta({
  layout: 'empty',
})

const { locale } = useI18n()

const availableNodes = computed(() => {
  const nodes = getAvailableNodes(locale.value as SupportedLocale)
  nodes.push({
    nodeName: 'FileInput',
    label: 'File Input',
    categories: ['Other'],
    description: 'Select an IFC file from local development files',
  })
  nodes.push({
    nodeName: 'JsonOutput',
    label: 'JSON Output',
    categories: ['Other'],
    description: 'Visual endcap for workflow output',
  })
  return nodes
})

const nodeTypes = {
  custom: markRaw(WorkflowNode),
}

const selectedNode = shallowRef<Node<NodeData> | null>(null)
const overlay = useOverlay()
const slideover = overlay.create(SlideOver)

const router = useRouter()
const store = useFlowStore()

const { hasNodes, nodeCount, viewport } = storeToRefs(store)
const { setNodes, setEdges, fitView } = store
const nodes = computed(() => Object.values(store.nodesById))

if (!hasNodes.value) {
  setNodes([])
  setEdges([])
}

function handleConnect(params: Connection) {
  const edge: Edge = {
    id: nanoid(),
    source: params.source,
    target: params.target,
    sourceHandle: params.sourceHandle,
    targetHandle:
      params.targetHandle === 'input-hitbox'
        ? 'input'
        : params.targetHandle,
  }
  store.addEdges(edge)

  const targetNode = store.nodesById[params.target]
  if (targetNode) {
    const inputs = getNodeInputs(targetNode.data.nodeName)
    const outputs = getNodeOutputs(params.source)

    if (inputs.length > 0 && outputs.length > 0) {
      const firstInput = inputs[0]
      const firstOutput = outputs[0]

      const currentBindings = targetNode.data.input_bindings || {}

      if (firstInput && !currentBindings[firstInput]) {
        store.updateNodeData(params.target, {
          input_bindings: {
            ...currentBindings,
            [firstInput]: `${params.source}.${firstOutput}`,
          },
        })
      }
    }
  }
}

function handleNodeClick(params: { node: Node<NodeData> }) {
  slideover.open({
    isOpen: true,
    nodeId: params.node.id,
  })
}

function getNextNodePosition() {
  const nodeIndex = nodes.value.length
  const basePosition = {
    x: window.innerWidth * 0.58,
    y: Math.max(window.innerHeight * 0.24, 180),
  }

  return {
    x: basePosition.x + (nodeIndex % 3) * 56,
    y: basePosition.y + Math.floor(nodeIndex / 3) * 108,
  }
}

function addNodeToCanvas(availableNode: AvailableNode, position?: { x: number, y: number }) {
  const shouldFitView = nodes.value.length === 0

  const isFileInputNode = availableNode.nodeName === 'FileInput'

  store.addNodes({
    id: nanoid(),
    type: 'custom',
    position: position ?? getNextNodePosition(),
    data: {
      label: availableNode.label,
      noInput: isFileInputNode,
      nodeName: availableNode.nodeName,
    },
  })

  if (shouldFitView && !position) {
    fitView(0.24)
  }
}

function clearCanvas() {
  selectedNode.value = null
  store.clear()
}

function parseSettings(settings: any, _nodeType: string) {
  const parsed = { ...settings }

  return parsed
}

async function runWorkflow() {
  const fileInputNode = nodes.value.find(node => node.data.nodeName === 'FileInput')
  const ifcPath = fileInputNode?.data?.filename || 'test.ifc'

  const workflowNodeIds = new Set<string>()
  const workflowNodes = nodes.value
    .filter(node => node.data.nodeName !== 'FileInput' && node.data.nodeName !== 'JsonOutput')
    .map((node) => {
      workflowNodeIds.add(node.id)
      return {
        id: node.id,
        type: node.data.nodeName.toLowerCase(),
        label: node.data.label || '',
        settings: parseSettings(node.data.settings || {}, node.data.nodeName),
        input_bindings: node.data.input_bindings || {},
      }
    })

  const workflowEdges = store.edges
    .filter(edge => workflowNodeIds.has(edge.source) && workflowNodeIds.has(edge.target))
    .map(edge => ({
      source: edge.source,
      target: edge.target,
    }))

  store.setWorkflowData({
    ifc_path: ifcPath,
    nodes: workflowNodes,
    edges: workflowEdges,
  })

  router.push({
    path: '/results',
  })
}
</script>

<template>
  <div class="h-screen overflow-hidden bg-default text-default">
    <UDashboardGroup class="h-full">
      <NodeLibrarySidebar
        :has-nodes="hasNodes"
        :node-count="nodeCount"
        @add-node="addNodeToCanvas"
        @run-workflow="runWorkflow"
        @clear-canvas="clearCanvas"
      />

      <NodeCanvas
        :nodes="nodes"
        :edges="store.edges"
        :viewport="viewport"
        :node-types="nodeTypes"
        :has-nodes="hasNodes"
        :available-nodes="availableNodes"
        @connect="handleConnect"
        @node-click="handleNodeClick"
      />
    </UDashboardGroup>
  </div>
</template>
