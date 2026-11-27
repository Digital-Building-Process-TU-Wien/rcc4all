/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

import type { BcfOutputNodeSchema } from './bcf_output'
import type { CollisionNodeSchema } from './collision'
import type { ComparisonNodeSchema } from './comparison'
import type { ConcatStringNodeSchema } from './concat_string'
import type { FileInputNodeSchema } from './file_input'
import type { Generate3DCubeNodeSchema } from './generate_3d_cube'
import type { GetElementCreationPositionDoorNodeSchema } from './get_element_creation_position_door'
import type { GetPropertyNodeSchema } from './get_property'
import type { IdsCheckerNodeSchema } from './ids_checker'
import type { IfcElementFilterNodeSchema } from './ifc_element_filter'
import type { LoiCheckNodeSchema } from './loi_check'
import type { MeasurementNodeSchema } from './measurement'
import type { OpeningSurfaceNodeSchema } from './opening_surface'
import type { OpeningSurfaceIfcGeneratorNodeSchema } from './opening_surface_ifc_generator'
import type { Set3DPositionRotationNodeSchema } from './set_3d_position_rotation'
import type { TiltOfComponentsNodeSchema } from './tilt_of_components'

export interface NodeRegistrySchema {
  bcf_output: BcfOutputNodeSchema
  collision: CollisionNodeSchema
  comparison: ComparisonNodeSchema
  concat_string: ConcatStringNodeSchema
  file_input: FileInputNodeSchema
  generate_3d_cube: Generate3DCubeNodeSchema
  get_element_creation_position_door: GetElementCreationPositionDoorNodeSchema
  get_property: GetPropertyNodeSchema
  ids_checker: IdsCheckerNodeSchema
  ifc_element_filter: IfcElementFilterNodeSchema
  loi_check: LoiCheckNodeSchema
  measurement: MeasurementNodeSchema
  opening_surface: OpeningSurfaceNodeSchema
  opening_surface_ifc_generator: OpeningSurfaceIfcGeneratorNodeSchema
  set_3d_position_rotation: Set3DPositionRotationNodeSchema
  tilt_of_components: TiltOfComponentsNodeSchema
}
