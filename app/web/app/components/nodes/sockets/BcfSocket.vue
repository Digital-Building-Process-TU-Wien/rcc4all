<script setup lang="ts">
import type { NodeSocketProps } from '~/composables/useNodeSockets'
import NodeSocket from './NodeSocket.vue'

const props = defineProps<NodeSocketProps>()
const { t } = useI18n()

const label = computed(() => props.title ?? t('editor.bcfOutputCompatible'))
</script>

<template>
  <NodeSocket v-bind="props" :title="label">
    <svg
      viewBox="0 0 24 14"
      class="pointer-events-none h-3.5 w-6 shrink-0"
      role="img"
      :aria-label="label"
    >
      <text
        x="12"
        y="10.5"
        text-anchor="middle"
        fill="#ffffff"
        font-size="9"
        font-weight="800"
        font-family="ui-sans-serif, system-ui, sans-serif"
        letter-spacing="0.4"
      >
        BCF
      </text>
    </svg>
  </NodeSocket>
</template>
