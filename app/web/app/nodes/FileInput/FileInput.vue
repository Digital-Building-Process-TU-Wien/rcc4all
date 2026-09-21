<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import { useScopedNode } from '~/composables/useScopedNode'
import { useFlowStore } from '~/stores/flow'

// File Input node. Its sidebar lists the IFC models assigned in the editor's
// top-bar model manager and lets the user pick which one this node refers to.
// The node outputs that model's slug (`model_slug`), which is wired to a
// consumer's model input (see the Slideover input bindings). Consumers fall
// back to the reserved `main` model when nothing is connected.
interface FileInputData {
  label?: string
  settings?: {
    slug?: string
  }
}

type FileInputNode = Node<FileInputData>

const props = defineProps<{
  node: FileInputNode
}>()

const { t } = useI18n()
const store = useFlowStore()

const node = useScopedNode<FileInputNode>(props.node.id)

const modelOptions = computed(() => store.files.map(file => ({
  label: file.slug === 'main' ? t('library.modelMain') : file.slug,
  value: file.slug,
})))

if (!node.value.data) {
  node.value.data = { label: '', settings: { slug: 'main' } }
}
if (!node.value.data.settings) {
  node.value.data.settings = { slug: 'main' }
}

function selectModel(value: unknown) {
  if (node.value.data) {
    node.value.data.settings = {
      ...node.value.data.settings,
      slug: (typeof value === 'string' && value) ? value : 'main',
    }
  }
}
</script>

<template>
  <div class="flex flex-col gap-2">
    <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">
      {{ t('node.fileInput.title') }}
    </label>
    <USelect
      :model-value="node.data?.settings?.slug ?? 'main'"
      :items="modelOptions"
      :placeholder="t('node.fileInput.selectModel')"
      @update:model-value="selectModel"
    />
  </div>
</template>
