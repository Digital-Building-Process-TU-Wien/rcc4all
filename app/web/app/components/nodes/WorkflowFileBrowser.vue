<script setup lang="ts">
import type { WorkflowDirectoryListing, WorkflowFileEntry } from '#shared/types/workflow-files'
import { DEV_FILES_LABEL } from '#shared/types/workflow-files'
import { useWorkflowFiles, workflowFileErrorMessage } from '~/composables/useWorkflowFiles'

interface Props {
  dir: string
  mode?: 'files' | 'directories'
  selected?: string
  refreshToken?: number
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'files',
  selected: '',
  refreshToken: 0,
})

const emit = defineEmits<{
  'update:dir': [dir: string]
  'select': [entry: WorkflowFileEntry]
}>()

const { t, locale } = useI18n()
const { listDirectory } = useWorkflowFiles()

const listing = ref<WorkflowDirectoryListing | null>(null)
const query = ref('')
const pending = ref(false)
const error = ref('')

const isFileMode = computed(() => props.mode === 'files')

const searchPlaceholder = computed(() =>
  isFileMode.value
    ? t('workflowFiles.searchFiles')
    : t('workflowFiles.searchFolders'),
)

function matches(name: string): boolean {
  const value = query.value.trim().toLowerCase()
  return !value || name.toLowerCase().includes(value)
}

const filteredDirectories = computed(() =>
  (listing.value?.directories ?? []).filter(entry => matches(entry.name)),
)

const filteredFiles = computed(() =>
  isFileMode.value
    ? (listing.value?.files ?? []).filter(entry => matches(entry.name))
    : [],
)

const hasResults = computed(() =>
  filteredDirectories.value.length > 0 || filteredFiles.value.length > 0,
)

const emptyMessage = computed(() => {
  if (query.value.trim())
    return t('workflowFiles.noMatches')
  return isFileMode.value
    ? t('workflowFiles.noFiles')
    : t('workflowFiles.noFolders')
})

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime()))
    return ''
  return new Intl.DateTimeFormat(locale.value, {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(date)
}

function goUp() {
  const parent = listing.value?.parent
  if (typeof parent === 'string')
    emit('update:dir', parent)
}

async function refresh() {
  pending.value = true
  error.value = ''
  try {
    listing.value = await listDirectory(props.dir)
  }
  catch (cause) {
    listing.value = null
    error.value = workflowFileErrorMessage(cause, t('workflowFiles.listFailed'))
  }
  finally {
    pending.value = false
  }
}

watch(
  [() => props.dir, () => props.refreshToken],
  refresh,
  { immediate: true },
)
</script>

<template>
  <div class="space-y-2">
    <UInput
      v-model="query"
      icon="i-lucide-search"
      :placeholder="searchPlaceholder"
      size="sm"
      class="w-full"
      clearable
    />

    <div class="max-h-64 overflow-y-auto rounded-lg border border-default bg-surface/50">
      <div v-if="pending" class="flex items-center justify-center gap-2 px-3 py-6 text-sm text-muted">
        <UIcon name="i-lucide-loader" class="size-4 animate-spin" />
        {{ t('workflowFiles.loading') }}
      </div>

      <div v-else-if="error" class="flex flex-col items-center gap-2 px-3 py-6 text-center">
        <p class="text-sm text-error">
          {{ error }}
        </p>
        <UButton
          size="xs"
          variant="ghost"
          color="neutral"
          :label="t('workflowFiles.retry')"
          @click="refresh"
        />
      </div>

      <div v-else class="flex flex-col">
        <button
          v-if="listing && listing.parent !== null"
          type="button"
          class="flex items-center gap-2 px-3 py-2 text-left text-sm text-muted transition-colors hover:bg-elevated"
          @click="goUp"
        >
          <UIcon name="i-lucide-corner-left-up" class="size-4 shrink-0" />
          <span class="truncate">{{ t('workflowFiles.parentFolder') }}</span>
        </button>

        <button
          v-for="directory in filteredDirectories"
          :key="directory.path"
          type="button"
          class="flex items-center gap-2 px-3 py-2 text-left text-sm text-default transition-colors hover:bg-elevated"
          @click="emit('update:dir', directory.path)"
        >
          <UIcon name="i-lucide-folder" class="size-4 shrink-0 text-muted" />
          <span class="truncate">{{ directory.name }}</span>
        </button>

        <button
          v-for="file in filteredFiles"
          :key="file.path"
          type="button"
          class="flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-elevated"
          :class="selected === file.path ? 'bg-primary/10 font-medium text-primary' : 'text-default'"
          @click="emit('select', file)"
        >
          <UIcon name="i-lucide-file-json" class="size-4 shrink-0 text-muted" />
          <span class="min-w-0 flex-1">
            <span class="block truncate">{{ file.name }}</span>
            <span class="block text-xs text-muted">{{ formatDate(file.modifiedAt) }}</span>
          </span>
          <UIcon
            v-if="selected === file.path"
            name="i-lucide-check"
            class="size-4 shrink-0 text-primary"
          />
        </button>

        <div v-if="!hasResults" class="px-3 py-6 text-center text-sm text-muted">
          {{ emptyMessage }}
        </div>
      </div>
    </div>

    <p class="flex items-center gap-1.5 truncate font-mono text-xs text-muted">
      <UIcon name="i-lucide-folder-open" class="size-3.5 shrink-0" />
      {{ DEV_FILES_LABEL }}/{{ listing?.dir ?? dir }}
    </p>
  </div>
</template>
