<script setup lang="ts">
import type { ComparisonCondition, ComparisonNode } from './types'
import { useScopedNode } from '~/composables/useScopedNode'
import {
  CONDITION_OPTIONS,
  requiresRange,
  requiresTargetValue,
} from './types'

interface Props {
  node: ComparisonNode
}

const props = defineProps<Props>()
const node = useScopedNode<ComparisonNode>(props.node.id)

const { t } = useI18n()

const decimalTooltip = 'Decimal values use a point: e.g. 0.25. A comma is not accepted.'

if (!node.value.data.settings) {
  node.value.data.settings = {
    condition: 'lt',
    target_value: 0.0,
    target_min: 0.0,
    target_max: 0.0,
    inclusive_min: true,
    inclusive_max: true,
  }
}

if (node.value.data.settings.condition === undefined)
  node.value.data.settings.condition = 'lt'

if (node.value.data.settings.target_value === undefined)
  node.value.data.settings.target_value = 0.0

if (node.value.data.settings.target_min === undefined)
  node.value.data.settings.target_min = 0.0

if (node.value.data.settings.target_max === undefined)
  node.value.data.settings.target_max = 0.0

if (node.value.data.settings.inclusive_min === undefined)
  node.value.data.settings.inclusive_min = true

if (node.value.data.settings.inclusive_max === undefined)
  node.value.data.settings.inclusive_max = true

const condition = computed<ComparisonCondition | undefined>(
  () => node.value.data.settings?.condition,
)
</script>

<template>
  <div class="flex flex-col gap-3 px-2">
    <div>
      <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
        {{ t('node.comparison.title') }}
      </div>
      <p class="mt-1 text-xs text-slate-500">
        {{ t('node.comparison.description') }}
      </p>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">
        {{ t('node.comparison.condition') }}
      </label>
      <select
        v-model="node.data.settings!.condition"
        class="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800"
      >
        <option
          v-for="opt in CONDITION_OPTIONS"
          :key="opt.value"
          :value="opt.value"
        >
          {{ opt.label }}
        </option>
      </select>
    </div>

    <div v-if="requiresTargetValue(condition)" class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">
        {{ t('node.comparison.targetValue') }}
      </label>
      <UTooltip :text="decimalTooltip" class="w-full">
        <input
          v-model.number="node.data.settings!.target_value"
          type="number"
          step="any"
          class="w-full rounded border border-slate-200 px-2 py-1 text-sm text-slate-800"
        >
      </UTooltip>
    </div>

    <div v-if="requiresRange(condition)" class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">
        {{ t('node.comparison.range') }}
      </label>
      <div class="flex items-center gap-2">
        <UTooltip :text="decimalTooltip" class="w-full">
          <input
            v-model.number="node.data.settings!.target_min"
            type="number"
            step="any"
            :placeholder="t('node.comparison.minPlaceholder')"
            class="w-full rounded border border-slate-200 px-2 py-1 text-sm text-slate-800"
          >
        </UTooltip>
        <UTooltip :text="decimalTooltip" class="w-full">
          <input
            v-model.number="node.data.settings!.target_max"
            type="number"
            step="any"
            :placeholder="t('node.comparison.maxPlaceholder')"
            class="w-full rounded border border-slate-200 px-2 py-1 text-sm text-slate-800"
          >
        </UTooltip>
      </div>
    </div>

    <div v-if="requiresRange(condition)" class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">
        {{ t('node.comparison.inclusion') }}
      </label>
      <div class="flex items-center gap-4">
        <label class="flex items-center gap-2 text-sm text-slate-700">
          <input
            v-model="node.data.settings!.inclusive_min"
            type="checkbox"
            class="h-4 w-4 rounded border-slate-300"
          >
          {{ t('node.comparison.inclusiveMin') }}
        </label>
        <label class="flex items-center gap-2 text-sm text-slate-700">
          <input
            v-model="node.data.settings!.inclusive_max"
            type="checkbox"
            class="h-4 w-4 rounded border-slate-300"
          >
          {{ t('node.comparison.inclusiveMax') }}
        </label>
      </div>
    </div>
  </div>
</template>
