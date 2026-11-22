/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Join a list of resolved string values into one output string.
 */
export interface ConcatStringNodeSchema {
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
