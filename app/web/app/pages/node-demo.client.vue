<script setup lang="ts">
import type { Connection, Edge, Node } from '@vue-flow/core'
import type { AvailableNode, NodeData } from '~/utils/nodes'
import { nanoid } from 'nanoid'
import { storeToRefs } from 'pinia'
import SlideOver from '~/components/nodes/Slideover.vue'
import WorkflowNode from '~/components/nodes/WorkflowNode.vue'
import { usei18n } from '~/composables/usei18n'
import { useFlowStore } from '~/stores/flow'
import { getAvailableNodes } from '~/utils/nodes'
import { getNodeInputs, getNodeOutputs } from '~/utils/schema-helpers'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

definePageMeta({
  layout: 'empty',
})

const { currentLocale } = usei18n()

const availableNodes = computed(() => {
  const nodes = getAvailableNodes(currentLocale.value)
  nodes.push({
    nodeName: 'FileInput',
    label: 'File Input',
    categories: ['Other'],
    description: 'Select an IFC file from local development files',
  })
  return nodes
})

const nodeTypes = {
  custom: markRaw(WorkflowNode),
}

const selectedNode = shallowRef<Node<NodeData> | null>(null)
const overlay = useOverlay()
const slideover = overlay.create(SlideOver)

const store = useFlowStore()
const { hasNodes, nodeCount, viewport } = storeToRefs(store)
const { setNodes, setEdges, fitView } = store
const nodes = computed(() => Object.values(store.nodesById))
const isRunning = ref(false)

setNodes([])
setEdges([])

function handleConnect(params: Connection) {
  const edge: Edge = {
    id: nanoid(),
    source: params.source,
    target: params.target,
    sourceHandle: params.sourceHandle,
    targetHandle: params.targetHandle,
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
    node: params.node,
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

function parseSettings(settings: any, nodeType: string) {
  const parsed = { ...settings }

  if (nodeType === 'get_name' && parsed.express_ids) {
    const ids = parsed.express_ids
    if (typeof ids === 'string') {
      parsed.express_ids = ids.split(',').map((s: string) => Number.parseInt(s.trim(), 10)).filter((n: number) => !Number.isNaN(n))
    }
  }

  return parsed
}

async function runWorkflow() {
  if (isRunning.value)
    return

  const fileInputNode = nodes.value.find(node => node.data.nodeName === 'FileInput')
  const ifcPath = fileInputNode?.data?.filename || 'test.ifc'

  const workflowNodeIds = new Set<string>()
  const workflowNodes = nodes.value
    .filter(node => node.data.nodeName !== 'FileInput')
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

  const workflow = {
    ifc_path: ifcPath,
    nodes: workflowNodes,
    edges: workflowEdges,
  }

  isRunning.value = true

  try {
    const result = await $fetch('/api/workflow/execute', {
      method: 'POST',
      body: workflow,
    })

    if (result.success) {
      window.open(`/results?file=${result.resultsPath}`, '_blank')
    }
    else if ('error' in result && result.error) {
      console.error('Workflow execution failed:', result.error)
    }
  }
  catch (error: any) {
    console.error('Failed to execute workflow:', error)
  }
  finally {
    isRunning.value = false
  }
}
</script>

<template>
  <div class="h-screen overflow-hidden bg-default text-default">
    <UDashboardGroup class="h-full">
      <NodeLibrarySidebar
        :has-nodes="hasNodes"
        :node-count="nodeCount"
        :is-running="isRunning"
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
