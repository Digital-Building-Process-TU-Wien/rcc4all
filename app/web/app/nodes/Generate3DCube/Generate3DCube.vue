<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type Generate3DCubeNode = SchemaNodeType<'generate_3d_cube'>

interface Props {
  node: Generate3DCubeNode
}

const props = defineProps<Props>()

const node = useScopedNode<Generate3DCubeNode>(props.node.id)

if (!node.value.data.settings) {
  node.value.data.settings = {
    position: [0.0, 0.0, 0.0],
    rotation: [0.0, 0.0, 0.0],
    size: [1.0, 1.0, 1.0],
    object_id: 'cube',
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
      Generate 3D Cube
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      Creates a cuboid geometry in the cache under a unique object_id, for use in a collision node.
    </p>
  </div>

  <div class="flex flex-col gap-3 px-2 pb-2">
    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Position (X, Y, Z)</label>
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
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Rotation (X°, Y°, Z°)</label>
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
    </div>

    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Size (W, H, D)</label>
      <div class="grid grid-cols-3 gap-1">
        <input
          type="number"
          step="0.1"
          min="0.1"
          :value="node.data.settings?.size?.[0]"
          placeholder="W"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          @input="(e) => updateArrayValue(node.data.settings!.size, 0, (e.target as HTMLInputElement).value)"
        >
        <input
          type="number"
          step="0.1"
          min="0.1"
          :value="node.data.settings?.size?.[1]"
          placeholder="H"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          @input="(e) => updateArrayValue(node.data.settings!.size, 1, (e.target as HTMLInputElement).value)"
        >
        <input
          type="number"
          step="0.1"
          min="0.1"
          :value="node.data.settings?.size?.[2]"
          placeholder="D"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
          @input="(e) => updateArrayValue(node.data.settings!.size, 2, (e.target as HTMLInputElement).value)"
        >
      </div>
    </div>

    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Object ID</label>
      <input
        type="text"
        :value="node.data.settings?.object_id"
        placeholder="unique object id"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
        @input="node.data.settings!.object_id = (($event.target) as HTMLInputElement).value"
      >
      <p class="text-xs text-slate-400">
        Unique reference for the cube. Feed its object_ids output into a collision node.
      </p>
    </div>

    <div class="border-t border-slate-200 pt-3 flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Object IDs (output)</label>
      <div v-if="!node.data.result?.object_ids?.length" class="text-xs text-slate-400">
        No output yet. Run the workflow.
      </div>
      <div
        v-for="objectId in node.data.result?.object_ids"
        :key="objectId"
        class="rounded-full bg-green-50 px-2 py-1 text-xs font-medium text-green-700 w-fit"
      >
        {{ objectId }}
      </div>
    </div>
  </div>
</template>
