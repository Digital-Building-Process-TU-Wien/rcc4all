<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'
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
  getRequiredNodeInputs,
  isModelInput,
} from '~/utils/schema-helpers'
import { matchCompatibleOutput, splitReference } from '~/utils/workflow-bindings'

interface Props {
  nodeId: string
}

const props = defineProps<Props>()
const store = useFlowStore()
const node = useScopedNode<Node<NodeData>>(props.nodeId)
const { t } = useI18n()
const { getBindingOptions } = useFlowGraph()

const nodeInputs = computed(() => getNodeInputs(node.value))
const requiredInputs = computed(() => new Set(getRequiredNodeInputs(node.value)))
const bindingOptions = computed(() => getBindingOptions(props.nodeId))

// Sentinel for the explicit "None" entry in the binding dropdowns. Selecting it
// removes the binding so the input falls back to its default.
const NONE_VALUE = '__none__'

// Keeps a user-selected source visible while they choose between ambiguous
// outputs (or see why no outputs are compatible) without writing a guess.
const pendingSourceByInput = ref<Record<string, string>>({})

watch(() => props.nodeId, () => {
  pendingSourceByInput.value = {}
})

const currentBindings = computed<Record<string, string>>(() => node.value.data!.input_bindings || {})

/** Friendly, localized labels for the dedicated model input port. */
function resolveInputLabel(inputName: string): string {
  if (isModelInput(inputName))
    return t('bindings.model')
  return getInputLabel(node.value, inputName)
}

function getBindingSource(inputName: string): string | undefined {
  const binding = currentBindings.value[inputName]
  if (binding) {
    const parsed = splitReference(binding)
    return parsed ? parsed[0] : binding
  }
  return pendingSourceByInput.value[inputName]
}

function getBindingOutput(inputName: string): string | undefined {
  const binding = currentBindings.value[inputName]
  if (!binding)
    return undefined
  return splitReference(binding)?.[1]
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
      .filter(output => arePortsCompatible(node.value, inputName, option.node, output))
      .map(output => ({ label: output, value: output })),
  ]
}

function clearPendingSource(inputName: string) {
  if (inputName in pendingSourceByInput.value) {
    const next = { ...pendingSourceByInput.value }
    delete next[inputName]
    pendingSourceByInput.value = next
  }
}

function clearBinding(inputName: string) {
  clearPendingSource(inputName)
  const bindings = { ...currentBindings.value }
  delete bindings[inputName]
  node.value.data!.input_bindings = bindings
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
    const match = sourceOption
      ? matchCompatibleOutput(sourceOption.node, node.value, inputName, sourceOption.outputs)
      : { kind: 'incompatible' as const }

    if (match.kind === 'matched') {
      newOutput = match.output
    }
    else {
      // Leave the binding blank rather than guessing; keep the source selected
      // so the user can pick an output right away.
      pendingSourceByInput.value = { ...pendingSourceByInput.value, [inputName]: newSource }
      delete bindings[inputName]
      node.value.data!.input_bindings = bindings
      return
    }
  }

  if (newSource && newOutput) {
    clearPendingSource(inputName)
    bindings[inputName] = `${newSource}.${newOutput}`
  }
  else {
    clearPendingSource(inputName)
    delete bindings[inputName]
  }

  node.value.data!.input_bindings = bindings
}

function getInputWarning(inputName: string): string | null {
  const binding = currentBindings.value[inputName]
  if (binding) {
    const parsed = splitReference(binding)
    if (!parsed)
      return null
    const [sourceId, outputField] = parsed
    const sourceNode = bindingOptions.value.find(opt => opt.id === sourceId)?.node
      ?? store.nodes.find(n => n.id === sourceId)
    if (!sourceNode)
      return null

    if (!arePortsCompatible(node.value, inputName, sourceNode, outputField)) {
      const outputType = getOutputType(sourceNode, outputField)
      const inputType = getInputType(node.value, inputName)
      return `${t('bindings.typeMismatch')}: ${describeType(outputType)} → ${describeType(inputType)}`
    }
    return null
  }

  const pendingSource = pendingSourceByInput.value[inputName]
  if (pendingSource) {
    const sourceOption = bindingOptions.value.find(opt => opt.id === pendingSource)
    const match = sourceOption
      ? matchCompatibleOutput(sourceOption.node, node.value, inputName, sourceOption.outputs)
      : { kind: 'incompatible' as const }
    if (match.kind === 'ambiguous')
      return t('bindings.ambiguousOutputs')
    if (match.kind === 'incompatible')
      return t('bindings.noCompatibleOutputs')
  }

  if (requiredInputs.value.has(inputName))
    return t('bindings.required')

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
        <span v-if="requiredInputs.has(inputName)" class="text-warning">*</span>
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

      <div v-if="getInputWarning(inputName)" class="mt-1 flex items-center gap-1 text-xs text-warning">
        <Icon name="i-lucide-triangle-alert" class="size-3" />
        <span>{{ getInputWarning(inputName) }}</span>
      </div>

      <p class="mt-1 text-xs text-muted">
        {{ getInputDescription(node, inputName) }}
      </p>
    </div>
  </div>

  <div v-else class="border-t border-default pt-4 mt-4">
    <p class="text-sm text-muted italic">
      {{ t('bindings.noConfigurableInputs') }}
    </p>
  </div>
</template>
