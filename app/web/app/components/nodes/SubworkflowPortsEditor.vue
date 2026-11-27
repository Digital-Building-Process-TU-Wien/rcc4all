<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import type { NodeData, SubworkflowPort } from '~/utils/nodes'
import { useScopedNode } from '~/composables/useScopedNode'
import { useFlowStore } from '~/stores/flow'
import { isValidPortName } from '~/utils/subworkflow-graph'

interface Props {
  nodeId: string
}

const props = defineProps<Props>()
const { t } = useI18n()
const store = useFlowStore()
const node = useScopedNode<Node<NodeData>>(props.nodeId)

const kind = computed<'input' | 'output' | null>(() => {
  const nodeName = node.value?.data?.nodeName
  if (nodeName === 'subworkflow_input')
    return 'input'
  if (nodeName === 'subworkflow_output')
    return 'output'
  return null
})

const port = computed<SubworkflowPort | null>(() => {
  const raw = node.value?.data?.settings?.port
  if (!raw || typeof raw !== 'object' || typeof raw.name !== 'string')
    return null
  return { name: raw.name }
})

const draftName = ref('')
const error = ref('')

watch(
  () => port.value?.name ?? '',
  (name) => {
    draftName.value = name
    error.value = ''
  },
  { immediate: true },
)

function commitName() {
  const current = port.value?.name
  if (!current)
    return

  const next = draftName.value.trim()
  if (next === current) {
    draftName.value = current
    error.value = ''
    return
  }
  if (!isValidPortName(next)) {
    draftName.value = current
    error.value = t('node.subworkflow.invalidPortName')
    return
  }
  if (!store.renameSubworkflowPort(props.nodeId, next)) {
    draftName.value = current
    error.value = t('node.subworkflow.duplicatePortName')
    return
  }
  error.value = ''
}

/** Inside a subworkflow, an input port is silent unless the parent binds it. */
const parentBinding = computed<string | undefined>(() => {
  const stack = store.scopeStack
  const frame = stack.at(-1)
  const parentFrame = stack.at(-2)
  if (!frame?.nodeId || !parentFrame)
    return undefined
  const parentNode = parentFrame.nodes.find(entry => entry.id === frame.nodeId)
  const name = port.value?.name
  return name ? parentNode?.data.input_bindings?.[name] : undefined
})

const outputUnbound = computed(() =>
  kind.value === 'output'
  && !!port.value
  && !node.value?.data?.input_bindings?.[port.value.name],
)
</script>

<template>
  <div v-if="kind" class="border-t border-default pt-4 mt-4">
    <h3 class="text-sm font-semibold text-highlighted mb-3">
      {{ kind === 'input' ? t('node.subworkflow.inputPortTitle') : t('node.subworkflow.outputPortTitle') }}
    </h3>

    <div v-if="port">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">
        {{ t('node.subworkflow.portName') }}
      </label>
      <UInput
        v-model="draftName"
        class="mt-1 w-full"
        @blur="commitName"
        @keydown.enter="commitName"
      />
    </div>

    <p v-if="error" class="mt-2 flex items-center gap-1 text-xs text-error">
      <UIcon name="i-lucide-triangle-alert" class="size-3" />
      {{ error }}
    </p>
    <p
      v-else-if="kind === 'input' && !parentBinding"
      class="mt-2 flex items-center gap-1 text-xs text-warning"
    >
      <UIcon name="i-lucide-triangle-alert" class="size-3" />
      {{ t('node.subworkflow.unboundPort') }}
    </p>
    <p
      v-else-if="outputUnbound"
      class="mt-2 flex items-center gap-1 text-xs text-warning"
    >
      <UIcon name="i-lucide-triangle-alert" class="size-3" />
      {{ t('node.subworkflow.outputUnbound') }}
    </p>
  </div>
</template>
