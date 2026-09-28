<script setup lang="ts">
import type { ModelFile } from '~/stores/flow'
import { useFlowStore } from '~/stores/flow'

// Keep in sync with the runner validator:
// app/runner/src/openbim_runner/workflow.py (MODEL_SLUG_PATTERN).
const MODEL_SLUG_RE = /^[a-z0-9][a-z0-9-_]*$/

const { t } = useI18n()
const store = useFlowStore()

const { data: devFilesData } = useFetch('/api/dev-files', {
  default: () => ({ files: [] }),
  lazy: true,
  server: false,
})

const allFiles = computed(() => devFilesData.value?.files ?? [])

const isOpen = ref(false)
const query = ref('')
const selectedFile = ref('')
const isMain = ref(false)
const nameInput = ref('')
const error = ref('')
const adding = ref(false)
// Empty when adding a new model; the slug being replaced otherwise.
const editingSlug = ref('')

const isEditing = computed(() => editingSlug.value !== '')

const filteredFiles = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q)
    return allFiles.value
  return allFiles.value.filter(file => file.toLowerCase().includes(q))
})

function modelLabel(slug: string): string {
  return slug === 'main' ? t('library.modelMain') : slug
}

// The reserved `main` slot is pinned to the left; added models follow it.
const orderedFiles = computed(() => [
  ...store.files.filter(file => file.slug === 'main'),
  ...store.files.filter(file => file.slug !== 'main'),
])

function open() {
  // The first assigned file defaults to main; later files default to a named
  // slot. The main slot always exists as an (empty) placeholder, so "first
  // file" means the main slot has not been assigned a path yet.
  editingSlug.value = ''
  isMain.value = !store.files.find(file => file.slug === 'main')?.path
  nameInput.value = isMain.value ? 'main' : ''
  query.value = ''
  selectedFile.value = ''
  error.value = ''
  isOpen.value = true
}

function openReplace(file: ModelFile) {
  editingSlug.value = file.slug
  isMain.value = file.slug === 'main'
  nameInput.value = file.slug
  query.value = ''
  selectedFile.value = file.path
  error.value = ''
  isOpen.value = true
}

function onMainChange(value: boolean | 'indeterminate') {
  isMain.value = value === true
  if (isMain.value)
    nameInput.value = 'main'
}

function selectFile(filename: string) {
  selectedFile.value = filename
}

// Best-effort: records a bare SHA-256 hex digest so the runner can warn when a
// file on disk changes after assignment. A failure records an empty hash, which
// tells the runner to skip the check.
async function hashFile(filename: string): Promise<string> {
  try {
    const result = await $fetch<{ hash: string }>('/api/dev-file-hash', {
      query: { name: filename },
    })
    return result?.hash ?? ''
  }
  catch {
    return ''
  }
}

async function confirm() {
  error.value = ''
  if (!selectedFile.value) {
    error.value = t('modelBar.fileRequired')
    return
  }

  let slug: string
  if (isEditing.value) {
    // Replacing a slot keeps its slug; only the file changes.
    slug = editingSlug.value
  }
  else {
    slug = isMain.value ? 'main' : nameInput.value.trim()
    if (!isMain.value) {
      if (!MODEL_SLUG_RE.test(slug)) {
        error.value = t('library.invalidModelSlug')
        return
      }
      if (store.files.some(file => file.slug === slug)) {
        error.value = t('library.duplicateModelSlug', { slug })
        return
      }
    }
  }

  adding.value = true
  try {
    const hash = await hashFile(selectedFile.value)
    store.addFile({ slug, path: selectedFile.value, hash })
    isOpen.value = false
  }
  finally {
    adding.value = false
  }
}
</script>

