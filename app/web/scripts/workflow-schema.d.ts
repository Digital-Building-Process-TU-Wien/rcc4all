/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */

/**
 * Path to the IFC file, relative to the workflow JSON when not absolute.
 */
export type Path = string
/**
 * User-chosen identifier for this model. The reserved slug 'main' is the main IFC file.
 */
export type Slug = string
/**
 * Optional SHA-256 content hash of the file, recorded when the file was assigned.
 */
export type FileHash = string
/**
 * IFC files loaded for this workflow, each keyed by a model slug. Exactly one file must use the reserved slug 'main'.
 */
export type IFCFiles = ModelFile[]
/**
 * Unique workflow node identifier.
 */
export type NodeID = string
/**
 * Registered node type name.
 */
export type NodeType = string
/**
 * Human-readable label for the node. Falls back to node type if empty.
 */
export type NodeLabel = string
/**
 * Canvas position. Persisted so the editor can restore layout; ignored by execution.
 */
export type Position = (NodePosition | null)
/**
 * Canvas X coordinate.
 */
export type X = number
/**
 * Canvas Y coordinate.
 */
export type Y = number
/**
 * Embedded subworkflow definition when this node's type is 'subworkflow'.
 */
export type Subworkflow = (SubworkflowDefinition | null)
/**
 * Display name.
 */
export type Name = string
/**
 * Nodes belonging to the subworkflow.
 */
export type Nodes1 = WorkflowNode[]
/**
 * Upstream node ID.
 */
export type SourceNode = string
/**
 * Downstream node ID.
 */
export type TargetNode = string
/**
 * Edges belonging to the subworkflow.
 */
export type Edges = WorkflowEdge[]
/**
 * Workflow nodes to execute.
 */
export type Nodes = WorkflowNode[]
/**
 * Directed edges used to determine execution order.
 */
export type Edges1 = WorkflowEdge[]
/**
 * Port name used in bindings.
 */
export type PortName = string
export type PortType = (PortScalar | PortArray | PortUnion)
/**
 * One of the scalar JSON types, or 'any' for an explicit wildcard.
 */
export type Type = ('string' | 'integer' | 'number' | 'boolean' | 'object' | 'any')
/**
 * Always 'array'.
 */
export type Type1 = 'array'
/**
 * Type of every element.
 */
export type ItemType = (PortScalar | PortArray | PortUnion)
/**
 * Always 'union'.
 */
export type Type2 = 'union'
/**
 * Every member type an assignable value may have.
 */
export type Members = (PortScalar | PortArray | PortUnion)[]

export interface WorkflowModels {
  workflow?: WorkflowDefinition
  port?: SubworkflowPort
  [k: string]: unknown
}
export interface WorkflowDefinition {
  files?: IFCFiles
  nodes?: Nodes
  edges?: Edges1
}
/**
 * An IFC file assigned to a workflow slot, keyed by a user-chosen slug.
 */
export interface ModelFile {
  path: Path
  slug: Slug
  hash?: FileHash
}
export interface WorkflowNode {
  id: NodeID
  type: NodeType
  label?: NodeLabel
  settings?: NodeSettings
  input_bindings?: InputBindings
  position?: Position
  subworkflow?: Subworkflow
}
/**
 * User-authored settings passed directly to the node function.
 */
export interface NodeSettings {
  [k: string]: unknown
}
/**
 * Mappings from node input names to previously produced '<node_id>.<field_name>' references.
 */
export interface InputBindings {
  [k: string]: string
}
export interface NodePosition {
  x?: X
  y?: Y
}
export interface SubworkflowDefinition {
  name?: Name
  nodes?: Nodes1
  edges?: Edges
}
export interface WorkflowEdge {
  source: SourceNode
  target: TargetNode
}
export interface SubworkflowPort {
  name: PortName
  type: PortType
}
export interface PortScalar {
  type: Type
}
export interface PortArray {
  type: Type1
  items: ItemType
}
export interface PortUnion {
  type: Type2
  members: Members
}
