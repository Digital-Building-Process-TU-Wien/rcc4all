<script setup lang="ts">
import type { Connection, Edge, Node } from '@vue-flow/core'
import type { AvailableNode, NodeData, SupportedLocale } from '~/utils/nodes'
import { nanoid } from 'nanoid'
import { storeToRefs } from 'pinia'
import SlideOver from '~/components/nodes/Slideover.vue'
import SubworkflowBreadcrumbs from '~/components/nodes/SubworkflowBreadcrumbs.vue'
import WorkflowFileActions from '~/components/nodes/WorkflowFileActions.vue'
import WorkflowNode from '~/components/nodes/WorkflowNode.vue'
import { openNodeSettingsKey } from '~/composables/useNodeSettings'
import SubworkflowInput from '~/nodes/SubworkflowInput/SubworkflowInput.vue'
import SubworkflowNode from '~/nodes/SubworkflowNode/SubworkflowNode.vue'
import SubworkflowOutput from '~/nodes/SubworkflowOutput/SubworkflowOutput.vue'
import { useFlowStore } from '~/stores/flow'
import {
  createNodeData,
  getAvailableNodeNames,
  getAvailableNodes,
} from '~/utils/nodes'
import {
  getNodeInputs,
  getNodeOutputs,
  INPUT_HANDLE_PREFIX,
  isModelInput,
  OUTPUT_HANDLE_PREFIX,
  parsePortHandle,
} from '~/utils/schema-helpers'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

definePageMeta({
  layout: 'empty',
})

const { locale, t } = useI18n()

const availableNodes = computed(() => {
  const nodes = getAvailableNodes(locale.value as SupportedLocale)
  nodes.push({
    nodeName: 'JsonOutput',
    label: t('node.jsonOutput.title'),
    categories: ['Other'],
    description: t('node.jsonOutput.description'),
  })
  nodes.push({
    nodeName: 'subworkflow',
    label: t('node.subworkflow.title'),
    categories: ['Other'],
    description: t('node.subworkflow.description'),
  })
  return nodes
})

const nodeTypes: Record<string, any> = {
  custom: markRaw(WorkflowNode),
  subworkflow: markRaw(SubworkflowNode),
  subworkflow_input: markRaw(SubworkflowInput),
  subworkflow_output: markRaw(SubworkflowOutput),
}
for (const nodeName of getAvailableNodeNames())
  nodeTypes[nodeName] = markRaw(WorkflowNode)
nodeTypes.JsonOutput = markRaw(WorkflowNode)

const overlay = useOverlay()
const slideover = overlay.create(SlideOver)

function openNodeSettings(nodeId: string) {
  slideover.open({
    isOpen: true,
    nodeId,
  })
}

provide(openNodeSettingsKey, openNodeSettings)

const router = useRouter()
const store = useFlowStore()
const toast = useToast()

const { hasNodes, nodeCount, viewport, breadcrumbs } = storeToRefs(store)
const { setNodes, setEdges, fitView } = store
const nodes = computed(() => Object.values(store.nodesById))

if (!hasNodes.value) {
  setNodes([])
  setEdges([])
}

function handleConnect(params: Connection) {
  const normalizedTargetHandle
    = params.targetHandle === 'input-hitbox' ? 'input' : params.targetHandle

  const edge: Edge = {
    id: nanoid(),
    source: params.source,
    target: params.target,
    sourceHandle: params.sourceHandle,
    targetHandle: normalizedTargetHandle,
  }
  store.addEdges(edge)

  const targetNode = store.nodesById[params.target]
  const sourceNode = store.nodesById[params.source]
  if (!targetNode || !sourceNode)
    return

  const sourceOutputs = getNodeOutputs(sourceNode)
  if (sourceOutputs.length === 0)
    return

  const targetInputs = getNodeInputs(targetNode)
  if (targetInputs.length === 0)
    return

  const currentBindings = targetNode.data.input_bindings || {}
  const explicitOutput = parsePortHandle(params.sourceHandle, OUTPUT_HANDLE_PREFIX)
  const explicitInput = parsePortHandle(params.targetHandle, INPUT_HANDLE_PREFIX)
  const sourceOutput = explicitOutput && sourceOutputs.includes(explicitOutput)
    ? explicitOutput
    : sourceOutputs[0]

  // A File Input node's output is a model slug; ifc_element_filter is the only
  // node with a model input left, so it is the only valid auto-wire target.
  if (sourceNode.data.nodeName === 'file_input') {
    if (targetNode.data.nodeName !== 'ifc_element_filter')
      return

    const modelInput = (explicitInput && isModelInput(explicitInput) ? explicitInput : undefined)
      ?? targetInputs.find(name => isModelInput(name) && !currentBindings[name])
      ?? targetInputs.find(name => isModelInput(name))
    if (!modelInput)
      return

    store.updateNodeData(params.target, {
      input_bindings: {
        ...currentBindings,
        [modelInput]: `${params.source}.model_slug`,
      },
    })
    return
  }

  const firstInput = explicitInput && targetInputs.includes(explicitInput)
    ? explicitInput
    : targetInputs.find(name => !isModelInput(name) && !currentBindings[name])
  if (!firstInput)
    return

  store.updateNodeData(params.target, {
    input_bindings: {
      ...currentBindings,
      [firstInput]: `${params.source}.${sourceOutput}`,
    },
  })
}

