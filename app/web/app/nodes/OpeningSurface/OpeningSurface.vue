<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type OpeningSurfaceNode = SchemaNodeType<'opening_surface'>

interface Props {
  node: OpeningSurfaceNode
}

const props = defineProps<Props>()

const node = useScopedNode<OpeningSurfaceNode>(props.node.id)

const { t } = useI18n()

const openingCount = computed(() => node.value.data.result?.opening_count)
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      {{ t('node.openingSurface.title') }}
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      {{ t('node.openingSurface.description') }}
    </p>
    <p class="text-xs text-slate-400">
      {{ t('node.openingSurface.bindHint') }}
    </p>
  </div>

  <div class="flex flex-col gap-3 px-2 pb-2">
    <div class="border-t border-slate-200 pt-3 flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">{{ t('node.openingSurface.openingsOutput') }}</label>
      <div v-if="openingCount === undefined" class="text-xs text-slate-400">
        {{ t('node.openingSurface.noOutputYet') }}
      </div>
      <div
        v-else
        class="rounded-full bg-green-50 px-2 py-1 text-xs font-medium text-green-700 w-fit"
      >
        {{ t('node.openingSurface.openingCount', { count: openingCount }) }}
      </div>
    </div>
  </div>
</template>
