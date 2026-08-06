<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type IdsCheckerNode = SchemaNodeType<'ids_checker'>

const props = defineProps<{
  node: IdsCheckerNode
}>()

const node = useScopedNode<IdsCheckerNode>(props.node.id)

if (!node.value.data.settings) {
  node.value.data.settings = { ids_file: '', output_mode: 'combined' }
}

if (!node.value.data.settings.output_mode) {
  node.value.data.settings.output_mode = 'combined'
}

const search = ref('')

const { data, error, pending, refresh } = useFetch('/api/ids-files', {
  default: () => ({ files: [] }),
  lazy: true,
  server: false,
})

const idsFiles = computed(() => data.value?.files ?? [])

const filteredFiles = computed(() => {
  const query = search.value.trim().toLowerCase()

  if (!query)
    return idsFiles.value

  return idsFiles.value.filter(file => file.toLowerCase().includes(query))
})

function clearSelection() {
  node.value.data.settings!.ids_file = ''
}

function selectFile(filename: string) {
  node.value.data.settings!.ids_file = filename
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="px-2">
      <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
        IDS Checker Node
      </div>
      <p class="mt-1 text-sm text-slate-500">
        Select a local development IDS file.
      </p>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">Selected IDS file</label>
      <div class="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
        <Icon name="i-lucide-file-check" class="size-4 text-slate-400" />
        <span class="flex-1 truncate">
          {{ node.data?.settings?.ids_file || 'No file selected' }}
        </span>
        <UButton
          v-if="node.data?.settings?.ids_file"
          color="neutral"
          variant="ghost"
          size="xs"
          label="Clear"
          @click="clearSelection"
        />
      </div>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">Output Mode</label>
      <select
        v-model="node.data.settings!.output_mode"
        class="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option value="combined">
          Combined
        </option>
        <option value="per_specification">
          Per Specification
        </option>
        <option value="both">
          Both
        </option>
      </select>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">Search files</label>
      <UInput
        v-model="search"
        icon="i-lucide-search"
        placeholder="Filter filenames"
      />
    </div>

    <div v-if="error" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      <p>{{ error.statusMessage || 'Unable to load IDS files.' }}</p>
      <UButton
        color="error"
        variant="ghost"
        size="sm"
        label="Retry"
        class="mt-2"
        @click="refresh()"
      />
    </div>

    <div v-else class="flex flex-col gap-2">
      <div class="max-h-80 overflow-y-auto rounded-lg border border-slate-200 bg-white p-2">
        <div v-if="pending" class="px-2 py-3 text-sm text-slate-500">
          Loading files...
        </div>

        <div v-else-if="!idsFiles.length" class="px-2 py-3 text-sm text-slate-500">
          No IDS files were found in web/.dev-files <br>
          Please add .ids files in the folder <span class="font-mono text-slate-700">web/.dev-files</span> to use this node.
        </div>

        <div v-else-if="!filteredFiles.length" class="px-2 py-3 text-sm text-slate-500">
          No filenames match your search.
        </div>

        <div v-else class="flex flex-col gap-2">
          <UButton
            v-for="file in filteredFiles"
            :key="file"
            color="neutral"
            :variant="node.data?.settings?.ids_file === file ? 'soft' : 'ghost'"
            block
            class="justify-start truncate"
            @click="selectFile(file)"
          >
            <span class="truncate">{{ file }}</span>
          </UButton>
        </div>
      </div>
    </div>
  </div>
</template>
