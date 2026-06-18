<script setup lang="ts">
import type { FilterRow, FilterRowOperator, FilterRows, IfcElementFilterNode, IfcFilterEntity, IfcFilterIndex, IfcFilterProperty, IfcFilterPropertySet } from './types'
import { useScopedNode } from '~/composables/useScopedNode'
import { exportFilterRowsToCsv, importFilterRowsFromCsv } from './utils/csv-import-export'

interface Props {
  node: IfcElementFilterNode
}

const props = defineProps<Props>()
const node = useScopedNode<IfcElementFilterNode>(props.node.id)
const csvInput = ref<HTMLInputElement | null>(null)
const csvMessage = ref('')

const { data: filterIndex, error: filterIndexError, pending: filterIndexPending } = useFetch<IfcFilterIndex>(
  '/list/ifc-4.3-filter-index.json',
  { default: () => ({ entities: [] }) },
)

const entities = computed(() => filterIndex.value?.entities ?? [])
const filterRows = computed(() => node.value.data.settings?.filter_rows ?? [])

const operators: FilterRowOperator[] = [
  '==',
  '!=',
  '<',
  '>',
  '<=',
  '>=',
  'contains',
  'starts_with',
  'ends_with',
]

if (!node.value.data.settings)
  node.value.data.settings = { filter_rows: [] }

function getFilterRows(): FilterRows {
  if (!node.value.data.settings)
    node.value.data.settings = { filter_rows: [] }

  if (!node.value.data.settings.filter_rows)
    node.value.data.settings.filter_rows = []

  return node.value.data.settings.filter_rows
}

function createEmptyRow(): FilterRow {
  return {
    mode: 'include',
    entity_type: '',
    predefined_type: '',
    property_set: '',
    property_name: '',
    operator: '==',
    value: '',
  }
}

function addRow() {
  getFilterRows().push(createEmptyRow())
}

function removeRow(index: number) {
  getFilterRows().splice(index, 1)
}

function getEntity(entityType: string | undefined): IfcFilterEntity | undefined {
  if (!entityType)
    return undefined

  return entities.value.find(entity => entity.code === entityType.toUpperCase())
}

function getPredefinedTypesForEntity(entityType: string | undefined) {
  return getEntity(entityType)?.predefinedTypes ?? []
}

function uniqueByCode<T extends { code: string }>(items: T[]): T[] {
  return [...new Map(items.map(item => [item.code, item])).values()]
    .sort((a, b) => a.code.localeCompare(b.code))
}

function getPropertySetsForEntity(entityType: string | undefined): IfcFilterPropertySet[] {
  const entity = getEntity(entityType)
  if (entity)
    return entity.propertySets

  if (entityType)
    return []

  return uniqueByCode(entities.value.flatMap(candidate => candidate.propertySets))
}

function getPropertySetForRow(row: FilterRow): IfcFilterPropertySet | undefined {
  return getPropertySetsForEntity(row.entity_type)
    .find(propertySet => propertySet.code === row.property_set)
}

function getPropertiesForRow(row: FilterRow): IfcFilterProperty[] {
  const propertySet = getPropertySetForRow(row)
  if (propertySet)
    return propertySet.properties

  const propertySets = getPropertySetsForEntity(row.entity_type)
  if (row.property_set) {
    return uniqueByCode(
      propertySets
        .filter(candidate => candidate.code === row.property_set)
        .flatMap(candidate => candidate.properties),
    )
  }

  return uniqueByCode(propertySets.flatMap(candidate => candidate.properties))
}

function getPropertyForRow(row: FilterRow): IfcFilterProperty | undefined {
  if (!row.property_name)
    return undefined

  return getPropertiesForRow(row)
    .find(property => property.code === row.property_name)
}

function isBooleanProperty(property: IfcFilterProperty | undefined): boolean {
  return property?.dataType.toLowerCase() === 'boolean'
}

function isNumberProperty(property: IfcFilterProperty | undefined): boolean {
  const dataType = property?.dataType.toLowerCase() ?? ''
  return ['integer', 'number', 'real'].includes(dataType)
}

