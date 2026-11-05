import type { Edge, Node } from '@vue-flow/core'
import type { Ref } from 'vue'
import type { NodeData, StoredEdge, StoredNode, SubworkflowDefinitionData, SubworkflowPort } from '~/utils/nodes'
import type { TypeInfo } from '~/utils/schema-helpers'
import { nanoid } from 'nanoid'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  createSubworkflowPortNode,
  DEFAULT_SUBWORKFLOW_OUTPUT_PORT,
  isValidPortName,
} from '~/utils/nodes'
import { getOutputType } from '~/utils/schema-helpers'

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

export interface ScopeFrame {
  nodeId: string | null
  label: string
  nodes: StoredNode[]
  edges: StoredEdge[]
  viewport: Viewport
}

export interface BreadcrumbItem {
  index: number
  nodeId: string | null
  label: string
}

export interface SerializedWorkflowNode {
  id: string
  type: string
  label: string
  settings: Record<string, any>
  input_bindings: Record<string, string>
  position: { x: number, y: number }
  subworkflow?: SerializedSubworkflow
}

export interface SerializedSubworkflow {
  name: string
  nodes: SerializedWorkflowNode[]
  edges: Array<{ source: string, target: string }>
}

export interface SerializedWorkflowGraph {
  nodes: SerializedWorkflowNode[]
  edges: Array<{ source: string, target: string }>
}

function cloneValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function toStoredData(data: NodeData): NodeData {
  return {
    label: data.label,
    nodeName: data.nodeName,
    ...(data.noInput ? { noInput: true } : {}),
    ...(data.noOutput ? { noOutput: true } : {}),
    settings: data.settings ? cloneValue(data.settings) : {},
    input_bindings: { ...(data.input_bindings ?? {}) },
    ...(data.subworkflow ? { subworkflow: cloneSubworkflow(data.subworkflow) } : {}),
  }
}

function cloneSubworkflow(definition: SubworkflowDefinitionData): SubworkflowDefinitionData {
  return {
    name: definition.name,
    nodes: definition.nodes.map(node => ({
      id: node.id,
      position: { ...node.position },
      data: toStoredData(node.data),
    })),
    edges: definition.edges.map(edge => ({ ...edge })),
    ...(definition.viewport ? { viewport: { ...definition.viewport } } : {}),
  }
}

function serializeScope(nodes: StoredNode[], edges: StoredEdge[]): SerializedWorkflowGraph {
  const keptNodes = nodes.filter(node => node.data.nodeName.toLowerCase() !== 'jsonoutput')
  const keptIds = new Set(keptNodes.map(node => node.id))

  return {
    nodes: keptNodes.map(serializeStoredNode),
    edges: edges
      .filter(edge => keptIds.has(edge.source) && keptIds.has(edge.target))
      .map(edge => ({ source: edge.source, target: edge.target })),
  }
}

function serializeStoredNode(node: StoredNode): SerializedWorkflowNode {
  const data = node.data
  return {
    id: node.id,
    type: data.nodeName.toLowerCase(),
    label: data.label || '',
    settings: data.settings ?? {},
    input_bindings: data.input_bindings ?? {},
    position: { x: node.position.x, y: node.position.y },
    ...(data.subworkflow ? { subworkflow: serializeSubworkflow(data.subworkflow, data.label) } : {}),
  }
}

function serializeSubworkflow(
  definition: SubworkflowDefinitionData,
  nodeLabel: string,
): SerializedSubworkflow {
  const scope = serializeScope(definition.nodes, definition.edges)
  return { name: definition.name || nodeLabel, nodes: scope.nodes, edges: scope.edges }
}

