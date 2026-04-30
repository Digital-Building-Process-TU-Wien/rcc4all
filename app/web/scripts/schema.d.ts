/**
 * String inserted between the resolved input strings.
 */
export type Separator = string
/**
 * Final string assembled from the input strings.
 */
export type ConcatenatedString = string
/**
 * Resolved values to concatenate.
 */
export type InputValues = (string | null)[]
/**
 * IFC entity name to filter by, for example IFCWALL.
 */
export type EntityType = string
/**
 * Express IDs for all IFC entities matching the requested entity type.
 */
export type ExpressIDs = number[]
/**
 * When enabled, unresolved express IDs or nameless IFC entities produce None instead of raising an error.
 */
export type AllowMissingNames = boolean
/**
 * Ordered list of IFC express IDs whose object names should be resolved.
 */
export type ExpressIDs1 = number[]
/**
 * Ordered list of IFC object names aligned with the input express IDs.
 */
export type ObjectNames = (string | null)[]

export interface NodeRegistrySchema {
  concat_string?: ConcatenateStrings
  element_filter?: FilterIFCElements
  get_name?: ResolveObjectNames
  [k: string]: unknown
}
/**
 * Join a list of resolved string values into one output string.
 */
export interface ConcatenateStrings {
  settings: ConcatStringSettings
  result: ConcatStringResult
  inputs: ConcatStringInputs
  [k: string]: unknown
}
export interface ConcatStringSettings {
  separator?: Separator
}
export interface ConcatStringResult {
  value?: ConcatenatedString
}
export interface ConcatStringInputs {
  values?: InputValues
}
/**
 * Resolve all IFC entities of a requested type to their express IDs.
 */
export interface FilterIFCElements {
  settings: ElementFilterSettings
  result: ElementFilterResult
  [k: string]: unknown
}
export interface ElementFilterSettings {
  entity_type?: EntityType
}
export interface ElementFilterResult {
  express_ids?: ExpressIDs
}
/**
 * Look up IFC object names for a configured list of express IDs.
 */
export interface ResolveObjectNames {
  settings: GetNameSettings
  result: GetNameResult
  [k: string]: unknown
}
export interface GetNameSettings {
  allow_missing?: AllowMissingNames
  express_ids?: ExpressIDs1
}
export interface GetNameResult {
  object_names?: ObjectNames
}
