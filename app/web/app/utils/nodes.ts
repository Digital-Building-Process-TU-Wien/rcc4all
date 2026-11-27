import type { NodeRegistrySchema, SubworkflowPort } from '~/schemas'
import {
  getNodeLocaleMetadata,
  getRegisteredNodeNames,
} from '~/schemas'
import {
  createSubworkflowPortNode,
  DEFAULT_SUBWORKFLOW_OUTPUT_PORT,
} from './subworkflow-graph'

export type { SubworkflowPort }

export type SupportedLocale = 'en' | 'de'

// Editor-side mirrors of the generated workflow-file types. They are
// deliberately hand-written: the editor graph carries concerns the stored
// workflow file does not (the `viewport` on a subworkflow definition, Vue
// Flow handles on edges, and the runtime `label` on node data). The stored
// file types stay generated in `app/schemas/generated/workflow.d.ts`.
export interface StoredEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string | null
  targetHandle?: string | null
}

/**
 * Base interface for all node data
 */
export interface NodeData {
  label: string
  noInput?: boolean
  noOutput?: boolean
  nodeName: string
  filename?: string
  settings?: Record<string, any>
  input_bindings?: Record<string, string>
  subworkflow?: SubworkflowDefinitionData
}

export interface StoredNode {
  id: string
  position: { x: number, y: number }
  data: NodeData
}

export interface SubworkflowDefinitionData {
  name: string
  nodes: StoredNode[]
  edges: StoredEdge[]
  viewport?: { x: number, y: number, zoom: number }
}

export interface AvailableNode {
  label: string
  nodeName: string
  categories: string[]
  description?: string
  markdownDescription?: string
}

const CAMEL_BOUNDARY_RE = /([a-z0-9])([A-Z])/g
const ACRONYM_BOUNDARY_RE = /([A-Z])([A-Z][a-z])/g
const UPPERCASE_DIGIT_RE = /([A-Z])(\d)/gi
const DIGIT_UPPERCASE_RE = /(\d)([A-Z])/gi
const DIGIT_LOWERCASE_RE = /(\d)([a-z])/g

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
    .replace(CAMEL_BOUNDARY_RE, '$1 $2')
    .replace(ACRONYM_BOUNDARY_RE, '$1 $2')
    .replace(UPPERCASE_DIGIT_RE, '$1 $2')
    .replace(DIGIT_UPPERCASE_RE, '$1 $2')
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
    const processed = rest.replace(DIGIT_LOWERCASE_RE, (match, digit, letter) => {
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
  comparison: 'Comparison',
  concat_string: 'ConcatString',
  file_input: 'FileInput',
  generate_3d_cube: 'Generate3DCube',
  geometry_projection: 'GeometryProjection',
  get_element_creation_position_door: 'GetElementCreationPositionDoor',
  get_property: 'GetProperty',
  ids_checker: 'IdsChecker',
  ifc_element_filter: 'IfcElementFilter',
  json_output: 'JsonOutput',
  loi_check: 'LoiCheck',
  measurement: 'Measurement',
  set_3d_position_rotation: 'Set3DPositionRotation',
  subworkflow: 'SubworkflowNode',
  subworkflow_input: 'SubworkflowInput',
  subworkflow_output: 'SubworkflowOutput',
  tilt_of_components: 'TiltOfComponents',
}

export function createSubworkflowDefinition(): SubworkflowDefinitionData {
  return {
    name: '',
    nodes: [
      createSubworkflowPortNode(
        'output',
        { name: DEFAULT_SUBWORKFLOW_OUTPUT_PORT },
        { x: 480, y: 140 },
      ),
    ],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  }
}

export function createNodeData(availableNode: AvailableNode): NodeData {
  if (availableNode.nodeName === 'subworkflow') {
    return {
      label: availableNode.label,
      nodeName: 'subworkflow',
      subworkflow: createSubworkflowDefinition(),
    }
  }

  return {
    label: availableNode.label,
    noInput: availableNode.nodeName === 'file_input',
    nodeName: availableNode.nodeName,
  }
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

export function getAvailableNodes(locale: SupportedLocale = 'en'): AvailableNode[] {
  return getRegisteredNodeNames()
    .map((nodeName) => {
      const metadata = getNodeLocaleMetadata(nodeName, locale)
      return {
        nodeName,
        label: metadata.title || getNodeLabel(nodeName),
        categories: metadata.categories,
        description: metadata.description,
        markdownDescription: metadata.markdownDescription,
      }
    })
    .sort((left, right) => left.label.localeCompare(right.label))
}

/**
 * Get all available node component names
 * @returns Array of available node names
 */
export function getAvailableNodeNames(): string[] {
  return getRegisteredNodeNames()
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
