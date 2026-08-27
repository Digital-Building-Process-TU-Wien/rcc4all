<script setup lang="ts">
import type {
  ComparisonRow,
  IfcFilterEntity,
  IfcFilterIndex,
  IfcFilterProperty,
  IfcFilterPropertySet,
  LoiCheckNode,
} from './types'
import { useScopedNode } from '~/composables/useScopedNode'
import { CONDITION_OPTIONS, isOneOfCondition, isRangeCondition, requiresExpectedValue } from './types'
import { exportRowsToCsv, importRowsFromCsv } from './utils/csv-import-export'
import { hasEnumValues, isBooleanType, isNumericType, resolvePropertyType } from './utils/property-type'

interface Props {
  node: LoiCheckNode
}

const props = defineProps<Props>()
const node = useScopedNode<LoiCheckNode>(props.node.id)
const { t } = useI18n()
const csvInput = ref<HTMLInputElement | null>(null)
const csvMessage = ref('')

const { data: filterIndex, error: filterIndexError, pending: filterIndexPending } = useFetch<IfcFilterIndex>(
  '/list/ifc-4.3-filter-index.json',
  { default: () => ({ entities: [] }) },
)

const entities = computed(() => filterIndex.value?.entities ?? [])
const rows = computed(() => node.value.data.settings?.rows ?? [])
const conditions = CONDITION_OPTIONS

// Build a deduplicated global property index (code → dataType + allowedValues)
const globalProperties = computed(() => {
  const map = new Map<string, { dataType: string, psets: Set<string> }>()
  const allEntities = filterIndex.value?.entities ?? []
  for (const entity of allEntities) {
    for (const pset of entity.propertySets) {
      for (const prop of pset.properties) {
        const existing = map.get(prop.code)
        if (!existing)
          map.set(prop.code, { dataType: prop.dataType, psets: new Set([pset.code]) })
        else
          existing.psets.add(pset.code)
      }
    }
  }
  return map
})

// All unique property codes for autocomplete
const allPropertyNames = computed(() => Array.from(globalProperties.value.keys()).sort())

if (!node.value.data.settings)
  node.value.data.settings = { rows: [] }

if (!node.value.data.settings.rows)
  node.value.data.settings.rows = []

