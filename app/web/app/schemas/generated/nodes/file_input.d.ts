/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Refers to an IFC model assigned in the editor and outputs its slug.
 */
export interface FileInputNodeSchema {
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
