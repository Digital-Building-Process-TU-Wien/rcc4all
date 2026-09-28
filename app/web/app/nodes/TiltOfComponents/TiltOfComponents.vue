<script setup lang="ts">
import type {
  ComparisonMethod,
  ElementCategory,
  TiltOfComponentsNode,
} from './types'
import { useScopedNode } from '~/composables/useScopedNode'
import {
  COMPARISON_METHOD_OPTIONS,
  ELEMENT_CATEGORY_OPTIONS,
  requiresInterval,
  requiresLowerLimit,
  requiresUpperLimit,
} from './types'

interface Props {
  node: TiltOfComponentsNode
}

const props = defineProps<Props>()
const node = useScopedNode<TiltOfComponentsNode>(props.node.id)

const decimalTooltip = 'Decimal values use a point: e.g. 0.25. A comma is not accepted.'

if (!node.value.data.settings) {
  node.value.data.settings = {
    element_category: '2d',
    comparison_method: 'greater_than_lower',
    lower_limit: 0,
    upper_limit: 90,
    interval_lower: 0,
    interval_upper: 90,
    horizontal_separation_angle: 5,
    tolerance: 0.1,
  }
}

if (!node.value.data.settings.element_category)
  node.value.data.settings.element_category = '2d'

if (!node.value.data.settings.comparison_method)
  node.value.data.settings.comparison_method = 'greater_than_lower'

if (node.value.data.settings.lower_limit === undefined)
  node.value.data.settings.lower_limit = 0

if (node.value.data.settings.upper_limit === undefined)
  node.value.data.settings.upper_limit = 90

if (node.value.data.settings.interval_lower === undefined)
  node.value.data.settings.interval_lower = 0

if (node.value.data.settings.interval_upper === undefined)
  node.value.data.settings.interval_upper = 90

if (node.value.data.settings.horizontal_separation_angle === undefined)
  node.value.data.settings.horizontal_separation_angle = 5

if (node.value.data.settings.tolerance === undefined)
  node.value.data.settings.tolerance = 0.1

const comparisonMethod = computed<ComparisonMethod | undefined>(
  () => node.value.data.settings?.comparison_method,
)

const elementCategory = computed<ElementCategory | undefined>(
  () => node.value.data.settings?.element_category,
)

const angleLabel = computed<string>(() =>
  elementCategory.value === '2d' ? 'α₁ or α₂' : 'α',
)
</script>

