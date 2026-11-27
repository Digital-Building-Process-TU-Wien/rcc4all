/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Compute geometric measurements (volume, surface area, component height, minimum distance between elements, distance to reference) of IFC elements or cached geometries.
 */
export interface MeasurementNodeSchema {
  settings: {
    /**
     * The type of measurement to compute: 'volume', 'surface_area', 'component_height', 'distance_between', 'distance_to_reference'.
     */
    measurement_type?: ('volume' | 'surface_area' | 'component_height' | 'distance_between' | 'distance_to_reference')
    /**
     * Direction vector [x, y, z] for extent computation. Default [0,0,1] computes vertical height. Only used for 'component_height' mode. All three values must be finite. Normalized internally.
     *
     * @minItems 3
     * @maxItems 3
     */
    direction?: [number, number, number]
    /**
     * Reference type for 'distance_to_reference' mode. 'point' computes distance to a reference point; 'plane' computes perpendicular distance to a reference plane.
     */
    reference_type?: ('point' | 'plane')
    /**
     * Reference point coordinates [x, y, z] in metres. Used for both 'point' and 'plane' reference types (plane origin for 'plane'). All three values must be finite.
     *
     * @minItems 3
     * @maxItems 3
     */
    reference_point?: [number, number, number]
    /**
     * Plane normal vector [x, y, z]. Only used for 'distance_to_reference' mode with reference_type='plane'. All three values must be finite. Normalized internally; zero normal results in an error entry.
     *
     * @minItems 3
     * @maxItems 3
     */
    reference_normal?: [number, number, number]
  }
  result: {
    /**
     * The measurement type used to generate this result.
     */
    type: ('volume' | 'surface_area' | 'component_height' | 'distance_between' | 'distance_to_reference')
    /**
     * The unit of measurement ('volume_unit' for volume, 'area_unit' for area and 'length_unit' for distance). Cached IFC geometry is tessellated in metres, so values are m³, m² or m.
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
       * Error reason if measurement failed (e.g., 'no cached geometry', 'non-watertight', 'empty geometry').
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
     * Second (optional) list of fully qualified geometry cache keys. When empty, pairs are formed within List A. When non-empty, computes cartesian product AxB. Also accepts a dict (e.g., collision node's `intersection_meshes` output); non-null values are used as cache keys. A dict whose values are all null is treated like an empty List B.
     */
    list_b?: (string[] | {
      [k: string]: (string | null)
    })
  }
}
