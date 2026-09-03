<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type MeasurementNode = SchemaNodeType<'measurement'>

interface Props {
  node: MeasurementNode
}

const props = defineProps<Props>()

const node = useScopedNode<MeasurementNode>(props.node.id)

const { t } = useI18n()

if (!node.value.data.settings) {
  node.value.data.settings = { measurement_type: 'volume', projection_normal: [0.0, 0.0, 1.0], direction: [0.0, 0.0, 1.0], reference_type: 'point', reference_point: [0.0, 0.0, 0.0], reference_normal: [0.0, 0.0, 1.0] }
}

if (!node.value.data.settings.projection_normal) {
  node.value.data.settings.projection_normal = [0.0, 0.0, 1.0]
}

if (!node.value.data.settings.direction) {
  node.value.data.settings.direction = [0.0, 0.0, 1.0]
}

if (!node.value.data.settings.reference_type) {
  node.value.data.settings.reference_type = 'point'
}

if (!node.value.data.settings.reference_point) {
  node.value.data.settings.reference_point = [0.0, 0.0, 0.0]
}

if (!node.value.data.settings.reference_normal) {
  node.value.data.settings.reference_normal = [0.0, 0.0, 1.0]
}

const measurementTypes = [
  { value: 'volume', labelKey: 'node.measurement.typeVolume' },
  { value: 'surface_area', labelKey: 'node.measurement.typeSurfaceArea' },
  { value: 'projected_area', labelKey: 'node.measurement.typeProjectedArea' },
  { value: 'component_height', labelKey: 'node.measurement.typeComponentHeight' },
  { value: 'distance_between', labelKey: 'node.measurement.typeDistanceBetween' },
  { value: 'distance_to_reference', labelKey: 'node.measurement.typeDistanceToReference' },
]

function setPresetNormal(preset: [number, number, number]) {
  node.value.data.settings!.projection_normal = [...preset]
}

function setPresetDirection(preset: [number, number, number]) {
  node.value.data.settings!.direction = [...preset]
}

function setPresetReferenceNormal(preset: [number, number, number]) {
  node.value.data.settings!.reference_normal = [...preset]
}

const hasListBWarning = computed(() => {
  return node.value.data.settings?.measurement_type !== 'distance_between'
    && (node.value.data as any).input_bindings?.list_b
})

