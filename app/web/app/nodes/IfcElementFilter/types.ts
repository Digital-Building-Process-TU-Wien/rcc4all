import type { SchemaNodeType } from '~/utils/schema-helpers'

export type IfcElementFilterNode = SchemaNodeType<'ifc_element_filter'>
export type FilterRows = NonNullable<NonNullable<IfcElementFilterNode['data']['settings']>['filter_rows']>
export type FilterRow = FilterRows[number]
export type FilterRowKey = keyof FilterRow
export type FilterRowMode = NonNullable<FilterRow['mode']>
export type FilterRowOperator = NonNullable<FilterRow['operator']>

// IFC filter-index types are shared across nodes (see ~/utils/ifc-filter-types)
export type {
  IfcAllowedValue,
  IfcFilterEntity,
  IfcFilterIndex,
  IfcFilterProperty,
  IfcFilterPropertySet,
} from '~/utils/ifc-filter-types'
