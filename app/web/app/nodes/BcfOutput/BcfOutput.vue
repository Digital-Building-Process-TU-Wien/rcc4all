<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type BcfOutputNode = SchemaNodeType<'bcf_output'>

interface Props {
  node: BcfOutputNode
}

const props = defineProps<Props>()

const node = useScopedNode<BcfOutputNode>(props.node.id)

const AUTO_TITLE = '{class_name} {name} failed {property_name}'
const AUTO_DESCRIPTION = 'Element #{id} failed because {failure_reason}'

if (!node.value.data.settings) {
  node.value.data.settings = {
    mode: 'auto',
    title_template: AUTO_TITLE,
    description_template: AUTO_DESCRIPTION,
  }
}

const modes = [
  { value: 'auto', label: 'Auto' },
  { value: 'manual', label: 'Manual' },
] as const

function setMode(mode: 'auto' | 'manual') {
  node.value.data.settings!.mode = mode
  if (mode === 'auto') {
    node.value.data.settings!.title_template = AUTO_TITLE
    node.value.data.settings!.description_template = AUTO_DESCRIPTION
  }
  else {
    node.value.data.settings!.title_template = ''
    node.value.data.settings!.description_template = ''
  }
}

const manualTitleSuggestions = [
  AUTO_TITLE,
  '{id} – {name}: {property_name} check',
  'Guid {guid}: {property_name} failed',
  '{name} ({class_name}) comparison on {property_name}',
]

const manualDescSuggestions = [
  AUTO_DESCRIPTION,
  '{property_name}{condition_symbol}{expected}',
  'Expected {property_name} {expectation}; found {actual_display}',
  'Requirement {Pset_WallCommon.ThermalTransmittance.expected}; got {Pset_WallCommon.ThermalTransmittance.actual} (condition {Pset_WallCommon.ThermalTransmittance.condition})',
  'Length expected between {expected_min} and {expected_max}',
  '{name} ({class_name}, id {id}, guid {guid})',
]
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="px-2">
      <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
        BCF Output
      </div>
      <p class="mt-1 text-xs text-slate-500">
        Turn LOI-Check failures into a BCF 3.0 file. Connect the
        <span class="font-semibold">elements</span> output of an LOI-Check node.
      </p>
    </div>

    <div class="flex items-center gap-1 bg-slate-100 p-1 rounded">
      <button
        v-for="m in modes"
        :key="m.value"
        type="button"
        class="flex-1 rounded px-2 py-1 text-xs font-semibold transition-all"
        :class="node.data.settings!.mode === m.value
          ? 'bg-white text-slate-800 shadow-sm'
          : 'text-slate-500 hover:text-slate-700'"
        @click="setMode(m.value)"
      >
        {{ m.label }}
      </button>
    </div>

    <div v-if="node.data.settings!.mode === 'auto'" class="px-2">
      <p class="text-xs text-slate-500">
        <span class="font-semibold text-slate-700">Auto:</span> the standard
        templates are applied automatically for every LOI-Check scenario.
        Switch to manual mode to write your own title and description
        templates.
      </p>
    </div>

    <div v-if="node.data.settings!.mode === 'manual'" class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        Title template
      </label>
      <input
        v-model="node.data.settings!.title_template"
        :list="`bcf-output-titles-${node.id}`"
        placeholder="Choose a suggestion or type your own"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
      <datalist :id="`bcf-output-titles-${node.id}`">
        <option
          v-for="suggestion in manualTitleSuggestions"
          :key="suggestion"
          :value="suggestion"
        />
      </datalist>
    </div>

    <div v-if="node.data.settings!.mode === 'manual'" class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        Description template
      </label>
      <input
        v-model="node.data.settings!.description_template"
        :list="`bcf-output-descs-${node.id}`"
        placeholder="Choose a suggestion or type your own"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
      <datalist :id="`bcf-output-descs-${node.id}`">
        <option
          v-for="suggestion in manualDescSuggestions"
          :key="suggestion"
          :value="suggestion"
        />
      </datalist>
    </div>
  </div>
</template>
