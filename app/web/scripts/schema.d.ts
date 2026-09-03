/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

export interface NodeRegistrySchema {
  collision?: CollisionDetection
  concat_string?: ConcatenateStrings
  generate_3d_cube?: Generate3DCube
  get_name?: ResolveObjectNames
  get_property?: GetProperty
  ifc_element_filter?: IfcElementFilter
  property_comparison?: PropertyComparison
  tilt_of_components?: TiltOfComponents
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
export interface PropertyComparison {
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
/**
 * Measures the tilt of building components (walls/slabs as 2D surfaces, columns/beams as 1D axes) and flags components whose tilt violates the configured comparison threshold.
 */
export interface TiltOfComponents {
  settings: {
    /**
     * '2d' measures the two largest flat surfaces (walls & slabs); '1d' measures the longitudinal axis of the element (columns & beams).
     */
    element_category?: ('2d' | '1d')
    /**
     * How the measured tilt is checked against the limits. 'greater_than_lower' / 'less_than_upper' use the single lower / upper limit; 'inside_interval' / 'outside_interval' use the interval barriers.
     */
    comparison_method?: ('greater_than_lower' | 'less_than_upper' | 'inside_interval' | 'outside_interval')
    /**
     * Tilt is flagged when it exceeds this value (comparison_method = greater_than_lower).
     */
    lower_limit?: number
    /**
     * Tilt is flagged when it is below this value (comparison_method = less_than_upper).
     */
    upper_limit?: number
    /**
     * Lower barrier used for inside_interval / outside_interval.
     */
    interval_lower?: number
    /**
     * Upper barrier used for inside_interval / outside_interval.
     */
    interval_upper?: number
    /**
     * Maximum horizontal angle deviation between two triangles to still count as the same surface. Used to merge the facets of curved / round objects.
     */
    horizontal_separation_angle?: number
    /**
     * Shared tolerance added/subtracted to the limits when flagging.
     */
    tolerance?: number
  }
  result: {
    /**
     * Number of elements processed.
     */
    element_count: number
    /**
     * Number of elements with at least one surface/axis check.
     */
    check_count: number
    /**
     * Number of elements with at least one flagged surface/axis.
     */
    failed_count: number
    /**
     * Name of the checked IFC model.
     */
    model_name?: string
    /**
     * Ordered list of elements with their tilt checks.
     */
    elements?: {
      /**
       * The express ID of the IFC entity.
       */
      express_id: number
      /**
       * IFC entity class (e.g. IFCWALL) or 'unknown' for missing entities.
       */
      class_name: string
      /**
       * The element category ('2d' or '1d') used to measure this element.
       */
      element_category: ('2d' | '1d')
      /**
       * True if at least one surface/axis check in this element was flagged.
       */
      failed: boolean
      /**
       * Surface ('2d') or axis ('1d') tilt checks for this element.
       */
      checks?: {
        /**
         * Human-readable expectation combined from the comparison method and limits.
         */
        expected: string
        /**
         * Measured tilt of the surface or axis in degrees.
         */
        tilt_angle: number
        /**
         * False when this surface/axis is flagged by the comparison method.
         */
        passed: boolean
        /**
         * Geometry-cache key of the helper geometry for flagged surfaces/axes.
         */
        geometry_key?: (string | null)
      }[]
    }[]
  }
  inputs: {
    /**
     * Optional list of IFC express IDs to measure. When empty, all IFC elements in the model are checked.
     */
    express_ids?: number[]
  }
}
