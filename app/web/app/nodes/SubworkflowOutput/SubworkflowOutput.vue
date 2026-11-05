<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
import { Handle, Position } from '@vue-flow/core'
import NodeDeleteButton from '~/components/nodes/NodeDeleteButton.vue'
import { getNodeInputPorts } from '~/utils/schema-helpers'

const props = defineProps<NodeProps<NodeData>>()
const { t } = useI18n()

const portsNode = computed(() => ({ data: props.data }))
const port = computed(() => getNodeInputPorts(portsNode.value)[0])
</script>

<template>
  <div
    class="group bg-slate-50 text-slate-900 border-2 border-green-200 rounded-lg min-w-45 shadow-sm relative cursor-pointer hover:shadow-md transition-shadow"
  >
    <Handle
      v-if="port"
      :id="`input:${port.name}`"
      type="target"
      :position="Position.Left"
      :title="port.name"
      class="w-4! h-4! bg-green-600! border-2! border-white! -left-2! shadow-sm"
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
      <NodeDeleteButton :node-id="props.id" />
    </div>
  </div>
</template>
