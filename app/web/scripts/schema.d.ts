/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

export interface NodeRegistrySchema {
  collision?: CollisionDetection
  concat_string?: ConcatenateStrings
  generate_3d_cube?: Generate3DCube
  get_name?: ResolveObjectNames
  get_property?: GetProperty
  ifc_element_filter?: IfcElementFilter
  loi_check?: LOICheck
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
        [k: string]: {
          /**
           * A distinct property value.
           */
          value: string
          /**
           * Number of occurrences of this value.
           */
          count: number
        }[]
      }
    }[] | null)
    /**
     * Distinct values with counts per property (output_mode = model).
     */
    properties?: ({
      [k: string]: {
        /**
         * A distinct property value.
         */
        value: string
        /**
         * Number of occurrences of this value.
         */
        count: number
      }[]
    } | null)
  }
  inputs: {
    /**
     * List of IFC express IDs to read property values from.
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
  inputs: {
    /**
     * Optional list of IFC express IDs to filter within. When the input is not connected, the whole model is scanned. When connected, an empty list yields an empty result.
     */
    express_ids?: (number[] | null)
  }
}
/**
 * Check IFC property values against expected target values with table-based rules.
 */
export interface LOICheck {
  settings: {
    /**
     * List of property comparison rules. Each row is checked against every input element.
     */
    rows?: {
      /**
       * Optional IFC entity type (e.g., IFCWALL, IFCDOOR). Empty means any entity type. Used for UI preselection only.
       */
      entity_type?: string
      /**
       * IFC PropertySet name (e.g., Pset_WallCommon) or custom property set name.
       */
      property_set?: string
      /**
       * Name of the property to compare within the PropertySet.
       */
      property_name?: string
      /**
       * Comparison operator applied to the property value. 'between' / 'outside' use the numeric range barriers.
       */
      condition: ('equals' | 'not_equals' | 'lt' | 'le' | 'gt' | 'ge' | 'contains' | 'one_of' | 'is_true' | 'is_false' | 'between' | 'outside')
      /**
       * Target value the property is compared against. Ignored for is_true / is_false and range checks.
       */
      expected_value?: string
      /**
       * List of accepted values for the 'one_of' condition. Empty entries are ignored.
       */
      allowed_values?: string[]
      /**
       * Lower barrier for numeric range checks (condition = between / outside).
       */
      range_min?: string
      /**
       * Upper barrier for numeric range checks (condition = between / outside).
       */
      range_max?: string
      /**
       * If True the range includes values equal to the lower barrier (>=); otherwise it is strictly greater (>).
       */
      inclusive_min?: boolean
      /**
       * If True the range includes values equal to the upper barrier (<=); otherwise it is strictly less (<).
       */
      inclusive_max?: boolean
    }[]
  }
  result: {
    /**
     * Number of elements processed.
     */
    element_count: number
    /**
     * Total number of property checks across all elements.
     */
    total_checks: number
    /**
     * Total number of failed checks across all elements.
     */
    failed_count: number
    /**
     * Express IDs of elements whose checks all passed. Only elements that were actually checked (had at least one applied check) are included.
     */
    passed_express_ids?: number[]
    /**
     * Express IDs of elements with at least one failed check. Only elements that were actually checked (had at least one applied check) are included.
     */
    failed_express_ids?: number[]
    /**
     * Ordered list of elements with their property check results.
     */
    elements?: {
      /**
       * The express ID of the IFC entity.
       */
      express_id: number
      /**
       * IFC entity class (e.g., IFCWALL) or 'unknown' for missing entities.
       */
      class_name: string
      /**
       * True if at least one check on this element failed.
       */
      failed: boolean
      /**
       * List of property check results for this element.
       */
      checks?: {
        /**
         * Stable identifier for this check (the property key, e.g., 'Pset.X' or 'X').
         */
        id: string
        /**
         * Property key in 'Pset.Property' or 'Property' format.
         */
        property_key: string
        /**
         * Name of the property being compared.
         */
        property_name: string
        /**
         * The comparison operator that was applied.
         */
        condition: ('equals' | 'not_equals' | 'lt' | 'le' | 'gt' | 'ge' | 'contains' | 'one_of' | 'is_true' | 'is_false' | 'between' | 'outside')
        /**
         * Expected value as a string (empty for is_true / is_false and range checks).
         */
        expected?: string
        /**
         * Lower barrier used for numeric range checks, or None for single-value checks.
         */
        expected_min?: (string | null)
        /**
         * Upper barrier used for numeric range checks, or None for single-value checks.
         */
        expected_max?: (string | null)
        /**
         * Actual property value as a string, or None if the property is missing.
         */
        actual?: (string | null)
        /**
         * Whether the property value satisfies the condition.
         */
        passed: boolean
      }[]
    }[]
  }
  inputs: {
    /**
     * Optional list of IFC express IDs to run property comparisons against. When empty (not connected), all IFC elements in the model are checked.
     */
    express_ids?: number[]
  }
}
