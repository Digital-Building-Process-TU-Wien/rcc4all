<script setup lang="ts">
import type { Node } from '@vue-flow/core'
import { useFlowStore } from '~/stores/flow'

// This is a web-only visual node. It does not exist in the runner schema and is
// excluded from the workflow payload. Selecting a file here assigns the workflow's
// MAIN IFC model slot (path + content hash); other model slots are managed in the
// sidebar model manager. The runner receives the assigned files via the workflow
// definition's `files` member.
interface FileInputData {
  label?: string
}

type FileInputNode = Node<FileInputData>

defineProps<{
  node: FileInputNode
}>()

const { t } = useI18n()
const store = useFlowStore()

const mainFile = computed(() => store.files.find(file => file.slug === 'main'))

const search = ref('')
const assigning = ref(false)

const { data, error, pending, refresh } = useFetch('/api/dev-files', {
  default: () => ({ files: [] }),
  lazy: true,
  server: false,
})

const files = computed(() => data.value?.files ?? [])

const filteredFiles = computed(() => {
  const query = search.value.trim().toLowerCase()

  if (!query)
    return files.value

  return files.value.filter(file => file.toLowerCase().includes(query))
})

async function assignMainFile(filename: string) {
  assigning.value = true
  try {
    let hash = ''
    try {
      const result = await $fetch<{ hash: string }>('/api/dev-file-hash', {
        query: { name: filename },
      })
      hash = result?.hash ?? ''
    }
    catch {
      // Hashing is best-effort; the runner only warns on a mismatch.
      hash = ''
    }
    store.setMainFile({ path: filename, hash })
  }
  finally {
    assigning.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="px-2">
      <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
        {{ t('node.fileInput.title') }}
      </div>
      <p class="mt-1 text-sm text-slate-500">
        {{ t('node.fileInput.description') }}
      </p>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">{{ t('node.fileInput.selectedFile') }}</label>
      <div class="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
        <Icon name="i-lucide-file" class="size-4 text-slate-400" />
        <span class="flex-1 truncate">
          {{ mainFile?.path || t('node.fileInput.noFileSelected') }}
        </span>
      </div>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">{{ t('node.fileInput.searchFiles') }}</label>
      <UInput
        v-model="search"
        icon="i-lucide-search"
        :placeholder="t('node.fileInput.filterFilenames')"
      />
    </div>

    <div v-if="error" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      <p>{{ error.statusMessage || t('node.fileInput.unableToLoad') }}</p>
      <UButton
        color="error"
        variant="ghost"
        size="sm"
        :label="t('node.fileInput.retry')"
        class="mt-2"
        @click="refresh()"
      />
    </div>

    <div v-else class="flex flex-col gap-2">
      <div class="max-h-80 overflow-y-auto rounded-lg border border-slate-200 bg-white p-2">
        <div v-if="pending" class="px-2 py-3 text-sm text-slate-500">
          {{ t('node.fileInput.loadingFiles') }}
        </div>

        <div v-else-if="!files.length" class="px-2 py-3 text-sm text-slate-500">
          {{ t('node.fileInput.noFilesFound') }} <br>
          {{ t('node.fileInput.addIfcFile', { folder: 'web/.dev-files' }) }}
        </div>

        <div v-else-if="!filteredFiles.length" class="px-2 py-3 text-sm text-slate-500">
          {{ t('node.fileInput.noFilenameMatch') }}
        </div>

        <div v-else class="flex flex-col gap-2">
          <UButton
            v-for="file in filteredFiles"
            :key="file"
            color="neutral"
            :variant="mainFile?.path === file ? 'soft' : 'ghost'"
            block
            :loading="assigning"
            class="justify-start truncate"
            @click="assignMainFile(file)"
          >
            <span class="truncate">{{ file }}</span>
          </UButton>
        </div>
      </div>
    </div>
  </div>
</template>
