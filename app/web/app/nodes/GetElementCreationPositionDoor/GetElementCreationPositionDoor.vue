<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'

type GetElementCreationPositionDoorNode = SchemaNodeType<'get_element_creation_position_door'>

const props = defineProps<{
  node: GetElementCreationPositionDoorNode
}>()

const node = useScopedNode<GetElementCreationPositionDoorNode>(props.node.id)
const { t } = useI18n()

if (!node.value.data.settings) {
  node.value.data.settings = { point_index: 7 }
}

const pointOptions = [
  { value: 7, label: t('node.getElementCreationPositionDoor.p7Center'), available: true },
  { value: 1, label: t('node.getElementCreationPositionDoor.p1Corner'), available: true },
  { value: 2, label: t('node.getElementCreationPositionDoor.p2Corner'), available: true },
  { value: 3, label: t('node.getElementCreationPositionDoor.p3Corner'), available: true },
  { value: 4, label: t('node.getElementCreationPositionDoor.p4Corner'), available: true },
  { value: 5, label: t('node.getElementCreationPositionDoor.p5Midpoint'), available: true },
  { value: 6, label: t('node.getElementCreationPositionDoor.p6Midpoint'), available: true },
]
</script>

<template>
  <div class="px-2">
    <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
      {{ t('node.getElementCreationPositionDoor.title') }}
    </div>
    <p class="mt-1 mb-3 text-xs text-slate-500">
      {{ t('node.getElementCreationPositionDoor.description') }}
    </p>
  </div>

  <div class="flex flex-col gap-3 px-2 pb-2">
    <div class="flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.getElementCreationPositionDoor.pointIndex') }}
      </label>
      <select
        v-model.number="node.data.settings!.point_index"
        class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
      >
        <option
          v-for="option in pointOptions"
          :key="option.value"
          :value="option.value"
          :disabled="!option.available"
        >
          {{ option.label }}{{ !option.available ? ' (coming soon)' : '' }}
        </option>
      </select>
      <p class="text-xs text-slate-400">
        {{ t('node.getElementCreationPositionDoor.phase1Hint') }}
      </p>
    </div>

    <div class="border-t border-slate-200 pt-3 flex flex-col gap-1">
      <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">
        {{ t('node.getElementCreationPositionDoor.elementsOutput') }}
      </label>
      <div v-if="!node.data.result?.elements?.length" class="text-xs text-slate-400">
        {{ t('node.getElementCreationPositionDoor.noOutputYet') }}
      </div>
      <div v-else class="space-y-1">
        <div
          v-for="element in node.data.result.elements"
          :key="element.express_id"
          class="rounded bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700"
        >
          <div>Door ID: {{ element.express_id }}</div>
          <div>Position: [{{ element.position.join(', ') }}]</div>
        </div>
      </div>
    </div>
  </div>
</template>
