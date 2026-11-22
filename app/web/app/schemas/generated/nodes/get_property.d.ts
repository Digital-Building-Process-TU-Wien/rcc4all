/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Read property values from IFC entities for downstream processing.
 */
export interface GetPropertyNodeSchema {
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
