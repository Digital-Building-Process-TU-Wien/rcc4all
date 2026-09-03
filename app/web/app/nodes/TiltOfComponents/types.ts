import type { SchemaNodeType } from '~/utils/schema-helpers'

export type TiltOfComponentsNode = SchemaNodeType<'tilt_of_components'>
export type TiltOfComponentsSettings = NonNullable<TiltOfComponentsNode['data']['settings']>
export type ElementCategory = TiltOfComponentsSettings['element_category']
export type ComparisonMethod = TiltOfComponentsSettings['comparison_method']

export const ELEMENT_CATEGORY_OPTIONS: Array<{ value: ElementCategory, label: string }> = [
  { value: '2d', label: '2D — walls & slabs (surfaces)' },
  { value: '1d', label: '1D — columns & beams (axis)' },
]

export const COMPARISON_METHOD_OPTIONS: Array<{ value: ComparisonMethod, label: string }> = [
  { value: 'greater_than_lower', label: 'Greater than lower limit' },
  { value: 'less_than_upper', label: 'Less than upper limit' },
  { value: 'inside_interval', label: 'Inside interval' },
  { value: 'outside_interval', label: 'Outside interval' },
]

export function requiresLowerLimit(method: ComparisonMethod | undefined): boolean {
  return method === 'greater_than_lower'
}

export function requiresUpperLimit(method: ComparisonMethod | undefined): boolean {
  return method === 'less_than_upper'
}

export function requiresInterval(method: ComparisonMethod | undefined): boolean {
  return method === 'inside_interval' || method === 'outside_interval'
}
