<script setup lang="ts">
import type { SchemaNodeType } from '~/utils/schema-helpers'
import { useScopedNode } from '~/composables/useScopedNode'
import { exportRequirementsToCsv, importRequirementsFromCsv } from './utils/csv-import-export'

type GetPropertyNode = SchemaNodeType<'get_property'>

interface Props {
  node: GetPropertyNode
}

const props = defineProps<Props>()
const node = useScopedNode<GetPropertyNode>(props.node.id)
const csvInput = ref<HTMLInputElement | null>(null)
const csvMessage = ref('')

interface IfcAllowedValue {
  code: string
  value: string
  description: string
}

interface IfcFilterProperty {
  code: string
  name: string
  definition: string
  dataType: string
  propertyValueKind: string
  allowedValues: IfcAllowedValue[]
}

interface IfcFilterPropertySet {
  code: string
  properties: IfcFilterProperty[]
}

interface IfcFilterEntity {
  code: string
  ifcCode: string
  name: string
  definition: string
  parentClassCode: string
  predefinedTypes: Array<{
    code: string
    name: string
    definition: string
  }>
  propertySets: IfcFilterPropertySet[]
}

interface IfcFilterIndex {
  entities: IfcFilterEntity[]
}

const { data: filterIndex, error: filterIndexError, pending: filterIndexPending } = useFetch<IfcFilterIndex>(
  '/list/ifc-4.3-filter-index.json',
  { default: () => ({ entities: [] }) },
)

const entities = computed(() => filterIndex.value?.entities ?? [])
const selections = computed(() => node.value.data.settings?.selections ?? [])

// Build a deduplicated global property index (code → dataType + allowedValues)
// Each property code maps to exactly one dataType and one allowed-values set across all entities/psets.
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
    output_mode: 'model',
    selections: [],
  }
}

if (!node.value.data.settings.selections) {
  node.value.data.settings.selections = []
}

if (!node.value.data.settings.output_mode) {
  node.value.data.settings.output_mode = 'model'
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
  // When a PSet is selected, restrict to that PSet's properties
  if (sel.property_set) {
    return getPropertiesForPropertySet(sel.entity_type, sel.property_set)
      .map(property => property.code)
      .sort((a, b) => a.localeCompare(b))
  }
  // No PSet selected → show all unique properties (existing behavior)
  return allPropertyNames.value
}

function getPropertyForSelection(sel: PropertySelection): IfcFilterProperty | undefined {
  if (!sel.property_name)
    return undefined

  // First try to find via entity + pset (existing behavior)
  const psetScoped = getPropertiesForPropertySet(sel.entity_type, sel.property_set)
    .find(property => property.code === sel.property_name)
  if (psetScoped)
    return psetScoped

  // Fallback: resolve from global index by property code alone (works without entity/pset)
  const global = globalProperties.value.get(sel.property_name)
  if (global) {
    return {
      code: sel.property_name,
      name: sel.property_name,
      definition: '',
      dataType: global.dataType,
      propertyValueKind: global.allowedValues.length ? 'List' : 'Single',
      allowedValues: global.allowedValues,
    }
  }

  return undefined
}

function isBooleanProperty(property: IfcFilterProperty | undefined): boolean {
  return property?.dataType.toLowerCase() === 'boolean'
}

function isNumberProperty(property: IfcFilterProperty | undefined): boolean {
  const dataType = property?.dataType.toLowerCase() ?? ''
  return ['integer', 'real', 'number'].includes(dataType)
}

function clearInvalidValue(sel: PropertySelection) {
  const property = getPropertyForSelection(sel)
  if (!property)
    return

  if (property.allowedValues.length && sel.manual_value && !property.allowedValues.some(av => av.value === sel.manual_value)) {
    sel.manual_value = ''
    return
  }

  if (isBooleanProperty(property) && sel.manual_value && !['true', 'false'].includes(sel.manual_value.toLowerCase())) {
    sel.manual_value = ''
    return
  }

  if (isNumberProperty(property) && sel.manual_value && Number.isNaN(Number(sel.manual_value))) {
    sel.manual_value = ''
  }
}

function addSelection() {
  node.value.data.settings!.selections!.push({
    entity_type: '',
    property_set: '',
    property_name: '',
    source: 'from_model',
    manual_value: '',
    condition_operator: '>',
    condition_value: '',
  })
}

