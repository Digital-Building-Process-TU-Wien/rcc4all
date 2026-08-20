<script setup lang="ts">
import type {
  GetPropertyNode,
  IfcAllowedValue,
  IfcFilterEntity,
  IfcFilterIndex,
  IfcFilterProperty,
  IfcFilterPropertySet,
  PropertySelection,
} from './types'
import { useScopedNode } from '~/composables/useScopedNode'
import { exportRequirementsToCsv, importRequirementsFromCsv } from './utils/csv-import-export'

interface Props {
  node: GetPropertyNode
}

const props = defineProps<Props>()
const node = useScopedNode<GetPropertyNode>(props.node.id)
const { t } = useI18n()
const csvInput = ref<HTMLInputElement | null>(null)
const csvMessage = ref('')

const { data: filterIndex, error: filterIndexError, pending: filterIndexPending } = useFetch<IfcFilterIndex>(
  '/list/ifc-4.3-filter-index.json',
  { default: () => ({ entities: [] }) },
)

const entities = computed(() => filterIndex.value?.entities ?? [])
const selections = computed(() => node.value.data.settings?.selections ?? [])

// Build a deduplicated global property index (code → dataType + allowedValues)
const globalProperties = computed(() => {
  const map = new Map<string, { dataType: string, allowedValues: IfcAllowedValue[], psets: Set<string> }>()
  const allEntities = filterIndex.value?.entities ?? []
  for (const entity of allEntities) {
    for (const pset of entity.propertySets) {
      for (const prop of pset.properties) {
        const existing = map.get(prop.code)
        if (!existing) {
          map.set(prop.code, {
            dataType: prop.dataType,
            allowedValues: prop.allowedValues,
            psets: new Set([pset.code]),
          })
        }
        else {
          existing.psets.add(pset.code)
        }
      }
    }
  }
  return map
})

// All unique property codes for autocomplete
const allPropertyNames = computed(() => Array.from(globalProperties.value.keys()).sort())

const outputModes = [
  { value: 'elements', label: 'Per explicit element' },
  { value: 'by_class', label: 'Per element class' },
  { value: 'model', label: 'Without element class distinction' },
]

if (!node.value.data.settings) {
  node.value.data.settings = {
    output_mode: 'elements',
    selections: [],
  }
}

if (!node.value.data.settings.selections) {
  node.value.data.settings.selections = []
}

if (!node.value.data.settings.output_mode) {
  node.value.data.settings.output_mode = 'elements'
}

function getEntity(entityType: string | undefined): IfcFilterEntity | undefined {
  if (!entityType)
    return undefined

  return entities.value.find(entity => entity.code === entityType.toUpperCase())
}

function getPropertySetsForEntity(entityType: string | undefined): IfcFilterPropertySet[] {
  const entity = getEntity(entityType)
  if (entity)
    return entity.propertySets

  if (entityType)
    return []

  const allPsets = entities.value.flatMap(e => e.propertySets)
  const uniqueMap = new Map<string, IfcFilterPropertySet>()
  allPsets.forEach((pset) => {
    if (!uniqueMap.has(pset.code)) {
      uniqueMap.set(pset.code, pset)
    }
  })
  return Array.from(uniqueMap.values()).sort((a, b) => a.code.localeCompare(b.code))
}

function getPropertiesForPropertySet(entityType: string | undefined, propertySetCode: string | undefined): IfcFilterProperty[] {
  if (!propertySetCode)
    return []

  const psets = getPropertySetsForEntity(entityType)
  const pset = psets.find(p => p.code === propertySetCode)
  if (pset)
    return pset.properties

  return []
}

function getPropertyOptions(sel: PropertySelection): string[] {
  if (sel.property_set) {
    return getPropertiesForPropertySet(sel.entity_type, sel.property_set)
      .map(property => property.code)
      .sort((a, b) => a.localeCompare(b))
  }
  return allPropertyNames.value
}

function addSelection() {
  node.value.data.settings!.selections!.push({
    entity_type: '',
    property_set: '',
    property_name: '',
  })
}

function duplicateSelection(index: number) {
  const original = node.value.data.settings!.selections![index]
  node.value.data.settings!.selections!.splice(index + 1, 0, { ...original })
}

function removeSelection(index: number) {
  node.value.data.settings!.selections!.splice(index, 1)
}

function exportCsv() {
  exportRequirementsToCsv(selections.value, 'get-property.csv')
  csvMessage.value = 'CSV exported.'
}

function openCsvImport() {
  csvInput.value?.click()
}

async function importCsv(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]

  if (!file)
    return

  try {
    const importedSelections = await importRequirementsFromCsv(file)
    node.value.data.settings = { ...node.value.data.settings, selections: importedSelections }
    csvMessage.value = `${importedSelections.length} CSV rows imported.`
  }
  catch {
    csvMessage.value = 'CSV import failed.'
  }
  finally {
    input.value = ''
  }
}
</script>