function hydrateNode(raw: any): StoredNode {
  const data = raw?.data && typeof raw.data === 'object' ? raw.data : raw
  const subworkflow = raw?.subworkflow ?? data?.subworkflow
  return {
    id: raw.id,
    position: raw.position ?? { x: 0, y: 0 },
    data: {
      label: data?.label ?? '',
      nodeName: data?.nodeName ?? raw.type ?? 'unknown',
      settings: data?.settings ?? {},
      input_bindings: data?.input_bindings ?? {},
      ...(data?.noInput ? { noInput: true } : {}),
      ...(data?.noOutput ? { noOutput: true } : {}),
      ...(subworkflow ? { subworkflow: hydrateSubworkflow(subworkflow) } : {}),
    },
  }
}

function hydrateEdge(raw: any, index: number): StoredEdge {
  return {
    id: raw.id ?? `edge-${index}-${raw.source}-${raw.target}`,
    source: raw.source,
    target: raw.target,
    sourceHandle: raw.sourceHandle,
    targetHandle: raw.targetHandle,
  }
}

function hydrateSubworkflow(raw: any): SubworkflowDefinitionData {
  return {
    name: raw?.name ?? '',
    nodes: (raw?.nodes ?? []).map(hydrateNode),
    edges: (raw?.edges ?? []).map(hydrateEdge),
    viewport: { x: 0, y: 0, zoom: 1 },
  }
}

function moveBindingReference(
  node: Node<NodeData> | StoredNode,
  sourceId: string,
  oldField: string,
  newField: string,
) {
  const bindings = node.data?.input_bindings
  if (!bindings)
    return
  for (const [inputName, reference] of Object.entries(bindings)) {
    const [source, field] = reference.split('.')
    if (source === sourceId && field === oldField)
      bindings[inputName] = `${source}.${newField}`
  }
}

function removeBindingReference(
  node: Node<NodeData> | StoredNode,
  sourceId: string,
  fieldName: string,
) {
  const bindings = node.data?.input_bindings
  if (!bindings)
    return
  for (const [inputName, reference] of Object.entries(bindings)) {
    const [source, field] = reference.split('.')
    if (source === sourceId && field === fieldName)
      delete bindings[inputName]
  }
}

/** Every binding on `node` that points at `sourceId` is dropped. */
function clearBindingsFrom(node: Node<NodeData> | StoredNode, sourceId: string) {
  const bindings = node.data?.input_bindings
  if (!bindings)
    return
  for (const [inputName, reference] of Object.entries(bindings)) {
    if (reference.split('.')[0] === sourceId)
      delete bindings[inputName]
  }
}

function splitReference(reference: string): [string, string] | null {
  const index = reference.indexOf('.')
  if (index <= 0 || index === reference.length - 1)
    return null
  return [reference.slice(0, index), reference.slice(index + 1)]
}

function readPort(data: NodeData | undefined | null): SubworkflowPort | null {
  const raw = data?.settings?.port
  if (!raw || typeof raw !== 'object' || typeof raw.name !== 'string' || raw.name.length === 0)
    return null
  const type = raw.type && typeof raw.type === 'object' ? raw.type as TypeInfo : { type: 'null' as const }
  return { name: raw.name, type }
}

function writePort(node: Node<NodeData> | StoredNode, port: SubworkflowPort) {
  if (!node.data)
    node.data = {} as NodeData
  node.data.settings = { ...(node.data.settings ?? {}), port: { name: port.name, type: port.type } }
  node.data.label = port.name
}

function metaNodeKind(node: Node<NodeData> | StoredNode | undefined): 'input' | 'output' | null {
  const nodeName = node?.data?.nodeName
  if (nodeName === 'subworkflow_input')
    return 'input'
  if (nodeName === 'subworkflow_output')
    return 'output'
  return null
}

const NON_WORD_RE = /\W/g
const LEADING_DIGIT_RE = /^(\d)/

/** Port names must be usable as `<port>.field` binding references. */
function toPortName(raw: string, fallback = 'port'): string {
  const cleaned = raw.replace(NON_WORD_RE, '_').replace(LEADING_DIGIT_RE, '_$1')
  return isValidPortName(cleaned) ? cleaned : fallback
}

