/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Project cached geometries (e.g. element footprints) onto a plane through the world origin and store the flat projected footprint as generated geometry. Does not compute areas.
 */
export interface GeometryProjectionNodeSchema {
  settings: {
    /**
     * Normal vector of the projection plane, e.g. [0,0,1] projects onto the XY plane (top-down footprint). All three values must be finite. Normalized internally. Zero vector produces an 'undefined normal' error for every input.
     *
     * @minItems 3
     * @maxItems 3
     */
    projection_normal?: [number, number, number]
  }
  result: {
    /**
     * Maps each input geometry cache key to the generated `gen:proj_<...>` key under which its flat projected footprint was stored in the geometry cache.
     */
    projected_geometries?: {
      [k: string]: string
    }
    /**
     * Per-input projection failures.
     */
    errors?: {
      /**
       * The geometry cache key that failed to project, or the raw input when no geometry was found.
       */
      reference: string
      /**
       * Error reason: 'no cached geometry' (missing/invalid key), 'no projected geometry' (degenerate, edge-on projection or projection/triangulation failure) or 'undefined normal' (zero-length normal).
       */
      error: string
    }[]
  }
  inputs: {
    /**
     * List of fully qualified geometry cache keys — `<slug>:expr:<id>` for IFC elements, `gen:<object_id>` for generated geometry, `inter:<id>` for helper/intersection geometry — in the order to project. An empty list yields an empty result. Also accepts a dict (e.g., collision node's `intersection_meshes` output); in this case the dict's non-null values (cache keys) are used.
     */
    liste_a: (string[] | {
      [k: string]: (string | null)
    })
  }
}
