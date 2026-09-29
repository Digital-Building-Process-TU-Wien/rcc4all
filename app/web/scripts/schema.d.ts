/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

export interface NodeRegistrySchema {
  bcf_output?: BCFOutput
  collision?: CollisionDetection
  concat_string?: ConcatenateStrings
  file_input?: FileInput
  generate_3d_cube?: Generate3DCube
  get_property?: GetProperty
  ids_checker?: IDSChecker
  ifc_element_filter?: IfcElementFilter
  loi_check?: LOICheck
  measurement?: Measurement
  tilt_of_components?: TiltOfComponents
}
/**
 * Turn checking-node failures into a BCF 3.0 issue file.
 */
export interface BCFOutput {
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
     * Number of elements (with reported checks) skipped because they could not be resolved.
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
     * Harmonized check elements from an upstream checking node (LOI-Check.elements or Tilt-of-Components.elements).
     */
    elements?: {
      /**
       * The qualified element reference(s) (`<slug>:expr:<id>`) this element carries. Usually a single reference.
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
     * First list of geometry cache references (`<slug>:expr:<id>`, `gen:<object_id>` or `inter:<id>`), in the order to test. Bind ifc_element_filter output here.
     */
    list_a: string[]
    /**
     * Second list of geometry cache references (`<slug>:expr:<id>`, `gen:<object_id>` or `inter:<id>`) to test the first list against. Mixed-model lists are allowed; each reference resolves against its own model.
     */
    list_b: string[]
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
 * Refers to an IFC model assigned in the editor and outputs its slug.
 */
export interface FileInput {
  settings: {
    /**
     * Slug of the IFC model this File Input refers to. Defaults to the main model.
     */
    slug?: string
  }
  result: {
    /**
     * Slug of the selected IFC model, for binding to a consumer's model input.
     */
    model_slug?: string
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
     * 1-element list with the qualified geometry cache key (`gen:<object_id>`) of the generated cube.
     */
    object_ids?: string[]
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
       * The qualified element reference (`<slug>:expr:<id>`).
       */
      express_id: string
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
     * Qualified element references (`<slug>:expr:<id>`) to read property values from. Bind ifc_element_filter output here.
     */
    express_ids: string[]
  }
}
/**
 * Validates the IFC model against one or more IDS specifications.
 */
export interface IDSChecker {
  settings: {
    /**
     * Path to the IDS specification file to validate against.
     */
    ids_file?: string
    /**
     * Wenn aktiviert, werden die Ergebnisse zusätzlich nach Specification gruppiert ausgegeben (für Report-Generierung). Die kombinierten Listen (failed_express_ids, passed_express_ids) werden immer erstellt.
     */
    generate_detailed_report?: boolean
    /**
     * Format für den generierten Report. Nur wirksam wenn generate_detailed_report aktiviert ist.
     */
    report_format?: (('json' | 'html') | null)
  }
  result: {
    /**
     * Qualified references of entities that failed at least one IDS requirement (combined across all specifications).
     */
    failed_express_ids?: string[]
    /**
     * Qualified references of entities that passed all applicable IDS requirements (combined across all specifications).
     */
    passed_express_ids?: string[]
    /**
     * Per-specification breakdown. Only included when generate_detailed_report is enabled.
     */
    specifications?: ({
      /**
       * Name of the IDS specification.
       */
      name?: string
      /**
       * Qualified references of entities that failed this specification's requirements.
       */
      failed_express_ids?: string[]
      /**
       * Qualified references of entities that passed this specification's requirements.
       */
      passed_express_ids?: string[]
    }[] | null)
    /**
     * Path to the generated report file. Only included when generate_detailed_report and report_format are enabled.
     */
    report_path?: (string | null)
  }
  inputs: {
    /**
     * Qualified element references (`<slug>:expr:<id>`) to validate against the IDS requirements. Mixed-model lists are grouped by model and each model is validated once. Bind ifc_element_filter output here.
     */
    express_ids: string[]
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
     * Qualified references (`<slug>:expr:<id>`) of all matching IFC entities.
     */
    express_ids?: string[]
    /**
     * Qualified GUID references (`<slug>:guid:<GlobalId>`) for all matching IFC entities in the same order as express_ids.
     */
    guids?: string[]
  }
  inputs: {
    /**
     * Optional list of qualified element references (`<slug>:expr:<id>`) to filter within. When the input is not connected, the whole model is scanned. When connected, an empty list yields an empty result. Per-reference model slugs win over the model input.
     */
    express_ids?: (string[] | null)
    /**
     * Model slug to scan when no references are bound. Defaults to the main model.
     */
    model_slug?: string
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
       * The qualified element reference(s) (`<slug>:expr:<id>`) this element carries. Usually a single reference.
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
/**
 * Compute geometric measurements (volume, surface area, projected area, component height, minimum distance between elements, distance to reference) of IFC elements or cached geometries.
 */
export interface Measurement {
  settings: {
    /**
     * The type of measurement to compute: 'volume', 'surface_area', 'projected_area', 'component_height', 'distance_between', 'distance_to_reference'.
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
    /**
     * Reference type for 'distance_to_reference' mode. 'point' computes distance to a reference point; 'plane' computes perpendicular distance to a reference plane.
     */
    reference_type?: ('point' | 'plane')
    /**
     * Reference point coordinates [x, y, z]. Used for both 'point' and 'plane' reference types.
     */
    reference_point?: number[]
    /**
     * Plane normal vector [x, y, z]. Only used for 'distance_to_reference' mode with reference_type='plane'. Zero normal results in error entry.
     */
    reference_normal?: number[]
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
       * The geometry cache key (e.g., `main:expr:63`, `gen:mycube`, `inter:...`) of the measured element, or the raw input when no geometry was found.
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
     * First list of fully qualified geometry cache keys — `<slug>:expr:<id>` for IFC elements, `gen:<object_id>` for generated geometry, `inter:<id>` for helper/intersection geometry — in the order to test. An empty list yields zero measurements. Also accepts a dict (e.g., collision node's `intersection_meshes` output); in this case, the dict's non-null values (intersection mesh cache keys) are used.
     */
    list_a?: (string[] | {
      [k: string]: (string | null)
    })
    /**
     * Second (optional) list of fully qualified geometry cache keys. When empty, pairs are formed within List A. When non-empty, computes cartesian product AxB. Also accepts a dict (e.g., collision node's `intersection_meshes` output); non-null values are used as cache keys.
     */
    list_b?: (string[] | {
      [k: string]: (string | null)
    })
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
       * The qualified element reference(s) (`<slug>:expr:<id>`) this element carries. Usually a single reference.
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
