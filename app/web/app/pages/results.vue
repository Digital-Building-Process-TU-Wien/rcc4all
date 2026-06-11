<script setup lang="ts">
import type { CompleteResult } from '~/components/WorkflowExecutionView.vue'
import { useFlowStore } from '~/stores/flow'

const router = useRouter()
const store = useFlowStore()

const filename = ref<string | null>(null)

const executionComplete = ref(false)
const completedResult = ref<CompleteResult | null>(null)

const loading = ref(true)
const error = ref<string | null>(null)
const results = ref<any>(null)

const workflowData = computed(() => store.getWorkflowData())

function goBack() {
  router.push('/')
}

function handleExecutionComplete(result: CompleteResult) {
  executionComplete.value = true
  completedResult.value = result
  results.value = result
  filename.value = result.resultsPath
  loading.value = false
}

if (!workflowData.value) {
  error.value = 'No workflow data found. Please create a workflow first.'
  loading.value = false
}
else {
  loading.value = false
}
</script>

<template>
  <div class="flex h-screen flex-col bg-default">
    <div v-if="loading" class="flex h-full items-center justify-center">
      <div class="flex items-center text-muted">
        <UIcon name="i-lucide-loader" class="mr-3 size-8 animate-spin" />
        <span>Loading workflow...</span>
      </div>
    </div>

    <div v-else-if="error" class="flex h-full items-center justify-center">
      <div class="max-w-md rounded-xl border border-error bg-error/10 p-6 text-center">
        <h2 class="mb-2 text-lg font-semibold text-error">
          Error
        </h2>
        <p class="text-sm text-muted">
          {{ error }}
        </p>
        <UButton
          color="primary"
          variant="solid"
          label="Go to Editor"
          class="mt-4"
          @click="goBack"
        />
      </div>
    </div>

    <div v-else class="h-full">
      <WorkflowExecutionView
        :workflow="workflowData"
        @complete="handleExecutionComplete"
      />
    </div>
  </div>
</template>
