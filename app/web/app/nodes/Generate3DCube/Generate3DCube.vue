<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import type { NodeData } from '~/utils/nodes'

defineProps<{
  node: NodeProps<NodeData>
}>()

const outputs = ['vertices', 'faces']

const inputs = reactive({
  position: [0.0, 0.0, 0.0],
  rotation: [0.0, 0.0, 0.0],
  size: [1.0, 1.0, 1.0],
})

function updateArrayValue(
  array: number[],
  index: number,
  value: string,
) {
  const parsed = Number.parseFloat(value)
  if (!Number.isNaN(parsed)) {
    array[index] = parsed
  }
}
</script>

<template>
  <NodesNodeWrapper :inputs="outputs" :outputs="outputs">
    <div class="px-2">
      <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
        Generate 3D Cube
      </div>
    </div>

    <template #settings>
      <div class="flex flex-col gap-3">
        <div class="flex flex-col gap-1">
          <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Position (X, Y, Z)</label>
          <div class="grid grid-cols-3 gap-1">
            <input
              type="number"
              step="0.1"
              :value="inputs.position[0]"
              placeholder="X"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
              @input="(e) => updateArrayValue(inputs.position, 0, (e.target as HTMLInputElement).value)"
            >
            <input
              type="number"
              step="0.1"
              :value="inputs.position[1]"
              placeholder="Y"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
              @input="(e) => updateArrayValue(inputs.position, 1, (e.target as HTMLInputElement).value)"
            >
            <input
              type="number"
              step="0.1"
              :value="inputs.position[2]"
              placeholder="Z"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
              @input="(e) => updateArrayValue(inputs.position, 2, (e.target as HTMLInputElement).value)"
            >
          </div>
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Rotation (X°, Y°, Z°)</label>
          <div class="grid grid-cols-3 gap-1">
            <input
              type="number"
              step="1"
              :value="inputs.rotation[0]"
              placeholder="X°"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
              @input="(e) => updateArrayValue(inputs.rotation, 0, (e.target as HTMLInputElement).value)"
            >
            <input
              type="number"
              step="1"
              :value="inputs.rotation[1]"
              placeholder="Y°"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
              @input="(e) => updateArrayValue(inputs.rotation, 1, (e.target as HTMLInputElement).value)"
            >
            <input
              type="number"
              step="1"
              :value="inputs.rotation[2]"
              placeholder="Z°"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
              @input="(e) => updateArrayValue(inputs.rotation, 2, (e.target as HTMLInputElement).value)"
            >
          </div>
        </div>

        <div class="flex flex-col gap-1">
          <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Size (W, H, D)</label>
          <div class="grid grid-cols-3 gap-1">
            <input
              type="number"
              step="0.1"
              min="0.1"
              :value="inputs.size[0]"
              placeholder="W"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
              @input="(e) => updateArrayValue(inputs.size, 0, (e.target as HTMLInputElement).value)"
            >
            <input
              type="number"
              step="0.1"
              min="0.1"
              :value="inputs.size[1]"
              placeholder="H"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
              @input="(e) => updateArrayValue(inputs.size, 1, (e.target as HTMLInputElement).value)"
            >
            <input
              type="number"
              step="0.1"
              min="0.1"
              :value="inputs.size[2]"
              placeholder="D"
              class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
              @input="(e) => updateArrayValue(inputs.size, 2, (e.target as HTMLInputElement).value)"
            >
          </div>
        </div>
      </div>
    </template>
  </NodesNodeWrapper>
</template>
