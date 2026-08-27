<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type CollisionNode = SchemaNodeType<'collision'>

interface Props {
  node: CollisionNode
}

const props = defineProps<Props>()

const node = useScopedNode<CollisionNode>(props.node.id)

const { t } = useI18n()

if (!node.value.data.settings) {
  node.value.data.settings = { mode: 'boolean' }
}
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      {{ t('node.collision.title') }}
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      {{ t('node.collision.description') }}
    </p>
  </div>

  <div class="flex flex-col gap-3 px-2 pb-2">
    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.collision.mode') }}</label>
      <select
        v-model="node.data.settings!.mode"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
        <option value="boolean">
          {{ t('node.collision.modeBoolean') }}
        </option>
        <option value="intersection_mesh">
          {{ t('node.collision.modeIntersectionMesh') }}
        </option>
      </select>
      <p class="text-xs text-slate-400">
        {{ t('node.collision.modeHelp') }}
      </p>
    </div>
  </div>
</template>
