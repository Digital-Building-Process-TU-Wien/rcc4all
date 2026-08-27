/**
 * Base interface for all node data
 */
import type { NodeRegistrySchema } from '@@/scripts/schema'
import schemaJson from '@@/scripts/schema.json'

export type SupportedLocale = 'en' | 'de'

export interface NodeData {
  label: string
  noInput?: boolean
  nodeName: string
  filename?: string
  settings?: Record<string, any>
  input_bindings?: Record<string, string>
}

export interface AvailableNode {
  label: string
  nodeName: string
  categories: string[]
  description?: string
  markdownDescription?: string
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

function formatNodeLabel(nodeName: string): string {
  return nodeName
    .replace(/([a-z0-9])([A-Z])/g, '$1 $2')
    .replace(/([A-Z])([A-Z][a-z])/g, '$1 $2')
    .replace(/([A-Z])(\d)/gi, '$1 $2')
    .replace(/(\d)([A-Z])/gi, '$1 $2')
    .trim()
}

function toPascalCase(str: string): string {
  const parts = str.split('_')
  const capitalizedParts = parts.map((part) => {
    if (!part)
      return part
    const firstChar = part.charAt(0).toUpperCase()
    const rest = part.slice(1)
    // Handle letter after digit (e.g., "3d" -> "3D")
    const processed = rest.replace(/(\d)([a-z])/g, (match, digit, letter) => {
      return digit + letter.toUpperCase()
    })
    return firstChar + processed
  })
  const result = capitalizedParts.join('')
  return result
}

const nodeNameToComponent: Record<string, string> = {
  bcf_output: 'BcfOutput',
  collision: 'Collision',
  concat_string: 'ConcatString',
  file_input: 'FileInput',
  generate_3d_cube: 'Generate3DCube',
  get_name: 'GetName',
  get_property: 'GetProperty',
  ifc_element_filter: 'IfcElementFilter',
  json_output: 'JsonOutput',
  loi_check: 'LoiCheck',
}

/**
 * Get a node component by its nodeName
 * @param nodeName - The name of the node component to load (snake_case)
 * @returns The Vue component or undefined if not found
 */
export function getNodeComponent(nodeName: string) {
  const componentName = nodeNameToComponent[nodeName] || toPascalCase(nodeName)

  // Try to find a specific component for this node type first
  const specificComponent = components[componentName]
  if (specificComponent) {
    return specificComponent
  }

  // Fall back to generic WorkflowNode component
  return components.WorkflowNode
}

export function getNodeLabel(nodeName: string): string {
  return formatNodeLabel(nodeName)
}

function toSnakeCase(str: string): string {
  return str
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
}

function getNodeCategories(nodeName: string, locale: SupportedLocale = 'en'): string[] {
  const _key = toSnakeCase(nodeName)
  const nodeData = (schemaJson.properties as any)[nodeName]
  if (!nodeData)
    return []

  const localeData = nodeData.locales?.[locale] || nodeData.locales?.en
  return localeData?.categories || nodeData.categories || []
}

function getNodeDescription(nodeName: string, locale: SupportedLocale = 'en'): { description?: string, markdownDescription?: string } {
  const _key = toSnakeCase(nodeName)
  const nodeData = (schemaJson.properties as any)[nodeName]
  if (!nodeData)
    return {}

  const localeData = nodeData.locales?.[locale] || nodeData.locales?.en
  return {
    description: localeData?.description,
    markdownDescription: localeData?.markdownDescription,
  }
}

export function getAvailableNodes(locale: SupportedLocale = 'en'): AvailableNode[] {
  const nodeNames = Object.keys(schemaJson.properties || {})

  return nodeNames
    .map((nodeName) => {
      const nodeData = (schemaJson.properties as any)[nodeName]
      const localeData = nodeData?.locales?.[locale] || nodeData?.locales?.en
      const title = localeData?.title || nodeData?.title || getNodeLabel(nodeName)

      return {
        nodeName,
        label: title,
        categories: getNodeCategories(nodeName, locale),
        ...getNodeDescription(nodeName, locale),
      }
    })
    .sort((left, right) => left.label.localeCompare(right.label))
}

/**
 * Get all available node component names
 * @returns Array of available node names
 */
export function getAvailableNodeNames(): string[] {
  return Object.keys(schemaJson.properties || {})
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
