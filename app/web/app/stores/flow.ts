import type { Edge, Node } from '@vue-flow/core'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

interface Viewport {
  x: number
  y: number
  zoom: number
}

export const useFlowStore = defineStore('flow', () => {
  const nodesById = ref<Record<string, Node>>({})
  const edges = ref<Edge[]>([])
  const viewport = ref<Viewport>({
    x: 0,
    y: 0,
    zoom: 1,
  })

  const nodes = computed(() => Object.values(nodesById.value))

  const hasNodes = computed(() => nodes.value.length > 0)
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

  function removeNode(nodeId: string) {
    delete nodesById.value[nodeId]
    edges.value = edges.value.filter(
      edge => edge.source !== nodeId && edge.target !== nodeId,
    )
  }

  function addEdges(newEdges: Edge | Edge[]) {
    const edgesArray = Array.isArray(newEdges) ? newEdges : [newEdges]
    edges.value.push(...edgesArray)
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

  function clear() {
    nodesById.value = {}
    edges.value = []
    viewport.value = { x: 0, y: 0, zoom: 1 }
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
    nodes,
    hasNodes,
    nodeCount,
    addNodes,
    setNodes,
    removeNode,
    addEdges,
    setEdges,
    updateNodeData,
    updateNodePosition,
    updateViewport,
    clear,
    fitView,
  }
})
