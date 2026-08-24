<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type MeasurementNode = SchemaNodeType<'measurement'>

interface Props {
  node: MeasurementNode
}

const props = defineProps<Props>()

const node = useScopedNode<MeasurementNode>(props.node.id)

if (!node.value.data.settings) {
  node.value.data.settings = { measurement_type: 'volume' }
}

const measurementTypes = [
  { value: 'volume', label: 'Volume' },
  { value: 'surface_area', label: 'Surface Area' },
  { value: 'projected_area', label: 'Projected Area (coming soon)' },
  { value: 'component_height', label: 'Component Height (coming soon)' },
  { value: 'distance_between', label: 'Distance Between (coming soon)' },
  { value: 'distance_to_reference', label: 'Distance to Reference (coming soon)' },
]
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      Measurement
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      Compute geometric measurements (volume, surface area) of IFC elements or cached geometries.
    </p>
  </div>

  <div class="flex flex-col gap-3 px-2 pb-2">
    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Measurement Type</label>
      <select
        v-model="node.data.settings!.measurement_type"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
        <option
          v-for="type in measurementTypes"
          :key="type.value"
          :value="type.value"
        >
          {{ type.label }}
        </option>
      </select>
      <p class="text-xs text-slate-400">
        In v1, only volume and surface area are implemented. Other modes will raise an error at runtime.
      </p>
    </div>
  </div>
</template>
