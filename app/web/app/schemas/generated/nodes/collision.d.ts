/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Clash detection between two geometry lists via AABB prefilter, boolean intersection, and FCL fallback for non-repairable meshes.
 */
export interface CollisionNodeSchema {
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
