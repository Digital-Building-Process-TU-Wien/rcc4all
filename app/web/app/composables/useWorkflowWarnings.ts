import type { JsonSchema, PortResolutionContext } from '~/schemas'
import type { NodeData, StoredEdge } from '~/utils/nodes'
import {
  arePortsCompatible,
  describeSchema,
  findPortMismatchSchemas,
  getInputSchema,
  getNodeInputs,
  getNodeOutputs,
  getRequiredNodeInputs,
  INPUT_HANDLE_PREFIX,
  parsePortHandle,
  resolveScopeContext,
  resolveSubworkflowParentContext,
} from '~/schemas'
import { useFlowStore } from '~/stores/flow'
import { splitReference } from '~/utils/workflow-bindings'

export type WorkflowWarningKind = 'type-mismatch' | 'missing-required' | 'unbound-edge'

/** One editor warning mirroring runner validation or flagging an unbound wire. */
export interface WorkflowWarning {
  key: string
  kind: WorkflowWarningKind
  edgeId?: string
  sourceNodeId?: string
  sourceNodeLabel?: string
  sourcePort?: string
  sourceSchema?: JsonSchema
  targetNodeId: string
  targetNodeLabel: string
  targetPort?: string
  targetSchema?: JsonSchema
  /** Localized one-line description for badges and the canvas popover. */
  message: string
}

interface GraphNode {
  id: string
  data: NodeData
}

type GraphEdge = Pick<StoredEdge, 'id' | 'source' | 'target' | 'targetHandle'>
type RawWarning = Omit<WorkflowWarning, 'message'>

function portLabel(data: NodeData): string {
  return data.label || data.nodeName
}

function collectWarnings(
  nodes: GraphNode[],
  edges: GraphEdge[],
  warnings: RawWarning[],
  path: string[],
  context: PortResolutionContext,
): void {
  const nodeById = new Map(nodes.map(node => [node.id, node]))
  const scopeKey = path.length > 0 ? `${path.join('::')}::` : ''
  const scopedContext: PortResolutionContext = { ...context, siblingNodes: nodes }

  for (const node of nodes) {
    const bindings = node.data.input_bindings ?? {}

    for (const [targetPort, reference] of Object.entries(bindings)) {
      const parsed = splitReference(reference)
      if (!parsed)
        continue

      const [sourceId, sourcePort] = parsed
      const source = nodeById.get(sourceId)
      if (!source)
        continue

      if (arePortsCompatible({ data: node.data }, targetPort, { data: source.data }, sourcePort, scopedContext))
        continue

      const { sourceSchema, targetSchema } = findPortMismatchSchemas(
        { data: node.data },
        targetPort,
        { data: source.data },
        sourcePort,
        scopedContext,
      )

      warnings.push({
        key: `${scopeKey}mismatch:${node.id}:${targetPort}`,
        kind: 'type-mismatch',
        sourceNodeId: source.id,
        sourceNodeLabel: portLabel(source.data),
        sourcePort,
        sourceSchema,
        targetNodeId: node.id,
        targetNodeLabel: portLabel(node.data),
        targetPort,
        targetSchema,
      })
    }

    for (const requiredInput of getRequiredNodeInputs({ data: node.data })) {
      if (bindings[requiredInput])
        continue
      warnings.push({
        key: `${scopeKey}required:${node.id}:${requiredInput}`,
        kind: 'missing-required',
        targetNodeId: node.id,
        targetNodeLabel: portLabel(node.data),
        targetPort: requiredInput,
        targetSchema: getInputSchema({ data: node.data }, requiredInput),
      })
    }
  }

  for (const edge of edges) {
    const source = nodeById.get(edge.source)
    const target = nodeById.get(edge.target)
    if (!source || !target)
      continue
    if (getNodeOutputs({ data: source.data }).length === 0 || getNodeInputs({ data: target.data }).length === 0)
      continue

    const bindings = target.data.input_bindings ?? {}
    const explicitInput = parsePortHandle(edge.targetHandle, INPUT_HANDLE_PREFIX)

    const isBound = explicitInput
      ? splitReference(bindings[explicitInput] ?? '')?.[0] === source.id
      : Object.values(bindings).some(ref => splitReference(ref)?.[0] === source.id)

    if (isBound)
      continue

    warnings.push({
      key: `${scopeKey}unbound:${edge.id}`,
      kind: 'unbound-edge',
      edgeId: edge.id,
      sourceNodeId: source.id,
      sourceNodeLabel: portLabel(source.data),
      targetNodeId: target.id,
      targetNodeLabel: portLabel(target.data),
      ...(explicitInput ? { targetPort: explicitInput } : {}),
    })
  }

  for (const node of nodes) {
    if (node.data.subworkflow) {
      const innerContext = resolveSubworkflowParentContext(node, nodes, context)
      collectWarnings(
        node.data.subworkflow.nodes,
        node.data.subworkflow.edges,
        warnings,
        [...path, node.id],
        innerContext,
      )
    }
  }
}

