/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Create a 3D box geometry with configurable size, position offset, and rotation offset for clash detection.
 */
export interface Generate3DCubeNodeSchema {
  settings: {
    /**
     * Position offset [x, y, z] in meters added to base position from input. Default [0,0,0] means no offset.
     */
    position?: number[]
    /**
     * Rotation offset [x, y, z] in degrees added to base rotation from input. Default [0,0,0] means no offset.
     */
    rotation?: number[]
    /**
     * Dimensions [width, height, depth] in meters.
     */
    size?: number[]
    /**
     * Unique identifier for the generated cube, used to reference it e.g. in a collision node.
     */
    object_id: string
  }
  result: {
    /**
     * 1-element list with the qualified geometry cache key (`gen:<object_id>`) of the generated cube.
     */
    object_ids?: string[]
  }
  inputs: {
    /**
     * Elements from upstream node (e.g., set_3d_position_rotation or get_element_creation_position_door). First element is used for base position/rotation.
     */
    elements?: unknown[]
  }
}
