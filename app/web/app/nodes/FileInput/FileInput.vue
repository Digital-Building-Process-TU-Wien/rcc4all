<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'
import { useFlowStore } from '~/stores/flow'

type FileInputNode = SchemaNodeType<'file_input'>

interface Props {
  node: FileInputNode
}

const props = defineProps<Props>()

const { t } = useI18n()
const store = useFlowStore()

const node = useScopedNode<FileInputNode>(props.node.id)

const modelOptions = computed(() => store.files.map(file => ({
  label: file.slug === 'main' ? t('library.modelMain') : file.slug,
  value: file.slug,
})))

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
