<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
import { Handle, Position } from '@vue-flow/core'
import NodeDeleteButton from '~/components/nodes/NodeDeleteButton.vue'
import { getNodeOutputPorts } from '~/utils/schema-helpers'

const props = defineProps<NodeProps<NodeData>>()
const { t } = useI18n()

const portsNode = computed(() => ({ data: props.data }))
const port = computed(() => getNodeOutputPorts(portsNode.value)[0])
</script>

<template>
  <div
    class="group bg-slate-50 text-slate-900 border-2 border-blue-200 rounded-lg min-w-45 shadow-sm relative cursor-pointer hover:shadow-md transition-shadow"
  >
    <div class="flex items-center justify-between gap-2 px-3 py-2">
      <div class="min-w-0">
        <p class="text-xs uppercase tracking-tight text-blue-500">
          {{ t('node.subworkflow.inputNodeKind') }}
        </p>
        <p class="font-medium truncate">
          {{ port?.label ?? t('node.subworkflow.noPorts') }}
        </p>
      </div>
      <NodeDeleteButton :node-id="props.id" />
    </div>

    <Handle
      v-if="port"
      :id="`output:${port.name}`"
      type="source"
      :position="Position.Right"
      :title="port.name"
      class="w-4! h-4! bg-blue-600! border-2! border-white! -right-2! shadow-sm"
    />
  </div>
</template>
