<script setup lang="ts">
import type { Node, NodeProps } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
import { Handle, Position } from '@vue-flow/core'
import NodeDeleteButton from '~/components/nodes/NodeDeleteButton.vue'
import { useOpenNodeSettings } from '~/composables/useNodeSettings'
import { useScopedNode } from '~/composables/useScopedNode'
import { useFlowStore } from '~/stores/flow'
import { getNodeInputPorts, getNodeOutputPorts } from '~/utils/schema-helpers'

const props = defineProps<NodeProps<NodeData>>()
const { t } = useI18n()
const store = useFlowStore()
const node = useScopedNode<Node<NodeData>>(props.id)
const openNodeSettings = useOpenNodeSettings()

const portsNode = computed(() => ({ data: props.data }))
const inputPorts = computed(() => getNodeInputPorts(portsNode.value))
const outputPorts = computed(() => getNodeOutputPorts(portsNode.value))
const hasPorts = computed(() => inputPorts.value.length > 0 || outputPorts.value.length > 0)

const title = computed({
  get: () => props.data.label ?? '',
  set: (value: string) => {
    const current = node.value
    if (!current?.data)
      return
    current.data.label = value
    if (current.data.subworkflow)
      current.data.subworkflow.name = value
  },
})

async function openSubworkflow() {
  if (store.enterSubworkflow(props.id)) {
    await nextTick()
    store.fitView(0.3)
  }
}

function handleSettingsClick() {
  openNodeSettings?.(props.id)
}

/** After typing, the input keeps its scroll offset and clips the start of the name. */
function resetTitleScroll(event: FocusEvent) {
  const input = event.currentTarget as HTMLInputElement
  input.scrollLeft = 0
}
</script>

<template>
  <div
    class="group bg-white text-slate-900 border-2 border-slate-200 rounded-lg w-80 shadow-sm relative cursor-pointer hover:shadow-md transition-shadow"
  >
    <div class="flex items-center gap-2 border-b border-slate-100 px-3 py-2">
      <UIcon name="i-lucide-boxes" class="size-4 shrink-0 text-slate-400" />
      <input
        v-model="title"
        type="text"
        class="nodrag nopan min-w-0 flex-1 rounded bg-transparent px-1 py-0.5 text-sm font-semibold outline-none hover:bg-slate-50 focus:bg-slate-50 focus:ring-1 focus:ring-primary"
        :placeholder="t('node.subworkflow.namePlaceholder')"
        :aria-label="t('node.subworkflow.nameLabel')"
        @click.stop
        @blur="resetTitleScroll"
      >
      <button
        type="button"
        class="text-slate-400 transition-colors hover:text-primary"
        :title="t('node.subworkflow.open')"
        :aria-label="t('node.subworkflow.open')"
        @click.stop="openSubworkflow"
      >
        <UIcon name="i-lucide-folder-open" class="size-4" />
      </button>
      <button
        type="button"
        class="text-slate-400 transition-colors hover:text-primary"
        :title="t('node.subworkflow.settings')"
        :aria-label="t('node.subworkflow.settings')"
        @click.stop="handleSettingsClick"
        @dblclick.stop
      >
        <UIcon name="i-lucide-settings" class="size-4" />
      </button>
      <NodeDeleteButton :node-id="props.id" />
    </div>

    <div v-if="hasPorts" class="py-1">
      <div
        v-for="port in inputPorts"
        :key="`in-${port.name}`"
        class="relative flex items-center gap-2 px-3 py-1"
      >
        <Handle
          :id="`input:${port.name}`"
          type="target"
          :position="Position.Left"
          :title="port.name"
          class="w-4! h-4! bg-blue-600! border-2! border-white! -left-3.5! shadow-sm"
        />
        <span class="truncate text-xs font-medium text-slate-600">{{ port.label }}</span>
      </div>

      <div
        v-for="port in outputPorts"
        :key="`out-${port.name}`"
        class="relative flex items-center justify-end gap-2 px-3 py-1"
      >
        <span class="truncate text-xs font-medium text-slate-600">{{ port.label }}</span>
        <Handle
          :id="`output:${port.name}`"
          type="source"
          :position="Position.Right"
          :title="port.name"
          class="w-4! h-4! bg-green-600! border-2! border-white! -right-3.5! shadow-sm"
        />
      </div>
    </div>

    <p v-else class="px-3 pb-2 text-xs italic text-slate-400">
      {{ t('node.subworkflow.noPorts') }}
    </p>
  </div>
</template>