function handleNodeClick(params: { node: Node<NodeData>, event: MouseEvent | TouchEvent }) {
  const { node, event } = params
  // Modifier clicks build a multi-selection; the panel would cover the canvas.
  if ('shiftKey' in event && (event.shiftKey || event.ctrlKey || event.metaKey)) {
    slideover.close()
    return
  }

  // A subworkflow opens on double click. Opening the modal panel on the first
  // click would swallow the second one, so its settings live behind the gear icon.
  if (node.data?.nodeName === 'subworkflow')
    return

  openNodeSettings(node.id)
}

function handleSelectionStart() {
  slideover.close()
}

async function handleNodeDoubleClick(params: { node: Node<NodeData> }) {
  if (params.node.data?.nodeName !== 'subworkflow')
    return
  slideover.close()
  if (store.enterSubworkflow(params.node.id)) {
    await nextTick()
    fitView(0.3)
  }
}

async function handleBreadcrumb(index: number) {
  if (index === breadcrumbs.value.length - 1)
    return
  store.goToScope(index)
  await nextTick()
  fitView(0.24)
}

function handleBreadcrumbRename(name: string) {
  store.renameActiveSubworkflow(name)
}

const insideSubworkflow = computed(() => breadcrumbs.value.length > 1)
const hasSubworkflowOutput = computed(() =>
  store.nodes.some(node => node.data?.nodeName === 'subworkflow_output'),
)

function handleAddPort(kind: 'input' | 'output') {
  store.addSubworkflowPort(kind)
}

async function handleExtract(nodeIds: string[]) {
  const result = store.extractToSubworkflow(nodeIds, t('node.subworkflow.defaultName'))
  if (!result.ok) {
    toast.add({
      title: t('editor.extractFailed'),
      description: result.reason === 'output-conflict'
        ? t('editor.extractOutputConflict', {
            references: result.details.join(', '),
          })
        : result.reason === 'meta-node'
          ? t('editor.extractMetaNode')
          : t('editor.extractEmpty'),
      color: 'error',
    })
    return
  }

  if (store.enterSubworkflow(result.nodeId)) {
    await nextTick()
    fitView(0.3)
  }
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

  store.addNodes({
    id: nanoid(),
    type: availableNode.nodeName,
    position: position ?? getNextNodePosition(),
    data: createNodeData(availableNode),
  })

  if (shouldFitView && !position) {
    fitView(0.24)
  }
}

function clearCanvas() {
  store.clear()
}

async function handleWorkflowLoaded() {
  // The panel points at a node id that the loaded workflow no longer has.
  slideover.close()
  await nextTick()
  fitView(0.24)
}

async function runWorkflow() {
  store.setWorkflowData(store.exportWorkflow())

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
        :inside-subworkflow="insideSubworkflow"
        :has-subworkflow-output="hasSubworkflowOutput"
        @add-node="addNodeToCanvas"
        @add-input="handleAddPort('input')"
        @add-output="handleAddPort('output')"
        @run-workflow="runWorkflow"
        @clear-canvas="clearCanvas"
      />

      <UDashboardPanel class="min-w-0">
        <template #default>
          <div class="flex h-full min-h-0 flex-col">
            <div class="flex items-stretch border-b border-default bg-elevated">
              <div class="flex min-w-0 flex-1">
                <ModelBar />
              </div>
              <div class="flex shrink-0 items-center px-4">
                <WorkflowFileActions @loaded="handleWorkflowLoaded" />
              </div>
            </div>

            <SubworkflowBreadcrumbs
              v-if="breadcrumbs.length > 1"
              :items="breadcrumbs"
              @navigate="handleBreadcrumb"
              @rename="handleBreadcrumbRename"
            />

            <NodeCanvas
              class="min-h-0 flex-1"
              :nodes="nodes"
              :edges="store.edges"
              :viewport="viewport"
              :node-types="nodeTypes"
              :has-nodes="hasNodes"
              :available-nodes="availableNodes"
              @connect="handleConnect"
              @node-click="handleNodeClick"
              @node-double-click="handleNodeDoubleClick"
              @selection-start="handleSelectionStart"
              @extract="handleExtract"
            />
          </div>
        </template>
      </UDashboardPanel>
    </UDashboardGroup>
  </div>
</template>
