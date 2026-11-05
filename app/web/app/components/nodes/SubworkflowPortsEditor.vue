<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import type { NodeData, SubworkflowPort } from '~/utils/nodes'
import type { TypeInfo } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'
import { useFlowStore } from '~/stores/flow'
import { isValidPortName } from '~/utils/nodes'

interface Props {
  nodeId: string
}

const props = defineProps<Props>()
const { t } = useI18n()
const store = useFlowStore()
const node = useScopedNode<Node<NodeData>>(props.nodeId)

const TYPE_MAP: Record<string, TypeInfo> = {
  any: { type: 'null' },
  string: { type: 'string' },
  number: { type: 'number' },
  integer: { type: 'integer' },
  boolean: { type: 'boolean' },
  object: { type: 'object' },
  arrayString: { type: 'array', items: { type: 'string' } },
  arrayNumber: { type: 'array', items: { type: 'number' } },
  arrayObject: { type: 'array', items: { type: 'object' } },
}

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
  return { name: raw.name, type: raw.type ?? { type: 'null' } }
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

const typeOptions = computed(() =>
  Object.keys(TYPE_MAP).map(key => ({
    label: t(`node.subworkflow.types.${key}`),
    value: key,
  })),
)

function typeToKey(type: TypeInfo | undefined): string {
  if (!type)
    return 'any'
  if (type.type === 'array') {
    const itemType = type.items?.type
    if (itemType === 'string')
      return 'arrayString'
    if (itemType === 'number' || itemType === 'integer')
      return 'arrayNumber'
    if (itemType === 'object')
      return 'arrayObject'
    return 'any'
  }
  return type.type in TYPE_MAP ? type.type : 'any'
}

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

function setType(key: string) {
  store.setSubworkflowPortType(props.nodeId, { ...TYPE_MAP[key] ?? { type: 'null' } })
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

    <div v-if="port" class="flex items-end gap-2">
      <div class="flex-1">
        <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">
          {{ t('node.subworkflow.portName') }}
        </label>
        <UInput
          v-model="draftName"
          class="mt-1"
          @blur="commitName"
          @keydown.enter="commitName"
        />
      </div>
      <div class="flex-1">
        <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">
          {{ t('node.subworkflow.portType') }}
        </label>
        <USelect
          :model-value="typeToKey(port.type)"
          :items="typeOptions"
          value-key="value"
          label-key="label"
          class="mt-1"
          @update:model-value="setType"
        />
      </div>
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
