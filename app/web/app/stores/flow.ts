import type { Edge, Node } from '@vue-flow/core'
import type { Ref } from 'vue'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

interface Viewport {
  x: number
  y: number
  zoom: number
}

export interface ModelFile {
  slug: string
  path: string
  hash: string
}

interface WorkflowData {
  files: ModelFile[]
  nodes: any[]
  edges: any[]
}

export const useFlowStore = defineStore('flow', () => {
  const nodesById = ref<Record<string, Node>>({})
  // Real deep `ref`. The `as unknown as Ref<Edge[]>` only lets TS treat `.value` as
  // `Edge[]` directly instead of expanding `UnwrapRef<Edge[]>` (whose self-referential
  // `GraphEdge` callbacks blow TS's instantiation depth limit). Runtime semantics unchanged.
  const edges = ref<Edge[]>([]) as unknown as Ref<Edge[]>
  const viewport = ref<Viewport>({
    x: 0,
    y: 0,
    zoom: 1,
  })
  const workflowData = ref<WorkflowData | null>(null)
  // The `main` slot is always present but starts unassigned; no file is implied.
  const files = ref<ModelFile[]>([{ slug: 'main', path: '', hash: '' }])

  const nodes = computed(() => Object.values(nodesById.value))

  const hasNodes = computed(() => nodes.value.length > 0)
  const nodeCount = computed(() => nodes.value.length)

  function addNodes(newNodes: Node | Node[]) {
    const nodesArray = Array.isArray(newNodes) ? newNodes : [newNodes]
    nodesArray.forEach((node) => {
      nodesById.value[node.id] = node
    })
  }

  function setNodes(newNodes: Node[]) {
    const newById: Record<string, Node> = {}
    newNodes.forEach((node) => {
      newById[node.id] = node
    })
    nodesById.value = newById
  }

  function removeNode(nodeId: string): void {
    delete nodesById.value[nodeId]
    const remaining: Edge[] = []
    for (const edge of edges.value) {
      if (edge.source !== nodeId && edge.target !== nodeId) {
        remaining.push(edge)
      }
    }
    edges.value = remaining
  }

  function addEdges(newEdges: Edge | Edge[]) {
    const edgesArray = Array.isArray(newEdges) ? newEdges : [newEdges]
    edges.value = [...edges.value, ...edgesArray]
  }

  function setEdges(newEdges: Edge[]) {
    edges.value = [...newEdges]
  }

  function updateNodeData(nodeId: string, data: Partial<Node['data']>) {
    const node = nodesById.value[nodeId]
    if (node) {
      node.data = { ...node.data, ...data }
    }
  }

  function updateNodePosition(nodeId: string, position: Node['position']) {
    const node = nodesById.value[nodeId]
    if (node) {
      node.position = position
    }
  }

  function updateViewport(viewportUpdate: Partial<Viewport>) {
    viewport.value = { ...viewport.value, ...viewportUpdate }
  }

  function clear() {
    nodesById.value = {}
    edges.value = []
    viewport.value = { x: 0, y: 0, zoom: 1 }
    workflowData.value = null
  }

  function setWorkflowData(data: WorkflowData) {
    workflowData.value = data
  }

  function getWorkflowData() {
    return workflowData.value
  }

  /**
   * Add or replace a file slot. The reserved `main` slug is always retained;
   * an update to `main` only changes its path/hash.
   */
  function addFile(file: ModelFile) {
    const index = files.value.findIndex(entry => entry.slug === file.slug)
    if (index >= 0) {
      files.value = files.value.map((entry, i) => (i === index ? { ...entry, ...file } : entry))
    }
    else {
      files.value = [...files.value, file]
    }
  }

  /**
   * Remove a model slot. The reserved `main` slot is never removed; deleting it
   * unassigns its file and leaves the empty placeholder in place.
   */
  function removeFile(slug: string) {
    if (slug === 'main') {
      const mainEntry = files.value.find(entry => entry.slug === 'main')
      if (mainEntry) {
        mainEntry.path = ''
        mainEntry.hash = ''
      }
      return
    }
    files.value = files.value.filter(entry => entry.slug !== slug)
  }

  /**
   * Update the main slot's file (path/hash) without allowing its slug to change.
   */
  function setMainFile(file: Omit<ModelFile, 'slug'>) {
    const mainEntry = files.value.find(entry => entry.slug === 'main')
    if (mainEntry) {
      mainEntry.path = file.path
      mainEntry.hash = file.hash
    }
  }

  function fitView(padding?: number) {
    if (nodes.value.length === 0) {
      return
    }

    const nodePadding = padding ?? 0.2
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity

    nodes.value.forEach((node) => {
      minX = Math.min(minX, node.position.x)
      minY = Math.min(minY, node.position.y)
      maxX = Math.max(maxX, node.position.x + 200)
      maxY = Math.max(maxY, node.position.y + 100)
    })

    const width = maxX - minX
    const height = maxY - minY
    const centerX = minX + width / 2
    const centerY = minY + height / 2

    const containerWidth = window.innerWidth * 0.75
    const containerHeight = window.innerHeight * 0.8

    const scaleX = containerWidth / (width * (1 + nodePadding))
    const scaleY = containerHeight / (height * (1 + nodePadding))
    const zoom = Math.min(scaleX, scaleY, 1.5)

    viewport.value = {
      x: -centerX * zoom + containerWidth / 2,
      y: -centerY * zoom + containerHeight / 2,
      zoom,
    }
  }

  return {
    nodesById,
    edges,
    viewport,
    workflowData,
    files,
    nodes,
    hasNodes,
    nodeCount,
    addNodes,
    setNodes,
    removeNode,
    addEdges,
    setEdges,
    updateNodeData,
    updateNodePosition,
    updateViewport,
    setWorkflowData,
    getWorkflowData,
    addFile,
    removeFile,
    setMainFile,
    clear,
    fitView,
  }
})
