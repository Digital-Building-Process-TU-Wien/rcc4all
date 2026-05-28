/**
 * Base interface for all node data
 */
import type { NodeRegistrySchema } from '@@/scripts/schema'

export interface NodeData {
  label: string
  noInput?: boolean
  nodeName: string
  filename?: string
}

export interface AvailableNode {
  label: string
  nodeName: string
  categories: string[]
  description?: string
  markdownDescription?: string
}

export const VUEFLOW_ID = 'main-vue-flow'

/**
 * Node component loader - loads Vue components from the nodes directory
 */
const modules = import.meta.glob('../nodes/**/*.vue')

const components = Object.fromEntries(
  Object.entries(modules).map(([path, loader]) => {
    const parts = path.split('/')
    const fileName = parts.pop()?.replace('.vue', '') ?? ''
    return [fileName, defineAsyncComponent(loader as any)]
  }),
)

function formatNodeLabel(nodeName: string): string {
  return nodeName
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z])([A-Z][a-z])/g, '$1 $2')
    .replace(/([A-Z])(\d)/gi, '$1 $2')
    .replace(/(\d)([A-Z])/gi, '$1 $2')
    .trim()
}

/**
 * Get a node component by its nodeName
 * @param nodeName - The name of the node component to load
 * @returns The Vue component or undefined if not found
 */
export function getNodeComponent(nodeName: string) {
  return components[nodeName]
}

export function getNodeLabel(nodeName: string): string {
  return formatNodeLabel(nodeName)
}

const nodeCategories: Record<string, string[]> = {
  'concat_string': ['Demo'],
  'element_filter': ['IFC', 'Filter'],
  'generate_3d_cube': ['3D operation'],
  'get_name': ['IFC'],
  'file_input': [],
}

const nodeDescriptions: Record<string, { description?: string; markdownDescription?: string }> = {
  'concat_string': {
    description: 'Join a list of resolved string values into one output string.',
    markdownDescription: 'The `concat_string` node combines the incoming `values` list into a single string.\n\nUse this node when a workflow needs to turn several upstream values into a readable label, summary, or message.\n\n## Use case example\n\nCombine object names from an earlier lookup step into a comma-separated sentence for display in the UI or for downstream reporting.',
  },
  'element_filter': {
    description: 'Resolve all IFC entities of a requested type to their express IDs.',
    markdownDescription: 'The `element_filter` node queries the IFC model for all entities matching the configured `entity_type`.\n\nUse this node at the start of a workflow when you need a stable list of express IDs for a specific IFC class before passing those IDs to downstream nodes.\n\n## Use case example\n\nCollect all `IFCWALL` entities from the model, then forward their express IDs to other nodes that inspect names, properties, or custom validation rules.',
  },
  'generate_3d_cube': {
    description: 'Create a 3D cube geometry with customizable size, position, and rotation for clash detection.',
    markdownDescription: 'The `generate_3d_cube` node creates a 3D box geometry with configurable dimensions, position, and rotation. The output is trimesh-compatible geometry data that can be used for clash detection, visualization, or further geometric operations.\n\n## Inputs\n\n| Name | Type | Description |\n|------|------|-------------|\n| `position` | `list[float]` | Position of the cube center as `[x, y, z]` coordinates. Default: `[0.0, 0.0, 0.0]` |\n| `rotation` | `list[float]` | Rotation around X, Y, Z axes in degrees (Euler angles). Default: `[0.0, 0.0, 0.0]` |\n| `size` | `list[float]` | Dimensions of the cube as `[width, height, depth]`. Default: `[1.0, 1.0, 1.0]` |\n\n## Outputs\n\n| Name | Type | Description |\n|------|------|-------------|\n| `vertices` | `list[list[float]]` | List of 8 vertex coordinates as `[x, y, z]` lists |\n| `faces` | `list[list[int]]` | List of 6 face definitions as vertex index lists |\n\n## Example\n\n```json\n{\n  "position": [5.0, 3.0, 0.0],\n  "rotation": [0.0, 0.0, 45.0],\n  "size": [2.0, 2.0, 2.0]\n}\n```\n\nThis creates a 2×2×2 cube centered at (5, 3, 0), rotated 45 degrees around the Z-axis.\n\n## Notes\n\n- The cube is created centered at the origin first, then rotated and translated\n- All size dimensions must be positive (greater than 0)\n- Rotation follows the right-hand rule\n- Output format is compatible with `trimesh.Trimesh(vertices, faces)` constructor',
  },
  'get_name': {
    description: 'Look up IFC object names for a configured list of express IDs.',
    markdownDescription: 'The `get_name` node reads IFC entities by express ID and returns their `Name` values in the same order as the configured input list.\n\nUse this node when a workflow needs human-readable labels for model elements, especially after a filtering step has already narrowed the candidate entities.\n\n## Use case example\n\nResolve the names of a wall selection, then send that ordered name list into a formatting node such as `concat_string` to create a readable summary.',
  },
  'file_input': {
    description: 'Read file content from the workspace.',
    markdownDescription: 'The `file_input` node reads file content from the workspace and makes it available for downstream processing.',
  },
}

function toSnakeCase(str: string): string {
  return str
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
}

function getNodeCategories(nodeName: string): string[] {
  const key = toSnakeCase(nodeName)
  return nodeCategories[key] || []
}

function getNodeDescription(nodeName: string): { description?: string; markdownDescription?: string } {
  const key = toSnakeCase(nodeName)
  return nodeDescriptions[key] || {}
}

export function getAvailableNodes(): AvailableNode[] {
  return getAvailableNodeNames()
    .map(nodeName => ({
      nodeName,
      label: getNodeLabel(nodeName),
      categories: getNodeCategories(nodeName),
      ...getNodeDescription(nodeName),
    }))
    .sort((left, right) => left.label.localeCompare(right.label))
}

/**
 * Get all available node component names
 * @returns Array of available node names
 */
export function getAvailableNodeNames(): string[] {
  return Object.keys(components)
}

/**
 * Check if a node component exists
 * @param nodeName - The name of the node to check
 * @returns true if the component exists
 */
export function hasNodeComponent(nodeName: string): boolean {
  return nodeName in components
}

/**
 * Type helper to get the node type from NodeRegistrySchema
 * @template K - Key from NodeRegistrySchema
 * @example type ConcatNodeType = NodeTypeFromSchema<'concat_string'>
 */
export type NodeTypeFromSchema<K extends keyof NodeRegistrySchema> = NodeRegistrySchema[K]
