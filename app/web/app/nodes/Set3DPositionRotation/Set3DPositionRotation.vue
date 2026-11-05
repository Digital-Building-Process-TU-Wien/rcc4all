<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type Set3DPositionRotationNode = SchemaNodeType<'set_3d_position_rotation'>

interface Props {
  node: Set3DPositionRotationNode
}

const props = defineProps<Props>()

const node = useScopedNode<Set3DPositionRotationNode>(props.node.id)

const { t } = useI18n()

if (!node.value.data.settings) {
  node.value.data.settings = {
    position: [0.0, 0.0, 0.0],
    rotation: [0.0, 0.0, 0.0],
  }
}

function updateArrayValue(
  array: number[] | undefined,
  index: number,
  value: string,
) {
  if (!array)
    return
  const parsed = Number.parseFloat(value)
  if (!Number.isNaN(parsed)) {
    array[index] = parsed
  }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      {{ t('node.set3DPositionRotation.title') }}
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      {{ t('node.set3DPositionRotation.description') }}
    </p>
  </div>

  <div class="flex flex-col gap-3 px-2 pb-2">
    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.set3DPositionRotation.position') }}</label>
      <div class="grid grid-cols-3 gap-1">
        <input
          type="number"
          step="0.1"
          :value="node.data.settings?.position?.[0]"
          placeholder="X"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          @input="(e) => updateArrayValue(node.data.settings!.position, 0, (e.target as HTMLInputElement).value)"
        >
        <input
          type="number"
          step="0.1"
          :value="node.data.settings?.position?.[1]"
          placeholder="Y"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          @input="(e) => updateArrayValue(node.data.settings!.position, 1, (e.target as HTMLInputElement).value)"
        >
        <input
          type="number"
          step="0.1"
          :value="node.data.settings?.position?.[2]"
          placeholder="Z"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          @input="(e) => updateArrayValue(node.data.settings!.position, 2, (e.target as HTMLInputElement).value)"
        >
      </div>
    </div>

    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.set3DPositionRotation.rotation') }}</label>
      <div class="grid grid-cols-3 gap-1">
        <input
          type="number"
          step="1"
          :value="node.data.settings?.rotation?.[0]"
          placeholder="X°"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          @input="(e) => updateArrayValue(node.data.settings!.rotation, 0, (e.target as HTMLInputElement).value)"
        >
        <input
          type="number"
          step="1"
          :value="node.data.settings?.rotation?.[1]"
          placeholder="Y°"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          @input="(e) => updateArrayValue(node.data.settings!.rotation, 1, (e.target as HTMLInputElement).value)"
        >
        <input
          type="number"
          step="1"
          :value="node.data.settings?.rotation?.[2]"
          placeholder="Z°"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          @input="(e) => updateArrayValue(node.data.settings!.rotation, 2, (e.target as HTMLInputElement).value)"
        >
      </div>
      <p class="text-xs text-slate-400">
        {{ t('node.set3DPositionRotation.rotationHint') }}
      </p>
    </div>

    <div class="border-t border-slate-200 pt-3 flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.set3DPositionRotation.outputPosition') }}</label>
      <div v-if="!node.data.result?.elements?.length" class="text-xs text-slate-400">
        {{ t('node.set3DPositionRotation.noOutputYet') }}
      </div>
      <div
        v-for="(element, index) in node.data.result?.elements"
        :key="index"
        class="flex flex-col gap-2"
      >
        <div class="rounded-md bg-slate-50 px-3 py-2 text-xs">
          <div class="font-medium text-slate-700 mb-1">
            {{ t('node.set3DPositionRotation.position') }}
          </div>
          <div class="text-slate-600 font-mono">
            [{{ element.position?.[0]?.toFixed(3) ?? '0.000' }}, {{ element.position?.[1]?.toFixed(3) ?? '0.000' }}, {{ element.position?.[2]?.toFixed(3) ?? '0.000' }}]
          </div>
        </div>
        <div class="rounded-md bg-slate-50 px-3 py-2 text-xs">
          <div class="font-medium text-slate-700 mb-1">
            {{ t('node.set3DPositionRotation.rotation') }}
          </div>
          <div class="text-slate-600 font-mono">
            [{{ element.rotation?.rotation_x?.toFixed(1) ?? '0.0' }}°, {{ element.rotation?.rotation_y?.toFixed(1) ?? '0.0' }}°, {{ element.rotation?.rotation_z?.toFixed(1) ?? '0.0' }}°]
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
