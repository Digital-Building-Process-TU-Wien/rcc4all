import type {
  ModelFile,
  PortType,
  SubworkflowPort,
  WorkflowEdge,
  WorkflowNode,
} from '@@/scripts/workflow-schema'
import type { Connection, Edge, Node } from '@vue-flow/core'
import type { Ref } from 'vue'
import type { NodeData } from '~/utils/nodes'
import type { ExtractResult } from '~/utils/subworkflow-graph'
import type { AutoBindResult } from '~/utils/workflow-bindings'
import type {
  BreadcrumbItem,
  ExportedWorkflow,
  ScopeFrame,
  Viewport,
} from '~/utils/workflow-serialization'
import { nanoid } from 'nanoid'
import { defineStore } from 'pinia'
import {
  INPUT_HANDLE_PREFIX,
  OUTPUT_HANDLE_PREFIX,
  parsePortHandle,
} from '~/utils/schema-helpers'
import {
  createSubworkflowPortNode,
  DEFAULT_SUBWORKFLOW_OUTPUT_PORT,
  extractSubworkflowGraph,
  isValidPortName,
  metaNodeKind,
  nextPortPosition,
  readPort,
  uniquePortName,
  writePort,
} from '~/utils/subworkflow-graph'
import {
  clearBindingsFrom,
  moveBindingReference,
  pruneBindingsForRemovedEdges,
  removeBindingReference,
  resolveAutoBindings,
} from '~/utils/workflow-bindings'
import {
  cloneSubworkflow,
  cloneValue,
  hydrateWorkflow,
  serializeScope,
  toStoredData,
} from '~/utils/workflow-serialization'

export type { ModelFile }

