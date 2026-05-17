export interface NodeRegistrySchema {
  concat_string?: ConcatenateStrings
  element_filter?: FilterIFCElements
  generate_3d_cube?: Generate3DCube
  get_name?: ResolveObjectNames
}
/**
 * Join a list of resolved string values into one output string.
 */
export interface ConcatenateStrings {
  settings: {
    /**
     * String inserted between the resolved input strings.
     */
    separator?: string
  }
  result: {
    /**
     * Final string assembled from the input strings.
     */
    value?: string
  }
  inputs: {
    /**
     * Resolved values to concatenate.
     */
    values?: (string | null)[]
  }
}
/**
 * Resolve all IFC entities of a requested type to their express IDs.
 */
export interface FilterIFCElements {
  settings: {
    /**
     * IFC entity name to filter by, for example IFCWALL.
     */
    entity_type?: string
  }
  result: {
    /**
     * Express IDs for all IFC entities matching the requested entity type.
     */
    express_ids?: number[]
  }
}
/**
 * Create a 3D cube geometry with customizable size, position, and rotation for clash detection.
 */
export interface Generate3DCube {
  result: {
    /**
     * List of 3D vertex coordinates [[x, y, z], ...] defining the cube geometry.
     */
    vertices?: number[][]
    /**
     * List of face definitions [[v1, v2, v3], ...] as vertex indices forming triangles.
     */
    faces?: number[][]
  }
  inputs: {
    /**
     * 3D position [x, y, z] for the cube center in meters.
     */
    position?: number[]
    /**
     * Euler angles [x, y, z] in degrees for rotation around each axis.
     */
    rotation?: number[]
    /**
     * Dimensions [width, height, depth] in meters.
     */
    size?: number[]
  }
}
/**
 * Look up IFC object names for a configured list of express IDs.
 */
export interface ResolveObjectNames {
  settings: {
    /**
     * When enabled, unresolved express IDs or nameless IFC entities produce None instead of raising an error.
     */
    allow_missing?: boolean
    /**
     * Ordered list of IFC express IDs whose object names should be resolved.
     */
    express_ids?: number[]
  }
  result: {
    /**
     * Ordered list of IFC object names aligned with the input express IDs.
     */
    object_names?: (string | null)[]
  }
}
