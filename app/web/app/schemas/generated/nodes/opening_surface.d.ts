/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Retrieves a watertight closed surface per opening and caches it as generated geometry.
 */
export interface OpeningSurfaceNodeSchema {
  result: {
    /**
     * Number of openings found on the input elements.
     */
    opening_count: number
    /**
     * Number of openings whose closed-surface geometry was retrieved into the geometry cache.
     */
    surface_count: number
    /**
     * Geometry-cache keys (`gen:`) of the retrieved opening closed surfaces, in opening order. Bind to geometry consumers such as measurement or collision.
     */
    geometry_keys?: string[]
    /**
     * Flat list of openings with their retrieved closed-surface data.
     */
    openings?: {
      /**
       * The qualified opening reference (`<slug>:expr:<id>`).
       */
      express_id: string
      /**
       * GlobalId of the opening element, empty when missing.
       */
      guid?: string
      /**
       * Qualified reference of the host element the opening voids.
       */
      host_express_id: string
      /**
       * Geometry-cache key (`gen:`) of the retrieved opening closed surface, or None when it could not be retrieved.
       */
      geometry_key?: (string | null)
      /**
       * How the closed surface was derived: 'closed_cut_surface' (a through-bore whose cut-surface tube closed watertight), 'lofted_caps' (the two cap faces were lofted/connected, possibly with a synthesized second cap), or 'caps_only' (no watertight closed surface; the cap/tube geometry is emitted unchanged).
       */
      method?: (string | null)
      /**
       * Whether the emitted geometry is a closed, winding-consistent, positive-volume solid.
       */
      watertight?: boolean
      /**
       * Opening area in the plane of the host surface (the larger cap face), or None when it could not be retrieved.
       */
      area?: (number | null)
      /**
       * Horizontal extent of the opening in the host plane, or None when it could not be retrieved.
       */
      width?: (number | null)
      /**
       * Vertical extent of the opening in the host plane, or None when it could not be retrieved.
       */
      height?: (number | null)
      /**
       * Distance between the two cap faces along the host surface normal. None when only one cap face exists or it could not be retrieved.
       */
      depth?: (number | null)
      /**
       * Error reason when the opening closed surface could not be retrieved.
       */
      error?: (string | null)
    }[]
  }
  inputs: {
    /**
     * Qualified element references (`<slug>:expr:<id>`) of host building elements (e.g. walls, slabs, roofs) whose openings are retrieved. Bind ifc_element_filter output here.
     */
    express_ids: string[]
  }
}
