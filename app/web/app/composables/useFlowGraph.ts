import type { Node } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
import { useFlowStore } from '@/stores/flow'
import { formatLabel, getNodeOutputs } from '~/utils/schema-helpers'

export interface BindingOption {
  id: string
  label: string
  nodeName: string
  node: Node<NodeData>
  outputs: string[]
}

export function useFlowGraph() {
  const store = useFlowStore()

  function getAncestorNodes(targetNodeId: string): Node[] {
    const ancestors = new Set<string>()
    const queue = [targetNodeId]

    const incoming: Record<string, Set<string>> = {}
    function addIncoming(targetId: string, sourceId: string) {
      if (!incoming[targetId])
        incoming[targetId] = new Set()
      incoming[targetId]!.add(sourceId)
    }

    for (const edge of store.edges)
      addIncoming(edge.target, edge.source)

    for (const node of store.nodes) {
      const bindings = (node.data?.input_bindings ?? {}) as Record<string, string>
      for (const reference of Object.values(bindings)) {
        const [sourceId] = reference.split('.')
        if (sourceId && sourceId !== node.id)
          addIncoming(node.id, sourceId)
      }
    }

    while (queue.length > 0) {
      const currentId = queue.shift()!
      for (const sourceId of incoming[currentId] ?? []) {
        if (!ancestors.has(sourceId)) {
          ancestors.add(sourceId)
          queue.push(sourceId)
        }
      }
    }

    return store.nodes.filter(node => ancestors.has(node.id))
  }

  function getBindingOptions(targetNodeId: string): BindingOption[] {
    const targetNode = store.nodesById[targetNodeId]
    const ancestors = getAncestorNodes(targetNodeId)
    // Input nodes are valid binding sources even before an edge is drawn.
    const inputNodes = store.nodes.filter(
      node => node.data?.nodeName === 'subworkflow_input' && node.id !== targetNodeId,
    )
    const sources = [...ancestors]
    for (const inputNode of inputNodes) {
      if (!sources.some(node => node.id === inputNode.id))
        sources.push(inputNode)
    }
    // The subworkflow output node is a sink: any inner node can be its producer.
    if (targetNode?.data?.nodeName === 'subworkflow_output') {
      for (const node of store.nodes) {
        if (node.id !== targetNodeId && !sources.some(source => source.id === node.id))
          sources.push(node)
      }
    }

    return sources.map(ancestor => ({
      id: ancestor.id,
      label: `${ancestor.data.label} (${formatLabel(ancestor.data.nodeName)})`,
      nodeName: ancestor.data.nodeName,
      node: ancestor as Node<NodeData>,
      outputs: getNodeOutputs(ancestor),
    }))
  }

  return {
    getAncestorNodes,
    getBindingOptions,
  }
}
