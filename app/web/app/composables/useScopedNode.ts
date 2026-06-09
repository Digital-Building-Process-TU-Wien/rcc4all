import type { Node } from '@vue-flow/core'
import { computed } from 'vue'
import { useFlowStore } from '@/stores/flow'

export function useScopedNode<T extends Node = Node>(id: string) {
  const store = useFlowStore()

  return computed<T>({
    get: () => store.nodesById[id] as T,
    set: (value) => {
      store.nodesById[id] = value as Node
    },
  })
}
