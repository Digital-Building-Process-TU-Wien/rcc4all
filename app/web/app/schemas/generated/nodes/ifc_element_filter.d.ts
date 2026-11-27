/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Filter IFC entities using table-based include and exclude rules.
 */
export interface IfcElementFilterNodeSchema {
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
