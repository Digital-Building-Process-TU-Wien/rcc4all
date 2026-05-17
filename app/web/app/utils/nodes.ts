/**
 * Base interface for all node data
 */
import type { NodeRegistrySchema } from '@@/scripts/schema'

export interface NodeData {
  label: string
  noInput?: boolean
  nodeName: string
}

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

/**
 * Get a node component by its nodeName
 * @param nodeName - The name of the node component to load
 * @returns The Vue component or undefined if not found
 */
export function getNodeComponent(nodeName: string) {
  return components[nodeName]
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