/**
 * Every binding/type warning in the current scope and its nested subworkflows.
 * The editor stays permissive: these are warnings, not hard blocks, while the
 * runner enforces required inputs and port types strictly.
 */
export function useWorkflowWarnings() {
  const store = useFlowStore()
  const { t } = useI18n()

  function describeWarning(warning: RawWarning): string {
    if (warning.kind === 'missing-required') {
      return t('editor.warningMissingRequired', {
        target: warning.targetNodeLabel,
        input: warning.targetPort,
      })
    }
    if (warning.kind === 'unbound-edge') {
      return t('editor.warningUnboundEdge', {
        source: warning.sourceNodeLabel,
        target: warning.targetNodeLabel,
      })
    }
    return t('editor.warningItem', {
      target: warning.targetNodeLabel,
      input: warning.targetPort,
      expected: warning.targetSchema ? describeSchema(warning.targetSchema) : 'unknown',
      actual: warning.sourceSchema ? describeSchema(warning.sourceSchema) : 'unknown',
      source: warning.sourceNodeLabel,
      output: warning.sourcePort,
    })
  }

  const warnings = computed<WorkflowWarning[]>(() => {
    const collected: RawWarning[] = []
    const scopeContext = resolveScopeContext(store.scopeStack)
    collectWarnings(
      store.nodes.map(node => ({ id: node.id, data: node.data as NodeData })),
      store.edges,
      collected,
      [],
      scopeContext,
    )
    return collected.map(warning => ({ ...warning, message: describeWarning(warning) }))
  })

  const warningCount = computed(() => warnings.value.length)

  /** Edge ids that carry a type mismatch or have no binding to their target. */
  const warnedEdgeIds = computed(() => {
    const ids = new Set<string>()
    for (const warning of warnings.value) {
      if (warning.edgeId) {
        ids.add(warning.edgeId)
        continue
      }
      if (!warning.sourceNodeId)
        continue
      for (const edge of store.edges) {
        if (edge.source !== warning.sourceNodeId || edge.target !== warning.targetNodeId)
          continue
        const explicitInput = parsePortHandle(edge.targetHandle, INPUT_HANDLE_PREFIX)
        if (!explicitInput || !warning.targetPort || explicitInput === warning.targetPort)
          ids.add(edge.id)
      }
    }
    return ids
  })

  /** `nodeId` → number of warnings targeting that node. */
  const nodeWarningCounts = computed(() => {
    const counts: Record<string, number> = {}
    for (const warning of warnings.value)
      counts[warning.targetNodeId] = (counts[warning.targetNodeId] ?? 0) + 1
    return counts
  })

  /** `nodeId:portName` → warning, for badge placement on a specific port. */
  const warningsByPort = computed(() => {
    const byPort: Record<string, WorkflowWarning> = {}
    for (const warning of warnings.value) {
      if (!warning.targetPort)
        continue
      const portKey = `${warning.targetNodeId}:${warning.targetPort}`
      if (!byPort[portKey] || warning.kind === 'type-mismatch')
        byPort[portKey] = warning
    }
    return byPort
  })

  return {
    warnings,
    warningCount,
    warnedEdgeIds,
    nodeWarningCounts,
    warningsByPort,
  }
}
