import type {
  ModelFile,
  SubworkflowDefinition,
  WorkflowDefinition,
  WorkflowEdge,
  WorkflowNode,
} from '@@/scripts/workflow-schema'
import type { NodeData, StoredEdge, StoredNode, SubworkflowDefinitionData } from './nodes'
import { WorkflowDefinitionSchema } from '@@/scripts/workflow-schema.zod'
import { getNodeInputPorts, getNodeOutputPorts } from './schema-helpers'

export interface Viewport {
  x: number
  y: number
  zoom: number
}

/**
 * The runnable workflow payload: assigned model files plus the serialized graph.
 * `openbim_runner` forbids unknown keys, so this is also exactly what is written
 * to `.dev-files` by the save dialog.
 */
export type ExportedWorkflow = WorkflowDefinition

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

/** Nodes that never accept an incoming edge; their inputs come from settings only. */
export function nodeHasNoInput(nodeName: string): boolean {
  return nodeName === 'file_input'
}

export function cloneValue<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

export function toStoredData(data: NodeData): NodeData {
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

export function cloneSubworkflow(definition: SubworkflowDefinitionData): SubworkflowDefinitionData {
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

export function hydrateModelFiles(raw: ModelFile[] | undefined): ModelFile[] {
  const valid = (raw ?? [])
    .filter(entry => entry.slug.length > 0)
    .map(entry => ({
      slug: entry.slug,
      path: entry.path,
      hash: entry.hash ?? '',
    }))

  const main = valid.find(file => file.slug === 'main')
  return [
    { slug: 'main', path: main?.path ?? '', hash: main?.hash ?? '' },
    ...valid.filter(file => file.slug !== 'main'),
  ]
}

export function serializeScope(nodes: StoredNode[], edges: StoredEdge[]): {
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
} {
  const keptNodes = nodes.filter(node => node.data.nodeName.toLowerCase() !== 'jsonoutput')
  const keptIds = new Set(keptNodes.map(node => node.id))

  return {
    nodes: keptNodes.map(serializeStoredNode),
    edges: edges
      .filter(edge => keptIds.has(edge.source) && keptIds.has(edge.target))
      .map(edge => ({ source: edge.source, target: edge.target })),
  }
}

function serializeStoredNode(node: StoredNode): WorkflowNode {
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
): SubworkflowDefinition {
  const scope = serializeScope(definition.nodes, definition.edges)
  return { name: definition.name || nodeLabel, nodes: scope.nodes, edges: scope.edges }
}

/** Nodes whose handles are named after a port (`output:<port>`), not fixed. */
function usesPortHandles(node: StoredNode | undefined): boolean {
  const name = node?.data.nodeName
  return name === 'subworkflow'
    || name === 'subworkflow_input'
    || name === 'subworkflow_output'
}

/**
 * The binding on the target that consumes this edge. Saved files carry no
 * handles, so the binding's port names are the only source of truth for which
 * port a reloaded edge was attached to.
 */
function boundPorts(
  sourceId: string,
  target: StoredNode | undefined,
): { inputPort: string, outputPort: string } | null {
  for (const [inputPort, reference] of Object.entries(target?.data.input_bindings ?? {})) {
    if (reference.startsWith(`${sourceId}.`))
      return { inputPort, outputPort: reference.slice(sourceId.length + 1) }
  }
  return null
}

function hydrateSourceHandle(
  node: StoredNode | undefined,
  boundOutput: string | undefined,
): string {
  if (!node || !usesPortHandles(node))
    return 'output'
  const name = boundOutput ?? getNodeOutputPorts({ data: node.data })[0]?.name
  return name ? `output:${name}` : 'output'
}

function hydrateTargetHandle(
  node: StoredNode | undefined,
  boundInput: string | undefined,
): string {
  if (!node || !usesPortHandles(node))
    return 'input'
  const name = boundInput ?? getNodeInputPorts({ data: node.data })[0]?.name
  return name ? `input:${name}` : 'input'
}

function hydrateEdge(
  raw: WorkflowEdge,
  index: number,
  nodeById: Map<string, StoredNode>,
): StoredEdge {
  const target = nodeById.get(raw.target)
  const binding = boundPorts(raw.source, target)
  return {
    id: `edge-${index}-${raw.source}-${raw.target}`,
    source: raw.source,
    target: raw.target,
    // Handles are editor state, not part of the runner payload. Recompute a
    // handle that the node actually renders.
    sourceHandle: hydrateSourceHandle(nodeById.get(raw.source), binding?.outputPort),
    targetHandle: hydrateTargetHandle(target, binding?.inputPort),
  }
}

function hydrateSubworkflow(raw: SubworkflowDefinition): SubworkflowDefinitionData {
  const nodes = (raw.nodes ?? []).map(hydrateNode)
  const nodeById = new Map(nodes.map(node => [node.id, node]))
  return {
    name: raw.name ?? '',
    nodes,
    edges: (raw.edges ?? []).map((edge, index) => hydrateEdge(edge, index, nodeById)),
    viewport: { x: 0, y: 0, zoom: 1 },
  }
}

function hydrateNode(raw: WorkflowNode): StoredNode {
  const nodeName = raw.type
  return {
    id: raw.id,
    position: { x: raw.position?.x ?? 0, y: raw.position?.y ?? 0 },
    data: {
      label: raw.label ?? '',
      nodeName,
      settings: raw.settings ?? {},
      input_bindings: raw.input_bindings ?? {},
      // The runner payload has no editor flags, so derive the one fixed by the
      // node type.
      ...(nodeHasNoInput(nodeName) ? { noInput: true } : {}),
      ...(raw.subworkflow ? { subworkflow: hydrateSubworkflow(raw.subworkflow) } : {}),
    },
  }
}

export function hydrateWorkflow(rawWorkflow: unknown): {
  rootFrame: ScopeFrame
  files: ModelFile[]
} {
  const workflow = WorkflowDefinitionSchema.parse(rawWorkflow)
  const nodes = (workflow.nodes ?? []).map(hydrateNode)
  const nodeById = new Map(nodes.map(node => [node.id, node]))

  return {
    rootFrame: {
      nodeId: null,
      label: '',
      nodes,
      edges: (workflow.edges ?? []).map((edge, index) => hydrateEdge(edge, index, nodeById)),
      viewport: { x: 0, y: 0, zoom: 1 },
    },
    files: hydrateModelFiles(workflow.files),
  }
}
