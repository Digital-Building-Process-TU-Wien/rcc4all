<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import type { NodeData, SupportedLocale } from '~/utils/nodes'
import { Comark } from '@comark/vue'
import InputBindingsSection from '~/components/nodes/InputBindingsSection.vue'
import { useScopedNode } from '~/composables/useScopedNode'
import { useFlowStore } from '~/stores/flow'
import { getAvailableNodes, getNodeComponent } from '~/utils/nodes'
import { getNodeSchema } from '~/utils/schema-helpers'

interface Props {
  isOpen: boolean
  nodeId: string
}
const props = defineProps<Props>()
const emit = defineEmits<{
  close: []
}>()

const { locale, t } = useI18n()
const store = useFlowStore()
const node = useScopedNode<Node<NodeData>>(props.nodeId)

watch(() => store.nodesById[props.nodeId], (exists) => {
  if (!exists) {
    emit('close')
  }
}, { immediate: true })

function handleDelete() {
  store.removeNode(props.nodeId)
}

const component = computed(() => {
  if (!node.value?.id)
    return null
  return getNodeComponent(node.value.data!.nodeName)
})

const nodeDocs = computed(() => {
  const availableNodes = getAvailableNodes(locale.value as SupportedLocale)
  return availableNodes.find(n => n.nodeName === node.value?.data?.nodeName)
})

const nodeName = computed(() => node.value?.data?.nodeName ?? '')

const modelFields = computed(() => {
  if (!nodeName.value) {
    return []
  }
  const settings = (getNodeSchema(nodeName.value as any) as any)?.properties?.settings?.properties
  if (!settings) {
    return []
  }
  return Object.keys(settings)
    .filter(key => key.startsWith('model_slug'))
    .map(key => ({
      key,
      label: key === 'model_slug_a'
        ? t('slideover.modelA')
        : key === 'model_slug_b'
          ? t('slideover.modelB')
          : t('slideover.model'),
    }))
})

const modelOptions = computed(() => store.files.map(file => ({
  label: store.getSlugLabel(file.slug),
  value: file.slug,
})))

function getModelValue(key: string): string {
  return (node.value?.data?.settings?.[key] as string) ?? 'main'
}

function setModelValue(key: string, value: string) {
  const scoped = node.value
  if (!scoped?.data) {
    return
  }
  scoped.data.settings = { ...scoped.data.settings, [key]: value }
}

function onModelChange(key: string, value: unknown) {
  setModelValue(key, typeof value === 'string' && value ? value : 'main')
}
</script>

<template>
  <USlideover
    :title="t('slideover.nodeDetails')"
    :description="t('slideover.description')"
    :ui="{ content: 'max-w-4xl' }"
    @close="emit('close')"
  >
    <template #body>
      <div class="flex flex-col h-full">
        <div class="flex-1 overflow-y-auto p-4 space-y-4">
          <template v-if="node && component">
            <div class="mb-4">
              <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">
                {{ t('slideover.nodeLabel') }}
              </label>
              <UInput
                v-model="node.data!.label"
                :placeholder="t('slideover.customLabelPlaceholder')"
                class="mt-1"
              />
              <p class="mt-1 text-xs text-muted">
                {{ t('slideover.labelHint') }}
              </p>
            </div>

            <div v-if="modelFields.length" class="mb-4 space-y-3">
              <div v-for="field in modelFields" :key="field.key">
                <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">
                  {{ field.label }}
                </label>
                <USelect
                  :model-value="getModelValue(field.key)"
                  :options="modelOptions"
                  class="mt-1"
                  @update:model-value="value => onModelChange(field.key, value)"
                />
                <p class="mt-1 text-xs text-muted">
                  {{ t('slideover.modelHint') }}
                </p>
              </div>
            </div>

            <component
              :is="component"
              :node="node"
            />

            <InputBindingsSection
              v-if="node.data!.nodeName !== 'FileInput'"
              :node-id="node.id"
              :node-name="node.data!.nodeName"
            />

            <div v-if="nodeDocs" class="mt-6 border-t border-default pt-4">
              <h3 class="text-sm font-semibold text-highlighted mb-2">
                {{ t('slideover.documentation') }}
              </h3>
              <p v-if="nodeDocs.description" class="text-sm text-muted mb-3">
                {{ nodeDocs.description }}
              </p>
              <Comark
                v-if="nodeDocs?.markdownDescription"
                class="mt-4 prose prose-sm dark:prose-invert max-w-none"
              >
                {{ nodeDocs.markdownDescription }}
              </Comark>
              <div v-else class="text-sm text-muted italic">
                {{ t('slideover.noDetailedDocs') }}
              </div>
            </div>
          </template>

          <div
            v-else-if="node"
            class="text-sm text-slate-500"
          >
            <p class="font-semibold mb-2">
              {{ node?.data?.label || t('slideover.unknownNode') }}
            </p>
            <p>{{ t('slideover.componentNotFound') }}: {{ node.data!.nodeName }}</p>
          </div>

          <div
            v-else
            class="text-sm text-slate-400"
          >
            {{ t('slideover.selectNode') }}
          </div>
        </div>

        <div class="border-t border-default p-4 bg-surface">
          <UButton
            color="error"
            variant="soft"
            block
            @click="handleDelete"
          >
            {{ t('slideover.deleteNode') }}
          </UButton>
        </div>
      </div>
    </template>
  </USlideover>
</template>
