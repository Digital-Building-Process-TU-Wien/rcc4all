import type { Edge, Node } from '@vue-flow/core'
import type { Ref } from 'vue'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { nodeHasNoInput } from '~/utils/nodes'

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

/** One node as the runner reads it. `position` is editor state it ignores. */
export interface SerializedWorkflowNode {
  id: string
  type: string
  label: string
  settings: Record<string, any>
  input_bindings: Record<string, string>
  position: { x: number, y: number }
}

export interface SerializedWorkflowEdge {
  source: string
  target: string
}

/**
 * The runnable workflow payload: assigned model files plus the serialized graph.
 * `openbim_runner` forbids unknown keys, so this is also exactly what is written
 * to `.dev-files` by the save dialog.
 */
export interface ExportedWorkflow {
  files: ModelFile[]
  nodes: SerializedWorkflowNode[]
  edges: SerializedWorkflowEdge[]
}

function hydrateNode(raw: any): Node {
  const data = raw?.data && typeof raw.data === 'object' ? raw.data : raw
  const nodeName: string = data?.nodeName ?? raw.type ?? 'unknown'
  return {
    id: raw.id,
    type: 'custom',
    position: raw.position ?? { x: 0, y: 0 },
    data: {
      label: data?.label ?? '',
      nodeName,
      settings: data?.settings ?? {},
      input_bindings: data?.input_bindings ?? {},
      // The runner payload has no editor flags, so derive the ones fixed by the
      // node type and keep any flag the file happens to carry.
      ...(data?.noInput || nodeHasNoInput(nodeName) ? { noInput: true } : {}),
    },
  }
}

function hydrateEdge(raw: any, index: number): Edge {
  return {
    id: raw.id ?? `edge-${index}-${raw.source}-${raw.target}`,
    source: raw.source,
    target: raw.target,
    // Handles are editor state, not part of the runner payload; the connect
    // handler normalizes to these same ids.
    sourceHandle: raw.sourceHandle ?? 'output',
    targetHandle: raw.targetHandle ?? 'input',
  }
}

function hydrateModelFiles(raw: unknown): ModelFile[] {
  const entries = Array.isArray(raw) ? raw : []
  const valid = entries
    .filter((entry): entry is ModelFile =>
      !!entry
      && typeof entry === 'object'
      && typeof (entry as ModelFile).slug === 'string'
      && (entry as ModelFile).slug.length > 0
      && typeof (entry as ModelFile).path === 'string',
    )
    .map(entry => ({
      slug: entry.slug,
      path: entry.path,
      hash: typeof entry.hash === 'string' ? entry.hash : '',
    }))

  const main = valid.find(file => file.slug === 'main')
  return [
    { slug: 'main', path: main?.path ?? '', hash: main?.hash ?? '' },
    ...valid.filter(file => file.slug !== 'main'),
  ]
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
  const workflowData = ref<ExportedWorkflow | null>(null)
  // Path (relative to `web/.dev-files`) of the workflow file last loaded/saved.
  const activeWorkflowPath = ref<string | null>(null)
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

  /** The runnable workflow payload: assigned model files plus the serialized graph. */
  function exportWorkflow(): ExportedWorkflow {
    const workflowNodes = nodes.value.filter(node => node.data.nodeName !== 'JsonOutput')
    const keptIds = new Set(workflowNodes.map(node => node.id))

    return {
      files: files.value
        .filter(file => file.path)
        .map(file => ({ ...file })),
      nodes: workflowNodes.map(node => ({
        id: node.id,
        type: node.data.nodeName.toLowerCase(),
        label: node.data.label || '',
        settings: node.data.settings ?? {},
        input_bindings: node.data.input_bindings ?? {},
        position: { x: node.position.x, y: node.position.y },
      })),
      edges: edges.value
        .filter(edge => keptIds.has(edge.source) && keptIds.has(edge.target))
        .map(edge => ({ source: edge.source, target: edge.target })),
    }
  }

  /** Replace the canvas with a workflow read from `.dev-files`. */
  function hydrate(workflow: any) {
    setNodes((workflow?.nodes ?? []).map(hydrateNode))
    setEdges((workflow?.edges ?? []).map(hydrateEdge))
    // Loading a file replaces the canvas, so inherited model slots must not linger.
    files.value = hydrateModelFiles(workflow?.files)
    viewport.value = { x: 0, y: 0, zoom: 1 }
  }

  function clear() {
    nodesById.value = {}
    edges.value = []
    viewport.value = { x: 0, y: 0, zoom: 1 }
    workflowData.value = null
    activeWorkflowPath.value = null
  }

  function setActiveWorkflowPath(path: string | null) {
    activeWorkflowPath.value = path
  }

  function setWorkflowData(data: ExportedWorkflow) {
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
    exportWorkflow,
    hydrate,
    activeWorkflowPath,
    setActiveWorkflowPath,
    setWorkflowData,
    getWorkflowData,
    addFile,
    removeFile,
    setMainFile,
    clear,
    fitView,
  }
})
