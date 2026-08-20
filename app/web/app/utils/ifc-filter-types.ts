// Shared IFC 4.3 filter-index types, used by the IfcElementFilter,
// GetProperty and PropertyComparison nodes. This is the single source of
// truth; node-specific types.ts re-export from here instead of re-declaring.

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
