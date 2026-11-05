import type { NodeRegistrySchema } from '@@/scripts/schema'
import type { Node } from '@vue-flow/core'
import type { NodeData } from './nodes'
import schemaJson from '@@/scripts/schema.json'

const CAMEL_BOUNDARY_RE = /([a-z0-9])([A-Z])/g
const ACRONYM_BOUNDARY_RE = /([A-Z])([A-Z][a-z])/g
const UPPERCASE_DIGIT_RE = /([A-Z])(\d)/gi
const DIGIT_UPPERCASE_RE = /(\d)([A-Z])/gi

export const INPUT_HANDLE_PREFIX = 'input:'
export const OUTPUT_HANDLE_PREFIX = 'output:'

/**
 * A node-shaped value whose ports can be resolved. Normal nodes read the
 * generated schema; subworkflow nodes read their inner input/output nodes.
 */
export interface PortNode {
  data?: NodeData
}

export interface PortInfo {
  name: string
  type: TypeInfo
  label: string
  description: string
}

/**
 * Convert a schema type to a Vue Flow Node type.
 * Schema types (e.g., ConcatenateStrings) have { settings, result, inputs } at the root,
 * which maps to the Node's `data` property.
 * This type ensures `data` is always defined (not undefined).
 */
export type NodeWithSchema<T> = Omit<Node<T>, 'data'> & { data: T }

/**
 * Get the Node type for a specific node by its snake_case name.
 * @template K - The node name key from NodeRegistrySchema
 * @example type ConcatNode = SchemaNodeType<'concat_string'>
 */
export type SchemaNodeType<K extends keyof NodeRegistrySchema> = NodeWithSchema<NonNullable<NodeRegistrySchema[K]>>

/**
 * Helper type to extract the data type from a Node.
 * Useful for getting the schema type back from a Node type.
 */
export type NodeDataType<T extends Node> = T extends Node<infer Data> ? Data : never

export function getNodeSchema<K extends keyof NodeRegistrySchema>(nodeName: K): NodeRegistrySchema[K] {
  return schemaJson.properties[nodeName] as any
}

function getSchemaPorts(nodeName: string, direction: 'inputs' | 'outputs'): PortInfo[] {
  const schema = (schemaJson.properties as any)[nodeName]
  const properties = direction === 'inputs'
    ? schema?.properties?.inputs?.properties
    : schema?.properties?.result?.properties

  if (!properties)
    return []

  return Object.entries(properties).map(([name, property]) => ({
    name,
    type: parseTypeSchema(property),
    label: (property as any)?.title || formatLabel(name),
    description: (property as any)?.description || '',
  }))
}

function normalizeTypeInfo(value: unknown): TypeInfo {
  if (typeof value === 'string')
    return { type: value as TypeInfo['type'] }
  if (value && typeof value === 'object' && typeof (value as any).type === 'string')
    return value as TypeInfo
  return { type: 'null' }
}

function parsePort(raw: unknown): PortInfo | null {
  if (!raw || typeof raw !== 'object')
    return null

  const entry = raw as { name?: unknown, type?: unknown }
  if (typeof entry.name !== 'string' || entry.name.length === 0)
    return null

  return {
    name: entry.name,
    type: normalizeTypeInfo(entry.type),
    label: formatLabel(entry.name),
    description: '',
  }
}

function getSubworkflowPorts(node: PortNode, direction: 'inputs' | 'outputs'): PortInfo[] {
  const innerNodes = node.data?.subworkflow?.nodes ?? []

  if (direction === 'inputs') {
    return innerNodes
      .filter(inner => inner.data.nodeName === 'subworkflow_input')
      .map(inner => parsePort(inner.data.settings?.port))
      .filter((port): port is PortInfo => port !== null)
  }

  const outputNode = innerNodes.find(inner => inner.data.nodeName === 'subworkflow_output')
  const port = outputNode ? parsePort(outputNode.data.settings?.port) : null
  return port ? [port] : []
}

function getMetaNodePorts(node: PortNode, direction: 'inputs' | 'outputs'): PortInfo[] | null {
  const nodeName = node.data?.nodeName
  const isSource = nodeName === 'subworkflow_input' && direction === 'outputs'
  const isSink = nodeName === 'subworkflow_output' && direction === 'inputs'
  if (!isSource && !isSink)
    return null

  const port = parsePort(node.data?.settings?.port)
  return port ? [port] : []
}

export function getNodeInputPorts(node: PortNode): PortInfo[] {
  const metaPorts = getMetaNodePorts(node, 'inputs')
  if (metaPorts)
    return metaPorts
  if (node.data?.nodeName === 'subworkflow')
    return getSubworkflowPorts(node, 'inputs')
  return getSchemaPorts(node.data?.nodeName ?? '', 'inputs')
}

export function getNodeOutputPorts(node: PortNode): PortInfo[] {
  const metaPorts = getMetaNodePorts(node, 'outputs')
  if (metaPorts)
    return metaPorts
  if (node.data?.nodeName === 'subworkflow')
    return getSubworkflowPorts(node, 'outputs')
  return getSchemaPorts(node.data?.nodeName ?? '', 'outputs')
}

export function getNodeOutputs(node: PortNode): string[] {
  return getNodeOutputPorts(node).map(port => port.name)
}

