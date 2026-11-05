<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type OpeningSurfaceIfcGeneratorNode = SchemaNodeType<'opening_surface_ifc_generator'>

interface Props {
  node: OpeningSurfaceIfcGeneratorNode
}

const props = defineProps<Props>()

const node = useScopedNode<OpeningSurfaceIfcGeneratorNode>(props.node.id)
const { t } = useI18n()

if (!node.value.data.settings) {
  node.value.data.settings = { output_filename: 'opening_surface_model.ifc' }
}

const result = computed(() => node.value.data.result)
const elementCount = computed(() => result.value?.element_count)
const storeyCount = computed(() => result.value?.storey_count)
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="px-2">
      <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
        {{ t('node.openingSurfaceIfcGenerator.title') }}
      </div>
      <p class="mt-1 text-xs text-slate-500">
        {{ t('node.openingSurfaceIfcGenerator.description') }}
      </p>
    </div>

    <div class="px-2 flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.openingSurfaceIfcGenerator.outputFilename') }}
      </label>
      <input
        v-model="node.data.settings!.output_filename"
        :placeholder="t('node.openingSurfaceIfcGenerator.outputFilenamePlaceholder')"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
    </div>

    <div class="px-2 pb-2 flex flex-col gap-1 border-t border-slate-200 pt-3">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.openingSurfaceIfcGenerator.resultOutput') }}
      </label>
      <div v-if="elementCount === undefined" class="text-xs text-slate-400">
        {{ t('node.openingSurfaceIfcGenerator.noOutputYet') }}
      </div>
      <div v-else class="flex flex-col gap-1">
        <div class="rounded-full bg-green-50 px-2 py-1 text-xs font-medium text-green-700 w-fit">
          {{ t('node.openingSurfaceIfcGenerator.elementCount', { count: elementCount }) }}
        </div>
        <div class="text-xs text-slate-500">
          {{ t('node.openingSurfaceIfcGenerator.storeyCount', { count: storeyCount ?? 0 }) }}
        </div>
        <div class="text-xs text-slate-400 break-all">
          {{ result?.output_path }}
        </div>
      </div>
    </div>
  </div>
</template>
