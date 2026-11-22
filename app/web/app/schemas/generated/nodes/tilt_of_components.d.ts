/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Measures the tilt of building components (walls/slabs as 2D surfaces, columns/beams as 1D axes) and flags components whose tilt violates the configured comparison threshold.
 */
export interface TiltOfComponentsNodeSchema {
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
    summary_element_count: number
    /**
     * Number of checked elements with no flagged surface/axis.
     */
    summary_passed_count: number
    /**
     * Number of checked elements with at least one flagged surface/axis.
     */
    summary_failed_count: number
    /**
     * Total number of surface/axis checks across all elements.
     */
    summary_check_count: number
    /**
     * Qualified references of elements whose checks all passed. Only elements with at least one check are included.
     */
    passed_express_ids?: string[]
    /**
     * Qualified references of elements with at least one flagged check. Only elements with at least one check are included.
     */
    failed_express_ids?: string[]
    /**
     * Ordered list of elements with their tilt checks.
     */
    elements?: {
      /**
       * The element reference(s) this element carries. Usually a single raw reference (`<slug>:expr:<id>`, an `inter:intersection_...` helper key, or a `_`-joined distance pair) that bcf_output expands into IFC member objects for viewpoints.
       */
      express_ids: string[]
      /**
       * IFC entity class (e.g. IFCWALL) or 'unknown' for missing entities.
       */
      class_name: string
      /**
       * True if at least one check on this element failed.
       */
      failed: boolean
      /**
       * List of check results for this element.
       */
      checks?: {
        /**
         * Stable identifier for this check (e.g. a property key or 'surface_0').
         */
        key: string
        /**
         * The parameter being checked (e.g. the property name, or 'angle').
         */
        check_parameter: string
        /**
         * Expected value as a string (empty for is_true / is_false and range checks).
         */
        expected_value?: string
        /**
         * Measured/read value as a string, or empty if the value is missing.
         */
        actual_value?: string
        /**
         * Measurement unit of the compared value, or empty when unknown.
         */
        unit?: string
        /**
         * True when the value is not present / could not be measured.
         */
        missing?: boolean
        /**
         * Whether the check passed.
         */
        passed: boolean
        /**
         * The comparison operator that was applied (empty for checks with none).
         */
        expected_value_condition?: string
        /**
         * Lower barrier used for numeric range checks, or empty for single-value checks.
         */
        expected_value_min?: string
        /**
         * Upper barrier used for numeric range checks, or empty for single-value checks.
         */
        expected_value_max?: string
      }[]
    }[]
  }
  inputs: {
    /**
     * Qualified element references (`<slug>:expr:<id>`) to measure. Bind ifc_element_filter output here.
     */
    express_ids: string[]
  }
}
