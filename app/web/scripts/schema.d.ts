export interface NodeRegistrySchema {
  collision?: CollisionDetection
  concat_string?: ConcatenateStrings
  generate_3d_cube?: Generate3DCube
  get_geometry?: GetGeometry
  get_name?: ResolveObjectNames
  ifc_element_filter?: IfcElementFilter
}
/**
 * Pairwise collision detection between two geometry lists via mesh boolean intersection.
 */
export interface CollisionDetection {
  settings: {
    /**
     * When enabled, colliding pairs store the intersection mesh in the geometry cache and carry an intersection_key handle. Enables a future workflow extension that writes intersection geometry back as IFC.
     */
    include_intersection_mesh?: boolean
  }
  result: {
    /**
     * One record per paired geometry pair (zip by index).
     */
    pairs?: {
      /**
       * Zero-based pair index within the result.
       */
      index: number
      /**
       * Cache key of the first geometry in the pair.
       */
      key_a: string
      /**
       * Cache key of the second geometry in the pair.
       */
      key_b: string
      /**
       * IFC express ID of the first geometry, or None.
       */
      express_id_a?: (number | null)
      /**
       * IFC express ID of the second geometry, or None.
       */
      express_id_b?: (number | null)
      /**
       * True if the pair intersects with positive volume, False if disjoint. None if undecidable (see error).
       */
      collides?: (boolean | null)
      /**
       * Volume of the intersection mesh when colliding, otherwise None.
       */
      intersection_volume?: (number | null)
      /**
       * Error reason when collides is None, e.g. 'non-watertight' or 'boolean failed: ...'.
       */
      error?: (string | null)
      /**
       * Geometry-cache handle for the intersection mesh, only when include_intersection_mesh is enabled and the pair collides. Enables a future workflow extension that writes intersection geometry back as IFC.
       */
      intersection_key?: (string | null)
    }[]
  }
  inputs: {
    /**
     * First list of geometry handles.
     */
    geometries_a?: {
      /**
       * Key into the workflow-scoped geometry cache holding the trimesh mesh.
       */
      key: string
      /**
       * IFC express ID of the source element, or None for workflow-generated geometry.
       */
      express_id?: (number | null)
    }[]
    /**
     * Second list of geometry handles, paired pairwise with A.
     */
    geometries_b?: {
      /**
       * Key into the workflow-scoped geometry cache holding the trimesh mesh.
       */
      key: string
      /**
       * IFC express ID of the source element, or None for workflow-generated geometry.
       */
      express_id?: (number | null)
    }[]
  }
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
 * Create a 3D cube geometry with customizable size, position, and rotation for clash detection.
 */
export interface Generate3DCube {
  result: {
    /**
     * The generated cube as a 1-element geometry list (express_id=None).
     */
    geometry?: {
      /**
       * Key into the workflow-scoped geometry cache holding the trimesh mesh.
       */
      key: string
      /**
       * IFC express ID of the source element, or None for workflow-generated geometry.
       */
      express_id?: (number | null)
    }[]
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
 * Tessellate IFC element body geometry in worldspace and return cache handles.
 */
export interface GetGeometry {
  settings: {
    /**
     * When enabled, raises an error if an express ID does not exist in the model or an element has no body geometry representation.
     */
    fail_on_missing?: boolean
  }
  result: {
    /**
     * Geometry handles aligned with the input express IDs (missing elements are skipped).
     */
    geometries?: {
      /**
       * Key into the workflow-scoped geometry cache holding the trimesh mesh.
       */
      key: string
      /**
       * IFC express ID of the source element, or None for workflow-generated geometry.
       */
      express_id?: (number | null)
    }[]
  }
  inputs: {
    /**
     * Ordered list of IFC express IDs whose body geometry should be tessellated.
     */
    express_ids?: number[]
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
