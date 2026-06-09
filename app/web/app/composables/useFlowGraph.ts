import type { Node } from '@vue-flow/core'
import { useFlowStore } from '@/stores/flow'
import { formatLabel, getNodeOutputs } from '~/utils/schema-helpers'

export interface BindingOption {
  id: string
  label: string
  nodeName: string
  outputs: string[]
}

export function useFlowGraph() {
  const store = useFlowStore()

  function getAncestorNodes(targetNodeId: string): Node[] {
    const ancestors = new Set<string>()
    const queue = [targetNodeId]

    while (queue.length > 0) {
      const currentId = queue.shift()!
      const incomingEdges = store.edges.filter(e => e.target === currentId)

      for (const edge of incomingEdges) {
        if (!ancestors.has(edge.source)) {
          ancestors.add(edge.source)
          queue.push(edge.source)
        }
      }
    }

    return store.nodes.filter(n => ancestors.has(n.id))
  }

  function getBindingOptions(targetNodeId: string): BindingOption[] {
    const ancestors = getAncestorNodes(targetNodeId)

    const options = ancestors.map(ancestor => ({
      id: ancestor.id,
      label: `${ancestor.data.label} (${formatLabel(ancestor.data.nodeName)})`,
      nodeName: ancestor.data.nodeName,
      outputs: getNodeOutputs(ancestor.data.nodeName),
    }))
    return options
  }

  return {
    getAncestorNodes,
    getBindingOptions,
  }
}
