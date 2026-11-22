/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

import bcfOutputSchema from '../../../../../shared/schemas/nodes/bcf_output.schema.json'
import collisionSchema from '../../../../../shared/schemas/nodes/collision.schema.json'
import comparisonSchema from '../../../../../shared/schemas/nodes/comparison.schema.json'
import concatStringSchema from '../../../../../shared/schemas/nodes/concat_string.schema.json'
import fileInputSchema from '../../../../../shared/schemas/nodes/file_input.schema.json'
import generate3DCubeSchema from '../../../../../shared/schemas/nodes/generate_3d_cube.schema.json'
import getElementCreationPositionDoorSchema from '../../../../../shared/schemas/nodes/get_element_creation_position_door.schema.json'
import getPropertySchema from '../../../../../shared/schemas/nodes/get_property.schema.json'
import idsCheckerSchema from '../../../../../shared/schemas/nodes/ids_checker.schema.json'
import ifcElementFilterSchema from '../../../../../shared/schemas/nodes/ifc_element_filter.schema.json'
import loiCheckSchema from '../../../../../shared/schemas/nodes/loi_check.schema.json'
import measurementSchema from '../../../../../shared/schemas/nodes/measurement.schema.json'
import set3DPositionRotationSchema from '../../../../../shared/schemas/nodes/set_3d_position_rotation.schema.json'
import tiltOfComponentsSchema from '../../../../../shared/schemas/nodes/tilt_of_components.schema.json'

export const NODE_SCHEMAS = {
  bcf_output: bcfOutputSchema,
  collision: collisionSchema,
  comparison: comparisonSchema,
  concat_string: concatStringSchema,
  file_input: fileInputSchema,
  generate_3d_cube: generate3DCubeSchema,
  get_element_creation_position_door: getElementCreationPositionDoorSchema,
  get_property: getPropertySchema,
  ids_checker: idsCheckerSchema,
  ifc_element_filter: ifcElementFilterSchema,
  loi_check: loiCheckSchema,
  measurement: measurementSchema,
  set_3d_position_rotation: set3DPositionRotationSchema,
  tilt_of_components: tiltOfComponentsSchema,
} as const
