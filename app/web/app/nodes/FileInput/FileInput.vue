<script setup lang="ts">
import type { NodeProps } from '@vue-flow/core'
import { useVueFlow } from '@vue-flow/core'
import { VUEFLOW_ID } from '~/utils/nodes'

interface NodeData {
  filename: string
}

interface Props {
  node: NodeProps<NodeData>
}

const props = defineProps<Props>()
const { updateNodeData } = useVueFlow(VUEFLOW_ID)

const search = ref('')

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

function clearSelection() {
  updateNodeData(props.node.id, { filename: undefined })
}

function selectFilename(filename: string) {
  updateNodeData(props.node.id, { filename })
}
</script>

<template>
  <div class="flex flex-col gap-4">
    <div class="px-2">
      <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
        File Input Node
      </div>
      <p class="mt-1 text-sm text-slate-500">
        Select a local development file to attach to this node.
      </p>
    </div>

    <div class="flex flex-col gap-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-500">Selected file</label>
      <div class="flex items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
        <Icon name="i-lucide-file" class="size-4 text-slate-400" />
        <span class="flex-1 truncate">
          {{ props.node.data?.filename || 'No file selected' }}
        </span>
        <UButton
          v-if="props.node.data?.filename"
          color="neutral"
          variant="ghost"
          size="xs"
          label="Clear"
          @click="clearSelection"
        />
      </div>
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
      <p>{{ error.statusMessage || 'Unable to load development files.' }}</p>
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

        <div v-else-if="!files.length" class="px-2 py-3 text-sm text-slate-500">
          No files were found in .dev-files.
        </div>

        <div v-else-if="!filteredFiles.length" class="px-2 py-3 text-sm text-slate-500">
          No filenames match your search.
        </div>

        <div v-else class="flex flex-col gap-2">
          <UButton
            v-for="file in filteredFiles"
            :key="file"
            color="neutral"
            :variant="props.node.data?.filename === file ? 'soft' : 'ghost'"
            block
            class="justify-start truncate"
            @click="selectFilename(file)"
          >
            <span class="truncate">{{ file }}</span>
          </UButton>
        </div>
      </div>
    </div>
  </div>
</template>