<template>
  <div class="flex h-20 items-center gap-3 overflow-x-auto border-b border-default bg-elevated px-6">
    <div
      v-for="file in orderedFiles"
      :key="file.slug"
      class="flex h-16 w-64 shrink-0 items-center gap-2 rounded-xl border border-default bg-default px-3"
    >
      <div class="flex size-9 shrink-0 items-center justify-center rounded-lg bg-elevated">
        <Icon name="i-lucide-file" class="size-4 text-muted" />
      </div>
      <div class="min-w-0 flex-1">
        <p class="flex items-center gap-1.5 text-sm text-highlighted">
          <span class="truncate font-medium">{{ modelLabel(file.slug) }}</span>
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
      <div class="flex shrink-0 flex-col items-center gap-1">
        <UButton
          color="neutral"
          variant="ghost"
          icon="i-lucide-trash-2"
          size="xs"
          :title="file.slug === 'main' ? t('modelBar.removeFile') : t('library.removeModel')"
          @click="store.removeFile(file.slug)"
        />
        <UButton
          color="neutral"
          variant="ghost"
          icon="i-lucide-refresh-cw"
          size="xs"
          :title="t('modelBar.replace')"
          @click="openReplace(file)"
        />
      </div>
    </div>

    <button
      type="button"
      class="group flex h-16 w-56 shrink-0 flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed border-default bg-default/60 transition-colors hover:border-primary/60 hover:bg-primary/5"
      @click="open"
    >
      <Icon name="i-lucide-plus" class="size-6 text-muted transition-colors group-hover:text-primary" />
      <span class="text-sm font-medium text-muted transition-colors group-hover:text-primary">
        {{ t('modelBar.addModel') }}
      </span>
    </button>
  </div>

  <UModal
    v-model:open="isOpen"
    :title="isEditing ? t('modelBar.replaceTitle') : t('modelBar.modalTitle')"
    :description="isEditing ? t('modelBar.replaceDescription') : t('modelBar.modalDescription')"
  >
    <template #body>
      <div class="space-y-4">
        <UFormField :label="t('modelBar.fileLabel')">
          <div class="flex flex-col gap-2">
            <UInput v-model="query" icon="i-lucide-search" :placeholder="t('modelBar.searchFiles')" clearable />

            <div class="max-h-64 overflow-y-auto rounded-lg border border-default bg-surface/50">
              <div
                v-if="!filteredFiles.length"
                class="px-3 py-6 text-center text-sm text-muted"
              >
                {{ t('modelBar.noFilesFound') }}
              </div>
              <div v-else class="flex flex-col">
                <button
                  v-for="file in filteredFiles"
                  :key="file"
                  type="button"
                  class="flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-elevated"
                  :class="selectedFile === file ? 'bg-primary/10 font-medium text-primary' : 'text-default'"
                  @click="selectFile(file)"
                >
                  <Icon name="i-lucide-file" class="size-4 shrink-0 text-muted" />
                  <span class="truncate">{{ file }}</span>
                  <Icon
                    v-if="selectedFile === file"
                    name="i-lucide-check"
                    class="ml-auto size-4 shrink-0 text-primary"
                  />
                </button>
              </div>
            </div>
          </div>
        </UFormField>

        <UFormField :label="t('modelBar.isMain')">
          <UCheckbox
            :model-value="isMain"
            :label="t('modelBar.isMainHint')"
            :disabled="isEditing"
            @update:model-value="onMainChange"
          />
        </UFormField>

        <UFormField :label="t('modelBar.nameLabel')">
          <UInput
            v-model="nameInput"
            :disabled="isMain || isEditing"
            :placeholder="t('modelBar.namePlaceholder')"
          />
        </UFormField>

        <UAlert v-if="error" color="error" :title="error" />
      </div>
    </template>
    <template #footer="{ close }">
      <UButton
        color="neutral"
        variant="outline"
        :label="t('modelBar.cancel')"
        @click="close"
      />
      <UButton
        color="primary"
        :label="isEditing ? t('modelBar.save') : t('modelBar.confirm')"
        :loading="adding"
        @click="confirm"
      />
    </template>
  </UModal>
</template>
