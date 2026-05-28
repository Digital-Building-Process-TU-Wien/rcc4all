<script setup lang="ts">
import type { Connection, Node } from '@vue-flow/core'
import type { AvailableNode, NodeData } from '~/utils/nodes'
import { useVueFlow, VueFlow } from '@vue-flow/core'
import { nanoid } from 'nanoid'
import SlideOver from '~/components/nodes/Slideover.vue'
import WorkflowNode from '~/components/nodes/WorkflowNode.vue'
import { getAvailableNodes, VUEFLOW_ID } from '~/utils/nodes'

// Import nodes
// Basic Vue Flow styling
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

definePageMeta({
  layout: 'empty',
})

const availableNodes = getAvailableNodes()

const viewMode = ref<'all' | 'categories'>('all')
const searchQuery = ref('')
const expandedCategories = ref<Set<string>>(new Set(['IFC', '3D operation', 'Demo', 'Filter', 'Other']))

const allCategories = computed(() => {
  const categories = new Set<string>()
  availableNodes.forEach(node => {
    node.categories.forEach(cat => categories.add(cat))
  })
  return Array.from(categories).sort()
})

const filteredNodes = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query) return availableNodes
  
  return availableNodes.filter(node => 
    node.label.toLowerCase().includes(query) ||
    node.nodeName.toLowerCase().includes(query)
  )
})

const nodesByCategory = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const result: Record<string, AvailableNode[]> = {}
  
  availableNodes.forEach(node => {
    let nodeMatches = true
    if (query) {
      nodeMatches = node.label.toLowerCase().includes(query) ||
                    node.nodeName.toLowerCase().includes(query)
    }
    
    if (!nodeMatches) return
    
    const hasCategories = node.categories.length > 0
    
    if (hasCategories) {
      node.categories.forEach(cat => {
        let categoryMatches = true
        if (query) {
          categoryMatches = cat.toLowerCase().includes(query)
        }
        
        if (categoryMatches || nodeMatches) {
          if (!result[cat]) result[cat] = []
          if (!result[cat].some(n => n.nodeName === node.nodeName)) {
            result[cat].push(node)
          }
        }
      })
    } else {
      if (!result['Other']) result['Other'] = []
      result['Other'].push(node)
    }
  })
  
  Object.values(result).forEach(nodes => {
    nodes.sort((a, b) => a.label.localeCompare(b.label))
  })
  
  return result
})

const displayedCategories = computed(() => {
  return Object.keys(nodesByCategory.value).sort()
})

function toggleCategory(category: string) {
  if (expandedCategories.value.has(category)) {
    expandedCategories.value.delete(category)
  } else {
    expandedCategories.value.add(category)
  }
  expandedCategories.value = new Set(expandedCategories.value)
}

function isCategoryExpanded(category: string) {
  return expandedCategories.value.has(category)
}

const displayedNodes = computed(() => {
  if (viewMode.value === 'all') {
    return filteredNodes.value
  }
  return []
})

const nodeTypes = {
  custom: markRaw(WorkflowNode),
}

const selectedNode = shallowRef<Node<NodeData> | null>(null)
const overlay = useOverlay()
const slideover = overlay.create(SlideOver)

const {
  addEdges,
  addNodes,
  findNode,
  fitView,
  getNodes,
  onConnect,
  onNodeClick,
  screenToFlowCoordinate,
  setEdges,
  setNodes,
} = useVueFlow(VUEFLOW_ID)

const hasNodes = computed(() => getNodes.value.length > 0)
const nodeCount = computed(() => getNodes.value.length)

setNodes([])
setEdges([])

onConnect(handleConnect)
onNodeClick(handleNodeClick)

function handleConnect(params: Connection) {
  addEdges(params)
}

function handleNodeClick(params: { node: Node<NodeData> }) {
  slideover.open({
    isOpen: true,
    node: params.node,
  })
}

function getNextNodePosition() {
  const nodeIndex = getNodes.value.length
  const basePosition = screenToFlowCoordinate({
    x: window.innerWidth * 0.58,
    y: Math.max(window.innerHeight * 0.24, 180),
  })

  return {
    x: basePosition.x + (nodeIndex % 3) * 56,
    y: basePosition.y + Math.floor(nodeIndex / 3) * 108,
  }
}

function addNodeToCanvas(availableNode: AvailableNode) {
  const shouldFitView = getNodes.value.length === 0

  // TODO: Do this based on node shape
  const isFileInputNode = availableNode.nodeName === 'FileInput'

  addNodes({
    id: nanoid(),
    type: 'custom',
    position: getNextNodePosition(),
    data: {
      label: availableNode.label,
      noInput: isFileInputNode,
      nodeName: availableNode.nodeName,
    },
  })

  if (shouldFitView) {
    nextTick(() => {
      void fitView({ duration: 250, padding: 0.24 })
    })
  }
}

function clearCanvas() {
  selectedNode.value = null
  setEdges([])
  setNodes([])
}
</script>