export function getNodeInputs(node: PortNode): string[] {
  return getNodeInputPorts(node).map(port => port.name)
}

export function getInputLabel(node: PortNode, inputName: string): string {
  return getNodeInputPorts(node).find(port => port.name === inputName)?.label
    ?? formatLabel(inputName)
}

export function getInputDescription(node: PortNode, inputName: string): string {
  return getNodeInputPorts(node).find(port => port.name === inputName)?.description ?? ''
}

export interface TypeInfo {
  type: 'string' | 'number' | 'integer' | 'boolean' | 'array' | 'object' | 'null'
  items?: TypeInfo
  /**
   * Set when the schema is a union (`anyOf`) of two or more non-null types.
   * `type` mirrors the first member so plain displays stay sensible.
   */
  anyOf?: TypeInfo[]
}

export function getOutputType(node: PortNode, outputName: string): TypeInfo {
  return getNodeOutputPorts(node).find(port => port.name === outputName)?.type
    ?? { type: 'null' }
}

export function getInputType(node: PortNode, inputName: string): TypeInfo {
  return getNodeInputPorts(node).find(port => port.name === inputName)?.type
    ?? { type: 'null' }
}

function parseTypeSchema(schema: any): TypeInfo {
  if (!schema)
    return { type: 'null' }

  if (schema.type === 'array') {
    return {
      type: 'array',
      items: schema.items ? parseTypeSchema(schema.items) : undefined,
    }
  }

  if (Array.isArray(schema.anyOf)) {
    const members = schema.anyOf
      .filter((t: any) => t.type !== 'null')
      .map(parseTypeSchema)
    if (members.length === 0)
      return { type: 'null' }
    if (members.length === 1)
      return members[0]
    return { ...members[0], anyOf: members }
  }

  return { type: schema.type || 'null' }
}

/**
 * Whether an output type can feed an input type. Unions are honoured on both
 * sides: every member of a union output must fit, and a union input accepts an
 * output if any of its members do.
 */
function isAssignable(output: TypeInfo, input: TypeInfo): boolean {
  if (output.anyOf)
    return output.anyOf.every(member => isAssignable(member, input))
  if (input.anyOf)
    return input.anyOf.some(member => isAssignable(output, member))

  // 'null' means unknown/no type — accept while either side lacks a concrete
  // type. Manually typed subworkflow ports default to 'null' ("Any").
  if (output.type === 'null' || input.type === 'null')
    return true

  // For arrays, compare item types rather than only the top-level 'array' type.
  if (output.type === 'array' && input.type === 'array')
    return areItemsCompatible(output.items, input.items)

  if (output.type === input.type)
    return true
  if (output.type === 'integer' && input.type === 'number')
    return true
  return false
}

export function areTypesCompatible(output: TypeInfo, input: TypeInfo): boolean {
  return isAssignable(output, input)
}

function areItemsCompatible(output: TypeInfo | undefined, input: TypeInfo | undefined): boolean {
  if (!output || !input)
    return true
  return isAssignable(output, input)
}

/** Human-readable type name for warnings, e.g. `array<integer | string>`. */
export function describeType(type: TypeInfo): string {
  if (type.anyOf?.length)
    return type.anyOf.map(describeType).join(' | ')
  if (type.type === 'array')
    return `array<${type.items ? describeType(type.items) : 'any'}>`
  return type.type
}

const MODEL_SLUG_PREFIX = 'model_slug'

/**
 * A model input is a consumer's model selection (fed by a File Input node's output).
 * Model ports only connect to other model ports — never to ordinary data ports.
 */
export function isModelInput(inputName: string): boolean {
  return inputName.startsWith(MODEL_SLUG_PREFIX)
}

/**
 * The File Input node's `model_slug` output is the only model-producing port.
 */
export function isModelOutput(nodeName: string, outputName: string): boolean {
  return nodeName === 'file_input' && outputName === 'model_slug'
}

/**
 * Whether a source node's output may feed a target node's input, taking the
 * dedicated model port into account in addition to type compatibility.
 */
export function arePortsCompatible(
  targetNode: PortNode,
  inputName: string,
  sourceNode: PortNode,
  outputName: string,
): boolean {
  const modelToData = isModelInput(inputName) !== isModelOutput(sourceNode.data?.nodeName ?? '', outputName)
  if (modelToData)
    return false
  return areTypesCompatible(
    getOutputType(sourceNode, outputName),
    getInputType(targetNode, inputName),
  )
}

/** Extract the port name from a Vue Flow handle id such as `input:value`. */
export function parsePortHandle(
  handle: string | null | undefined,
  prefix: string,
): string | undefined {
  if (!handle || !handle.startsWith(prefix))
    return undefined
  const name = handle.slice(prefix.length)
  return name.length > 0 ? name : undefined
}

export function formatLabel(str: string): string {
  return str
    .replace(CAMEL_BOUNDARY_RE, '$1 $2')
    .replace(ACRONYM_BOUNDARY_RE, '$1 $2')
    .replace(UPPERCASE_DIGIT_RE, '$1 $2')
    .replace(DIGIT_UPPERCASE_RE, '$1 $2')
    .trim()
}
