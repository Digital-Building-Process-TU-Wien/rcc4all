import type { SchemaNodeType } from '~/utils/schema-helpers'

export type GetPropertyNode = SchemaNodeType<'get_property'>
export type GetPropertySettings = NonNullable<GetPropertyNode['data']['settings']>
export type Requirements = NonNullable<GetPropertySettings['selections']>
export type PropertySelection = Requirements[number]
export type OutputMode = NonNullable<GetPropertySettings['output_mode']>

// IFC filter-index types are shared across nodes (see ~/utils/ifc-filter-types)
export type {
  IfcAllowedValue,
  IfcFilterEntity,
  IfcFilterIndex,
  IfcFilterProperty,
  IfcFilterPropertySet,
} from '~/utils/ifc-filter-types'
