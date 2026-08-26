/**
 * A distinct property value.
 */
export type Value = string
/**
 * Number of occurrences of this value.
 */
export type Count = number
/**
 * A distinct property value.
 */
export type Value1 = string
/**
 * Number of occurrences of this value.
 */
export type Count1 = number

export interface NodeRegistrySchema {
  collision?: CollisionDetection
  concat_string?: ConcatenateStrings
  generate_3d_cube?: Generate3DCube
  get_name?: ResolveObjectNames
  get_property?: GetProperty
  ifc_element_filter?: IfcElementFilter
  measurement?: Measurement
}
/**
 * Clash detection between two geometry lists via AABB prefilter, boolean intersection, and FCL fallback for non-repairable meshes.
 */
export interface CollisionDetection {
  settings: {
    /**
     * 'boolean' reports which pairs collide without storing intersection geometry. 'intersection_mesh' additionally stores each collision's intersection mesh in the geometry cache under a deterministic key (documented in the README).
     */
    mode?: ('boolean' | 'intersection_mesh')
  }
  result: {
    /**
     * Grouped by side-A cache key; each value lists the side-B cache keys it collides with. Only colliding pairs are included.
     */
    collisions?: {
      [k: string]: string[]
    }
    /**
     * Pairs whose collision could not be decided (e.g. non-watertight or boolean failure).
     */
    errors?: {
      /**
       * Cache key of the first geometry in the failed pair.
       */
      key_a: string
      /**
       * Cache key of the second geometry in the failed pair.
       */
      key_b: string
      /**
       * Error reason, e.g. 'non-watertight' or 'boolean failed: ...'.
       */
      error: string
    }[]
    /**
     * Only populated in 'intersection_mesh' mode. Maps a pair key '{key_a}__{key_b}' to the geometry-cache key 'inter:intersection_{key_a}_{key_b}' under which the intersection mesh was stored. A null value signals an FCL-decided collision (mesh non-repairable or boolean failed) for which no intersection mesh could be generated. Empty in 'boolean' mode.
     */
    intersection_meshes?: {
      [k: string]: (string | null)
    }
  }
  inputs: {
    /**
     * First list of references — mix of express IDs (int → `ifc:<id>`) and object IDs (str → `gen:<id>`), in the order to test. When empty, the whole model is used.
     */
    list_a?: (number | string)[]
    /**
     * Second (optional) list of references — mix of express IDs (int → `ifc:<id>`) and object IDs (str → `gen:<id>`). When empty, the whole model is used as the counterpart set.
     */
    list_b?: (number | string)[]
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
  settings: {
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
    /**
     * Unique identifier for the generated cube, used to reference it e.g. in a collision node.
     */
    object_id: string
  }
  result: {
    /**
     * 1-element list with the object_id of the generated cube.
     */
    object_ids?: string[]
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
 * Read property values from IFC entities for downstream processing.
 */
export interface GetProperty {
  settings: {
    /**
     * Output granularity: 'elements' (per entity), 'by_class' (grouped by element class), or 'model' (distinct values across all entities).
     */
    output_mode?: ('elements' | 'by_class' | 'model')
    /**
     * List of properties to read from each entity.
     */
    selections?: {
      /**
       * Optional IFC entity type (e.g., IFCWALL, IFCDOOR). Empty means any entity type. Used for UI preselection only.
       */
      entity_type?: string
      /**
       * IFC PropertySet name (e.g., Pset_WallCommon) or custom property set name.
       */
      property_set?: string
      /**
       * Name of the property to read within the PropertySet.
       */
      property_name?: string
    }[]
  }
  result: {
    /**
     * The output mode used to generate this result.
     */
    mode: ('elements' | 'by_class' | 'model')
    /**
     * List of elements with their property values (output_mode = elements).
     */
    elements?: ({
      /**
       * The express ID of the IFC entity.
       */
      express_id: number
      /**
       * Dictionary of property values keyed by 'Pset.Property' format.
       */
      properties?: {
        [k: string]: (string | null)
      }
    }[] | null)
    /**
     * Elements grouped by IFC class (output_mode = by_class).
     */
    classes?: ({
      /**
       * IFC entity class (e.g., IFCWALL) or 'unknown' for missing entities.
       */
      id: string
      /**
       * Distinct values with counts per property for this class.
       */
      properties?: {
        [k: string]: ValueWithCount[]
      }
    }[] | null)
    /**
     * Distinct values with counts per property (output_mode = model).
     */
    properties?: ({
      [k: string]: ValueWithCount1[]
    } | null)
  }
  inputs: {
    /**
     * List of IFC express IDs to read property values from.
     */
    express_ids?: number[]
  }
}
export interface ValueWithCount {
  value: Value
  count: Count
}
export interface ValueWithCount1 {
  value: Value1
  count: Count1
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
/**
 * Compute geometric measurements (volume, surface area, projected area, component height) of IFC elements or cached geometries.
 */
export interface Measurement {
  settings: {
    /**
     * The type of measurement to compute. In v3, 'volume', 'surface_area', 'projected_area', 'component_height', and 'distance_between' are implemented.
     */
    measurement_type?: ('volume' | 'surface_area' | 'projected_area' | 'component_height' | 'distance_between' | 'distance_to_reference')
    /**
     * Normal vector for the projection plane. Default [0,0,1] computes footprint (top-down view). Only used for 'projected_area' mode.
     */
    projection_normal?: number[]
    /**
     * Direction vector for extent computation. Default [0,0,1] computes vertical height. Only used for 'component_height' mode. Normalized internally.
     */
    direction?: number[]
  }
  result: {
    /**
     * The measurement type used to generate this result.
     */
    type: ('volume' | 'surface_area' | 'projected_area' | 'component_height' | 'distance_between' | 'distance_to_reference')
    /**
     * The unit of measurement (model units, e.g., 'volume_unit' for volume, 'area_unit' for area and 'length_unit' for distance).
     */
    unit: string
    /**
     * List of per-element measurements.
     */
    measurements?: {
      /**
       * The geometry cache key (e.g., `ifc:123`, `gen:abc`, `inter:...`) of the measured element.
       */
      reference: string
      /**
       * The measured value. Null if geometry is missing or measurement failed.
       */
      value?: (number | null)
      /**
       * Error reason if measurement failed (e.g., 'no cached geometry', 'non-watertight').
       */
      error?: (string | null)
    }[]
  }
  inputs: {
    /**
     * First list of references — mix of express IDs (int → `ifc:<id>`) and object IDs (str → `gen:<id>`), in the order to test. When empty, the whole model is used. Also accepts a dict (e.g., collision node's `intersection_meshes` output); in this case, the dict's non-null values (intersection mesh cache keys) are used.
     */
    list_a?: ((number | string)[] | {
      [k: string]: (string | null)
    })
    /**
     * Second (optional) list of references — mix of express IDs (int → `ifc:<id>`) and object IDs (str → `gen:<id>`). When empty, pairs are formed within List A. When non-empty, computes cartesian product A×B. Also accepts a dict (e.g., collision node's `intersection_meshes` output); non-null values are used as cache keys.
     */
    list_b?: ((number | string)[] | {
      [k: string]: (string | null)
    })
  }
}
