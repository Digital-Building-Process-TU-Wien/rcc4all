<script setup lang="ts">
interface Props {
  nodeId: string
}

defineProps<Props>()

const emit = defineEmits<{
  open: [nodeId: string]
}>()

const { t } = useI18n()
</script>

<template>
  <div class="border-t border-default pt-4 mt-4">
    <h3 class="text-sm font-semibold text-highlighted">
      {{ t('node.subworkflow.title') }}
    </h3>
    <p class="mt-1 text-sm text-muted">
      {{ t('node.subworkflow.editInsideHint') }}
    </p>
    <UButton
      class="mt-3"
      icon="i-lucide-folder-open"
      color="primary"
      variant="soft"
      :label="t('node.subworkflow.open')"
      @click="emit('open', nodeId)"
    />
  </div>
</template>
