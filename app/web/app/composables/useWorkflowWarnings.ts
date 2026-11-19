import type { PortType } from '@@/scripts/workflow-schema'
import type { NodeData } from '~/utils/nodes'
import { useFlowStore } from '~/stores/flow'
import {
  arePortsCompatible,
  describeType,
  getInputType,
  getOutputType,
} from '~/utils/schema-helpers'

/** One incompatible binding, mirroring the runner's validation error. */
export interface WorkflowWarning {
  key: string
  sourceNodeId: string
  sourceNodeLabel: string
  sourcePort: string
  sourceType: PortType
  targetNodeId: string
  targetNodeLabel: string
  targetPort: string
  targetType: PortType
  /** Localized one-line description for badges and the canvas popover. */
  message: string
}

interface GraphNode {
  id: string
  data: NodeData
}

type RawWarning = Omit<WorkflowWarning, 'message'>

function portLabel(data: NodeData): string {
  return data.label || data.nodeName
}

function collectWarnings(
  nodes: GraphNode[],
  warnings: RawWarning[],
  path: string[],
): void {
  const nodeById = new Map(nodes.map(node => [node.id, node]))
  const scopeKey = path.length > 0 ? `${path.join('::')}::` : ''

  for (const node of nodes) {
    for (const [targetPort, reference] of Object.entries(node.data.input_bindings ?? {})) {
      const separator = reference.indexOf('.')
      if (separator <= 0 || separator === reference.length - 1)
        continue

      const sourceId = reference.slice(0, separator)
      const sourcePort = reference.slice(separator + 1)
      const source = nodeById.get(sourceId)
      if (!source)
        continue

      if (arePortsCompatible({ data: node.data }, targetPort, { data: source.data }, sourcePort))
        continue

      warnings.push({
        key: `${scopeKey}${node.id}:${targetPort}`,
        sourceNodeId: source.id,
        sourceNodeLabel: portLabel(source.data),
        sourcePort,
        sourceType: getOutputType({ data: source.data }, sourcePort),
        targetNodeId: node.id,
        targetNodeLabel: portLabel(node.data),
        targetPort,
        targetType: getInputType({ data: node.data }, targetPort),
      })
    }
  }

  for (const node of nodes) {
    if (node.data.subworkflow)
      collectWarnings(node.data.subworkflow.nodes, warnings, [...path, node.id])
  }
}

/**
 * Every incompatible input binding in the current scope and its nested
 * subworkflows. The editor is permissive: these are warnings, not errors, and
 * the same problems make the runner reject the file.
 */
export function useWorkflowWarnings() {
  const store = useFlowStore()
  const { t } = useI18n()

  function describeWarning(warning: RawWarning): string {
    return t('editor.warningItem', {
      target: warning.targetNodeLabel,
      input: warning.targetPort,
      expected: describeType(warning.targetType),
      actual: describeType(warning.sourceType),
      source: warning.sourceNodeLabel,
      output: warning.sourcePort,
    })
  }

  const warnings = computed<WorkflowWarning[]>(() => {
    const collected: RawWarning[] = []
    collectWarnings(store.nodes.map(node => ({ id: node.id, data: node.data as NodeData })), collected, [])
    return collected.map(warning => ({ ...warning, message: describeWarning(warning) }))
  })

  const warningCount = computed(() => warnings.value.length)

  /** Edge ids that connect two nodes with a mismatched binding. */
  const warnedEdgeIds = computed(() => {
    const ids = new Set<string>()
    for (const warning of warnings.value) {
      for (const edge of store.edges) {
        if (edge.source === warning.sourceNodeId && edge.target === warning.targetNodeId)
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
    for (const warning of warnings.value)
      byPort[`${warning.targetNodeId}:${warning.targetPort}`] = warning
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
