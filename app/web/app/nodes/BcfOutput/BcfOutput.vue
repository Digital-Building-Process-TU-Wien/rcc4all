<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type BcfOutputNode = SchemaNodeType<'bcf_output'>

interface Props {
  node: BcfOutputNode
}

const props = defineProps<Props>()

const node = useScopedNode<BcfOutputNode>(props.node.id)
const { t } = useI18n()

const AUTO_TITLE = '{class_name} {name} failed {check_parameter}'
const AUTO_DESCRIPTION = 'Element #{id} failed because {failure_reason}'

if (!node.value.data.settings) {
  node.value.data.settings = {
    mode: 'auto',
    title_template: AUTO_TITLE,
    description_template: AUTO_DESCRIPTION,
    project_name: 'Default Project',
    author: 'Default Author',
    topic_type: '',
    topic_status: '',
    output_filename: 'check-results.bcf',
    included_elements: 'failed',
  }
}

const modes = [
  { value: 'auto', labelKey: 'node.bcfOutput.modeAuto' },
  { value: 'manual', labelKey: 'node.bcfOutput.modeManual' },
] as const

const includedOptions = [
  { value: 'all', labelKey: 'node.bcfOutput.includedAll' },
  { value: 'failed', labelKey: 'node.bcfOutput.includedFailed' },
  { value: 'passed', labelKey: 'node.bcfOutput.includedPassed' },
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
  '{id} – {name}: {check_parameter} check',
  'Guid {guid}: {check_parameter} failed',
  '{name} ({class_name}) comparison on {check_parameter}',
]

const manualDescSuggestions = [
  AUTO_DESCRIPTION,
  '{check_parameter}{condition_symbol}{expected}',
  'Expected {check_parameter} {expectation}; found {actual_display}',
  'Requirement {key.expected}; got {key.actual} (condition {key.condition})',
  'Length expected between {expected_min} and {expected_max}',
  '{name} ({class_name}, id {id}, guid {guid})',
]

const topicTypeSuggestions = [
  'Model Check',
  'Clash',
  'Coordination Issue',
  'Information',
  'Quality',
  'Safety',
  'Change Request',
]

const topicStatusSuggestions = [
  'Open',
  'In Progress',
  'Question',
  'Answered',
  'Done',
  'Closed',
]
</script>

<template>
  <div class="flex flex-col gap-3 px-2">
    <div>
      <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
        {{ t('node.bcfOutput.title') }}
      </div>
      <p class="mt-1 text-xs text-slate-500">
        {{ t('node.bcfOutput.description', { elements: 'elements' }) }}
      </p>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.bcfOutput.projectName') }}
      </label>
      <input
        v-model="node.data.settings!.project_name"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.bcfOutput.author') }}
      </label>
      <input
        v-model="node.data.settings!.author"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
    </div>

    <div class="grid grid-cols-2 gap-2">
      <div class="flex flex-col gap-2">
        <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
          {{ t('node.bcfOutput.topicType') }}
        </label>
        <input
          v-model="node.data.settings!.topic_type"
          :list="`bcf-output-types-${node.id}`"
          :placeholder="t('node.bcfOutput.suggestionPlaceholder')"
          class="w-full rounded border border-slate-200 px-2 py-1 text-xs text-slate-800 focus:ring-1 focus:ring-blue-500 outline-none transition-all shadow-sm"
        >
        <datalist :id="`bcf-output-types-${node.id}`">
          <option
            v-for="suggestion in topicTypeSuggestions"
            :key="suggestion"
            :value="suggestion"
          />
        </datalist>
      </div>
      <div class="flex flex-col gap-2">
        <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
          {{ t('node.bcfOutput.topicStatus') }}
        </label>
        <input
          v-model="node.data.settings!.topic_status"
          :list="`bcf-output-statuses-${node.id}`"
          :placeholder="t('node.bcfOutput.suggestionPlaceholder')"
          class="w-full rounded border border-slate-200 px-2 py-1 text-xs text-slate-800 focus:ring-1 focus:ring-blue-500 outline-none transition-all shadow-sm"
        >
        <datalist :id="`bcf-output-statuses-${node.id}`">
          <option
            v-for="suggestion in topicStatusSuggestions"
            :key="suggestion"
            :value="suggestion"
          />
        </datalist>
      </div>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.bcfOutput.outputFilename') }}
      </label>
      <input
        v-model="node.data.settings!.output_filename"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.bcfOutput.includedElements') }}
      </label>
      <div class="flex items-center gap-1 bg-slate-100 p-1 rounded">
        <button
          v-for="opt in includedOptions"
          :key="opt.value"
          type="button"
          class="flex-1 rounded px-2 py-1 text-xs font-semibold transition-all"
          :class="node.data.settings!.included_elements === opt.value
            ? 'bg-white text-slate-800 shadow-sm'
            : 'text-slate-500 hover:text-slate-700'"
          @click="node.data.settings!.included_elements = opt.value"
        >
          {{ t(opt.labelKey) }}
        </button>
      </div>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.bcfOutput.outputMode') }}
      </label>
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
          {{ t(m.labelKey) }}
        </button>
      </div>
    </div>

    <div v-if="node.data.settings!.mode === 'auto'" class="px-2">
      <p class="text-xs text-slate-500">
        <span class="font-semibold text-slate-700">{{ t('node.bcfOutput.modeAuto') }}:</span>
        {{ t('node.bcfOutput.autoModeInfo') }}
      </p>
    </div>

    <div v-if="node.data.settings!.mode === 'manual'" class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.bcfOutput.titleTemplate') }}
      </label>
      <input
        v-model="node.data.settings!.title_template"
        :list="`bcf-output-titles-${node.id}`"
        :placeholder="t('node.bcfOutput.suggestionPlaceholder')"
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
        {{ t('node.bcfOutput.descriptionTemplate') }}
      </label>
      <input
        v-model="node.data.settings!.description_template"
        :list="`bcf-output-descs-${node.id}`"
        :placeholder="t('node.bcfOutput.suggestionPlaceholder')"
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
