export interface NodeRegistrySchema {
  concat_string?: ConcatenateStrings
  element_filter?: FilterIFCElements
  generate_3d_cube?: Generate3DCube
  get_name?: ResolveObjectNames
  ifc_element_filter?: IfcElementFilter
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
 * Look up IFC object names by express ID from workflow input.
 */
export interface ResolveObjectNames {
  settings: {
    /**
     * When enabled, raises an error if an express ID does not exist in the model.
     */
    fail_on_missing?: boolean
  }
  result: {
    /**
     * Ordered list of IFC object names aligned with the input express IDs.
     */
    object_names?: (string | null)[]
  }
  inputs: {
    /**
     * Ordered list of IFC express IDs whose object names should be resolved.
     */
    express_ids?: number[]
  }
}
/**
 * Filter IFC entities using table-based include and exclude rules.
 */
export interface IfcElementFilter {
  settings: {
    /**
     * List of component filter rows. Include rows are unioned, exclude rows are subtracted.
     */
    filter_rows?: {
      /**
       * Row mode: include adds matches, exclude removes matches, disabled ignores the row.
       */
      mode?: ('include' | 'exclude' | 'disabled')
      /**
       * IFC entity type name, for example IFCWALL, IFCDOOR, or IFCSPACE.
       */
      entity_type?: string
      /**
       * Optional PredefinedType value. Empty means any predefined type.
       */
      predefined_type?: string
      /**
       * Optional IFC PropertySet name. Empty means direct attribute lookup or search all PropertySets.
       */
      property_set?: string
      /**
       * Optional IFC attribute or PropertySet property name to compare.
       */
      property_name?: string
      /**
       * Comparison operator used for property or attribute values.
       */
      operator?: ('==' | '!=' | '<' | '>' | '<=' | '>=' | 'contains' | 'starts_with' | 'ends_with')
      /**
       * Value to compare against when property_name is set.
       */
      value?: string
    }[]
  }
  result: {
    /**
     * Express IDs of all matching IFC entities.
     */
    express_ids?: number[]
    /**
     * GlobalId values for all matching IFC entities in the same order as express_ids.
     */
    guids?: string[]
  }
}
