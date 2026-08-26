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
  node.value.data.settings = { measurement_type: 'volume', projection_normal: [0.0, 0.0, 1.0], direction: [0.0, 0.0, 1.0] }
}

if (!node.value.data.settings.projection_normal) {
  node.value.data.settings.projection_normal = [0.0, 0.0, 1.0]
}

if (!node.value.data.settings.direction) {
  node.value.data.settings.direction = [0.0, 0.0, 1.0]
}

const measurementTypes = [
  { value: 'volume', label: 'Volume' },
  { value: 'surface_area', label: 'Surface Area' },
  { value: 'projected_area', label: 'Projected Area' },
  { value: 'component_height', label: 'Component Height' },
  { value: 'distance_between', label: 'Minimum Distance Between Elements' },
  { value: 'distance_to_reference', label: 'Distance to Reference (coming soon)' },
]

function setPresetNormal(preset: [number, number, number]) {
  node.value.data.settings!.projection_normal = [...preset]
}

function setPresetDirection(preset: [number, number, number]) {
  node.value.data.settings!.direction = [...preset]
}

const hasListBWarning = computed(() => {
  return node.value.data.settings?.measurement_type !== 'distance_between'
    && node.value.data.input_bindings?.list_b
})
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      Measurement
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      Compute geometric measurements (volume, surface area, projected area, component height, minimum distance between elements) of IFC elements or cached geometries.
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
        In v3, volume, surface area, projected area, component height, and minimum distance between elements (List A × List B pattern) are implemented. Other modes will raise an error at runtime.
      </p>
      <div v-if="hasListBWarning" class="mt-2 flex items-start gap-1 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
        <Icon name="i-lucide-triangle-alert" class="size-3 flex-shrink-0 mt-0.5" />
        <span>List B is only used for "Minimum Distance Between Elements" mode and will be ignored.</span>
      </div>
    </div>

    <div v-if="node.data.settings!.measurement_type === 'projected_area'" class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Projection Normal</label>
      <p class="text-xs text-slate-400">
        Normal vector for the projection plane. Default [0,0,1] computes footprint (top-down view).
      </p>

      <div class="flex gap-2 mb-2">
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="node.data.settings!.projection_normal[0] === 0 && node.data.settings!.projection_normal[1] === 0 && node.data.settings!.projection_normal[2] === 1 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetNormal([0, 0, 1])"
        >
          XY Plane (Z)
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="node.data.settings!.projection_normal[0] === 1 && node.data.settings!.projection_normal[1] === 0 && node.data.settings!.projection_normal[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetNormal([1, 0, 0])"
        >
          YZ Plane (X)
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="node.data.settings!.projection_normal[0] === 0 && node.data.settings!.projection_normal[1] === 1 && node.data.settings!.projection_normal[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetNormal([0, 1, 0])"
        >
          XZ Plane (Y)
        </button>
      </div>

      <div class="grid grid-cols-3 gap-2">
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">X</label>
          <input
            v-model.number="node.data.settings!.projection_normal[0]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">Y</label>
          <input
            v-model.number="node.data.settings!.projection_normal[1]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">Z</label>
          <input
            v-model.number="node.data.settings!.projection_normal[2]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
      </div>
    </div>

    <div v-if="node.data.settings!.measurement_type === 'component_height'" class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Direction</label>
      <p class="text-xs text-slate-400">
        Direction vector for extent computation. Default [0,0,1] computes vertical height.
      </p>

      <div class="flex gap-2 mb-2">
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="node.data.settings!.direction[0] === 0 && node.data.settings!.direction[1] === 0 && node.data.settings!.direction[2] === 1 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetDirection([0, 0, 1])"
        >
          Z Axis (Height)
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="node.data.settings!.direction[0] === 1 && node.data.settings!.direction[1] === 0 && node.data.settings!.direction[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetDirection([1, 0, 0])"
        >
          X Axis
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="node.data.settings!.direction[0] === 0 && node.data.settings!.direction[1] === 1 && node.data.settings!.direction[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetDirection([0, 1, 0])"
        >
          Y Axis
        </button>
      </div>

      <div class="grid grid-cols-3 gap-2">
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">X</label>
          <input
            v-model.number="node.data.settings!.direction[0]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">Y</label>
          <input
            v-model.number="node.data.settings!.direction[1]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">Z</label>
          <input
            v-model.number="node.data.settings!.direction[2]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
      </div>
    </div>
  </div>
</template>
