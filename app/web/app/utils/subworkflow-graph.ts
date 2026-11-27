import type { Edge, Node } from '@vue-flow/core'
import type { NodeData, StoredEdge, StoredNode } from './nodes'
import type { SubworkflowPort } from '~/schemas'
import { nanoid } from 'nanoid'
import { getNodeOutputPorts, OUTPUT_HANDLE_PREFIX } from '~/schemas'
import { splitReference } from './workflow-bindings'
import { toStoredData } from './workflow-serialization'

export const DEFAULT_SUBWORKFLOW_OUTPUT_PORT = 'result'

const PORT_NAME_RE = /^[A-Z_]\w*$/i
const NON_WORD_RE = /\W/g
const LEADING_DIGIT_RE = /^(\d)/

export type ExtractFailureReason = 'empty' | 'meta-node' | 'output-conflict' | 'duplicate-id'

export type ExtractResult
  = | { ok: true, nodeId: string }
    | { ok: false, reason: ExtractFailureReason, details: string[] }

export type SubworkflowGraphExtractResult
  = | {
    ok: true
    subworkflowNode: StoredNode
    removedNodeIds: string[]
    reboundParents: Array<{ nodeId: string, bindings: Record<string, string> }>
    remainingEdges: StoredEdge[]
  }
  | { ok: false, reason: ExtractFailureReason, details: string[] }

interface IncomingPort {
  sourceId: string
  field: string
  portName: string
  inputNodeId: string
  consumers: string[]
}

export function isValidPortName(name: string): boolean {
  return PORT_NAME_RE.test(name)
}

/** Build one meta node. Each meta node owns exactly one port. */
export function createSubworkflowPortNode(
  kind: 'input' | 'output',
  port: SubworkflowPort,
  position: { x: number, y: number },
  id: string = nanoid(),
): StoredNode {
  return {
    id,
    position,
    data: {
      label: port.name,
      nodeName: kind === 'input' ? 'subworkflow_input' : 'subworkflow_output',
      settings: { port },
    },
  }
}

export function readPort(data: NodeData | undefined | null): SubworkflowPort | null {
  const raw = data?.settings?.port
  if (!raw || typeof raw !== 'object' || typeof raw.name !== 'string' || raw.name.length === 0)
    return null
  return { name: raw.name }
}

export function writePort(node: Node<NodeData> | StoredNode, port: SubworkflowPort): void {
  if (!node.data)
    node.data = {} as NodeData
  node.data.settings = { ...(node.data.settings ?? {}), port: { name: port.name } }
  node.data.label = port.name
}

export function metaNodeKind(
  node: Node<NodeData> | StoredNode | undefined,
): 'input' | 'output' | null {
  const nodeName = node?.data?.nodeName
  if (nodeName === 'subworkflow_input')
    return 'input'
  if (nodeName === 'subworkflow_output')
    return 'output'
  return null
}

/** Port names must be usable as `<port>.field` binding references. */
export function toPortName(raw: string, fallback = 'port'): string {
  const cleaned = raw.replace(NON_WORD_RE, '_').replace(LEADING_DIGIT_RE, '_$1')
  return isValidPortName(cleaned) ? cleaned : fallback
}

export function uniquePortName(base: string, taken: Set<string>): string {
  if (!taken.has(base))
    return base
  let suffix = 2
  while (taken.has(`${base}_${suffix}`))
    suffix += 1
  return `${base}_${suffix}`
}

export function nextPortPosition(
  nodes: Array<{ position: { x: number, y: number } }>,
  kind: 'input' | 'output',
): { x: number, y: number } {
  if (nodes.length === 0)
    return kind === 'input' ? { x: 40, y: 140 } : { x: 560, y: 140 }

  const minX = Math.min(...nodes.map(node => node.position.x))
  const maxX = Math.max(...nodes.map(node => node.position.x))
  const maxY = Math.max(...nodes.map(node => node.position.y))
  return {
    x: kind === 'input' ? minX - 280 : maxX + 320,
    y: maxY + 80,
  }
}

/**
 * Pure graph transformation for extracting selected nodes into a subworkflow.
 *
 * Incoming references become one input node each. Exactly one distinct outgoing
 * value becomes the output; several are refused so nothing is silently dropped.
 */
