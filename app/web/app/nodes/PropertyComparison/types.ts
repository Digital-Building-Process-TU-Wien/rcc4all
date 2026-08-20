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

// Reuse IFC filter types from GetProperty for entity/pset/property data
export interface IfcAllowedValue {
  code: string
  value: string
  description: string
}

export interface IfcFilterProperty {
  code: string
  name: string
  definition: string
  dataType: string
  propertyValueKind: string
  allowedValues: IfcAllowedValue[]
}

export interface IfcFilterPropertySet {
  code: string
  properties: IfcFilterProperty[]
}

export interface IfcFilterEntity {
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

export interface IfcFilterIndex {
  entities: IfcFilterEntity[]
}