export const useFlowStore = defineStore('flow', () => {
  const nodesById = ref<Record<string, Node>>({})
  // Real deep `ref`. The `as unknown as Ref<Edge[]>` only lets TS treat `.value` as
  // `Edge[]` directly instead of expanding `UnwrapRef<Edge[]>` (whose self-referential
  // `GraphEdge` callbacks blow TS's instantiation depth limit). Runtime semantics unchanged.
  const edges = ref<Edge[]>([]) as unknown as Ref<Edge[]>
  const viewport = ref<Viewport>({ x: 0, y: 0, zoom: 1 })
  const workflowData = ref<ExportedWorkflow | null>(null)
  // Path (relative to `app/web/.dev-files`) of the workflow file last loaded/saved.
  const activeWorkflowPath = ref<string | null>(null)
  // The `main` slot is always present but starts unassigned; no file is implied.
  const files = ref<ModelFile[]>([{ slug: 'main', path: '', hash: '' }])
  const scopeStack = ref<ScopeFrame[]>([
    { nodeId: null, label: '', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
  ])

  const nodes = computed(() => Object.values(nodesById.value))
  const currentScope = computed(() => scopeStack.value.at(-1)!)
  const canGoBack = computed(() => scopeStack.value.length > 1)

  const breadcrumbs = computed<BreadcrumbItem[]>(() =>
    scopeStack.value.map((frame, index) => ({
      index,
      nodeId: frame.nodeId,
      label: frame.label,
    })),
  )

  const hasNodes = computed(() => nodes.value.length > 0 || scopeStack.value[0]!.nodes.length > 0)
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
    const node = nodesById.value[nodeId] as Node<NodeData> | undefined
    const kind = metaNodeKind(node)
    const port = readPort(node?.data)
    const parentFrame = scopeStack.value.length > 1 ? scopeStack.value.at(-2)! : null
    const parentNodeId = currentScope.value.nodeId

    for (const other of nodes.value) {
      if (other.id !== nodeId)
        clearBindingsFrom(other as Node<NodeData>, nodeId)
    }

    // Removing a meta node drops the matching boundary binding too, otherwise the
    // subworkflow keeps a port nobody can see or re-add from the palette.
    if (kind === 'input' && port && parentFrame && parentNodeId) {
      const parentNode = parentFrame.nodes.find(entry => entry.id === parentNodeId)
      if (parentNode?.data.input_bindings)
        delete parentNode.data.input_bindings[port.name]
    }
    if (kind === 'output' && port && parentFrame && parentNodeId) {
      for (const other of parentFrame.nodes)
        removeBindingReference(other, parentNodeId, port.name)
    }

    delete nodesById.value[nodeId]
    edges.value = edges.value.filter(edge => edge.source !== nodeId && edge.target !== nodeId)
  }

  function addEdges(newEdges: Edge | Edge[]) {
    const edgesArray = Array.isArray(newEdges) ? newEdges : [newEdges]
    edges.value = [...edges.value, ...edgesArray]
  }

  function setEdges(newEdges: Edge[]) {
    edges.value = [...newEdges]
  }

  /**
   * Persist canvas edge updates from Vue Flow and drop stale input bindings
   * whenever the user removes an edge.
   */
  function syncEdges(newEdges: Edge[]) {
    const remainingIds = new Set(newEdges.map(edge => edge.id))
    const removedEdges = edges.value.filter(edge => !remainingIds.has(edge.id))
    if (removedEdges.length > 0) {
      pruneBindingsForRemovedEdges(
        nodesById.value as Record<string, Node<NodeData>>,
        removedEdges,
        newEdges,
      )
    }
    edges.value = [...newEdges]
  }

  /**
   * Create an edge from a canvas connection and apply strictly unambiguous
   * auto-bindings derived from Python's exported port schema.
   */
  function connectNodes(params: Connection): AutoBindResult {
    const normalizedTargetHandle
      = params.targetHandle === 'input-hitbox' ? 'input' : params.targetHandle

    addEdges({
      id: nanoid(),
      source: params.source,
      target: params.target,
      sourceHandle: params.sourceHandle,
      targetHandle: normalizedTargetHandle,
    })

    const sourceNode = nodesById.value[params.source] as Node<NodeData> | undefined
    const targetNode = nodesById.value[params.target] as Node<NodeData> | undefined
    if (!sourceNode || !targetNode) {
      return { bindings: {}, status: 'no-op', ambiguousInputs: [], ambiguousOutputs: [] }
    }

    const result = resolveAutoBindings(params.source, sourceNode, targetNode, {
      explicitOutput: parsePortHandle(params.sourceHandle, OUTPUT_HANDLE_PREFIX),
      explicitInput: parsePortHandle(normalizedTargetHandle, INPUT_HANDLE_PREFIX),
    })

    if (Object.keys(result.bindings).length > 0) {
      updateNodeData(params.target, {
        input_bindings: {
          ...(targetNode.data?.input_bindings ?? {}),
          ...result.bindings,
        },
      })
    }

    return result
  }

  function updateNodeData(nodeId: string, data: Partial<Node['data']>) {
    const node = nodesById.value[nodeId]
    if (node)
      node.data = { ...node.data, ...data }
  }

  function updateNodePosition(nodeId: string, position: Node['position']) {
    const node = nodesById.value[nodeId]
    if (node)
      node.position = position
  }

  function updateViewport(viewportUpdate: Partial<Viewport>) {
    viewport.value = { ...viewport.value, ...viewportUpdate }
  }

  function syncActiveScope() {
    const frame = currentScope.value
    frame.nodes = nodes.value.map(node => ({
      id: node.id,
      position: { x: node.position.x, y: node.position.y },
      data: toStoredData(node.data as NodeData),
    }))
    frame.edges = edges.value.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle,
      targetHandle: edge.targetHandle,
    }))
    frame.viewport = { ...viewport.value }
  }

  function loadScope(frame: ScopeFrame) {
    const newById: Record<string, Node> = {}
    frame.nodes.forEach((stored) => {
      newById[stored.id] = {
        id: stored.id,
        type: stored.data.nodeName,
        position: { ...stored.position },
        data: cloneValue(stored.data),
      }
    })
    nodesById.value = newById
    edges.value = frame.edges.map(edge => ({ ...edge })) as Edge[]
    viewport.value = { ...frame.viewport }
  }

  function persistChildIntoParent(parentFrame: ScopeFrame, childFrame: ScopeFrame) {
    if (!childFrame.nodeId)
      return
    const parentNode = parentFrame.nodes.find(node => node.id === childFrame.nodeId)
    if (!parentNode)
      return
    parentNode.data = {
      ...parentNode.data,
      subworkflow: {
        name: childFrame.label,
        nodes: childFrame.nodes,
        edges: childFrame.edges,
        viewport: childFrame.viewport,
      },
    }
  }

  function enterSubworkflow(nodeId: string): boolean {
    const node = nodesById.value[nodeId]
    if (!node || node.data?.nodeName !== 'subworkflow' || !node.data.subworkflow)
      return false

    syncActiveScope()
    const definition = cloneSubworkflow(node.data.subworkflow)
    scopeStack.value.push({
      nodeId,
      label: node.data.label || '',
      nodes: definition.nodes,
      edges: definition.edges,
      viewport: definition.viewport ?? { x: 0, y: 0, zoom: 1 },
    })
    loadScope(currentScope.value)
    return true
  }

  function leaveSubworkflow(): boolean {
    if (scopeStack.value.length <= 1)
      return false

    syncActiveScope()
    const childFrame = scopeStack.value.pop()!
    const parentFrame = currentScope.value
    persistChildIntoParent(parentFrame, childFrame)
    loadScope(parentFrame)
    return true
  }

  function goToScope(index: number) {
    while (scopeStack.value.length - 1 > index) {
      if (!leaveSubworkflow())
        break
    }
  }

  function serializeWorkflow(): { nodes: WorkflowNode[], edges: WorkflowEdge[] } {
    syncActiveScope()
    for (let index = scopeStack.value.length - 1; index > 0; index--)
      persistChildIntoParent(scopeStack.value[index - 1]!, scopeStack.value[index]!)
    return serializeScope(scopeStack.value[0]!.nodes, scopeStack.value[0]!.edges)
  }

  function hydrate(rawWorkflow: unknown) {
    const hydrated = hydrateWorkflow(rawWorkflow)
    scopeStack.value = [hydrated.rootFrame]
    loadScope(hydrated.rootFrame)
    // Loading a file replaces the canvas, so inherited model slots must not linger.
    files.value = hydrated.files
  }

  function collectPortNames(exceptNodeId?: string): string[] {
    const names: string[] = []
    for (const node of nodes.value) {
      if (node.id === exceptNodeId)
        continue
      if (metaNodeKind(node as Node<NodeData>) === null)
        continue
      const port = readPort(node.data as NodeData)
      if (port)
        names.push(port.name)
    }
    return names
  }

  /** Add one meta node. Each meta node owns exactly one port. */
  function addSubworkflowPort(
    kind: 'input' | 'output',
    position?: { x: number, y: number },
  ): string {
    const taken = new Set(collectPortNames())
    const base = kind === 'input' ? 'input' : DEFAULT_SUBWORKFLOW_OUTPUT_PORT
    const port: SubworkflowPort = {
      name: uniquePortName(base, taken),
      type: { type: 'any' },
    }
    const created = createSubworkflowPortNode(
      kind,
      port,
      position ?? nextPortPosition(nodes.value, kind),
    )
    addNodes({
      id: created.id,
      type: created.data.nodeName,
      position: created.position,
      data: created.data,
    })
    return created.id
  }

  function setSubworkflowPortType(metaNodeId: string, type: PortType): void {
    const node = nodesById.value[metaNodeId] as Node<NodeData> | undefined
    const port = readPort(node?.data)
    if (!node || !port)
      return
    writePort(node, { name: port.name, type })
  }

  /**
   * Rename the single port a meta node owns and follow every reference the old
   * name had: inner bindings, the parent's boundary binding, and edge handles.
   */
  function renameSubworkflowPort(metaNodeId: string, newName: string): boolean {
    const node = nodesById.value[metaNodeId] as Node<NodeData> | undefined
    const port = readPort(node?.data)
    const kind = metaNodeKind(node)
    if (!node || !port || !kind || !isValidPortName(newName))
      return false

    const oldName = port.name
    if (newName === oldName)
      return true
    if (collectPortNames(metaNodeId).includes(newName))
      return false

    writePort(node, { name: newName, type: port.type })

    const parentFrame = scopeStack.value.length > 1 ? scopeStack.value.at(-2)! : null
    const parentNodeId = currentScope.value.nodeId

    if (kind === 'input') {
      for (const other of nodes.value) {
        if (other.id !== metaNodeId)
          moveBindingReference(other as Node<NodeData>, metaNodeId, oldName, newName)
      }
      if (parentFrame && parentNodeId) {
        const parentNode = parentFrame.nodes.find(entry => entry.id === parentNodeId)
        const bindings = parentNode?.data.input_bindings
        if (bindings && oldName in bindings) {
          bindings[newName] = bindings[oldName]!
          delete bindings[oldName]
        }
        for (const edge of parentFrame.edges) {
          if (edge.target === parentNodeId && edge.targetHandle === `input:${oldName}`)
            edge.targetHandle = `input:${newName}`
        }
      }
      for (const edge of edges.value) {
        if (edge.source === metaNodeId && edge.sourceHandle === `output:${oldName}`)
          edge.sourceHandle = `output:${newName}`
      }
      return true
    }

    const ownBindings = node.data?.input_bindings
    if (ownBindings && oldName in ownBindings) {
      ownBindings[newName] = ownBindings[oldName]!
      delete ownBindings[oldName]
    }
    if (parentFrame && parentNodeId) {
      for (const other of parentFrame.nodes)
        moveBindingReference(other, parentNodeId, oldName, newName)
      for (const edge of parentFrame.edges) {
        if (edge.source === parentNodeId && edge.sourceHandle === `output:${oldName}`)
          edge.sourceHandle = `output:${newName}`
      }
    }
    for (const edge of edges.value) {
      if (edge.target === metaNodeId && edge.targetHandle === `input:${oldName}`)
        edge.targetHandle = `input:${newName}`
    }
    return true
  }

  /** Rename the subworkflow the user is currently inside. */
  function renameActiveSubworkflow(name: string): void {
    if (scopeStack.value.length <= 1)
      return

    const frame = currentScope.value
    frame.label = name
    const parentFrame = scopeStack.value.at(-2)!
    const parentNode = parentFrame.nodes.find(node => node.id === frame.nodeId)
    if (!parentNode)
      return
    parentNode.data.label = name
    if (parentNode.data.subworkflow)
      parentNode.data.subworkflow.name = name
  }

  function extractToSubworkflow(selectedIds: string[], label: string): ExtractResult {
    const result = extractSubworkflowGraph(
      nodes.value as Node<NodeData>[],
      edges.value,
      selectedIds,
      label,
    )
    if (!result.ok)
      return result

    for (const id of result.removedNodeIds)
      delete nodesById.value[id]
    for (const rebound of result.reboundParents) {
      const target = nodesById.value[rebound.nodeId]
      if (target?.data)
        target.data.input_bindings = rebound.bindings
    }

    addNodes({
      id: result.subworkflowNode.id,
      type: result.subworkflowNode.data.nodeName,
      position: result.subworkflowNode.position,
      data: result.subworkflowNode.data,
    })
    edges.value = result.remainingEdges as Edge[]
    return { ok: true, nodeId: result.subworkflowNode.id }
  }

  /** The runnable workflow payload: assigned model files plus the serialized graph. */
  function exportWorkflow(): ExportedWorkflow {
    const graph = serializeWorkflow()
    return {
      files: files.value
        .filter(file => file.path)
        .map(file => ({ ...file })),
      nodes: graph.nodes,
      edges: graph.edges,
    }
  }

  function clear() {
    nodesById.value = {}
    edges.value = []
    viewport.value = { x: 0, y: 0, zoom: 1 }
    workflowData.value = null
    scopeStack.value = [
      { nodeId: null, label: '', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
    ]
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
    if (index >= 0)
      files.value = files.value.map((entry, i) => (i === index ? { ...entry, ...file } : entry))
    else
      files.value = [...files.value, file]
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
    if (nodes.value.length === 0)
      return

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
    scopeStack,
    currentScope,
    canGoBack,
    breadcrumbs,
    addNodes,
    setNodes,
    removeNode,
    addEdges,
    setEdges,
    syncEdges,
    connectNodes,
    updateNodeData,
    updateNodePosition,
    updateViewport,
    enterSubworkflow,
    leaveSubworkflow,
    goToScope,
    serializeWorkflow,
    exportWorkflow,
    hydrate,
    addSubworkflowPort,
    setSubworkflowPortType,
    renameSubworkflowPort,
    renameActiveSubworkflow,
    extractToSubworkflow,
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