function uniquePortName(base: string, taken: Set<string>): string {
  if (!taken.has(base))
    return base
  let suffix = 2
  while (taken.has(`${base}_${suffix}`))
    suffix += 1
  return `${base}_${suffix}`
}

export type ExtractFailureReason = 'empty' | 'meta-node' | 'output-conflict' | 'duplicate-id'

export type ExtractResult
  = | { ok: true, nodeId: string }
    | { ok: false, reason: ExtractFailureReason, details: string[] }

interface IncomingPort {
  sourceId: string
  field: string
  portName: string
  inputNodeId: string
  consumers: string[]
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

  function serializeWorkflow(): SerializedWorkflowGraph {
    syncActiveScope()
    for (let index = scopeStack.value.length - 1; index > 0; index--) {
      persistChildIntoParent(scopeStack.value[index - 1]!, scopeStack.value[index]!)
    }
    return serializeScope(scopeStack.value[0]!.nodes, scopeStack.value[0]!.edges)
  }

  function hydrate(workflow: any) {
    const rootFrame: ScopeFrame = {
      nodeId: null,
      label: '',
      nodes: (workflow?.nodes ?? []).map(hydrateNode),
      edges: (workflow?.edges ?? []).map(hydrateEdge),
      viewport: { x: 0, y: 0, zoom: 1 },
    }

    if (Array.isArray(workflow?.files) && workflow.files.length > 0)
      files.value = workflow.files

    scopeStack.value = [rootFrame]
    loadScope(rootFrame)
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

  function nextPortPosition(kind: 'input' | 'output'): { x: number, y: number } {
    const placed = nodes.value
    if (placed.length === 0)
      return kind === 'input' ? { x: 40, y: 140 } : { x: 560, y: 140 }

    const minX = Math.min(...placed.map(node => node.position.x))
    const maxX = Math.max(...placed.map(node => node.position.x))
    const maxY = Math.max(...placed.map(node => node.position.y))
    return {
      x: kind === 'input' ? minX - 280 : maxX + 320,
      y: maxY + 80,
    }
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
      type: { type: 'null' },
    }
    const created = createSubworkflowPortNode(kind, port, position ?? nextPortPosition(kind))
    addNodes({
      id: created.id,
      type: created.data.nodeName,
      position: created.position,
      data: created.data,
    })
    return created.id
  }