export function extractSubworkflowGraph(
  allNodes: Array<Node<NodeData> | StoredNode>,
  allEdges: Array<Edge | StoredEdge>,
  selectedIds: string[],
  label: string,
  createId: () => string = nanoid,
): SubworkflowGraphExtractResult {
  const nodesById = new Map(allNodes.map(node => [node.id, node]))
  const selection = new Set(selectedIds)
  const selectedNodes = allNodes.filter(node => selection.has(node.id))
  if (selectedNodes.length === 0)
    return { ok: false, reason: 'empty', details: [] }

  const metaNodes = selectedNodes.filter(node => metaNodeKind(node) !== null)
  if (metaNodes.length > 0)
    return { ok: false, reason: 'meta-node', details: metaNodes.map(node => node.id) }

  const incoming = new Map<string, IncomingPort>()
  for (const node of selectedNodes) {
    for (const reference of Object.values<string>(node.data?.input_bindings ?? {})) {
      const parsed = splitReference(reference)
      if (!parsed)
        continue
      const [sourceId, field] = parsed
      if (selection.has(sourceId) || !nodesById.has(sourceId))
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
  for (const node of allNodes) {
    if (selection.has(node.id))
      continue
    for (const reference of Object.values<string>(node.data?.input_bindings ?? {})) {
      const parsed = splitReference(reference)
      if (parsed && selection.has(parsed[0]))
        outgoing.add(reference)
    }
  }
  if (outgoing.size === 0) {
    for (const edge of allEdges) {
      if (!selection.has(edge.source) || selection.has(edge.target))
        continue
      const sourceNode = nodesById.get(edge.source)
      if (!sourceNode)
        continue
      const explicitOutput = edge.sourceHandle?.startsWith(OUTPUT_HANDLE_PREFIX)
        ? edge.sourceHandle.slice(OUTPUT_HANDLE_PREFIX.length)
        : undefined
      const fallbackOutput = explicitOutput ?? getNodeOutputPorts({ data: sourceNode.data as NodeData })[0]?.name
      if (fallbackOutput)
        outgoing.add(`${edge.source}.${fallbackOutput}`)
    }
  }
  if (outgoing.size > 1)
    return { ok: false, reason: 'output-conflict', details: [...outgoing].sort() }

  const takenPorts = new Set<string>()
  const incomingPorts = [...incoming.values()].sort(
    (left, right) => left.sourceId.localeCompare(right.sourceId) || left.field.localeCompare(right.field),
  )
  for (const entry of incomingPorts) {
    const consumer = nodesById.get(entry.consumers[0]!)
    const consumerInput = consumer
      ? Object.entries(consumer.data?.input_bindings ?? {})
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
    entry.inputNodeId = createId()
    const firstConsumerY = innerPosition.get(entry.consumers[0]!)?.y ?? offsetY
    innerNodes.push(
      createSubworkflowPortNode(
        'input',
        { name: entry.portName },
        { x: 0, y: firstConsumerY },
        entry.inputNodeId,
      ),
    )
    for (const consumerId of entry.consumers) {
      innerEdges.push({
        id: createId(),
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

  for (const edge of allEdges) {
    if (!selection.has(edge.source) || !selection.has(edge.target))
      continue
    innerEdges.push({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle ?? null,
      targetHandle: edge.targetHandle ?? null,
    })
  }

  if (outputParsed && outputPortName) {
    const [producerId, producerField] = outputParsed
    const outputNodeId = createId()
    const outputY = innerPosition.get(producerId)?.y ?? offsetY
    innerNodes.push({
      id: outputNodeId,
      position: { x: maxX - minX + offsetX + 320, y: outputY },
      data: {
        label: outputPortName,
        nodeName: 'subworkflow_output',
        settings: {
          port: { name: outputPortName },
        },
        input_bindings: { [outputPortName]: `${producerId}.${producerField}` },
      },
    })
    innerEdges.push({
      id: createId(),
      source: producerId,
      target: outputNodeId,
      sourceHandle: null,
      targetHandle: `input:${outputPortName}`,
    })
  }

  const newNodeId = createId()
  const parentBindings: Record<string, string> = {}
  for (const entry of incomingPorts)
    parentBindings[entry.portName] = `${entry.sourceId}.${entry.field}`

  const reboundParents: Array<{ nodeId: string, bindings: Record<string, string> }> = []
  for (const node of allNodes) {
    if (selection.has(node.id))
      continue
    const existing = node.data?.input_bindings
    if (!existing)
      continue
    let changed = false
    const nextBindings = { ...existing }
    for (const [inputName, reference] of Object.entries<string>(existing)) {
      const parsed = splitReference(reference)
      if (!parsed || !selection.has(parsed[0]))
        continue
      changed = true
      if (outputPortName)
        nextBindings[inputName] = `${newNodeId}.${outputPortName}`
      else
        delete nextBindings[inputName]
    }
    if (changed)
      reboundParents.push({ nodeId: node.id, bindings: nextBindings })
  }

  // A source outside the selection may feed several input ports. Key by
  // source *and* field so each boundary edge gets the right handle.
  const portsBySource = new Map<string, IncomingPort[]>()
  for (const entry of incomingPorts) {
    const entries = portsBySource.get(entry.sourceId) ?? []
    entries.push(entry)
    portsBySource.set(entry.sourceId, entries)
  }

  const remainingEdges: StoredEdge[] = []
  const boundary: StoredEdge[] = []
  for (const edge of allEdges) {
    const sourceInside = selection.has(edge.source)
    const targetInside = selection.has(edge.target)
    if (sourceInside && targetInside)
      continue
    if (sourceInside) {
      boundary.push({
        id: createId(),
        source: newNodeId,
        target: edge.target,
        sourceHandle: outputPortName ? `output:${outputPortName}` : null,
        targetHandle: edge.targetHandle ?? null,
      })
      continue
    }
    if (targetInside) {
      const entries = portsBySource.get(edge.source) ?? []
      if (entries.length === 0) {
        boundary.push({
          id: createId(),
          source: edge.source,
          target: newNodeId,
          sourceHandle: edge.sourceHandle ?? null,
          targetHandle: null,
        })
        continue
      }
      for (const entry of entries) {
        boundary.push({
          id: createId(),
          source: edge.source,
          target: newNodeId,
          sourceHandle: edge.sourceHandle ?? null,
          targetHandle: `input:${entry.portName}`,
        })
      }
      continue
    }
    remainingEdges.push({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.sourceHandle ?? null,
      targetHandle: edge.targetHandle ?? null,
    })
  }

  const seenBoundary = new Set<string>()
  for (const edge of boundary) {
    const key = `${edge.source}->${edge.target}->${edge.sourceHandle}->${edge.targetHandle}`
    if (seenBoundary.has(key))
      continue
    seenBoundary.add(key)
    remainingEdges.push(edge)
  }

  return {
    ok: true,
    subworkflowNode: {
      id: newNodeId,
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
    },
    removedNodeIds: selectedNodes.map(node => node.id),
    reboundParents,
    remainingEdges,
  }
}