for (const row of node.value.data.settings.rows) {
  if (!Array.isArray(row.allowed_values))
    (row as ComparisonRow).allowed_values = ['']
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
    if (!uniqueMap.has(pset.code))
      uniqueMap.set(pset.code, pset)
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

function getPropertyOptions(row: ComparisonRow): string[] {
  if (row.property_set)
    return getPropertiesForPropertySet(row.entity_type, row.property_set).map(property => property.code).sort((a, b) => a.localeCompare(b))
  return allPropertyNames.value
}

const booleanOptions = [
  { value: 'true', label: 'True', labelKey: 'node.property.true' },
  { value: 'false', label: 'False', labelKey: 'node.property.false' },
]

const decimalTooltip = computed(() => t('node.loiCheck.decimalTooltip'))

function resolvedType(row: ComparisonRow) {
  return resolvePropertyType(filterIndex.value, row)
}

function enumValueOptions(row: ComparisonRow): Array<{ value: string, description?: string }> {
  return resolvedType(row).allowedValues.map(option => ({
    value: option.value ?? option.code,
    description: option.description,
  }))
}

function showTargetValue(row: ComparisonRow): boolean {
  return requiresExpectedValue(row.condition)
}

function hasTargetSuggestions(row: ComparisonRow): boolean {
  return isBooleanType(resolvedType(row)) || hasEnumValues(resolvedType(row))
}

function addRow() {
  node.value.data.settings!.rows!.push({
    entity_type: '',
    property_set: '',
    property_name: '',
    condition: 'equals',
    expected_value: '',
    allowed_values: [''],
    range_min: '',
    range_max: '',
    inclusive_min: true,
    inclusive_max: true,
  })
}

function ensureValueEditSlot(row: ComparisonRow) {
  const values = row.allowed_values ??= ['']
  if (values.length === 0 || values.at(-1) !== '')
    values.push('')
}

function onValueInput(row: ComparisonRow) {
  ensureValueEditSlot(row)
}

function updateAllowedValue(row: ComparisonRow, index: number, event: Event) {
  const values = row.allowed_values ??= ['']
  values[index] = (event.target as HTMLInputElement).value
  onValueInput(row)
}

function removeAllowedValue(row: ComparisonRow, index: number) {
  const values = row.allowed_values ??= ['']
  values.splice(index, 1)
  ensureValueEditSlot(row)
}

function duplicateRow(index: number) {
  const original = node.value.data.settings!.rows![index]
  if (!original)
    return
  // Copy the row including a fresh allowed_values array so the two rows do not
  // share the same array reference (previously editing one mutated the other).
  node.value.data.settings!.rows!.splice(index + 1, 0, {
    ...original,
    allowed_values: [...(original.allowed_values ?? [])],
  })
}

function removeRow(index: number) {
  node.value.data.settings!.rows!.splice(index, 1)
}

function exportCsv() {
  exportRowsToCsv(rows.value, 'loi-check.csv')
  csvMessage.value = t('node.csv.exported')
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
    const importedRows = await importRowsFromCsv(file)
    node.value.data.settings = { ...node.value.data.settings, rows: importedRows }
    csvMessage.value = t('node.csv.rowsImported', { count: importedRows.length })
  }
  catch (error) {
    csvMessage.value = error instanceof Error ? error.message : t('node.csv.importFailed')
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
        {{ t('node.loiCheck.title') }}
      </div>
      <p class="mt-1 text-xs text-slate-500">
        {{ t('node.loiCheck.description') }}
      </p>
      <p v-if="filterIndexPending" class="mt-1 text-xs text-slate-400">
        {{ t('node.ifc.loadingIndex') }}
      </p>
      <p v-else-if="filterIndexError" class="mt-1 text-xs text-red-500">
        {{ t('node.ifc.loadFailed') }}
      </p>
    </div>

    <div class="overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div class="grid grid-cols-[1.5fr_1.5fr_1.8fr_1.5fr_1.4fr_2.5rem_2.5rem] gap-px bg-slate-200 text-xs font-semibold uppercase tracking-tight text-slate-600">
        <div class="bg-slate-100 px-2 py-2">
          {{ t('node.loiCheck.componentHeader') }}
        </div>
        <div class="bg-slate-100 px-2 py-2">
          {{ t('node.loiCheck.psetHeader') }}
        </div>
        <div class="bg-slate-100 px-2 py-2">
          {{ t('node.loiCheck.propertyHeader') }}
        </div>
        <div class="bg-slate-100 px-2 py-2">
          {{ t('node.loiCheck.conditionHeader') }}
        </div>
        <div class="bg-slate-100 px-2 py-2">
          {{ t('node.loiCheck.targetValueHeader') }}
        </div>
        <div class="bg-slate-100 px-2 py-2" />
        <div class="bg-slate-100 px-2 py-2" />
      </div>

      <div v-if="!rows.length" class="p-6 text-center">
        <p class="text-sm text-slate-500">
          {{ t('node.loiCheck.noRulesAdded') }}
        </p>
        <p class="mt-1 text-xs text-slate-400">
          {{ t('node.loiCheck.clickAddRow') }}
        </p>
      </div>

      <div v-else class="max-h-80 overflow-y-auto">
        <div
          v-for="(row, index) in rows"
          :key="index"
          class="grid grid-cols-[1.5fr_1.5fr_1.8fr_1.5fr_1.4fr_2.5rem_2.5rem] gap-px border-t border-slate-200 bg-slate-200"
        >
          <div class="bg-white p-1">
            <input
              v-model="row.entity_type"
              :list="`property-comparison-entities-${index}`"
              :placeholder="t('node.property.anyElement')"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
            >
            <datalist :id="`property-comparison-entities-${index}`">
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
              v-model="row.property_set"
              :list="`property-comparison-psets-${index}`"
              :placeholder="t('node.property.anyPset')"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
            >
            <datalist :id="`property-comparison-psets-${index}`">
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
              :list="`property-comparison-properties-${index}`"
              :placeholder="t('node.property.required')"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
            >
            <datalist :id="`property-comparison-properties-${index}`">
              <option
                v-for="name in getPropertyOptions(row)"
                :key="name"
                :value="name"
              />
            </datalist>
          </div>

          <div class="bg-white p-1">
            <select
              v-model="row.condition"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
            >
              <option
                v-for="condition in conditions"
                :key="condition.value"
                :value="condition.value"
              >
                {{ t(`node.loiCheck.condition.${condition.value}`) }}
              </option>
            </select>
          </div>

          <div class="bg-white p-1">
            <template v-if="isRangeCondition(row.condition)">
              <div class="flex items-center gap-1">
                <UTooltip :text="decimalTooltip" class="w-full">
                  <input
                    v-model="row.range_min"
                    type="text"
                    inputmode="decimal"
                    :placeholder="t('node.loiCheck.min')"
                    class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
                  >
                </UTooltip>
                <UTooltip :text="decimalTooltip" class="w-full">
                  <input
                    v-model="row.range_max"
                    type="text"
                    inputmode="decimal"
                    :placeholder="t('node.loiCheck.max')"
                    class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
                  >
                </UTooltip>
              </div>
              <div class="mt-1 flex items-center gap-2 text-xs text-slate-600">
                <label class="flex items-center gap-1">
                  <input v-model="row.inclusive_min" type="checkbox" class="accent-slate-600">
                  {{ t('node.property.inclMin') }}
                </label>
                <label class="flex items-center gap-1">
                  <input v-model="row.inclusive_max" type="checkbox" class="accent-slate-600">
                  {{ t('node.property.inclMax') }}
                </label>
              </div>
            </template>

            <template v-else-if="isOneOfCondition(row.condition)">
              <div class="space-y-1">
                <div
                  v-for="(_, valueIndex) in row.allowed_values"
                  :key="valueIndex"
                  class="flex items-center gap-1"
                >
                  <input
                    :value="row.allowed_values?.[valueIndex]"
                    :list="hasEnumValues(resolvedType(row)) ? `property-comparison-oneof-${index}` : undefined"
                    :placeholder="t('node.property.value')"
                    class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
                    @input="updateAllowedValue(row, valueIndex, $event)"
                    @keyup.enter="ensureValueEditSlot(row)"
                  >
                  <button
                    type="button"
                    class="shrink-0 rounded p-0.5 text-xs text-red-600 hover:bg-red-50"
                    :aria-label="t('node.property.removeValue')"
                    :title="t('node.property.removeValue')"
                    @click="removeAllowedValue(row, valueIndex)"
                  >
                    <Icon name="i-lucide-x" class="size-3.5" />
                  </button>
                </div>
                <datalist v-if="hasEnumValues(resolvedType(row))" :id="`property-comparison-oneof-${index}`">
                  <option
                    v-for="option in enumValueOptions(row)"
                    :key="option.value"
                    :value="option.value"
                    :label="option.description || undefined"
                  />
                </datalist>
              </div>
            </template>

            <template v-else-if="showTargetValue(row)">
              <UTooltip :text="isNumericType(resolvedType(row)) ? decimalTooltip : undefined" class="w-full">
                <input
                  v-model="row.expected_value"
                  :list="hasTargetSuggestions(row) ? `property-comparison-targets-${index}` : undefined"
                  :placeholder="t('node.property.value')"
                  class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
                >
              </UTooltip>
              <datalist v-if="hasTargetSuggestions(row)" :id="`property-comparison-targets-${index}`">
                <template v-if="isBooleanType(resolvedType(row))">
                  <option
                    v-for="option in booleanOptions"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ t(option.labelKey) }}
                  </option>
                </template>
                <template v-else-if="hasEnumValues(resolvedType(row))">
                  <option
                    v-for="option in enumValueOptions(row)"
                    :key="option.value"
                    :value="option.value"
                    :label="option.description || undefined"
                  />
                </template>
              </datalist>
            </template>

            <input
              v-else
              v-model="row.expected_value"
              disabled
              placeholder="—"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800 disabled:bg-slate-50 disabled:text-slate-400"
            >
          </div>

          <div class="flex items-center justify-center bg-white p-1">
            <UTooltip :text="t('node.property.duplicateRowTitle')">
              <button
                type="button"
                class="rounded p-1 text-xs text-blue-600 hover:bg-blue-50"
                :aria-label="t('node.property.duplicateRow')"
                :title="t('node.property.duplicateRowTitle')"
                @click="duplicateRow(index)"
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
                @click="removeRow(index)"
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
        @click="addRow"
      >
        {{ t('node.property.addRow') }}
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
  </div>
</template>
