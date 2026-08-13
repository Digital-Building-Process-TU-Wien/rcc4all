import type { SchemaNodeType } from '~/utils/schema-helpers'

export type GetPropertyNode = SchemaNodeType<'get_property'>
export type GetPropertySettings = NonNullable<GetPropertyNode['data']['settings']>
export type Requirements = NonNullable<GetPropertySettings['selections']>
export type PropertySelection = Requirements[number]
export type ValueSource = NonNullable<PropertySelection['source']>
export type OutputMode = NonNullable<GetPropertySettings['output_mode']>

// Reuse IFC filter types from IfcElementFilter for property set/entity data
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