const projectionNormal = computed(() => node.value.data.settings?.projection_normal ?? [0, 0, 1])
const direction = computed(() => node.value.data.settings?.direction ?? [0, 0, 1])
const referencePoint = computed(() => node.value.data.settings?.reference_point ?? [0, 0, 0])
const referenceNormal = computed(() => node.value.data.settings?.reference_normal ?? [0, 0, 1])
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      {{ t('node.measurement.title') }}
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      {{ t('node.measurement.description') }}
    </p>
  </div>

  <div class="flex flex-col gap-3 px-2 pb-2">
    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.measurement.measurementType') }}</label>
      <select
        v-model="node.data.settings!.measurement_type"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
        <option
          v-for="type in measurementTypes"
          :key="type.value"
          :value="type.value"
        >
          {{ t(type.labelKey) }}
        </option>
      </select>
      <p class="text-xs text-slate-400">
        {{ t('node.measurement.measurementTypeHelp') }}
      </p>
      <div v-if="hasListBWarning" class="mt-2 flex items-start gap-1 text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-2 py-1">
        <Icon name="i-lucide-triangle-alert" class="size-3 flex-shrink-0 mt-0.5" />
        <span>{{ t('node.measurement.listBWarning') }}</span>
      </div>
    </div>

    <div v-if="node.data.settings!.measurement_type === 'projected_area'" class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.measurement.projectionNormal') }}</label>
      <p class="text-xs text-slate-400">
        {{ t('node.measurement.projectionNormalHelp') }}
      </p>

      <div class="flex gap-2 mb-2">
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="projectionNormal[0] === 0 && projectionNormal[1] === 0 && projectionNormal[2] === 1 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetNormal([0, 0, 1])"
        >
          {{ t('node.measurement.presetXyPlane') }}
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="projectionNormal[0] === 1 && projectionNormal[1] === 0 && projectionNormal[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetNormal([1, 0, 0])"
        >
          {{ t('node.measurement.presetYzPlane') }}
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="projectionNormal[0] === 0 && projectionNormal[1] === 1 && projectionNormal[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetNormal([0, 1, 0])"
        >
          {{ t('node.measurement.presetXzPlane') }}
        </button>
      </div>

      <div class="grid grid-cols-3 gap-2">
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">X</label>
          <input
            v-model.number="projectionNormal[0]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">Y</label>
          <input
            v-model.number="projectionNormal[1]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">Z</label>
          <input
            v-model.number="projectionNormal[2]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
      </div>
    </div>

    <div v-if="node.data.settings!.measurement_type === 'component_height'" class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.measurement.direction') }}</label>
      <p class="text-xs text-slate-400">
        {{ t('node.measurement.directionHelp') }}
      </p>

      <div class="flex gap-2 mb-2">
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="direction[0] === 0 && direction[1] === 0 && direction[2] === 1 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetDirection([0, 0, 1])"
        >
          {{ t('node.measurement.presetZAxis') }}
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="direction[0] === 1 && direction[1] === 0 && direction[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetDirection([1, 0, 0])"
        >
          {{ t('node.measurement.presetXAxis') }}
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="direction[0] === 0 && direction[1] === 1 && direction[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetDirection([0, 1, 0])"
        >
          {{ t('node.measurement.presetYAxis') }}
        </button>
      </div>

      <div class="grid grid-cols-3 gap-2">
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">X</label>
          <input
            v-model.number="direction[0]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">Y</label>
          <input
            v-model.number="direction[1]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
        <div class="flex flex-col gap-1">
          <label class="text-[9px] text-slate-400 font-medium uppercase">Z</label>
          <input
            v-model.number="direction[2]"
            type="number"
            step="0.1"
            class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          >
        </div>
      </div>
    </div>

    <div v-if="node.data.settings!.measurement_type === 'distance_to_reference'" class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.measurement.referenceType') }}</label>
      <p class="text-xs text-slate-400">
        {{ t('node.measurement.referenceTypeHelp') }}
      </p>

      <select
        v-model="node.data.settings!.reference_type"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
        <option value="point">
          {{ t('node.measurement.referenceTypePoint') }}
        </option>
        <option value="plane">
          {{ t('node.measurement.referenceTypePlane') }}
        </option>
      </select>

      <div class="flex flex-col gap-2 mt-2">
        <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.measurement.referencePoint') }}</label>
        <p class="text-xs text-slate-400">
          {{ t('node.measurement.referencePointHelp') }}
        </p>

        <div class="grid grid-cols-3 gap-2">
          <div class="flex flex-col gap-1">
            <label class="text-[9px] text-slate-400 font-medium uppercase">X</label>
            <input
              v-model.number="referencePoint[0]"
              type="number"
              step="0.1"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
            >
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-[9px] text-slate-400 font-medium uppercase">Y</label>
            <input
              v-model.number="referencePoint[1]"
              type="number"
              step="0.1"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
            >
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-[9px] text-slate-400 font-medium uppercase">Z</label>
            <input
              v-model.number="referencePoint[2]"
              type="number"
              step="0.1"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
            >
          </div>
        </div>
      </div>

      <div v-if="node.data.settings!.reference_type === 'plane'" class="flex flex-col gap-2 mt-2">
        <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.measurement.planeNormal') }}</label>
        <p class="text-xs text-slate-400">
          {{ t('node.measurement.planeNormalHelp') }}
        </p>

        <div class="flex gap-2 mb-2">
          <button
            class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
            :class="referenceNormal[0] === 0 && referenceNormal[1] === 0 && referenceNormal[2] === 1 ? 'bg-blue-100 border-blue-400' : ''"
            @click="setPresetReferenceNormal([0, 0, 1])"
          >
            {{ t('node.measurement.presetXyPlane') }}
          </button>
          <button
            class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
            :class="referenceNormal[0] === 1 && referenceNormal[1] === 0 && referenceNormal[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
            @click="setPresetReferenceNormal([1, 0, 0])"
          >
            {{ t('node.measurement.presetYzPlane') }}
          </button>
          <button
            class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
            :class="referenceNormal[0] === 0 && referenceNormal[1] === 1 && referenceNormal[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
            @click="setPresetReferenceNormal([0, 1, 0])"
          >
            {{ t('node.measurement.presetXzPlane') }}
          </button>
        </div>

        <div class="grid grid-cols-3 gap-2">
          <div class="flex flex-col gap-1">
            <label class="text-[9px] text-slate-400 font-medium uppercase">X</label>
            <input
              v-model.number="referenceNormal[0]"
              type="number"
              step="0.1"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
            >
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-[9px] text-slate-400 font-medium uppercase">Y</label>
            <input
              v-model.number="referenceNormal[1]"
              type="number"
              step="0.1"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
            >
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-[9px] text-slate-400 font-medium uppercase">Z</label>
            <input
              v-model.number="referenceNormal[2]"
              type="number"
              step="0.1"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
            >
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
