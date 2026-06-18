import type { SchemaNodeType } from '~/utils/schema-helpers'

export type IfcElementFilterNode = SchemaNodeType<'ifc_element_filter'>
export type FilterRows = NonNullable<NonNullable<IfcElementFilterNode['data']['settings']>['filter_rows']>
export type FilterRow = FilterRows[number]
export type FilterRowKey = keyof FilterRow
export type FilterRowMode = NonNullable<FilterRow['mode']>
export type FilterRowOperator = NonNullable<FilterRow['operator']>

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