  function setSubworkflowPortType(metaNodeId: string, type: TypeInfo): void {
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

  /**
   * Move the selected nodes into a new subworkflow.
   *
   * Incoming references become one input node each. Exactly one distinct outgoing
   * value becomes the output; several are refused so nothing is silently dropped.
   */
  function extractToSubworkflow(selectedIds: string[], label: string): ExtractResult {
    const selection = new Set(selectedIds)
    const selectedNodes = nodes.value.filter(node => selection.has(node.id))
    if (selectedNodes.length === 0)
      return { ok: false, reason: 'empty', details: [] }

    const metaNodes = selectedNodes.filter(node => metaNodeKind(node as Node<NodeData>) !== null)
    if (metaNodes.length > 0)
      return { ok: false, reason: 'meta-node', details: metaNodes.map(node => node.id) }

    const incoming = new Map<string, IncomingPort>()
    for (const node of selectedNodes) {
      for (const reference of Object.values<string>(node.data?.input_bindings ?? {})) {
        const parsed = splitReference(reference)
        if (!parsed)
          continue
        const [sourceId, field] = parsed
        if (selection.has(sourceId) || !nodesById.value[sourceId])
          continue
        const key = `${sourceId}.${field}`
        const entry = incoming.get(key)
        if (entry)
          entry.consumers.push(node.id)
        else
          incoming.set(key, { sourceId, field, portName: '', inputNodeId: '', consumers: [node.id] })
      }
    }

    const outgoing = new Set<string>()
    for (const node of nodes.value) {
      if (selection.has(node.id))
        continue
      for (const reference of Object.values<string>(node.data?.input_bindings ?? {})) {
        const parsed = splitReference(reference)
        if (parsed && selection.has(parsed[0]))
          outgoing.add(reference)
      }
    }
    if (outgoing.size > 1)
      return { ok: false, reason: 'output-conflict', details: [...outgoing].sort() }

    const takenPorts = new Set<string>()
    const incomingPorts = [...incoming.values()].sort(
      (left, right) => left.sourceId.localeCompare(right.sourceId) || left.field.localeCompare(right.field),
    )
    for (const entry of incomingPorts) {
      const consumer = nodesById.value[entry.consumers[0]!]
      const consumerInput = consumer
        ? Object.entries(consumer.data.input_bindings ?? {})
          .find(([, reference]) => reference === `${entry.sourceId}.${entry.field}`)?.[0]
        : undefined
      entry.portName = uniquePortName(toPortName(consumerInput ?? entry.field), takenPorts)
      takenPorts.add(entry.portName)
    }

    const outputRef = outgoing.size === 1 ? [...outgoing][0]! : null
    const outputParsed = outputRef ? splitReference(outputRef) : null
    const outputPortName = outputParsed
      ? uniquePortName(toPortName(outputParsed[1]), takenPorts)
      : null

    const minX = Math.min(...selectedNodes.map(node => node.position.x))
    const minY = Math.min(...selectedNodes.map(node => node.position.y))
    const maxX = Math.max(...selectedNodes.map(node => node.position.x))
    const offsetX = 320
    const offsetY = 120

    const innerNodes: StoredNode[] = []
    const innerEdges: StoredEdge[] = []
    const innerPosition = new Map<string, { x: number, y: number }>()
    for (const node of selectedNodes) {
      innerPosition.set(node.id, {
        x: node.position.x - minX + offsetX,
        y: node.position.y - minY + offsetY,
      })
    }

    for (const entry of incomingPorts) {
      entry.inputNodeId = nanoid()
      const source = nodesById.value[entry.sourceId] as Node<NodeData> | undefined
      const firstConsumerY = innerPosition.get(entry.consumers[0]!)?.y ?? offsetY
      innerNodes.push(
        createSubworkflowPortNode(
          'input',
          {
            name: entry.portName,
            type: source ? getOutputType(source, entry.field) : { type: 'null' },
          },
          { x: 0, y: firstConsumerY },
          entry.inputNodeId,
        ),
      )
      for (const consumerId of entry.consumers) {
        innerEdges.push({
          id: nanoid(),
          source: entry.inputNodeId,
          target: consumerId,
          sourceHandle: `output:${entry.portName}`,
          targetHandle: null,
        })
      }
    }

    for (const node of selectedNodes) {
      const copy: StoredNode = {
        id: node.id,
        position: innerPosition.get(node.id)!,
        data: toStoredData(node.data as NodeData),
      }
      const bindings: Record<string, string> = {}
      for (const [inputName, reference] of Object.entries(copy.data.input_bindings ?? {})) {
        const parsed = splitReference(reference)
        if (!parsed)
          continue
        if (selection.has(parsed[0])) {
          bindings[inputName] = reference
          continue
        }
        const entry = incoming.get(reference)
        if (!entry)
          continue
        bindings[inputName] = `${entry.inputNodeId}.${entry.portName}`
      }
      copy.data.input_bindings = bindings
      innerNodes.push(copy)
    }

    for (const edge of edges.value) {
      if (!selection.has(edge.source) || !selection.has(edge.target))
        continue
      innerEdges.push({ ...edge })
    }

    if (outputParsed && outputPortName) {
      const [producerId, producerField] = outputParsed
      const outputNodeId = nanoid()
      const producer = nodesById.value[producerId] as Node<NodeData> | undefined
      const outputY = innerPosition.get(producerId)?.y ?? offsetY
      innerNodes.push({
        id: outputNodeId,
        position: { x: maxX - minX + offsetX + 320, y: outputY },
        data: {
          label: outputPortName,
          nodeName: 'subworkflow_output',
          settings: {
            port: {
              name: outputPortName,
              type: producer ? getOutputType(producer, producerField) : { type: 'null' },
            },
          },
          input_bindings: { [outputPortName]: `${producerId}.${producerField}` },
        },
      })
      innerEdges.push({
        id: nanoid(),
        source: producerId,
        target: outputNodeId,
        sourceHandle: null,
        targetHandle: `input:${outputPortName}`,
      })
    }

    const newNodeId = nanoid()
    const parentBindings: Record<string, string> = {}
    for (const entry of incomingPorts)
      parentBindings[entry.portName] = `${entry.sourceId}.${entry.field}`

    for (const id of selection)
      delete nodesById.value[id]
    for (const node of nodes.value) {
      const bindings = node.data?.input_bindings
      if (!bindings)
        continue
      for (const [inputName, reference] of Object.entries<string>(bindings)) {
        const parsed = splitReference(reference)
        if (!parsed || !selection.has(parsed[0]))
          continue
        if (outputPortName)
          bindings[inputName] = `${newNodeId}.${outputPortName}`
        else
          delete bindings[inputName]
      }
    }

    const portBySource = new Map<string, string>()
    for (const entry of incomingPorts) {
      if (!portBySource.has(entry.sourceId))
        portBySource.set(entry.sourceId, entry.portName)
    }

    const remainingEdges: Edge[] = []
    const boundary: Array<[string, string]> = []
    for (const edge of edges.value) {
      const sourceInside = selection.has(edge.source)
      const targetInside = selection.has(edge.target)
      if (sourceInside && targetInside)
        continue
      if (sourceInside) {
        boundary.push([newNodeId, edge.target])
        continue
      }
      if (targetInside) {
        boundary.push([edge.source, newNodeId])
        continue
      }
      remainingEdges.push(edge)
    }

    const seenBoundary = new Set<string>()
    for (const [source, target] of boundary) {
      const key = `${source}->${target}`
      if (seenBoundary.has(key))
        continue
      seenBoundary.add(key)
      const port = source === newNodeId ? outputPortName : portBySource.get(source) ?? null
      remainingEdges.push({
        id: nanoid(),
        source,
        target,
        sourceHandle: source === newNodeId && port ? `output:${port}` : null,
        targetHandle: target === newNodeId && port ? `input:${port}` : null,
      })
    }

    addNodes({
      id: newNodeId,
      type: 'subworkflow',
      position: { x: minX, y: minY },
      data: {
        label,
        nodeName: 'subworkflow',
        input_bindings: parentBindings,
        subworkflow: {
          name: label,
          nodes: innerNodes,
          edges: innerEdges,
          viewport: { x: 0, y: 0, zoom: 1 },
        },
      },
    })
    edges.value = remainingEdges
    return { ok: true, nodeId: newNodeId }
  }

  function clear() {
    nodesById.value = {}
    edges.value = []
    viewport.value = { x: 0, y: 0, zoom: 1 }
    workflowData.value = null
    scopeStack.value = [
      { nodeId: null, label: '', nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } },
    ]
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
    scopeStack,
    currentScope,
    canGoBack,
    breadcrumbs,
    addNodes,
    setNodes,
    removeNode,
    addEdges,
    setEdges,
    updateNodeData,
    updateNodePosition,
    updateViewport,
    enterSubworkflow,
    leaveSubworkflow,
    goToScope,
    serializeWorkflow,
    hydrate,
    addSubworkflowPort,
    setSubworkflowPortType,
    renameSubworkflowPort,
    renameActiveSubworkflow,
    extractToSubworkflow,
    setWorkflowData,
    getWorkflowData,
    addFile,
    removeFile,
    setMainFile,
    clear,
    fitView,
  }
})
