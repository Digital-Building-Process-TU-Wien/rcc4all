/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Compares numeric values against a target value or range and produces harmonized check elements for BCF output.
 */
export interface ComparisonNodeSchema {
  settings: {
    /**
     * Comparison operator applied to the value.
     */
    condition?: ('equals' | 'not_equals' | 'lt' | 'le' | 'gt' | 'ge' | 'between' | 'outside')
    /**
     * Target value for single-value operators (equals, not_equals, lt, le, gt, ge).
     */
    target_value?: number
    /**
     * Lower barrier for between / outside operators.
     */
    target_min?: number
    /**
     * Upper barrier for between / outside operators.
     */
    target_max?: number
    /**
     * If True, the range includes values equal to the lower barrier (>=); otherwise strictly greater (>).
     */
    inclusive_min?: boolean
    /**
     * If True, the range includes values equal to the upper barrier (<=); otherwise strictly less (<).
     */
    inclusive_max?: boolean
    /**
     * Absolute tolerance for float comparisons. Negative values are treated as their absolute value.
     */
    abs_tol?: number
  }
  result: {
    /**
     * Number of elements processed.
     */
    summary_element_count: number
    /**
     * Number of elements whose check passed.
     */
    summary_passed_count: number
    /**
     * Number of elements with a failed check.
     */
    summary_failed_count: number
    /**
     * Total number of checks (equals element count, one check per element).
     */
    summary_check_count: number
    /**
     * Qualified references of elements whose check passed.
     */
    passed_express_ids?: string[]
    /**
     * Qualified references of elements with a failed check.
     */
    failed_express_ids?: string[]
    /**
     * Ordered list of elements with their comparison check results.
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
     * List of values to compare. Each item has a `reference` to its source element and a `value`. Bind to a list output of an upstream node.
     */
    values?: {
      /**
       * Reference of the value's source element (e.g. `main:expr:1`, an `inter:intersection_...` helper key, or a `_`-joined distance pair).
       */
      reference: string
      /**
       * The numeric value to compare. Null if the value is missing or could not be computed.
       */
      value?: (number | null)
      /**
       * Error reason when the value could not be computed (e.g. 'no cached geometry').
       */
      error?: (string | null)
    }[]
    /**
     * Unit of the compared values. Bind to a unit output of an upstream node, e.g. measurement.unit.
     */
    unit?: string
    /**
     * Label naming the check (becomes the BCF check key). Bind to a type/check_parameter output of an upstream node, e.g. measurement.type.
     */
    check_parameter?: string
  }
}
