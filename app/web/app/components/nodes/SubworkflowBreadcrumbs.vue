<script setup lang="ts">
import type { BreadcrumbItem } from '~/stores/flow'

interface Props {
  items: BreadcrumbItem[]
}

const props = defineProps<Props>()

const emit = defineEmits<{
  navigate: [index: number]
  rename: [name: string]
}>()

const { t } = useI18n()

const active = computed(() => props.items.at(-1) ?? null)
const draft = ref('')

watch(
  () => active.value?.label ?? '',
  label => draft.value = label,
  { immediate: true },
)

function label(item: BreadcrumbItem): string {
  return item.label || t('node.subworkflow.root')
}

function isLast(index: number): boolean {
  return index === props.items.length - 1
}

function commitRename() {
  const item = active.value
  if (!item?.nodeId)
    return
  const name = draft.value.trim()
  if (!name || name === item.label) {
    draft.value = item.label
    return
  }
  emit('rename', name)
}
</script>

<template>
  <div class="flex shrink-0 items-center gap-1 border-b border-default bg-elevated/50 px-4 py-2">
    <template v-for="item in items" :key="item.index">
      <UIcon
        v-if="item.index > 0"
        name="i-lucide-chevron-right"
        class="size-3 shrink-0 text-muted"
      />
      <UInput
        v-if="isLast(item.index) && item.index > 0"
        v-model="draft"
        size="sm"
        class="w-56"
        :placeholder="t('node.subworkflow.namePlaceholder')"
        :aria-label="t('node.subworkflow.nameLabel')"
        @blur="commitRename"
        @keydown.enter="commitRename"
      />
      <UButton
        v-else
        :label="label(item)"
        color="neutral"
        :variant="isLast(item.index) ? 'soft' : 'ghost'"
        size="xs"
        :disabled="isLast(item.index)"
        :aria-current="isLast(item.index) ? 'page' : undefined"
        @click="emit('navigate', item.index)"
      />
    </template>
  </div>
</template>
