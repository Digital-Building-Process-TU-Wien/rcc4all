import type { NodeRegistrySchema } from '@@/scripts/schema'
import type { Node } from '@vue-flow/core'
import schemaJson from '@@/scripts/schema.json'

const CAMEL_BOUNDARY_RE = /([a-z0-9])([A-Z])/g
const ACRONYM_BOUNDARY_RE = /([A-Z])([A-Z][a-z])/g
const UPPERCASE_DIGIT_RE = /([A-Z])(\d)/gi
const DIGIT_UPPERCASE_RE = /(\d)([A-Z])/gi

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

export function getNodeOutputs(nodeName: string): string[] {
  const schema = (schemaJson.properties as any)[nodeName]
  if (!schema?.properties?.result?.properties)
    return []
  return Object.keys(schema.properties.result.properties)
}

export function getNodeInputs(nodeName: string): string[] {
  const schema = (schemaJson.properties as any)[nodeName]
  if (!schema?.properties?.inputs?.properties)
    return []
  return Object.keys(schema.properties.inputs.properties)
}

export function getInputLabel(nodeName: string, inputName: string): string {
  const schema = (schemaJson.properties as any)[nodeName]
  const inputSchema = schema?.properties?.inputs?.properties?.[inputName]
  return inputSchema?.title || formatLabel(inputName)
}

export function getInputDescription(nodeName: string, inputName: string): string {
  const schema = (schemaJson.properties as any)[nodeName]
  const inputSchema = schema?.properties?.inputs?.properties?.[inputName]
  return inputSchema?.description || ''
}

export interface TypeInfo {
  type: 'string' | 'number' | 'integer' | 'boolean' | 'array' | 'object' | 'null'
  items?: TypeInfo
  anyOf?: TypeInfo[]
}

export function getOutputType(nodeName: string, outputField: string): TypeInfo {
  const schema = (schemaJson.properties as any)[nodeName]
  const outputSchema = schema?.properties?.result?.properties?.[outputField]
  return parseTypeSchema(outputSchema)
}

export function getInputType(nodeName: string, inputName: string): TypeInfo {
  const schema = (schemaJson.properties as any)[nodeName]
  const inputSchema = schema?.properties?.inputs?.properties?.[inputName]
  return parseTypeSchema(inputSchema)
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

  if (schema.anyOf) {
    const candidates = schema.anyOf
      .filter((t: any) => t.type !== 'null')
      .map((t: any) => parseTypeSchema(t))
    if (candidates.length === 0)
      return { type: 'null' }
    const [primary, ...rest] = candidates
    return rest.length ? { ...primary, anyOf: candidates } : primary
  }

  return { type: schema.type || 'null' }
}

export function areTypesCompatible(output: TypeInfo, input: TypeInfo): boolean {
  // 'null' means unknown/no type — accept while the schema lacks a concrete type.
  if (output.type === 'null')
    return true

  // If the input accepts multiple forms (anyOf), accept if output matches any candidate.
  if (input.anyOf?.length)
    return input.anyOf.some(candidate => areTypesCompatible(output, candidate))

  // For arrays, compare item types rather than only the top-level 'array' type.
  if (output.type === 'array' && input.type === 'array')
    return areItemsCompatible(output.items, input.items)

  if (output.type === input.type)
    return true
  if (output.type === 'integer' && input.type === 'number')
    return true
  return false
}

function areItemsCompatible(output: TypeInfo | undefined, input: TypeInfo | undefined): boolean {
  if (!output || !input)
    return true
  if (output.type === 'null')
    return true
  if (output.type === input.type)
    return true
  if (output.type === 'integer' && input.type === 'number')
    return true
  return false
}

export function formatLabel(str: string): string {
  return str
    .replace(CAMEL_BOUNDARY_RE, '$1 $2')
    .replace(ACRONYM_BOUNDARY_RE, '$1 $2')
    .replace(UPPERCASE_DIGIT_RE, '$1 $2')
    .replace(DIGIT_UPPERCASE_RE, '$1 $2')
    .trim()
}
