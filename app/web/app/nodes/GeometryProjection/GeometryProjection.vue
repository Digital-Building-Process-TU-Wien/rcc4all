<script setup lang="ts">
import type { SchemaNodeType } from '~/schemas'
import { useScopedNode } from '~/composables/useScopedNode'

type GeometryProjectionNode = SchemaNodeType<'geometry_projection'>

interface Props {
  node: GeometryProjectionNode
}

const props = defineProps<Props>()

const node = useScopedNode<GeometryProjectionNode>(props.node.id)

const { t } = useI18n()

if (!node.value.data.settings) {
  node.value.data.settings = { projection_normal: [0.0, 0.0, 1.0] }
}

if (!node.value.data.settings.projection_normal) {
  node.value.data.settings.projection_normal = [0.0, 0.0, 1.0]
}

const projectionNormal = computed(() => node.value.data.settings?.projection_normal ?? [0, 0, 1])

function setPresetNormal(preset: [number, number, number]) {
  node.value.data.settings!.projection_normal = [...preset]
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      {{ t('node.geometryProjection.title') }}
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      {{ t('node.geometryProjection.description') }}
    </p>
  </div>

  <div class="flex flex-col gap-3 px-2 pb-2">
    <div class="flex flex-col gap-2">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.geometryProjection.projectionNormal') }}</label>
      <p class="text-xs text-slate-400">
        {{ t('node.geometryProjection.projectionNormalHelp') }}
      </p>

      <div class="flex gap-2 mb-2">
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="projectionNormal[0] === 0 && projectionNormal[1] === 0 && projectionNormal[2] === 1 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetNormal([0, 0, 1])"
        >
          {{ t('node.geometryProjection.presetXyPlane') }}
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="projectionNormal[0] === 1 && projectionNormal[1] === 0 && projectionNormal[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetNormal([1, 0, 0])"
        >
          {{ t('node.geometryProjection.presetYzPlane') }}
        </button>
        <button
          class="flex-1 px-2 py-1 text-xs bg-slate-100 hover:bg-slate-200 border border-slate-300 rounded transition-colors"
          :class="projectionNormal[0] === 0 && projectionNormal[1] === 1 && projectionNormal[2] === 0 ? 'bg-blue-100 border-blue-400' : ''"
          @click="setPresetNormal([0, 1, 0])"
        >
          {{ t('node.geometryProjection.presetXzPlane') }}
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
  </div>
</template>
