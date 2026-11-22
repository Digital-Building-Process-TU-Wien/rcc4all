/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Define a 3D position and rotation via UI settings.
 */
export interface Set3DPositionRotationNodeSchema {
  settings: {
    /**
     * 3D position [x, y, z] in meters.
     */
    position?: number[]
    /**
     * Euler angles [x, y, z] in degrees for rotation around each axis.
     */
    rotation?: number[]
  }
  result: {
    /**
     * List with one element containing position and rotation values.
     */
    elements?: {
      /**
       * Empty string (no IFC element reference).
       */
      express_id?: string
      /**
       * World coordinates [x, y, z] in meters.
       */
      position: number[]
      /**
       * Euler angles (X, Y, Z) in degrees.
       */
      rotation: {
        /**
         * Rotation around global X-axis in degrees.
         */
        rotation_x: number
        /**
         * Rotation around global Y-axis in degrees.
         */
        rotation_y: number
        /**
         * Rotation around global Z-axis in degrees.
         */
        rotation_z: number
      }
    }[]
  }
}
