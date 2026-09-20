<script setup lang="ts">
import type { AvailableNode, SupportedLocale } from '~/utils/nodes'
import { useFlowStore } from '~/stores/flow'
import { getAvailableNodes } from '~/utils/nodes'

withDefaults(defineProps<Props>(), {
  isRunning: false,
})

const emit = defineEmits<{
  addNode: [node: AvailableNode]
  runWorkflow: []
  clearCanvas: []
}>()

const MODEL_SLUG_RE = /^[a-z0-9][a-z0-9-_]*$/

interface Props {
  hasNodes: boolean
  nodeCount: number
  isRunning?: boolean
}

const { locale, t } = useI18n()

const store = useFlowStore()

const { data: devFilesData } = useFetch('/api/dev-files', {
  default: () => ({ files: [] }),
  lazy: true,
  server: false,
})

const newModelSlug = ref('')
const newModelFile = ref('')
const modelError = ref('')

const modelFileOptions = computed(() => (devFilesData.value?.files ?? []).map(
  file => ({ label: file, value: file }),
))

function addModel() {
  const slug = newModelSlug.value.trim()
  modelError.value = ''
  if (!MODEL_SLUG_RE.test(slug)) {
    modelError.value = t('library.invalidModelSlug')
    return
  }
  if (slug.toLowerCase() === 'main') {
    modelError.value = t('library.mainSlugReserved')
    return
  }
  if (store.files.some(file => file.slug === slug)) {
    modelError.value = t('library.duplicateModelSlug', { slug })
    return
  }
  if (!newModelFile.value) {
    modelError.value = t('library.modelFileRequired')
    return
  }
  store.addFile({ slug, path: newModelFile.value, hash: '' })
  newModelSlug.value = ''
  newModelFile.value = ''
}

const availableNodes = computed(() => {
  const nodes = getAvailableNodes(locale.value as SupportedLocale)
  nodes.push({
    nodeName: 'FileInput',
    label: t('node.fileInput.title'),
    categories: ['Other'],
    description: t('node.fileInput.description'),
  })
  nodes.push({
    nodeName: 'JsonOutput',
    label: t('node.jsonOutput.title'),
    categories: ['Other'],
    description: t('node.jsonOutput.description'),
  })
  return nodes
})

const viewMode = ref<'all' | 'categories'>('all')
const searchQuery = ref('')
const expandedCategories = ref<Set<string>>(new Set(['IFC', '3D operation', 'Demo', 'Filter', 'Other']))

function setViewMode(mode: 'all' | 'categories') {
  viewMode.value = mode
}

const filteredNodes = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  if (!query)
    return availableNodes.value

  return availableNodes.value.filter(node =>
    node.label.toLowerCase().includes(query)
    || node.nodeName.toLowerCase().includes(query),
  )
})

const nodesByCategory = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  const result: Record<string, AvailableNode[]> = {}

  availableNodes.value.forEach((node) => {
    let nodeMatches = true
    if (query) {
      nodeMatches = node.label.toLowerCase().includes(query)
        || node.nodeName.toLowerCase().includes(query)
    }

    if (!nodeMatches)
      return

    const hasCategories = node.categories.length > 0

    if (hasCategories) {
      node.categories.forEach((cat) => {
        let categoryMatches = true
        if (query) {
          categoryMatches = cat.toLowerCase().includes(query)
        }

        if (categoryMatches || nodeMatches) {
          if (!result[cat])
            result[cat] = []
          if (!result[cat].some(n => n.nodeName === node.nodeName)) {
            result[cat].push(node)
          }
        }
      })
    }
    else {
      if (!result.Other)
        result.Other = []
      result.Other.push(node)
    }
  })

  Object.values(result).forEach((nodes) => {
    nodes.sort((a, b) => a.label.localeCompare(b.label))
  })

  return result
})

const displayedCategories = computed(() => {
  return Object.keys(nodesByCategory.value).sort()
})

const displayedNodes = computed(() => {
  if (viewMode.value === 'all') {
    return filteredNodes.value
  }
  return Object.values(nodesByCategory.value).flat()
})

function toggleCategory(category: string) {
  if (expandedCategories.value.has(category)) {
    expandedCategories.value.delete(category)
  }
  else {
    expandedCategories.value.add(category)
  }
  expandedCategories.value = new Set(expandedCategories.value)
}

function isCategoryExpanded(category: string) {
  return expandedCategories.value.has(category)
}

const draggedNode = ref<AvailableNode | null>(null)

function handleDragStart(event: DragEvent, node: AvailableNode) {
  draggedNode.value = node
  event.dataTransfer?.setData('application/node', node.nodeName)
  event.dataTransfer!.effectAllowed = 'copy'
}

function handleDragEnd() {
  draggedNode.value = null
}

function handleAddNode(node: AvailableNode) {
  emit('addNode', node)
}
</script>

