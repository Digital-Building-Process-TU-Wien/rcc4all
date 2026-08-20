<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import { useScopedNode } from '~/composables/useScopedNode'

interface JsonOutputData {
  result?: {
    value?: any
  }
}

type JsonOutputNode = Node<JsonOutputData>

const props = defineProps<{
  node: JsonOutputNode
}>()

const { t } = useI18n()

useScopedNode<JsonOutputNode>(props.node.id)
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
      {{ t('node.jsonOutput.title') }}
    </div>
    <p class="mt-1 text-xs text-slate-500">
      {{ t('node.jsonOutput.description') }}
    </p>
  </div>
</template>
