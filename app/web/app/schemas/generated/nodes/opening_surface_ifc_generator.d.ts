/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Builds a self-contained IFC4X3 model of watertight opening closed surfaces from the opening_surface node, placed into the source model's spatial structure.
 */
export interface OpeningSurfaceIfcGeneratorNodeSchema {
  settings: {
    /**
     * Name of the generated IFC file. Written into the workflow output directory (the folder containing the workflow file).
     */
    output_filename?: string
  }
  result: {
    /**
     * Absolute path of the generated IFC file.
     */
    output_path: string
    /**
     * Number of generated opening closed-surface proxies.
     */
    element_count: number
    /**
     * Number of building storeys replicated from the source model.
     */
    storey_count: number
    /**
     * Ordered list of generated proxies with their spatial relation.
     */
    elements?: {
      /**
       * Qualified reference of the source opening (`<slug>:expr:<id>`).
       */
      opening_ref: string
      /**
       * GlobalId of the generated IfcBuildingElementProxy.
       */
      element_guid: string
      /**
       * Number of polygonal faces written for this opening closed surface.
       */
      face_count?: number
      /**
       * How the source closed surface was derived: 'closed_cut_surface', 'lofted_caps' or 'caps_only'.
       */
      method?: (string | null)
      /**
       * Volume of the opening solid written as an IfcQuantityVolume, in cubic metres, or None when it could not be retrieved.
       */
      volume?: (number | null)
      /**
       * Qualified reference of the host element the opening voids.
       */
      host_ref?: (string | null)
      /**
       * Qualified reference of the source building storey the proxy was contained in, or None when the host is not inside a storey.
       */
      storey_ref?: (string | null)
      /**
       * Opening area written as an IfcQuantityArea on the proxy.
       */
      area?: (number | null)
      /**
       * Error reason when the proxy could not be generated.
       */
      error?: (string | null)
    }[]
  }
  inputs: {
    /**
     * Opening closed-surface results of the opening_surface node. Bind its 'openings' output here.
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
}