<template>
  <div class="h-screen overflow-hidden bg-default text-default">
    <UDashboardGroup class="h-full">
      <UDashboardSidebar class="border-r border-default bg-elevated/50">
        <template #header>
          <div class="flex w-full items-center gap-2">
            <UButton
              to="/"
              color="neutral"
              variant="ghost"
              icon="i-lucide-arrow-left"
              label="Back Home"
              title="Back Home"
              class="justify-start"
            />
          </div>
        </template>

        <template #default>
          <div class="flex min-w-0 items-center gap-3">
            <div class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary text-inverted">
              <Icon name="i-lucide-box" class="size-5" />
            </div>
            <p class="truncate text-sm font-semibold text-highlighted">
              Node Library
            </p>
          </div>
          <div class="flex flex-col gap-2 px-3 pb-4">
            <div class="rounded-xl border border-default bg-default/80 p-3">
              <p class="text-sm font-medium text-highlighted">
                Add available nodes
              </p>
              <p class="mt-1 text-xs text-muted">
                Choose a node type to place it on the canvas.
              </p>
            </div>

            <div class="flex items-center gap-2 rounded-lg border border-default bg-default/50 p-1">
              <UButton
                :variant="viewMode === 'all' ? 'soft' : 'ghost'"
                color="neutral"
                size="sm"
                label="All"
                icon="i-lucide-list"
                class="flex-1"
                @click="viewMode = 'all'"
              />
              <UButton
                :variant="viewMode === 'categories' ? 'soft' : 'ghost'"
                color="neutral"
                size="sm"
                label="Categories"
                icon="i-lucide-folder-tree"
                class="flex-1"
                @click="viewMode = 'categories'"
              />
            </div>

            <UInput
              v-model="searchQuery"
              icon="i-lucide-search"
              placeholder="Filter nodes..."
              size="sm"
              clearable
            />

            <template v-if="viewMode === 'all'">
              <UButton
                v-for="availableNode in displayedNodes"
                :key="availableNode.nodeName"
                color="neutral"
                variant="soft"
                block
                icon="i-lucide-box"
                :label="availableNode.label"
                :title="availableNode.label"
                trailing-icon="i-lucide-plus"
                class="justify-start"
                @click="addNodeToCanvas(availableNode)"
              />
              <div v-if="!displayedNodes.length" class="py-4 text-center text-sm text-muted">
                No nodes match your search.
              </div>
            </template>

            <template v-else>
              <div v-for="category in displayedCategories" :key="category" class="mb-2">
                <button
                  class="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted hover:bg-default hover:text-highlighted"
                  @click="toggleCategory(category)"
                >
                  <span class="flex items-center gap-2">
                    <Icon
                      :name="isCategoryExpanded(category) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                      class="size-4"
                    />
                    {{ category }}
                  </span>
                  <UBadge color="neutral" variant="soft" size="xs">
                    {{ nodesByCategory[category]?.length || 0 }}
                  </UBadge>
                </button>
                <div v-if="isCategoryExpanded(category)" class="mt-1 flex flex-col gap-1 pl-2">
                  <UButton
                    v-for="node in nodesByCategory[category]"
                    :key="node.nodeName"
                    color="neutral"
                    variant="ghost"
                    size="sm"
                    block
                    icon="i-lucide-box"
                    :label="node.label"
                    :title="node.label"
                    trailing-icon="i-lucide-plus"
                    class="justify-start"
                    @click="addNodeToCanvas(node)"
                  />
                </div>
              </div>
              <div v-if="!displayedCategories.length" class="py-4 text-center text-sm text-muted">
                No nodes match your search.
              </div>
            </template>
          </div>
        </template>

        <template #footer>
          <div class="px-3 pb-4">
            <UButton
              color="neutral"
              variant="outline"
              block
              icon="i-lucide-eraser"
              label="Clear canvas"
              :disabled="!hasNodes"
              title="Clear canvas"
              class="justify-start"
              @click="clearCanvas"
            />
          </div>
        </template>
      </UDashboardSidebar>

      <UDashboardPanel id="node-demo-panel" class="min-w-0">
        <template #header>
          <UDashboardNavbar title="BIM Node Editor Demo">
            <template #right>
              <UBadge color="neutral" variant="soft">
                {{ nodeCount }} {{ nodeCount === 1 ? 'node' : 'nodes' }}
              </UBadge>
            </template>
          </UDashboardNavbar>
        </template>

        <template #default>
          <div class="relative h-full bg-default">
            <VueFlow
              :node-types="nodeTypes"
              class="h-full bg-default"
              fit-view-on-init
            >
              <div v-if="!hasNodes" class="pointer-events-none absolute inset-x-0 top-6 z-20 flex justify-center px-4">
                <div class="max-w-md rounded-xl border border-dashed border-default bg-default/90 px-4 py-3 text-center shadow-sm backdrop-blur">
                  <p class="mt-1 text-sm text-muted">
                    Add the first node to your canvas.
                  </p>
                </div>
              </div>
            </VueFlow>
          </div>
        </template>
      </UDashboardPanel>
    </UDashboardGroup>
  </div>
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

.vue-flow__handle {
  width: 12px !important;
  height: 12px !important;
}

/* Custom grid dots for light theme */
.vue-flow {
  background-image: radial-gradient(#e2e8f0 2px, transparent 1px);
  background-size: 48px 48px;
}
</style>