<template>
  <div class="flex flex-col gap-3">
    <div class="px-2">
      <div class="text-sm font-bold text-slate-800 uppercase tracking-wide">
        Get Property
      </div>
      <p class="mt-1 text-xs text-slate-500">
        Read property values from IFC entities. Define which properties to read in the table below.
      </p>
      <p v-if="filterIndexPending" class="mt-1 text-xs text-slate-400">
        Loading IFC 4.3 selection list...
      </p>
      <p v-else-if="filterIndexError" class="mt-1 text-xs text-red-500">
        IFC 4.3 selection list could not be loaded.
      </p>
    </div>

    <div class="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div class="grid grid-cols-[1.8fr_1.8fr_2fr_2.5rem_2.5rem] gap-px bg-slate-200 text-xs font-semibold uppercase tracking-tight text-slate-600">
        <div class="bg-slate-100 px-2 py-2">
          Entity
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Pset
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Property
        </div>
        <div class="bg-slate-100 px-2 py-2" />
        <div class="bg-slate-100 px-2 py-2" />
      </div>

      <div v-if="!selections.length" class="p-6 text-center">
        <p class="text-sm text-slate-500">
          {{ t('node.property.noSelectionsAdded') }}
        </p>
        <p class="mt-1 text-xs text-slate-400">
          {{ t('node.property.clickAddSelection') }}
        </p>
      </div>

      <div v-else class="max-h-80 overflow-y-auto">
        <div
          v-for="(sel, index) in selections"
          :key="index"
          class="grid grid-cols-[1.8fr_1.8fr_2fr_2.5rem_2.5rem] gap-px border-t border-slate-200 bg-slate-200"
        >
          <div class="bg-white p-1">
            <input
              v-model="sel.entity_type"
              :list="`get-property-entities-${index}`"
              :placeholder="t('node.property.anyElement')"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
            >
            <datalist :id="`get-property-entities-${index}`">
              <option value="">
                {{ t('node.property.anyElement') }}
              </option>
              <option
                v-for="entity in entities"
                :key="entity.code"
                :value="entity.code"
                :label="`${entity.ifcCode} - ${entity.name}`"
              />
            </datalist>
          </div>

          <div class="bg-white p-1">
            <input
              v-model="sel.property_set"
              :list="`get-property-psets-${index}`"
              :placeholder="t('node.property.anyPset')"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
            >
            <datalist :id="`get-property-psets-${index}`">
              <option
                v-for="propertySet in getPropertySetsForEntity(sel.entity_type)"
                :key="propertySet.code"
                :value="propertySet.code"
              />
            </datalist>
          </div>

          <div class="bg-white p-1">
            <input
              v-model="sel.property_name"
              :list="`get-property-properties-${index}`"
              :placeholder="t('node.property.required')"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
            >
            <datalist :id="`get-property-properties-${index}`">
              <option
                v-for="name in getPropertyOptions(sel)"
                :key="name"
                :value="name"
              />
            </datalist>
          </div>

          <div class="flex items-center justify-center bg-white p-1">
            <UTooltip :text="t('node.property.duplicateRowTitle')">
              <button
                type="button"
                class="rounded p-1 text-xs text-blue-600 hover:bg-blue-50"
                :aria-label="t('node.property.duplicateRow')"
                :title="t('node.property.duplicateRowTitle')"
                @click="duplicateSelection(index)"
              >
                <Icon name="i-lucide-copy-plus" class="size-4" />
              </button>
            </UTooltip>
          </div>

          <div class="flex items-center justify-center bg-white p-1">
            <UTooltip :text="t('node.property.removeRow')">
              <button
                type="button"
                class="rounded p-1 text-xs text-red-600 hover:bg-red-50"
                :aria-label="t('node.property.removeRow')"
                :title="t('node.property.removeRow')"
                @click="removeSelection(index)"
              >
                <Icon name="i-lucide-trash-2" class="size-4" />
              </button>
            </UTooltip>
          </div>
        </div>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <button
        type="button"
        class="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100"
        @click="addSelection"
      >
        {{ t('node.property.addSelection') }}
      </button>
      <button
        type="button"
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        @click="openCsvImport"
      >
        {{ t('node.property.importCsv') }}
      </button>
      <button
        type="button"
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        @click="exportCsv"
      >
        {{ t('node.property.exportCsv') }}
      </button>
      <span v-if="csvMessage" class="text-xs text-slate-500">
        {{ csvMessage }}
      </span>
      <input
        ref="csvInput"
        type="file"
        accept=".csv,text/csv"
        class="hidden"
        @change="importCsv"
      >
    </div>

    <div class="px-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">{{ t('node.property.outputMode') }}</label>
      <UTooltip text="Output granularity: 'Per explicit element' (Output structured on the level of explicit individual elements), 'Per element class' (Output structured on the level of element classes), or 'Without element class distinction' (Output without distinction of element classes).">
        <select
          v-model="node.data.settings!.output_mode"
          class="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800"
        >
          <option
            v-for="mode in outputModes"
            :key="mode.value"
            :value="mode.value"
          >
            {{ mode.label }}
          </option>
        </select>
      </UTooltip>
    </div>
  </div>
</template>
