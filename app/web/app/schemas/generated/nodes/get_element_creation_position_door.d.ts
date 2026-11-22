/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Retrieves footprint points (P1-P7) of IFC door openings for element creation.
 */
export interface GetElementCreationPositionDoorNodeSchema {
  settings: {
    /**
     * Which footprint point to return: 1-4 = corners (clockwise from closest to placement), 5-6 = midpoints, 7 = centroid.
     */
    point_index?: (1 | 2 | 3 | 4 | 5 | 6 | 7)
  }
  result: {
    /**
     * List of element positions (P7) for all processed doors and walls.
     */
    elements?: {
      /**
       * IFC entity type (IfcDoor or IfcWall).
       */
      element_type: string
      /**
       * The qualified element reference (`<slug>:expr:<id>`).
       */
      express_id: string
      /**
       * Which point was returned (1-4 for corners, 5-6 for midpoints, 7 for centroid). P1-P6 require at least 4 bottom vertices.
       */
      point_index: number
      /**
       * World coordinates [x, y, z] in meters (rounded to 3 decimals / millimeter precision).
       */
      position: number[]
      /**
       * Euler rotation angles (X, Y, Z) in degrees (0-360). None if Placement is unavailable.
       */
      rotation?: ({
        /**
         * Rotation about global X-axis in degrees (0-360).
         */
        rotation_x: number
        /**
         * Rotation about global Y-axis in degrees (0-360).
         */
        rotation_y: number
        /**
         * Rotation about global Z-axis in degrees (0-360).
         */
        rotation_z: number
      } | null)
    }[]
  }
  inputs: {
    /**
     * Qualified element references (`<slug>:expr:<id>`) to get positions from. Bind ifc_element_filter output here.
     */
    express_ids?: string[]
  }
}