<template>
  <div class="flex flex-col gap-3 px-2">
    <div>
      <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
        Tilt of Components
      </div>
      <p class="mt-1 text-xs text-slate-500">
        Measure the tilt of building components relative to the horizontal plane and flag components outside the configured limits.
      </p>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">Element category</label>
      <UTooltip text="'2D' measures the two largest flat surfaces (walls & slabs). '1D' measures the longitudinal axis (columns & beams).">
        <select
          v-model="node.data.settings!.element_category"
          class="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800"
        >
          <option
            v-for="category in ELEMENT_CATEGORY_OPTIONS"
            :key="category.value"
            :value="category.value"
          >
            {{ category.label }}
          </option>
        </select>
      </UTooltip>
    </div>

    <div class="flex flex-col gap-1 rounded-lg border border-slate-200 bg-white p-2">
      <svg
        v-if="elementCategory === '2d'"
        viewBox="0 0 460 150"
        class="h-56 w-full"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Tilt diagram for walls and slabs: two walls shown. Left: parallel faces, alpha-1 equals alpha-2. Right: tapered wall thicker at the base, alpha-1 differs from alpha-2."
      >
        <line
          x1="12"
          y1="128"
          x2="450"
          y2="128"
          stroke="#94a3b8"
          stroke-width="1.5"
          stroke-dasharray="5 4"
        />
        <polygon
          points="44,128 64,38 88,38 68,128"
          fill="#e2e8f0"
          stroke="#cbd5e1"
          stroke-width="1.5"
        />
        <line
          x1="44"
          y1="128"
          x2="64"
          y2="38"
          stroke="#2563eb"
          stroke-width="4"
          stroke-linecap="round"
        />
        <line
          x1="68"
          y1="128"
          x2="88"
          y2="38"
          stroke="#2563eb"
          stroke-width="4"
          stroke-linecap="round"
        />
        <path
          d="M 57 128 A 13 13 0 0 0 46.8 115.3"
          fill="none"
          stroke="#64748b"
          stroke-width="1.5"
        />
        <text
          x="57.2"
          y="117.4"
          font-size="13"
          fill="#334155"
          font-family="sans-serif"
          font-style="italic"
          text-anchor="middle"
        >
          α₁
        </text>
        <path
          d="M 86 128 A 18 18 0 0 0 71.9 110.4"
          fill="none"
          stroke="#64748b"
          stroke-width="1.5"
        />
        <text
          x="86.3"
          y="113.3"
          font-size="13"
          fill="#334155"
          font-family="sans-serif"
          font-style="italic"
          text-anchor="middle"
        >
          α₂
        </text>
        <polygon
          points="253,128 270.5,38 295.5,38 297,128"
          fill="#e2e8f0"
          stroke="#cbd5e1"
          stroke-width="1.5"
        />
        <line
          x1="253"
          y1="128"
          x2="270.5"
          y2="38"
          stroke="#2563eb"
          stroke-width="4"
          stroke-linecap="round"
        />
        <line
          x1="297"
          y1="128"
          x2="295.5"
          y2="38"
          stroke="#2563eb"
          stroke-width="4"
          stroke-linecap="round"
        />
        <path
          d="M 266 128 A 13 13 0 0 0 255.4 115.2"
          fill="none"
          stroke="#64748b"
          stroke-width="1.5"
        />
        <text
          x="266"
          y="117.3"
          font-size="13"
          fill="#334155"
          font-family="sans-serif"
          font-style="italic"
          text-anchor="middle"
        >
          α₁
        </text>
        <path
          d="M 314 128 A 17 17 0 0 0 297.3 111"
          fill="none"
          stroke="#64748b"
          stroke-width="1.5"
        />
        <text
          x="312.8"
          y="112.5"
          font-size="13"
          fill="#334155"
          font-family="sans-serif"
          font-style="italic"
          text-anchor="middle"
        >
          α₂
        </text>
      </svg>

      <svg
        v-else
        viewBox="0 0 220 150"
        class="h-44 w-full"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Tilt diagram for columns and beams: longitudinal axis measured, alpha angle shown"
      >
        <line
          x1="18"
          y1="126"
          x2="205"
          y2="126"
          stroke="#94a3b8"
          stroke-width="1.5"
          stroke-dasharray="5 4"
        />
        <polygon
          points="92.2,124.3 112.2,32.3 127.8,35.7 107.8,127.7"
          fill="#e2e8f0"
          stroke="#cbd5e1"
          stroke-width="1.5"
        />
        <line
          x1="100"
          y1="126"
          x2="120"
          y2="34"
          stroke="#2563eb"
          stroke-width="4"
          stroke-linecap="round"
        />
        <path
          d="M 128 126 A 28 28 0 0 0 106 98.6"
          fill="none"
          stroke="#64748b"
          stroke-width="1.5"
        />
        <line
          x1="132"
          y1="113"
          x2="150"
          y2="116"
          stroke="#64748b"
          stroke-width="1"
        />
        <text
          x="152"
          y="119"
          font-size="12"
          fill="#334155"
          font-family="sans-serif"
          font-style="italic"
        >
          α
        </text>
      </svg>

      <p class="text-[10px] text-slate-400">
        {{ elementCategory === '2d'
          ? 'Blue = front & back surfaces (measured). Left: parallel faces, so α₁ ≈ α₂. Right: wall thicker at the base than at the top, so α₁ ≠ α₂.'
          : 'Blue = longitudinal axis (measured). α = tilt of the axis to the horizontal.' }}
      </p>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">Comparison method</label>
      <select
        v-model="node.data.settings!.comparison_method"
        class="w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800"
      >
        <option
          v-for="method in COMPARISON_METHOD_OPTIONS"
          :key="method.value"
          :value="method.value"
        >
          {{ method.label }}
        </option>
      </select>
    </div>

    <div class="flex flex-col gap-2 rounded-lg border border-slate-200 bg-white p-2">
      <template v-if="requiresLowerLimit(comparisonMethod)">
        <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">Lower limit (°)</label>
        <UTooltip :text="decimalTooltip" class="w-full">
          <input
            v-model.number="node.data.settings!.lower_limit"
            type="number"
            step="any"
            class="w-full rounded border border-slate-200 px-2 py-1 text-sm text-slate-800"
          >
        </UTooltip>
        <p class="text-[10px] text-slate-400">
          Flagged when the tilt of a surface ({{ angleLabel }}) exceeds this value.
        </p>
      </template>

      <template v-else-if="requiresUpperLimit(comparisonMethod)">
        <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">Upper limit (°)</label>
        <UTooltip :text="decimalTooltip" class="w-full">
          <input
            v-model.number="node.data.settings!.upper_limit"
            type="number"
            step="any"
            class="w-full rounded border border-slate-200 px-2 py-1 text-sm text-slate-800"
          >
        </UTooltip>
        <p class="text-[10px] text-slate-400">
          Flagged when the tilt of a surface ({{ angleLabel }}) is below this value.
        </p>
      </template>

      <template v-else-if="requiresInterval(comparisonMethod)">
        <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">Interval (°)</label>
        <div class="flex items-center gap-2">
          <UTooltip :text="decimalTooltip" class="w-full">
            <input
              v-model.number="node.data.settings!.interval_lower"
              type="number"
              step="any"
              placeholder="Lower"
              class="w-full rounded border border-slate-200 px-2 py-1 text-sm text-slate-800"
            >
          </UTooltip>
          <UTooltip :text="decimalTooltip" class="w-full">
            <input
              v-model.number="node.data.settings!.interval_upper"
              type="number"
              step="any"
              placeholder="Upper"
              class="w-full rounded border border-slate-200 px-2 py-1 text-sm text-slate-800"
            >
          </UTooltip>
        </div>
        <p v-if="comparisonMethod === 'inside_interval'" class="text-[10px] text-slate-400">
          Flagged when the tilt of a surface ({{ angleLabel }}) is inside the interval.
        </p>
        <p v-else class="text-[10px] text-slate-400">
          Flagged when the tilt of a surface ({{ angleLabel }}) is outside the interval.
        </p>
      </template>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">Horizontal separation angle (°)</label>
      <UTooltip :text="decimalTooltip" class="w-full">
        <input
          v-model.number="node.data.settings!.horizontal_separation_angle"
          type="number"
          step="any"
          class="w-full rounded border border-slate-200 px-2 py-1 text-sm text-slate-800"
        >
      </UTooltip>
      <p class="text-[10px] text-slate-400">
        Defines the maximum deviation of the horizontal angle (x,y-plane) between two surfaces to be considered as one surface.<br>
        Necessary for curved surfaces, since they are divided in small even surfaces.<br>
        Must be at least 1° to avoid rounding errors.
      </p>
    </div>

    <div class="flex flex-col gap-1 rounded-lg border border-slate-200 bg-white p-2">
      <svg
        viewBox="0 0 700 165"
        class="h-40 w-full"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Top view of a bent strip; the strip facets within the horizontal separation angle are merged into one surface"
      >
        <polyline
          points="40,150 125,110 280,90 420,90 575,110 660,150"
          fill="none"
          stroke="#222"
          stroke-width="3"
        />
        <polygon
          points="278,90 398,90 396,70 285,87"
          fill="#6f95c8"
          fill-opacity="0.5"
          stroke="#6f95c8"
          stroke-width="1"
        />
        <text
          x="420"
          y="78"
          font-size="26"
          font-weight="bold"
          fill="#2563eb"
          font-family="sans-serif"
        >
          S
        </text>
        <text
          x="20"
          y="26"
          font-size="15"
          fill="#475569"
          font-family="sans-serif"
        >
          Top view
        </text>
      </svg>
      <p class="text-[10px] text-slate-400">
        Facets within the horizontal angle of the bend are merged into one surface.
      </p>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">Tolerance (°)</label>
      <UTooltip :text="decimalTooltip" class="w-full">
        <input
          v-model.number="node.data.settings!.tolerance"
          type="number"
          step="any"
          class="w-full rounded border border-slate-200 px-2 py-1 text-sm text-slate-800"
        >
      </UTooltip>
    </div>
  </div>
</template>
