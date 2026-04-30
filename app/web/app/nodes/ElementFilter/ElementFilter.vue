<script setup lang="ts">
const outputs = ['express_ids']

const settings = reactive({
  entity_type: 'IFCWALL',
})
</script>

<template>
  <NodesNodeWrapper :inputs="[]" :outputs="outputs">
    <div class="px-2">
      <div class="text-sm font-bold text-slate-800 mb-2 uppercase tracking-wide">
        Element Filter Node
      </div>
    </div>

    <template #settings>
      <div class="flex flex-col gap-2">
        <label class="text-[10px] text-slate-500 font-semibold uppercase tracking-tight">Entity Type</label>
        <input
          v-model="settings.entity_type"
          type="text"
          placeholder="e.g. IFCWALL"
          class="bg-white border border-slate-200 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-blue-500 outline-none text-slate-800 transition-all shadow-sm"
        >
      </div>
    </template>
  </NodesNodeWrapper>
</template>
