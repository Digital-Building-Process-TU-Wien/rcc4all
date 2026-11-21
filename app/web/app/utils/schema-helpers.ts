import type { NodeRegistrySchema } from '@@/scripts/schema'
import type { PortScalar, PortType } from '@@/scripts/workflow-schema'
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
 * The assignability table exported by the Python runner into `schema.json`,
 * so the editor follows the same rules as validation at run time.
 */
const WORKFLOW_SCHEMA = schemaJson as unknown as {
  'x-workflows'?: { compatibility?: Record<string, string[]> }
}

const COMPATIBILITY = WORKFLOW_SCHEMA['x-workflows']?.compatibility ?? {}

/**
 * A node-shaped value whose ports can be resolved. Normal nodes read the
 * generated schema; subworkflow nodes read their inner input/output nodes.
 */
export interface PortNode {
  data?: NodeData
}

export interface PortInfo {
  name: string
  type: PortType
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

const SCALAR_PORT_TYPES = new Set([
  'string',
  'integer',
  'number',
  'boolean',
  'object',
  'any',
])

function isSchemaRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function portTypesEqual(left: PortType, right: PortType): boolean {
  if (left.type !== right.type)
    return false
  if (left.type === 'array' && right.type === 'array')
    return portTypesEqual(left.items, right.items)
  if (left.type === 'union' && right.type === 'union') {
    return left.members.length === right.members.length
      && left.members.every((member, index) => portTypesEqual(member, right.members[index]!))
  }
  return true
}

function collapsePortMembers(members: PortType[]): PortType {
  const unique: PortType[] = []
  for (const member of members) {
    const flattened = member.type === 'union' ? member.members : [member]
    for (const candidate of flattened) {
      if (!unique.some(existing => portTypesEqual(existing, candidate)))
        unique.push(candidate)
    }
  }

  if (unique.length === 0)
    return { type: 'any' }
  if (unique.length === 1)
    return unique[0]!
  return { type: 'union', members: unique }
}

function literalValueToPortType(value: unknown): PortType {
  if (typeof value === 'boolean')
    return { type: 'boolean' }
  if (typeof value === 'number')
    return { type: Number.isInteger(value) ? 'integer' : 'number' }
  if (typeof value === 'string')
    return { type: 'string' }
  return { type: 'object' }
}

/**
 * Derive a runner-compatible `PortType` directly from a node field's JSON Schema.
 */
export function jsonSchemaToPortType(schema: unknown): PortType {
  if (!isSchemaRecord(schema))
    return { type: 'any' }

  const unionBranches = Array.isArray(schema.anyOf)
    ? schema.anyOf
    : Array.isArray(schema.oneOf)
      ? schema.oneOf
      : null
  if (unionBranches) {
    const nonNull = unionBranches.filter(branch => !(isSchemaRecord(branch) && branch.type === 'null'))
    return collapsePortMembers(nonNull.map(jsonSchemaToPortType))
  }

  if (Array.isArray(schema.allOf) && schema.allOf.length === 1)
    return jsonSchemaToPortType(schema.allOf[0])

  if (Array.isArray(schema.type)) {
    const nonNullTypes = schema.type.filter((entry): entry is string => typeof entry === 'string' && entry !== 'null')
    return collapsePortMembers(nonNullTypes.map(typeName => jsonSchemaToPortType({ ...schema, type: typeName })))
  }

  if (schema.type === 'array') {
    return {
      type: 'array',
      items: schema.items !== undefined ? jsonSchemaToPortType(schema.items) : { type: 'any' },
    }
  }

  if (typeof schema.type === 'string' && SCALAR_PORT_TYPES.has(schema.type))
    return { type: schema.type as PortScalar['type'] }

  if ('const' in schema)
    return schema.const === null ? { type: 'any' } : literalValueToPortType(schema.const)

  if (Array.isArray(schema.enum)) {
    const nonNullValues = schema.enum.filter(value => value !== null)
    return collapsePortMembers(nonNullValues.map(literalValueToPortType))
  }

  return { type: 'any' }
}

function getSchemaPorts(nodeName: string, direction: 'inputs' | 'outputs'): PortInfo[] {
  const section = direction === 'inputs' ? 'inputs' : 'result'
  const nodes = schemaJson.properties as Record<string, {
    properties?: Record<string, { properties?: Record<string, Record<string, unknown>> }>
  }>
  const fields = nodes[nodeName]?.properties?.[section]?.properties
  if (!fields)
    return []

  return Object.entries(fields).map(([name, fieldSchema]) => ({
    name,
    type: jsonSchemaToPortType(fieldSchema),
    label: typeof fieldSchema?.title === 'string' && fieldSchema.title.length > 0
      ? fieldSchema.title
      : formatLabel(name),
    description: typeof fieldSchema?.description === 'string' ? fieldSchema.description : '',
  }))
}

/** Whether a value read from workflow JSON is a well-formed port type. */
export function isPortType(value: unknown): value is PortType {
  if (!value || typeof value !== 'object')
    return false

  const port = value as { type?: unknown, items?: unknown, members?: unknown }
  switch (port.type) {
    case 'array':
      return isPortType(port.items)
    case 'union':
      return Array.isArray(port.members)
        && port.members.length > 0
        && port.members.every(isPortType)
    default:
      return typeof port.type === 'string' && SCALAR_PORT_TYPES.has(port.type)
  }
}

/**
 * A missing or malformed port type degrades to the explicit `any` wildcard.
 */
export function normalizePortType(value: unknown): PortType {
  return isPortType(value) ? value : { type: 'any' }
}

function parsePort(raw: unknown): PortInfo | null {
  if (!raw || typeof raw !== 'object')
    return null

  const entry = raw as { name?: unknown, type?: unknown }
  if (typeof entry.name !== 'string' || entry.name.length === 0)
    return null

  return {
    name: entry.name,
    type: normalizePortType(entry.type),
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

/**
 * Input names that have no default in Python's input model. The runner rejects
 * a workflow when any of these are left unbound.
 */
export function getRequiredNodeInputs(node: PortNode): string[] {
  const nodeName = node.data?.nodeName
  if (
    !nodeName
    || nodeName === 'subworkflow'
    || nodeName === 'subworkflow_input'
    || nodeName === 'subworkflow_output'
  ) {
    return []
  }

  const properties = schemaJson.properties as Record<string, {
    properties?: { inputs?: { required?: unknown } }
  }>
  const required = properties[nodeName]?.properties?.inputs?.required
  return Array.isArray(required)
    ? required.filter((entry): entry is string => typeof entry === 'string')
    : []
}

export function getInputLabel(node: PortNode, inputName: string): string {
  return getNodeInputPorts(node).find(port => port.name === inputName)?.label
    ?? formatLabel(inputName)
}

export function getInputDescription(node: PortNode, inputName: string): string {
  return getNodeInputPorts(node).find(port => port.name === inputName)?.description ?? ''
}

export function getOutputType(node: PortNode, outputName: string): PortType {
  return getNodeOutputPorts(node).find(port => port.name === outputName)?.type
    ?? { type: 'any' }
}

export function getInputType(node: PortNode, inputName: string): PortType {
  return getNodeInputPorts(node).find(port => port.name === inputName)?.type
    ?? { type: 'any' }
}

/**
 * Whether an output type can feed an input type. Unions are honoured on both
 * sides: every member of a union output must fit, and a union input accepts an
 * output if any of its members do. The scalar rules come from the table the
 * runner exports.
 */
function isAssignableType(output: PortType, input: PortType): boolean {
  if (output.type === 'union')
    return output.members.every(member => isAssignableType(member, input))
  if (input.type === 'union')
    return input.members.some(member => isAssignableType(output, member))

  if (output.type === 'array' && input.type === 'array')
    return isAssignableType(output.items, input.items)

  return (COMPATIBILITY[output.type] ?? []).includes(input.type)
}

export function areTypesCompatible(output: PortType, input: PortType): boolean {
  return isAssignableType(output, input)
}

/** Human-readable type name for warnings, e.g. `array<integer | string>`. */
export function describeType(type: PortType): string {
  if (type.type === 'union')
    return type.members.map(describeType).join(' | ')
  if (type.type === 'array')
    return `array<${describeType(type.items)}>`
  return type.type
}

const MODEL_SLUG_PREFIX = 'model_slug'

/**
 * A model input is a consumer's model selection, typically fed by a File Input
 * node's `model_slug` output. Editor UX only (auto-binding preferences and
 * labels) — compatibility itself is decided by the exported rule table,
 * exactly like the runner.
 */
export function isModelInput(inputName: string): boolean {
  return inputName.startsWith(MODEL_SLUG_PREFIX)
}

/**
 * Whether a source node's output may feed a target node's input. Pure type
 * compatibility through the exported rule table — the same rule the runner
 * applies, so the editor warns exactly where the runner would reject.
 */
export function arePortsCompatible(
  targetNode: PortNode,
  inputName: string,
  sourceNode: PortNode,
  outputName: string,
): boolean {
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
