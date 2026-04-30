<script setup lang="ts">
import type { NodeTypesObject } from '@vue-flow/core'
import { useVueFlow, VueFlow } from '@vue-flow/core'
import { markRaw } from 'vue'

import ConcatStringComponent from '@/nodes/ConcatString/ConcatString.vue'
import ElementFilterComponent from '@/nodes/ElementFilter/ElementFilter.vue'

// Import nodes
import GetNameComponent from '@/nodes/GetName/GetName.vue'
// Basic Vue Flow styling
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'

const nodeTypes = {
  GetName: markRaw(GetNameComponent),
  ConcatString: markRaw(ConcatStringComponent),
  ElementFilter: markRaw(ElementFilterComponent),
} as unknown as NodeTypesObject

const initialNodes = [
  {
    id: '1',
    type: 'GetName',
    position: { x: 100, y: 100 },
    data: { label: 'Get Name' },
  },
  {
    id: '2',
    type: 'ConcatString',
    position: { x: 400, y: 100 },
    data: { label: 'Concat String' },
  },
  {
    id: '3',
    type: 'ElementFilter',
    position: { x: 100, y: 320 },
    data: { label: 'Element Filter' },
  },
]

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', sourceHandle: 'object_names', targetHandle: 'values' },
]

const { onConnect, addEdges } = useVueFlow()

onConnect((params) => {
  addEdges(params)
})
</script>

<template>
  <div class="w-full h-screen bg-slate-50 overflow-hidden flex flex-col">
    <div class="p-4 bg-white border-b border-slate-200 flex justify-between items-center shadow-sm z-10">
      <div>
        <h1 class="text-xl font-bold text-slate-900 flex items-center gap-2">
          <Icon name="tabler:route" class="text-blue-600" />
          BIM Node Editor Demo
        </h1>
        <p class="text-slate-500 text-xs uppercase tracking-widest mt-1">
          Experimental Workflow Engine
        </p>
      </div>
      <div class="flex gap-2">
        <NuxtLink to="/" class="px-4 py-2 text-sm font-medium text-slate-600 hover:text-slate-900 bg-slate-100 hover:bg-slate-200 rounded transition-all flex items-center gap-2">
          <Icon name="tabler:arrow-left" />
          Back Home
        </NuxtLink>
      </div>
    </div>

    <div class="flex-1 relative">
      <VueFlow
        :nodes="initialNodes"
        :edges="initialEdges"
        :node-types="nodeTypes"
        class="bg-slate-50"
        fit-view-on-init
      >
        <div class="absolute bottom-4 left-4 z-20 bg-white p-3 rounded-lg border border-slate-200 shadow-xl text-slate-900 text-sm">
          <div class="flex items-center gap-2 mb-1">
            <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span class="font-bold opacity-70 text-slate-700">Status: Runtime Ready</span>
          </div>
          <p class="text-slate-400 text-xs">
            Node Graph Demo v0.1
          </p>
        </div>
      </VueFlow>
    </div>
  </div>
</template>

<style>
.vue-flow__node {
  background: transparent !important;
  border: none !important;
  padding: 0 !important;
}

.vue-flow__edge-path {
  stroke: #cbd5e1 !important;
  stroke-width: 3;
}

.vue-flow__handle {
  width: 12px !important;
  height: 12px !important;
}

/* Custom grid dots for light theme */
.vue-flow {
  background-image: radial-gradient(#e2e8f0 1px, transparent 1px);
  background-size: 24px 24px;
}
</style>
