<script setup lang="ts">
import type { CompleteResult, WorkflowData } from '~/composables/useWorkflowExecution'
import { useWorkflowExecution } from '~/composables/useWorkflowExecution'

const props = defineProps<{
  workflow: WorkflowData
}>()

const emit = defineEmits<{
  complete: [result: CompleteResult]
}>()

const router = useRouter()

const workflowRef = ref<WorkflowData>(props.workflow)
const currentTab = ref<'output' | 'results'>('output')

const {
  isRunning,
  outputLogs,
  error,
  results,
  parseError,
  exitCode,
  status,
  outputContainerRef,
  startExecution,
} = useWorkflowExecution(workflowRef)

const safeParseError = computed(() => parseError.value ?? null)
const safeExitCode = computed(() => exitCode.value ?? null)

function goBack() {
  router.push('/node-demo')
}

function selectTab(tab: 'output' | 'results') {
  currentTab.value = tab
}

function handleComplete(result: CompleteResult) {
  emit('complete', result)
  if (result.success) {
    currentTab.value = 'results'
  }
}

onMounted(() => {
  startExecution({
    onStdout: () => {},
    onStderr: () => {},
    onError: () => {},
    onComplete: handleComplete,
  })
})

watch(() => props.workflow, (newWorkflow) => {
  if (newWorkflow) {
    workflowRef.value = newWorkflow
  }
}, { immediate: true })
</script>

<template>
  <div class="flex h-full flex-col">
    <div class="flex items-center justify-between border-b border-default px-6 py-4">
      <UButton
        label="Back to Workflow"
        icon="i-lucide-arrow-left"
        color="neutral"
        variant="outline"
        size="sm"
        @click="goBack"
      />
      <div class="flex items-center gap-3">
        <UBadge v-if="status === 'running'" color="primary" variant="soft">
          Running...
        </UBadge>
        <UBadge v-else-if="status === 'error'" color="error" variant="soft">
          Failed
        </UBadge>
        <UBadge v-else-if="status === 'complete'" color="success" variant="soft">
          Completed
        </UBadge>
      </div>
      <div class="flex gap-2">
        <UButton
          label="Runner Output"
          :color="currentTab === 'output' ? 'primary' : 'neutral'"
          :variant="currentTab === 'output' ? 'solid' : 'outline'"
          size="sm"
          @click="selectTab('output')"
        />
        <UButton
          label="JSON Results"
          :color="currentTab === 'results' ? 'primary' : 'neutral'"
          :variant="currentTab === 'results' ? 'solid' : 'outline'"
          size="sm"
          :disabled="isRunning"
          @click="selectTab('results')"
        />
      </div>
    </div>

    <div class="flex-1 overflow-hidden p-6">
      <div v-if="currentTab === 'output'" class="flex h-full flex-col">
        <div
          ref="outputContainerRef"
          class="h-full overflow-auto bg-default p-3 font-mono text-xs"
        >
          <div
            v-for="(log, index) in outputLogs"
            :key="index"
            class="whitespace-pre-wrap"
            :class="log.type === 'stderr' ? 'text-error' : 'text-highlighted'"
          >
            {{ log.chunk }}
          </div>
          <div v-if="!outputLogs.length" class="flex h-full items-center justify-center">
            <div class="text-center text-muted">
              <UIcon name="i-lucide-loader" class="mx-auto mb-2 size-6 animate-spin" />
              <p>Waiting for output...</p>
            </div>
          </div>
        </div>
      </div>

      <div v-else-if="currentTab === 'results'" class="flex h-full flex-col">
        <div v-if="error && !results" class="border-b border-error bg-error/10 p-4">
          <div class="flex items-center gap-2 text-error">
            <UIcon name="i-lucide-alert-triangle" class="size-5" />
            <span class="font-semibold">Execution Error</span>
          </div>
          <p v-if="error.message" class="mt-2 text-sm text-error">
            {{ error.message }}
          </p>
          <p v-if="safeParseError" class="mt-2 text-sm text-error">
            Failed to parse output as JSON: {{ safeParseError }}
          </p>
          <p v-if="safeExitCode !== null && safeExitCode !== 0" class="mt-2 text-sm text-error">
            Exit code: {{ safeExitCode }}
          </p>
        </div>

        <div class="flex-1 overflow-hidden">
          <div class="bg-default/50 px-3 py-2 text-xs font-medium text-muted">
            {{ results ? 'JSON Result' : 'Raw Output' }}
          </div>
          <div class="h-[calc(100%-40px)] overflow-auto bg-default p-3">
            <pre class="font-mono text-xs">{{ JSON.stringify(results || error, null, 2) }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
