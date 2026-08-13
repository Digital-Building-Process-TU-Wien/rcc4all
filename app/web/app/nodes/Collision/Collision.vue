<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type CollisionNode = SchemaNodeType<'collision'>

interface Props {
  node: CollisionNode
}

const props = defineProps<Props>()

const node = useScopedNode<CollisionNode>(props.node.id)

if (!node.value.data.settings) {
  node.value.data.settings = { mode: 'boolean' }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      Collision
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      Clash detection between cached geometries. Tests every A reference against every B reference (cartesian product). Bind list_a / list_b from upstream nodes; an unbound side falls back to the whole model.
    </p>
  </div>

  <div class="flex flex-col gap-3 px-2 pb-2">
    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Mode</label>
      <select
        v-model="node.data.settings!.mode"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
        <option value="boolean">
          Boolean (report collisions only)
        </option>
        <option value="intersection_mesh">
          Intersection mesh (store overlap geometry)
        </option>
      </select>
      <p class="text-xs text-slate-400">
        Boolean reports which pairs collide. Intersection mesh additionally caches each overlap under a deterministic key.
      </p>
    </div>
  </div>
</template>