function duplicateSelection(index: number) {
  const original = node.value.data.settings!.selections![index]
  node.value.data.settings!.selections!.splice(index + 1, 0, { ...original })
}

function removeSelection(index: number) {
  node.value.data.settings!.selections!.splice(index, 1)
}

function updatePropertySelection(sel: PropertySelection) {
  clearInvalidValue(sel)
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

watch(() => node.value.data.input_bindings?.express_ids, (binding) => {
  if (binding && !binding.includes('.')) {
    node.value.data.input_bindings = {
      ...node.value.data.input_bindings,
      express_ids: `${binding}.express_ids`,
    }
  }
})

// Auto-switch output mode based on input binding and entity selection
const hasInputBinding = computed(() => !!node.value.data.input_bindings?.express_ids)

const hasAnyEntity = computed(() =>
  (node.value.data.settings?.selections ?? []).some(sel => sel.entity_type?.trim()))

const recommendedOutputMode = computed(() =>
  hasInputBinding.value
    ? 'elements'
    : hasAnyEntity.value
      ? 'by_class'
      : 'model')

watch([hasInputBinding, hasAnyEntity], () => {
  if (node.value.data.settings?.output_mode !== recommendedOutputMode.value) {
    node.value.data.settings = { ...node.value.data.settings, output_mode: recommendedOutputMode.value }
  }
})
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
      <div class="grid grid-cols-[1.2fr_1.8fr_1.8fr_1.3fr_1.3fr_2.5rem_2.5rem] gap-px bg-slate-200 text-xs font-semibold uppercase tracking-tight text-slate-600">
        <div class="bg-slate-100 px-2 py-2">
          Entity
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Pset
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Property
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Value Source
        </div>
        <div class="bg-slate-100 px-2 py-2">
          Manual Value
        </div>
        <div class="bg-slate-100 px-2 py-2" />
        <div class="bg-slate-100 px-2 py-2" />
      </div>

      <div v-if="!selections.length" class="p-6 text-center">
        <p class="text-sm text-slate-500">
          No selections added
        </p>
        <p class="mt-1 text-xs text-slate-400">
          Click Add Selection to start defining a property, or read it from the model via the input.
        </p>
      </div>

      <div v-else class="max-h-80 overflow-y-auto">
        <div
          v-for="(sel, index) in selections"
          :key="index"
          class="grid grid-cols-[1.2fr_1.8fr_1.8fr_1.3fr_1.3fr_2.5rem_2.5rem] gap-px border-t border-slate-200 bg-slate-200"
        >
          <div class="bg-white p-1">
            <input
              v-model="sel.entity_type"
              :list="`get-property-entities-${index}`"
              placeholder="Any Element"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
              @change="updatePropertySelection(sel)"
            >
            <datalist :id="`get-property-entities-${index}`">
              <option value="">
                Any Element
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
              placeholder="Any PSET"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
              @change="updatePropertySelection(sel)"
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
              placeholder="Required"
              class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
              @change="updatePropertySelection(sel)"
            >
            <datalist :id="`get-property-properties-${index}`">
              <option
                v-for="name in getPropertyOptions(sel)"
                :key="name"
                :value="name"
              />
            </datalist>
          </div>

          <div class="bg-white p-1">
            <UTooltip text="Value Source: 'From model' reads from the IFC entity; 'Fallback' uses manual value if model value is missing or empty; 'Manual' always uses manual value; 'Override if condition' uses manual value when model value meets a numeric or text condition.">
              <select
                v-model="sel.source"
                class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
              >
                <option value="from_model">
                  From model
                </option>
                <option value="fallback">
                  Fallback
                </option>
                <option value="override">
                  Manual
                </option>
                <option value="condition">
                  Override if condition
                </option>
              </select>
            </UTooltip>
          </div>

          <div class="bg-white p-1">
            <UTooltip v-if="sel.source === 'condition'" text="Override with manual value when model value meets the condition (e.g., > 30).">
              <div class="flex items-center gap-1">
                <select
                  v-model="sel.condition_operator"
                  class="w-20 rounded border border-slate-200 bg-white px-1 py-1 text-xs text-slate-800"
                  @change="updatePropertySelection(sel)"
                >
                  <option value=">">
                    &gt;
                  </option>
                  <option value=">=">
                    ≥
                  </option>
                  <option value="<">
                    &lt;
                  </option>
                  <option value="<=">
                    ≤
                  </option>
                  <option value="==">
                    =
                  </option>
                  <option value="!=">
                    ≠
                  </option>
                </select>
                <input
                  v-model="sel.condition_value"
                  placeholder="Threshold"
                  class="w-24 rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
                  @change="updatePropertySelection(sel)"
                >
                <!-- Type-aware "Switch to" manual value -->
                <select
                  v-if="getPropertyForSelection(sel)?.allowedValues.length"
                  v-model="sel.manual_value"
                  class="flex-1 rounded border border-slate-200 bg-white px-1 py-1 text-xs text-slate-800"
                  @change="updatePropertySelection(sel)"
                >
                  <option value="">
                    Not defined
                  </option>
                  <option
                    v-for="allowedValue in getPropertyForSelection(sel)?.allowedValues"
                    :key="allowedValue.value"
                    :value="allowedValue.value"
                  >
                    {{ allowedValue.value }}
                  </option>
                </select>
                <select
                  v-else-if="isBooleanProperty(getPropertyForSelection(sel))"
                  v-model="sel.manual_value"
                  class="flex-1 rounded border border-slate-200 bg-white px-1 py-1 text-xs text-slate-800"
                  @change="updatePropertySelection(sel)"
                >
                  <option value="">
                    Not defined
                  </option>
                  <option value="true">
                    True
                  </option>
                  <option value="false">
                    False
                  </option>
                </select>
                <input
                  v-else-if="isNumberProperty(getPropertyForSelection(sel))"
                  v-model="sel.manual_value"
                  type="number"
                  placeholder="Switch to"
                  class="flex-1 rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
                  @change="updatePropertySelection(sel)"
                >
                <input
                  v-else
                  v-model="sel.manual_value"
                  placeholder="Switch to"
                  class="flex-1 rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
                  @change="updatePropertySelection(sel)"
                >
              </div>
            </UTooltip>
            <UTooltip v-else text="Value used when Value Source is 'Fallback' or 'Manual'. Required for those sources.">
              <select
                v-if="getPropertyForSelection(sel)?.allowedValues.length && sel.source !== 'from_model'"
                v-model="sel.manual_value"
                class="w-full rounded border border-slate-200 bg-white px-1 py-1 text-xs text-slate-800"
                @change="updatePropertySelection(sel)"
              >
                <option value="">
                  Not defined
                </option>
                <option
                  v-for="allowedValue in getPropertyForSelection(sel)?.allowedValues"
                  :key="allowedValue.value"
                  :value="allowedValue.value"
                >
                  {{ allowedValue.value }}
                </option>
              </select>
              <select
                v-else-if="isBooleanProperty(getPropertyForSelection(sel)) && sel.source !== 'from_model'"
                v-model="sel.manual_value"
                class="w-full rounded border border-slate-200 bg-white px-1 py-1 text-xs text-slate-800"
                @change="updatePropertySelection(sel)"
              >
                <option value="">
                  Not defined
                </option>
                <option value="true">
                  True
                </option>
                <option value="false">
                  False
                </option>
              </select>
              <input
                v-else-if="isNumberProperty(getPropertyForSelection(sel)) && sel.source !== 'from_model'"
                v-model="sel.manual_value"
                type="number"
                placeholder="Not defined"
                class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800"
                @change="updatePropertySelection(sel)"
              >
              <input
                v-else
                v-model="sel.manual_value"
                :disabled="sel.source === 'from_model'"
                placeholder="Required for fallback/override"
                class="w-full rounded border border-slate-200 px-1 py-1 text-xs text-slate-800 disabled:bg-slate-100 disabled:text-slate-400"
              >
            </UTooltip>
          </div>

          <div class="flex items-center justify-center bg-white p-1">
            <UTooltip text="Duplicate this row (copies all fields)">
              <button
                type="button"
                class="rounded p-1 text-xs text-blue-600 hover:bg-blue-50"
                aria-label="Duplicate row"
                title="Duplicate this row (copies all fields)"
                @click="duplicateSelection(index)"
              >
                <Icon name="i-lucide-copy-plus" class="size-4" />
              </button>
            </UTooltip>
          </div>

          <div class="flex items-center justify-center bg-white p-1">
            <UTooltip text="Remove this row">
              <button
                type="button"
                class="rounded p-1 text-xs text-red-600 hover:bg-red-50"
                aria-label="Remove selection"
                title="Remove this row"
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
        Add Selection
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

    <div class="px-2">
      <label class="text-xs font-semibold uppercase tracking-tight text-slate-600">Output mode</label>
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