function isAllowedValue(row: FilterRow, property: IfcFilterProperty): boolean {
  return property.allowedValues.some(allowedValue => allowedValue.value === row.value)
}

function clearInvalidValue(row: FilterRow) {
  const property = getPropertyForRow(row)
  if (!property)
    return

  if (property.allowedValues.length && row.value && !isAllowedValue(row, property)) {
    row.value = ''
    return
  }

  if (isBooleanProperty(property) && row.value && !['true', 'false'].includes(row.value.toLowerCase())) {
    row.value = ''
    return
  }

  if (isNumberProperty(property) && row.value && Number.isNaN(Number(row.value))) {
    row.value = ''
  }
}

function updatePropertyName(row: FilterRow) {
  clearInvalidValue(row)
}

function updatePropertySet(row: FilterRow) {
  updatePropertyName(row)
}

function updateEntityType(row: FilterRow) {
  row.entity_type = (row.entity_type ?? '').toUpperCase()
  if (!row.entity_type)
    return

  const entity = getEntity(row.entity_type)
  if (!entity) {
    row.entity_type = ''
    return
  }

  row.entity_type = entity.code
}

function updatePredefinedType(row: FilterRow) {
  row.predefined_type = (row.predefined_type ?? '').toUpperCase()
}

function exportCsv() {
  exportFilterRowsToCsv(filterRows.value, 'ifc-element-filter.csv')
  csvMessage.value = 'CSV exportiert.'
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
    const importedRows = await importFilterRowsFromCsv(file)
    node.value.data.settings = { ...node.value.data.settings, filter_rows: importedRows }
    csvMessage.value = `${importedRows.length} CSV-Zeilen importiert.`
  }
  catch {
    csvMessage.value = 'CSV konnte nicht importiert werden.'
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
        IfcElementFilter
      </div>
      <p class="mt-1 text-xs text-slate-500">
        Filter IFC entities by class, PredefinedType, attributes, and PropertySets.
      </p>
      <p v-if="filterIndexPending" class="mt-1 text-xs text-slate-400">
        Loading IFC 4.3 selection list...
      </p>
      <p v-else-if="filterIndexError" class="mt-1 text-xs text-red-500">
        IFC 4.3 selection list could not be loaded.
      </p>
    </div>

    <div class="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div class="grid grid-cols-8 gap-px bg-slate-200 text-xs font-semibold uppercase tracking-tight text-slate-600">
        <div class="bg-slate-100 px-2 py-2">
          Mode
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Entity
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Predef.
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Pset
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Property
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Op
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Value
        </div>
        <div class="bg-slate-100 px-2 py-2" />
      </div>

      <div v-if="!filterRows.length" class="p-6 text-center">
        <p class="text-sm text-slate-500">
          No filter rows added
        </p>
        <p class="mt-1 text-xs text-slate-400">
          Click Add Filter Row to start filtering.
        </p>
      </div>

      <div v-else class="max-h-80 overflow-y-auto">
        <div
          v-for="(row, index) in filterRows"
          :key="index"
          class="grid grid-cols-8 gap-px border-t border-slate-200 bg-slate-200"
        >
          <div class="bg-white p-1">
            <select v-model="row.mode" class="w-full rounded border border-slate-200 bg-white px-1 py-1 text-xs text-slate-800">
              <option value="include">
                Include
              </option>
              <option value="exclude">
                Exclude
              </option>
              <option value="disabled">
                Disabled
              </option>
            </select>
          </div>

          <div class="bg-white p-1">
            <input
              v-model="row.entity_type"
              list="ifc-element-filter-entities"
              placeholder="Any"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
              @change="updateEntityType(row)"
              @blur="updateEntityType(row)"
            >
          </div>

          <div class="bg-white p-1">
            <input
              v-model="row.predefined_type"
              :list="`ifc-element-filter-predefined-${index}`"
              placeholder="Any"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
              @change="updatePredefinedType(row)"
              @blur="updatePredefinedType(row)"
            >
            <datalist :id="`ifc-element-filter-predefined-${index}`">
              <option
                v-for="predefinedType in getPredefinedTypesForEntity(row.entity_type)"
                :key="predefinedType.code"
                :label="predefinedType.name"
                :value="predefinedType.code"
              />
            </datalist>
          </div>

          <div class="bg-white p-1">
            <input
              v-model="row.property_set"
              :list="`ifc-element-filter-psets-${index}`"
              placeholder="Optional"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
              @change="updatePropertySet(row)"
              @blur="updatePropertySet(row)"
            >
            <datalist :id="`ifc-element-filter-psets-${index}`">
              <option
                v-for="propertySet in getPropertySetsForEntity(row.entity_type)"
                :key="propertySet.code"
                :value="propertySet.code"
              />
            </datalist>
          </div>

          <div class="bg-white p-1">
            <input
              v-model="row.property_name"
              :list="`ifc-element-filter-properties-${index}`"
              placeholder="Optional"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
              @change="updatePropertyName(row)"
              @blur="updatePropertyName(row)"
            >
            <datalist :id="`ifc-element-filter-properties-${index}`">
              <option
                v-for="property in getPropertiesForRow(row)"
                :key="property.code"
                :label="property.code"
                :value="property.code"
              />
            </datalist>
          </div>

          <div class="bg-white p-1">
            <select v-model="row.operator" class="w-full rounded border border-slate-200 bg-white px-1 py-1 text-xs text-slate-800">
              <option v-for="operator in operators" :key="operator" :value="operator">
                {{ operator }}
              </option>
            </select>
          </div>

          <div class="bg-white p-1">
            <select
              v-if="getPropertyForRow(row)?.allowedValues.length"
              v-model="row.value"
              class="w-full rounded border border-slate-200 bg-white px-1 py-1 text-xs text-slate-800"
            >
              <option value="">
                Any
              </option>
              <option
                v-for="allowedValue in getPropertyForRow(row)?.allowedValues"
                :key="allowedValue.value"
                :value="allowedValue.value"
              >
                {{ allowedValue.value }}
              </option>
            </select>
            <select
              v-else-if="isBooleanProperty(getPropertyForRow(row))"
              v-model="row.value"
              class="w-full rounded border border-slate-200 bg-white px-1 py-1 text-xs text-slate-800"
            >
              <option value="">
                Any
              </option>
              <option value="true">
                true
              </option>
              <option value="false">
                false
              </option>
            </select>
            <input
              v-else-if="isNumberProperty(getPropertyForRow(row))"
              v-model="row.value"
              type="number"
              placeholder="Value"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
            >
            <input
              v-else
              v-model="row.value"
              placeholder="Value"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
            >
          </div>

          <div class="flex items-center justify-center bg-white p-1">
            <button
              type="button"
              class="rounded px-2 py-1 text-xs text-red-600 hover:bg-red-50"
              title="Remove row"
              @click="removeRow(index)"
            >
              Remove
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <button
        type="button"
        class="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100"
        @click="addRow"
      >
        Add Filter Row
      </button>
      <button
        type="button"
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        @click="openCsvImport"
      >
        Import CSV
      </button>
      <button
        type="button"
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        @click="exportCsv"
      >
        Export CSV
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

    <div class="border-t border-slate-200 pt-3">
      <label class="mb-2 block text-xs font-semibold uppercase tracking-tight text-slate-500">Outputs</label>
      <div class="flex flex-wrap gap-2">
        <span class="rounded-full bg-green-50 px-2 py-1 text-xs font-medium text-green-700">express_ids</span>
        <span class="rounded-full bg-green-50 px-2 py-1 text-xs font-medium text-green-700">guids</span>
      </div>
    </div>

    <datalist id="ifc-element-filter-entities">
      <option
        v-for="entity in entities"
        :key="entity.code"
        :label="entity.ifcCode"
        :value="entity.code"
      />
    </datalist>
  </div>
</template>
