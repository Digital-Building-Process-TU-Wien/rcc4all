<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
import { Handle, Position } from '@vue-flow/core'
import NodeDeleteButton from '~/components/nodes/NodeDeleteButton.vue'
import { useWorkflowWarnings } from '~/composables/useWorkflowWarnings'
import { getNodeInputPorts } from '~/schemas'

const props = defineProps<NodeProps<NodeData>>()
const { t } = useI18n()
const { warningsByPort } = useWorkflowWarnings()

const portsNode = computed(() => ({ data: props.data }))
const port = computed(() => getNodeInputPorts(portsNode.value)[0])
const warning = computed(() =>
  port.value ? warningsByPort.value[`${props.id}:${port.value.name}`] : undefined,
)
</script>

<template>
  <div
    class="group bg-slate-50 text-slate-900 border-2 border-green-200 rounded-lg min-w-45 shadow-sm relative cursor-pointer hover:shadow-md transition-shadow"
  >
    <Handle
      v-if="port"
      id="input-hitbox"
      type="target"
      :position="Position.Left"
      class="node-hitbox"
    />

    <Handle
      v-if="port"
      :id="`input:${port.name}`"
      type="target"
      :position="Position.Left"
      :title="port.name"
      class="w-4! h-4! border-2! border-white! -left-2! shadow-sm"
      :class="warning ? 'bg-amber-500!' : 'bg-green-600!'"
    />

    <div class="flex items-center justify-between gap-2 px-3 py-2">
      <div class="min-w-0">
        <p class="text-xs uppercase tracking-tight text-green-600">
          {{ t('node.subworkflow.outputNodeKind') }}
        </p>
        <p class="font-medium truncate">
          {{ port?.label ?? t('node.subworkflow.noPorts') }}
        </p>
      </div>
      <UIcon
        v-if="warning"
        name="i-lucide-triangle-alert"
        class="size-4 shrink-0 text-amber-500"
        :title="warning.message"
      />
      <NodeDeleteButton :node-id="props.id" />
    </div>
  </div>
</template>

<style scoped>
.vue-flow__handle.node-hitbox {
  position: absolute;
  inset: 0;
  width: 100% !important;
  height: 100% !important;
  transform: none;
  border: none;
  background: transparent;
  opacity: 0;
  z-index: 1;
  pointer-events: none;
}
</style>