<template>
  <UDashboardSidebar class="border-r border-default bg-elevated/50 flex" style="min-width: 20rem">
    <template #header>
      <div class="flex w-full items-center gap-2">
        <UButton
          to="/"
          color="neutral"
          variant="ghost"
          icon="i-lucide-arrow-left"
          :label="t('library.backHome')"
          :title="t('library.backHome')"
          class="justify-start"
        />
        <div class="ml-auto">
          <LocaleSwitcher />
        </div>
      </div>
    </template>

    <template #default>
      <div class="flex min-w-0 items-center gap-3">
        <div class="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary text-inverted">
          <Icon name="i-lucide-box" class="size-5" />
        </div>
        <p class="truncate text-sm font-semibold text-highlighted">
          {{ t('library.title') }}
        </p>
      </div>
      <div class="flex flex-col gap-2 px-3 pb-4">
        <div class="rounded-xl border border-default bg-default/80 p-3">
          <p class="text-sm font-medium text-highlighted">
            {{ t('library.addAvailableNodes') }}
          </p>
          <p class="mt-1 text-xs text-muted">
            {{ t('library.chooseNodeType') }}
          </p>
        </div>

        <div class="flex items-center gap-2 rounded-lg border border-default bg-default/50 p-1">
          <UButton
            :variant="viewMode === 'all' ? 'soft' : 'ghost'"
            color="neutral"
            size="sm"
            :label="t('library.viewAll')"
            icon="i-lucide-list"
            class="flex-1"
            @click="setViewMode('all')"
          />
          <UButton
            :variant="viewMode === 'categories' ? 'soft' : 'ghost'"
            color="neutral"
            size="sm"
            :label="t('library.viewCategories')"
            icon="i-lucide-folder-tree"
            class="flex-1"
            @click="setViewMode('categories')"
          />
        </div>

        <UInput
          v-model="searchQuery"
          icon="i-lucide-search"
          :placeholder="t('library.filterNodes')"
          size="sm"
          clearable
        />

        <template v-if="viewMode === 'all'">
          <NodePaletteItem
            v-for="node in displayedNodes"
            :key="node.nodeName"
            :node="node"
            :draggable="true"
            @drag-start="handleDragStart"
            @drag-end="handleDragEnd"
            @add="handleAddNode"
          />
          <div v-if="!displayedNodes.length" class="py-4 text-center text-sm text-muted">
            {{ t('library.noNodesMatch') }}
          </div>
        </template>

        <template v-else>
          <CategoryNodeList
            v-for="category in displayedCategories"
            :key="category"
            :category="category"
            :nodes="nodesByCategory[category] || []"
            :is-expanded="isCategoryExpanded(category)"
            :draggable="true"
            @toggle="toggleCategory"
            @add="handleAddNode"
            @drag-start="handleDragStart"
            @drag-end="handleDragEnd"
          />
          <div v-if="!displayedCategories.length" class="py-4 text-center text-sm text-muted">
            {{ t('library.noNodesMatch') }}
          </div>
        </template>

        <UDivider class="my-1" />

        <div class="rounded-xl border border-default bg-default/80 p-3 space-y-3">
          <div>
            <p class="text-sm font-medium text-highlighted">
              {{ t('library.modelsTitle') }}
            </p>
            <p class="mt-1 text-xs text-muted">
              {{ t('library.modelsDescription') }}
            </p>
          </div>

          <div class="flex flex-col gap-2">
            <div
              v-for="file in store.files"
              :key="file.slug"
              class="flex items-center gap-2 rounded-lg border border-default bg-default/50 px-3 py-2"
            >
              <Icon name="i-lucide-file" class="size-4 text-muted shrink-0" />
              <div class="min-w-0 flex-1">
                <p class="flex items-center gap-1.5 text-sm text-highlighted">
                  <span class="truncate font-medium">{{ store.getSlugLabel(file.slug) }}</span>
                  <UBadge
                    v-if="file.slug === 'main'"
                    color="primary"
                    variant="subtle"
                    size="xs"
                  >
                    {{ t('library.mainBadge') }}
                  </UBadge>
                </p>
                <p class="truncate text-xs text-muted">
                  {{ file.path || t('library.noFileAssigned') }}
                </p>
              </div>
              <UButton
                v-if="file.slug !== 'main'"
                color="neutral"
                variant="ghost"
                icon="i-lucide-trash-2"
                size="xs"
                :title="t('library.removeModel')"
                @click="store.removeFile(file.slug)"
              />
            </div>
          </div>

          <div class="flex flex-col gap-2 pt-1">
            <UInput
              v-model="newModelSlug"
              icon="i-lucide-tag"
              :placeholder="t('library.newModelSlug')"
              size="sm"
              clearable
            />
            <USelect
              v-model="newModelFile"
              :options="modelFileOptions"
              :placeholder="t('library.newModelFile')"
              size="sm"
            />
            <UButton
              color="neutral"
              variant="outline"
              size="sm"
              icon="i-lucide-plus"
              :label="t('library.addModel')"
              block
              @click="addModel"
            />
            <p v-if="modelError" class="text-xs text-error">
              {{ modelError }}
            </p>
          </div>
        </div>
      </div>
    </template>

    <template #footer>
      <div class="flex flex-col gap-2 px-3 pb-4">
        <UButton
          color="primary"
          variant="solid"
          icon="i-lucide-play"
          :label="isRunning ? t('library.running') : t('library.runWorkflow')"
          :disabled="!hasNodes || isRunning"
          block
          @click="emit('runWorkflow')"
        />
        <UButton
          color="neutral"
          variant="outline"
          block
          icon="i-lucide-eraser"
          :label="t('library.clearCanvas')"
          :disabled="!hasNodes"
          :title="t('library.clearCanvas')"
          class="justify-start"
          @click="emit('clearCanvas')"
        />
      </div>
    </template>
  </UDashboardSidebar>
</template>
