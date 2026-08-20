import type { SchemaNodeType } from '~/utils/schema-helpers'

export type PropertyComparisonNode = SchemaNodeType<'property_comparison'>
export type PropertyComparisonSettings = NonNullable<PropertyComparisonNode['data']['settings']>
export type Rows = NonNullable<PropertyComparisonSettings['rows']>
export type ComparisonRow = Rows[number]
export type ComparisonCondition = ComparisonRow['condition']

export const CONDITION_OPTIONS: Array<{ value: ComparisonCondition, label: string }> = [
  { value: 'equals', label: 'equals (=)' },
  { value: 'not_equals', label: 'not equals (≠)' },
  { value: 'lt', label: 'less than (<)' },
  { value: 'le', label: 'less or equal (≤)' },
  { value: 'gt', label: 'greater than (>)' },
  { value: 'ge', label: 'greater or equal (≥)' },
  { value: 'contains', label: 'contains' },
  { value: 'one_of', label: 'one of (∈)' },
  { value: 'between', label: 'between' },
  { value: 'outside', label: 'outside' },
  { value: 'is_true', label: 'is true' },
  { value: 'is_false', label: 'is false' },
]

export function isValidCondition(value: string | undefined): boolean {
  return CONDITION_OPTIONS.some(option => option.value === value)
}

export const CONDITION_LIST = CONDITION_OPTIONS.map(option => option.value).join(', ')

export function requiresExpectedValue(condition: ComparisonCondition | undefined): boolean {
  return condition === 'equals'
    || condition === 'not_equals'
    || condition === 'lt'
    || condition === 'le'
    || condition === 'gt'
    || condition === 'ge'
    || condition === 'contains'
}

export function isRangeCondition(condition: ComparisonCondition | undefined): boolean {
  return condition === 'between' || condition === 'outside'
}

export function isOneOfCondition(condition: ComparisonCondition | undefined): boolean {
  return condition === 'one_of'
}

// IFC filter-index types are shared across nodes (see ~/utils/ifc-filter-types)
export type {
  IfcAllowedValue,
  IfcFilterEntity,
  IfcFilterIndex,
  IfcFilterProperty,
  IfcFilterPropertySet,
} from '~/utils/ifc-filter-types'
