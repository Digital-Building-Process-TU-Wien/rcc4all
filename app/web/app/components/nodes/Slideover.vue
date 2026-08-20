<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import type { NodeData, SupportedLocale } from '~/utils/nodes'
import { Comark } from '@comark/vue'
import InputBindingsSection from '~/components/nodes/InputBindingsSection.vue'
import { useScopedNode } from '~/composables/useScopedNode'
import { useFlowStore } from '~/stores/flow'
import { getAvailableNodes, getNodeComponent } from '~/utils/nodes'

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
