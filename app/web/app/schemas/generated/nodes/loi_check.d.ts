/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Check IFC property values against expected target values with table-based rules.
 */
export interface LoiCheckNodeSchema {
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
    summary_element_count: number
    /**
     * Number of checked elements whose checks all passed.
     */
    summary_passed_count: number
    /**
     * Number of checked elements with at least one failed check.
     */
    summary_failed_count: number
    /**
     * Total number of property checks across all elements.
     */
    summary_check_count: number
    /**
     * Qualified references of elements whose checks all passed. Only elements that were actually checked (had at least one applied check) are included.
     */
    passed_express_ids?: string[]
    /**
     * Qualified references of elements with at least one failed check. Only elements that were actually checked (had at least one applied check) are included.
     */
    failed_express_ids?: string[]
    /**
     * Ordered list of elements with their property check results.
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
     * Qualified element references (`<slug>:expr:<id>`) to run property comparisons against. Bind ifc_element_filter output here.
     */
    express_ids: string[]
  }
}
