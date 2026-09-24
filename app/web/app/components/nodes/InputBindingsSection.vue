<script setup lang="ts">
import { computed } from 'vue'
import { useFlowStore } from '@/stores/flow'
import { useFlowGraph } from '~/composables/useFlowGraph'
import { useScopedNode } from '~/composables/useScopedNode'
import {
  arePortsCompatible,
  describeType,
  getInputDescription,
  getInputLabel,
  getInputType,
  getNodeInputs,
  getOutputType,
  isModelInput,
} from '~/utils/schema-helpers'

interface Props {
  nodeId: string
  nodeName: string
}

const props = defineProps<Props>()
const store = useFlowStore()
const node = useScopedNode(props.nodeId)
const { t } = useI18n()
const { getBindingOptions } = useFlowGraph()

const nodeInputs = computed(() => getNodeInputs(props.nodeName))
const bindingOptions = computed(() => getBindingOptions(props.nodeId))

const currentBindings = computed(() => node.value.data.input_bindings || {})

// Sentinel for the explicit "None" entry in the binding dropdowns. Selecting it
// removes the binding so the input falls back to its default.
const NONE_VALUE = '__none__'

/** Friendly, localized labels for the dedicated model input port. */
function resolveInputLabel(inputName: string): string {
  if (isModelInput(inputName))
    return t('bindings.model')
  return getInputLabel(props.nodeName, inputName)
}

function getBindingSource(inputName: string): string | undefined {
  const binding = currentBindings.value[inputName]
  if (!binding)
    return undefined
  return binding.includes('.') ? binding.split('.')[0] : binding
}

function getBindingOutput(inputName: string): string | undefined {
  const binding = currentBindings.value[inputName]
  if (!binding || !binding.includes('.'))
    return undefined
  return binding.split('.')[1]
}

/** The source dropdown always offers an explicit "None" entry to clear the binding. */
function getSourceSelectValue(inputName: string): string {
  return getBindingSource(inputName) ?? NONE_VALUE
}

function getSourceOptions(): { label: string, value: string }[] {
  return [
    { label: t('bindings.none'), value: NONE_VALUE },
    ...bindingOptions.value.map(opt => ({ label: opt.label, value: opt.id })),
  ]
}

function getOutputOptions(inputName: string): { label: string, value: string }[] {
  const sourceId = getBindingSource(inputName)
  if (!sourceId)
    return []

  const option = bindingOptions.value.find(opt => opt.id === sourceId)
  if (!option)
    return []

  return [
    { label: t('bindings.none'), value: NONE_VALUE },
    ...option.outputs
      .filter(output => arePortsCompatible(props.nodeName, inputName, option.nodeName, output))
      .map(output => ({ label: output, value: output })),
  ]
}

function clearBinding(inputName: string) {
  const bindings = { ...currentBindings.value }
  delete bindings[inputName]
  node.value.data.input_bindings = bindings
}

function updateBinding(inputName: string, sourceId?: string, outputField?: string) {
  const currentSource = getBindingSource(inputName)
  const currentOutput = getBindingOutput(inputName)

  const sourceChanged = sourceId !== undefined && sourceId !== currentSource
  const newSource = sourceId ?? currentSource
  // Changing the source invalidates the previous output; re-resolve it below.
  let newOutput = outputField ?? (sourceChanged ? undefined : currentOutput)

  const bindings = { ...currentBindings.value }

  if (newSource && !newOutput) {
    const sourceOption = bindingOptions.value.find(opt => opt.id === newSource)
    const compatibleOutputs = sourceOption
      ? sourceOption.outputs.filter(output =>
          arePortsCompatible(props.nodeName, inputName, sourceOption.nodeName, output))
      : []
    newOutput = compatibleOutputs[0]
  }

  if (newSource && newOutput) {
    bindings[inputName] = `${newSource}.${newOutput}`
  }
  else {
    // No source, or a source with no compatible output: the input stays unbound
    // and falls back to its default.
    delete bindings[inputName]
  }

  node.value.data.input_bindings = bindings
}

function getTypeWarning(inputName: string): string | null {
  const binding = currentBindings.value[inputName]
  if (!binding)
    return null

  const [sourceId, outputField] = binding.split('.')
  const sourceNode = store.nodes.find(n => n.id === sourceId)
  if (!sourceNode)
    return null

  const outputType = getOutputType(sourceNode.data.nodeName, outputField)
  const inputType = getInputType(props.nodeName, inputName)

  if (!arePortsCompatible(props.nodeName, inputName, sourceNode.data.nodeName, outputField)) {
    return `${t('bindings.typeMismatch')}: ${describeType(outputType)} → ${describeType(inputType)}`
  }

  return null
}
</script>

<template>
  <div v-if="nodeInputs.length > 0" class="border-t border-default pt-4 mt-4">
    <h3 class="text-sm font-semibold text-highlighted mb-3">
      {{ t('bindings.title') }}
    </h3>

    <div v-for="inputName in nodeInputs" :key="inputName" class="mb-4">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">
        {{ resolveInputLabel(inputName) }}
      </label>

      <div class="grid grid-cols-2 gap-2 mt-1">
        <USelect
          :model-value="getSourceSelectValue(inputName)"
          :items="getSourceOptions()"
          value-key="value"
          label-key="label"
          :placeholder="t('bindings.selectSourceNode')"
          @update:model-value="(value: string) => value === NONE_VALUE ? clearBinding(inputName) : updateBinding(inputName, value)"
        />

        <USelect
          :model-value="getBindingOutput(inputName)"
          :items="getOutputOptions(inputName)"
          value-key="value"
          label-key="label"
          :placeholder="t('bindings.selectOutput')"
          :disabled="!getBindingSource(inputName)"
          @update:model-value="(value: string) => value === NONE_VALUE ? clearBinding(inputName) : updateBinding(inputName, undefined, value)"
        />
      </div>

      <div v-if="getTypeWarning(inputName)" class="mt-1 flex items-center gap-1 text-xs text-warning">
        <Icon name="i-lucide-triangle-alert" class="size-3" />
        <span>{{ getTypeWarning(inputName) }}</span>
      </div>

      <p class="mt-1 text-xs text-muted">
        {{ getInputDescription(props.nodeName, inputName) }}
      </p>
    </div>
  </div>

  <div v-else class="border-t border-default pt-4 mt-4">
    <p class="text-sm text-muted italic">
      {{ t('bindings.noConfigurableInputs') }}
    </p>
  </div>
</template>
