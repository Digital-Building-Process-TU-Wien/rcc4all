import type { HandleType, Position } from '@vue-flow/core'
import type { Component } from 'vue'
import type { NodeData } from '~/utils/nodes'
import type { OutputSocketTarget } from '~/utils/schema-helpers'
import BcfSocket from '~/components/nodes/sockets/BcfSocket.vue'
import NodeSocket from '~/components/nodes/sockets/NodeSocket.vue'
import { getOutputSocketTargets } from '~/utils/schema-helpers'

export interface NodeSocketProps {
  id: string
  type: HandleType
  position: Position
  connectable?: boolean
  warning?: boolean
  title?: string
}

export type SocketKind = 'default' | OutputSocketTarget

const SOCKET_COMPONENTS: Record<SocketKind, Component> = {
  default: markRaw(NodeSocket),
  bcf: markRaw(BcfSocket),
}

const SINK_NODE_NAMES = new Set(['JsonOutput', 'bcf_output'])

function resolveInputSocketKind(data: NodeData | undefined): SocketKind | null {
  if (!data || data.noInput)
    return null
  return 'default'
}

function resolveOutputSocketKind(data: NodeData | undefined): SocketKind | null {
  if (!data || data.noOutput || SINK_NODE_NAMES.has(data.nodeName))
    return null

  const [target] = getOutputSocketTargets({ data })
  return target ?? 'default'
}

export function useNodeSockets(getNodeData: () => NodeData | undefined) {
  const inputSocket = computed<Component | null>(() => {
    const kind = resolveInputSocketKind(getNodeData())
    return kind ? SOCKET_COMPONENTS[kind] : null
  })

  const outputSocket = computed<Component | null>(() => {
    const kind = resolveOutputSocketKind(getNodeData())
    return kind ? SOCKET_COMPONENTS[kind] : null
  })

  return {
    inputSocket,
    outputSocket,
  }
}
