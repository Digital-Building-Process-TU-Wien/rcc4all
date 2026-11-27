/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Turn checking-node failures into a BCF 3.0 issue file.
 */
export interface BcfOutputNodeSchema {
  settings: {
    /**
     * 'auto' applies the condition-aware standard templates in the editor; 'manual' resolves your own template exactly as written. The backend resolves the same placeholders in both modes; 'mode' is a UI-only toggle.
     */
    mode?: ('auto' | 'manual')
    /**
     * BCF topic title, resolved per failing check with Python string formatting. Placeholders: {id}, {guid}, {name}, {class_name} and check values keyed by the check's key, e.g. {key.expected}, {key.actual}.
     */
    title_template?: string
    /**
     * BCF topic description (sentence) resolved per failing check, same placeholders as the title template.
     */
    description_template?: string
    /**
     * Name written into the BCF project information. Empty means no project name.
     */
    project_name?: string
    /**
     * Author recorded on every BCF topic's creation data.
     */
    author?: string
    /**
     * BCF TopicType applied to every topic.
     */
    topic_type?: string
    /**
     * BCF TopicStatus applied to every topic.
     */
    topic_status?: string
    /**
     * Filename (relative to the output directory) to write the BCF into. A '{timestamp}' placeholder is replaced with a per-run timestamp.
     */
    output_filename?: string
    /**
     * 'failed' includes only elements with at least one failing check (their failing checks become topics); 'passed' includes only fully-passed elements (one info topic each); 'all' includes every element (failing checks become topics, fully-passed elements get one info topic each).
     */
    included_elements?: ('failed' | 'passed' | 'all')
  }
  result: {
    /**
     * Filesystem path the BCF 3.0 file was written to.
     */
    output_path: string
    /**
     * Number of BCF topics written.
     */
    topic_count: number
    /**
     * Number of viewpoints written (one per resolvable failing element).
     */
    viewpoint_count: number
    /**
     * Total number of checks processed across all input elements.
     */
    processed_result_count: number
    /**
     * Number of input elements consumed from the upstream node.
     */
    element_count: number
    /**
     * Total number of failed checks found.
     */
    failure_count: number
    /**
     * Number of elements (with reported checks) skipped because they could not be resolved to a BCF viewpoint: references whose IFC entity / GlobalId could not be resolved, plus elements whose raw references expand to no IFC members (helper/generated geometry).
     */
    skipped?: number
    /**
     * Non-fatal notices collected while running.
     */
    warnings?: string[]
    /**
     * Resolved topics (element GUID, check key, title, description).
     */
    topics?: {
      /**
       * IFC GlobalIds of the failing elements this topic references (resolved from the model by express ID).
       */
      guids: string[]
      /**
       * Key of the (first) failed check this topic reports.
       */
      key: string
      /**
       * Number of distinct failing elements this topic references.
       */
      element_count: number
      /**
       * Resolved topic title from the title template.
       */
      title: string
      /**
       * Resolved topic description from the description template.
       */
      description: string
    }[]
  }
  inputs: {
    /**
     * Harmonized check elements from an upstream checking node (LOI-Check.elements, Tilt-of-Components.elements or Comparison.elements).
     */
    elements: {
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
}
