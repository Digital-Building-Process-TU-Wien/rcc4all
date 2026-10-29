import type { SchemaNodeType } from '~/utils/schema-helpers'

export type ComparisonNode = SchemaNodeType<'comparison'>
export type ComparisonSettings = NonNullable<ComparisonNode['data']['settings']>
export type ComparisonCondition = ComparisonSettings['condition']

export const CONDITION_OPTIONS: Array<{ value: ComparisonCondition, label: string }> = [
  { value: 'equals', label: 'equals (=)' },
  { value: 'not_equals', label: 'not equals (≠)' },
  { value: 'lt', label: 'less than (<)' },
  { value: 'le', label: 'less or equal (≤)' },
  { value: 'gt', label: 'greater than (>)' },
  { value: 'ge', label: 'greater or equal (≥)' },
  { value: 'between', label: 'between' },
  { value: 'outside', label: 'outside' },
]

export function requiresTargetValue(condition: ComparisonCondition | undefined): boolean {
  return condition !== undefined && !['between', 'outside'].includes(condition)
}

export function requiresRange(condition: ComparisonCondition | undefined): boolean {
  return condition === 'between' || condition === 'outside'
}
