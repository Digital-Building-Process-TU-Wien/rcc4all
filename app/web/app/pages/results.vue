<script setup lang="ts">
const route = useRoute()
const filename = route.query.file as string

const loading = ref(true)
const error = ref<string | null>(null)
const stderr = ref<string | null>(null)
const results = ref<any>(null)

if (!filename) {
  error.value = 'No workflow file specified'
  loading.value = false
}
else {
  try {
    const response = await $fetch('/api/workflow/results', {
      query: { file: filename },
    })
    results.value = response
  }
  catch (e: any) {
    if (e.data) {
      error.value = e.data.error || 'Failed to load results'
      stderr.value = e.data.stderr
    }
    else {
      error.value = 'Failed to load results'
    }
  }
  finally {
    loading.value = false
  }
}

function goBack() {
  window.close()
}

function downloadResults() {
  if (!results.value)
    return

  const dataToDownload = results.value.results || results.value.error
  const blob = new Blob([JSON.stringify(dataToDownload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename.replace('.json', '-download.json')
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="min-h-screen bg-default p-8">
    <div class="mx-auto max-w-4xl">
      <div class="mb-6 flex items-center justify-between">
        <h1 class="text-2xl font-bold text-highlighted">
          Workflow Results
        </h1>
        <div class="flex gap-2">
          <UButton
            color="neutral"
            variant="outline"
            icon="i-lucide-download"
            label="Download"
            @click="downloadResults"
          />
          <UButton
            color="primary"
            variant="solid"
            icon="i-lucide-arrow-left"
            label="Back to Editor"
            @click="goBack"
          />
        </div>
      </div>

      <div v-if="loading" class="flex items-center justify-center py-12">
        <UIcon name="i-lucide-loader" class="size-8 animate-spin text-primary" />
        <span class="ml-3 text-muted">Loading results...</span>
      </div>

      <div v-else-if="error" class="rounded-xl border border-error bg-error/10 p-6">
        <h2 class="mb-2 text-lg font-semibold text-error">
          Execution Error
        </h2>
        <p class="text-sm text-muted">
          {{ error }}
        </p>
        <pre v-if="stderr" class="mt-4 max-h-64 overflow-auto rounded bg-default p-4 text-xs font-mono text-error">
{{ stderr }}
        </pre>
      </div>

      <div v-else-if="results" class="rounded-xl border border-default bg-default/50 p-6">
        <div class="mb-4 flex items-center gap-2">
          <UBadge :color="results.success ? 'success' : 'error'" variant="soft">
            {{ results.success ? 'Success' : 'Failed' }}
          </UBadge>
          <span class="text-sm text-muted">{{ filename }}</span>
        </div>
        <pre class="max-h-[60vh] overflow-auto rounded bg-default p-4 text-xs font-mono text-highlighted">{{ JSON.stringify(results.results || results.error, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>
