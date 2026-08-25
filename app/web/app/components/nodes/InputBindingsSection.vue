<script setup lang="ts">
import { computed } from 'vue'
import { useFlowStore } from '@/stores/flow'
import { useFlowGraph } from '~/composables/useFlowGraph'
import { useScopedNode } from '~/composables/useScopedNode'
import {
  areTypesCompatible,
  getInputDescription,
  getInputLabel,
  getInputType,
  getNodeInputs,
  getOutputType,
} from '~/utils/schema-helpers'

interface Props {
  nodeId: string
  nodeName: string
}

const props = defineProps<Props>()
const store = useFlowStore()
const node = useScopedNode(props.nodeId)
const { getBindingOptions } = useFlowGraph()

const nodeInputs = computed(() => getNodeInputs(props.nodeName))
const bindingOptions = computed(() => getBindingOptions(props.nodeId))

const currentBindings = computed(() => node.value.data.input_bindings || {})

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

function getSourceNodeOutputs(inputName: string): { label: string, value: string }[] {
  const sourceId = getBindingSource(inputName)
  if (!sourceId)
    return []

  const option = bindingOptions.value.find(opt => opt.id === sourceId)
  if (!option)
    return []

  const inputType = getInputType(props.nodeName, inputName)
  return option.outputs
    .filter(output => areTypesCompatible(getOutputType(option.nodeName, output), inputType))
    .map(output => ({
      label: output,
      value: output,
    }))
}

function updateBinding(inputName: string, sourceId?: string, outputField?: string) {
  const currentSource = getBindingSource(inputName)
  const currentOutput = getBindingOutput(inputName)

  const newSource = sourceId ?? currentSource
  let newOutput = outputField ?? currentOutput

  const bindings = { ...currentBindings.value }

  if (newSource && !newOutput) {
    const sourceOption = bindingOptions.value.find(opt => opt.id === newSource)
    if (sourceOption?.outputs?.length === 1) {
      newOutput = sourceOption.outputs[0]
    }
  }

  if (newSource && newOutput) {
    bindings[inputName] = `${newSource}.${newOutput}`
  }
  else if (newSource && !outputField) {
    bindings[inputName] = newSource
  }
  else if (!newSource) {
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

  if (!areTypesCompatible(outputType, inputType)) {
    return `Type mismatch: ${outputType.type} → ${inputType.type}`
  }

  return null
}
</script>

<template>
  <div v-if="nodeInputs.length > 0" class="border-t border-default pt-4 mt-4">
    <h3 class="text-sm font-semibold text-highlighted mb-3">
      Input Bindings
    </h3>

    <div v-for="inputName in nodeInputs" :key="inputName" class="mb-4">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">
        {{ getInputLabel(props.nodeName, inputName) }}
      </label>

      <div class="grid grid-cols-2 gap-2 mt-1">
        <USelect
          :model-value="getBindingSource(inputName)"
          :items="bindingOptions.map(opt => ({ value: opt.id, label: opt.label }))"
          value-key="value"
          label-key="label"
          placeholder="Select source node..."
          @update:model-value="(sourceId: string) => updateBinding(inputName, sourceId)"
        />

        <USelect
          :model-value="getBindingOutput(inputName)"
          :items="getSourceNodeOutputs(inputName)"
          item-key="value"
          placeholder="Select output..."
          :disabled="!getBindingSource(inputName)"
          @update:model-value="(output: string) => updateBinding(inputName, undefined, output)"
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
      This node has no configurable inputs
    </p>
  </div>
</template>
