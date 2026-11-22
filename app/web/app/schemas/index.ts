import type { Node } from '@vue-flow/core'
import type { NodeRegistrySchema } from './generated/nodes'
import type { NodeData, StoredNode, SupportedLocale } from '~/utils/nodes'
import type { ScopeFrame } from '~/utils/workflow-serialization'
import { NODE_SCHEMAS } from './generated/registry'

export type { NodeRegistrySchema } from './generated/nodes'
export { NODE_SCHEMAS } from './generated/registry'
export type {
  ModelFile,
  NodePosition,
  SubworkflowDefinition,
  SubworkflowPort,
  WorkflowDefinition,
  WorkflowEdge,
  WorkflowNode,
} from './generated/workflow'
export {
  ModelFileSchema,
  NodePositionSchema,
  SubworkflowDefinitionSchema,
  SubworkflowPortSchema,
  WorkflowDefinitionSchema,
  WorkflowEdgeSchema,
  WorkflowNodeSchema,
} from './generated/workflow.zod'

export type NodeName = keyof NodeRegistrySchema

export const INPUT_HANDLE_PREFIX = 'input:'
export const OUTPUT_HANDLE_PREFIX = 'output:'

const CAMEL_BOUNDARY_RE = /([a-z0-9])([A-Z])/g
const ACRONYM_BOUNDARY_RE = /([A-Z])([A-Z][a-z])/g
const UPPERCASE_DIGIT_RE = /([A-Z])(\d)/gi
const DIGIT_UPPERCASE_RE = /(\d)([A-Z])/gi

const METADATA_ONLY_KEYS = new Set(['title', 'description', 'default', 'examples', '$comment'])
const PRIMITIVE_TYPES = new Set(['string', 'integer', 'number', 'boolean', 'null'])

/** Standard JSON Schema (Draft 2020-12) node as exported by `rcc4all-runner`. */
export interface JsonSchema {
  $schema?: string
  $id?: string
  type?: string | readonly string[]
  title?: string
  description?: string
  default?: unknown
  const?: unknown
  enum?: readonly unknown[]
  items?: JsonSchema
  properties?: Record<string, JsonSchema>
  required?: readonly string[]
  additionalProperties?: boolean | JsonSchema
  anyOf?: readonly JsonSchema[]
  oneOf?: readonly JsonSchema[]
  allOf?: readonly JsonSchema[]
  [key: string]: unknown
}

export interface NodeLocaleMetadata {
  title?: string
  description?: string
  categories?: readonly string[]
  markdownDescription?: string
}

export interface NodeSchemaDocument extends JsonSchema {
  title?: string
  description?: string
  categories?: readonly string[]
  markdownDescription?: string
  locales?: Record<string, NodeLocaleMetadata>
  properties?: {
    settings?: JsonSchema
    inputs?: JsonSchema
    result?: JsonSchema
  }
}

/**
 * A node-shaped value whose ports can be resolved. Normal nodes read the
 * per-node JSON Schemas; subworkflow nodes resolve pass-through ports from
 * their inner nodes and enclosing scope.
 */
export interface PortNode {
  data?: NodeData
}

export interface PortInfo {
  name: string
  /** Concrete JSON Schema for this port, or `undefined` for an unconstrained pass-through slot. */
  schema?: JsonSchema
  label: string
  description: string
}

export interface PortResolutionContext {
  /**
   * Concrete output schemas bound by the enclosing scope to each
   * `subworkflow_input` port name when inspecting inside a subworkflow.
   */
  parentInputSchemas?: Record<string, JsonSchema | undefined>
  /**
   * Sibling nodes in the current scope, used to resolve pass-through
   * subworkflows whose `subworkflow_output` reads from a `subworkflow_input`.
   */
  siblingNodes?: ReadonlyArray<Pick<StoredNode, 'id' | 'data'>>
}

export type OutputSocketTarget = 'bcf'

/**
 * Convert a schema type to a Vue Flow Node type.
 * Schema types have `{ settings, result, inputs }` at the root, which maps to
 * the Node's `data` property. Ensures `data` is always defined.
 */
export type NodeWithSchema<T> = Omit<Node<T>, 'data'> & { data: T }

/**
 * Get the Vue Flow Node type for a specific node by its snake_case name.
 * @example type ConcatNode = SchemaNodeType<'concat_string'>
 */
export type SchemaNodeType<K extends keyof NodeRegistrySchema> = NodeWithSchema<NonNullable<NodeRegistrySchema[K]>>

/** Extract the data type from a Vue Flow Node type. */
export type NodeDataType<T extends Node> = T extends Node<infer Data> ? Data : never

/** Get the schema data type for a specific node by its snake_case name. */
export type NodeTypeFromSchema<K extends keyof NodeRegistrySchema> = NodeRegistrySchema[K]

const NODE_SCHEMA_MAP = NODE_SCHEMAS as unknown as Record<string, NodeSchemaDocument>

export function getNodeSchema<K extends keyof NodeRegistrySchema>(nodeName: K): NodeRegistrySchema[K] {
  return NODE_SCHEMAS[nodeName] as unknown as NodeRegistrySchema[K]
}

export function getNodeSchemaDocument(nodeName: string): NodeSchemaDocument | undefined {
  return NODE_SCHEMA_MAP[nodeName]
}

export function getRegisteredNodeNames(): NodeName[] {
  return Object.keys(NODE_SCHEMAS) as NodeName[]
}

export function getNodeLocaleMetadata(
  nodeName: string,
  locale: SupportedLocale = 'en',
): { title: string, categories: string[], description?: string, markdownDescription?: string } {
  const doc = NODE_SCHEMA_MAP[nodeName]
  if (!doc)
    return { title: formatLabel(nodeName), categories: [] }

  const localeData = doc.locales?.[locale] ?? doc.locales?.en
  return {
    title: localeData?.title || doc.title || formatLabel(nodeName),
    categories: [...(localeData?.categories ?? doc.categories ?? [])],
    description: localeData?.description ?? doc.description,
    markdownDescription: localeData?.markdownDescription ?? doc.markdownDescription,
  }
}

// ---------------------------------------------------------------------------
// Direct JSON Schema structural assignability & formatting
// Mirrors `app/runner/src/rcc4all_runner/schemas.py`.
// ---------------------------------------------------------------------------

function isSchemaObject(value: unknown): value is JsonSchema {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isUnconstrained(schema: JsonSchema): boolean {
  for (const key of Object.keys(schema)) {
    if (!METADATA_ONLY_KEYS.has(key))
      return false
  }
  return true
}

function unwrapAllOf(schema: JsonSchema): JsonSchema {
  if (Array.isArray(schema.allOf) && schema.allOf.length === 1 && isSchemaObject(schema.allOf[0]))
    return schema.allOf[0]
  return schema
}

function normalizeNullable(schema: JsonSchema): JsonSchema {
  const unwrapped = unwrapAllOf(schema)
  const branches = unwrapped.anyOf ?? unwrapped.oneOf
  if (Array.isArray(branches)) {
    const nonNull = branches.filter(
      (branch): branch is JsonSchema => isSchemaObject(branch) && branch.type !== 'null',
    )
    if (nonNull.length === 0)
      return { type: 'null' }
    if (nonNull.length === 1)
      return normalizeNullable(nonNull[0]!)
    return { anyOf: nonNull }
  }

  if (Array.isArray(unwrapped.type)) {
    const nonNullTypes = unwrapped.type.filter(
      (entry): entry is string => typeof entry === 'string' && entry !== 'null',
    )
    if (nonNullTypes.length === 0)
      return { type: 'null' }
    if (nonNullTypes.length === 1)
      return { ...unwrapped, type: nonNullTypes[0] }
    return { anyOf: nonNullTypes.map(typeName => ({ ...unwrapped, type: typeName })) }
  }

  return unwrapped
}

function extractLiterals(schema: JsonSchema): unknown[] | null {
  if ('const' in schema)
    return schema.const === null ? [] : [schema.const]
  if (Array.isArray(schema.enum))
    return schema.enum.filter(value => value !== null)
  return null
}

function literalKey(value: unknown): string {
  if (typeof value === 'boolean')
    return `boolean:${value}`
  if (typeof value === 'number')
    return `number:${value}`
  if (typeof value === 'string')
    return `string:${value}`
  return `other:${JSON.stringify(value)}`
}

function literalPrimitiveType(value: unknown): string {
  if (typeof value === 'boolean')
    return 'boolean'
  if (typeof value === 'number')
    return Number.isInteger(value) ? 'integer' : 'number'
  if (typeof value === 'string')
    return 'string'
  return 'object'
}

function primitiveAssignable(outputType: string, inputType: string): boolean {
  if (outputType === inputType)
    return true
  return outputType === 'integer' && inputType === 'number'
}

function isObjectAssignable(output: JsonSchema, input: JsonSchema): boolean {
  if (isSchemaObject(input.properties)) {
    if (!isSchemaObject(output.properties))
      return false

    const outputProps = output.properties
    const inputProps = input.properties
    const outputRequired = new Set(output.required ?? [])

    for (const req of input.required ?? []) {
      if (!(req in outputProps) || !outputRequired.has(req))
        return false
    }

    for (const [fieldName, inputProp] of Object.entries(inputProps)) {
      const outputProp = outputProps[fieldName]
      if (!outputProp)
        continue
      if (!isSchemaAssignable(outputProp, inputProp))
        return false
    }

    return true
  }

  if (isSchemaObject(input.additionalProperties)) {
    const inputVal = input.additionalProperties
    if (isSchemaObject(output.additionalProperties))
      return isSchemaAssignable(output.additionalProperties, inputVal)
    if (output.additionalProperties === false && isSchemaObject(output.properties))
      return Object.values(output.properties).every(prop => isSchemaAssignable(prop, inputVal))
    return isSchemaAssignable({}, inputVal)
  }

  // Unconstrained `object` (e.g. `dict[str, Any]`) accepts any object.
  return true
}

/**
 * Whether a value matching `rawOutput` JSON Schema may feed `rawInput`.
 * Matches `rcc4all_runner.schemas.is_schema_assignable`.
 */
export function isSchemaAssignable(rawOutput: JsonSchema, rawInput: JsonSchema): boolean {
  const output = normalizeNullable(rawOutput)
  const input = normalizeNullable(rawInput)

  if (isUnconstrained(output) || isUnconstrained(input))
    return true

  const outputBranches = output.anyOf ?? output.oneOf
  if (Array.isArray(outputBranches)) {
    return outputBranches.length > 0
      && outputBranches.every(branch => isSchemaAssignable(branch, input))
  }

  const inputBranches = input.anyOf ?? input.oneOf
  if (Array.isArray(inputBranches)) {
    return inputBranches.some(branch => isSchemaAssignable(output, branch))
  }

  const outputLiterals = extractLiterals(output)
  const inputLiterals = extractLiterals(input)
  if (outputLiterals !== null) {
    if (inputLiterals !== null) {
      const allowed = new Set(inputLiterals.map(literalKey))
      return outputLiterals.every(value => allowed.has(literalKey(value)))
    }
    if (typeof input.type === 'string' && PRIMITIVE_TYPES.has(input.type))
      return outputLiterals.every(value => primitiveAssignable(literalPrimitiveType(value), input.type as string))
    return false
  }

  if (inputLiterals !== null)
    return false

  const outputType = output.type
  const inputType = input.type

  if (
    typeof outputType === 'string'
    && typeof inputType === 'string'
    && PRIMITIVE_TYPES.has(outputType)
    && PRIMITIVE_TYPES.has(inputType)
  ) {
    return primitiveAssignable(outputType, inputType)
  }

  if (outputType === 'array' && inputType === 'array') {
    const outputItems = isSchemaObject(output.items) ? output.items : {}
    const inputItems = isSchemaObject(input.items) ? input.items : {}
    return isSchemaAssignable(outputItems, inputItems)
  }

  if (outputType === 'object' && inputType === 'object')
    return isObjectAssignable(output, input)

  return false
}

function needsArrayParens(schema: JsonSchema): boolean {
  const unwrapped = unwrapAllOf(schema)
  const branches = unwrapped.anyOf ?? unwrapped.oneOf
  if (Array.isArray(branches) && branches.length > 1)
    return true
  return Array.isArray(unwrapped.enum) && unwrapped.enum.length > 1
}

/** Human-readable label for a JSON Schema, e.g. `HarmonizedElement[]`. */
export function describeSchema(schema: JsonSchema): string {
  const unwrapped = unwrapAllOf(schema)
  if (isUnconstrained(unwrapped))
    return 'any'

  const branches = unwrapped.anyOf ?? unwrapped.oneOf
  if (Array.isArray(branches))
    return branches.map(describeSchema).join(' | ')

  if ('const' in unwrapped)
    return JSON.stringify(unwrapped.const)

  if (Array.isArray(unwrapped.enum))
    return unwrapped.enum.map(value => JSON.stringify(value)).join(' | ')

  if (Array.isArray(unwrapped.type))
    return unwrapped.type.join(' | ')

  if (unwrapped.type === 'array') {
    const items = isSchemaObject(unwrapped.items) ? unwrapped.items : {}
    const inner = describeSchema(items)
    return needsArrayParens(items) ? `(${inner})[]` : `${inner}[]`
  }

  if (unwrapped.type === 'object') {
    if (isSchemaObject(unwrapped.properties))
      return typeof unwrapped.title === 'string' && unwrapped.title.length > 0 ? unwrapped.title : 'object'
    if (isSchemaObject(unwrapped.additionalProperties))
      return `Record<string, ${describeSchema(unwrapped.additionalProperties)}>`
    return 'object'
  }

  if (typeof unwrapped.type === 'string')
    return unwrapped.type

  return 'any'
}

// ---------------------------------------------------------------------------
// Port resolution, subworkflow pass-throughs, and socket badges
// ---------------------------------------------------------------------------

function isSubworkflowMetaNode(nodeName: string | undefined): boolean {
  return nodeName === 'subworkflow'
    || nodeName === 'subworkflow_input'
    || nodeName === 'subworkflow_output'
}

function splitPortRef(reference: string | undefined): [string, string] | null {
  if (!reference)
    return null
  const dot = reference.indexOf('.')
  if (dot <= 0 || dot === reference.length - 1)
    return null
  return [reference.slice(0, dot), reference.slice(dot + 1)]
}

function getSchemaFieldMap(nodeName: string, section: 'inputs' | 'result'): Record<string, JsonSchema> {
  return NODE_SCHEMA_MAP[nodeName]?.properties?.[section]?.properties ?? {}
}

function getConcretePortSchema(
  nodeName: string,
  section: 'inputs' | 'result',
  portName: string,
): JsonSchema | undefined {
  return getSchemaFieldMap(nodeName, section)[portName]
}

function getSchemaPorts(nodeName: string, direction: 'inputs' | 'outputs'): PortInfo[] {
  const section = direction === 'inputs' ? 'inputs' : 'result'
  const fields = getSchemaFieldMap(nodeName, section)
  return Object.entries(fields).map(([name, fieldSchema]) => ({
    name,
    schema: fieldSchema,
    label: typeof fieldSchema?.title === 'string' && fieldSchema.title.length > 0
      ? fieldSchema.title
      : formatLabel(name),
    description: typeof fieldSchema?.description === 'string' ? fieldSchema.description : '',
  }))
}

function readMetaPortName(node: PortNode): string | null {
  const raw = node.data?.settings?.port
  if (!raw || typeof raw !== 'object' || typeof raw.name !== 'string' || raw.name.length === 0)
    return null
  return raw.name
}

function resolveSubworkflowOutputSchema(
  subworkflowNode: PortNode,
  portName: string,
  context: PortResolutionContext | undefined,
  visited: Set<object>,
): JsonSchema | undefined {
  const innerNodes = subworkflowNode.data?.subworkflow?.nodes ?? []
  const outputNode = innerNodes.find(
    inner => inner.data.nodeName === 'subworkflow_output' && readMetaPortName(inner) === portName,
  )
  if (!outputNode)
    return undefined

  const ref = outputNode.data.input_bindings?.[portName]
  const parsed = splitPortRef(ref)
  if (!parsed)
    return undefined

  const [producerId, producerField] = parsed
  const producer = innerNodes.find(inner => inner.id === producerId)
  if (!producer)
    return undefined

  const innerContext: PortResolutionContext = context?.siblingNodes && subworkflowNode.data
    ? {
        ...resolveSubworkflowParentContextInternal(
          { data: subworkflowNode.data },
          context.siblingNodes,
          context,
          visited,
        ),
        siblingNodes: innerNodes,
      }
    : { siblingNodes: innerNodes }

  return resolveOutputSchemaInternal(producer, producerField, innerContext, visited)
}

function resolveOutputSchemaInternal(
  node: PortNode,
  outputName: string,
  context: PortResolutionContext | undefined,
  visited: Set<object>,
): JsonSchema | undefined {
  const data = node.data
  if (!data || visited.has(data))
    return undefined
  visited.add(data)

  const nodeName = data.nodeName
  if (nodeName === 'subworkflow_input') {
    const portName = readMetaPortName(node)
    if (portName !== outputName)
      return undefined
    return context?.parentInputSchemas?.[portName]
  }
  if (nodeName === 'subworkflow_output')
    return undefined
  if (nodeName === 'subworkflow')
    return resolveSubworkflowOutputSchema(node, outputName, context, visited)

  return getConcretePortSchema(nodeName, 'result', outputName)
}

function collectExpectedInputSchemasInternal(
  node: PortNode,
  inputName: string,
  visited: Set<object>,
): JsonSchema[] {
  const data = node.data
  if (!data || visited.has(data))
    return []
  visited.add(data)

  const nodeName = data.nodeName
  if (nodeName === 'subworkflow_input' || nodeName === 'subworkflow_output')
    return []

  if (nodeName === 'subworkflow') {
    const innerNodes = data.subworkflow?.nodes ?? []
    const inputNode = innerNodes.find(
      inner => inner.data.nodeName === 'subworkflow_input' && readMetaPortName(inner) === inputName,
    )
    if (!inputNode)
      return []

    const targetRef = `${inputNode.id}.${inputName}`
    const expected: JsonSchema[] = []
    for (const inner of innerNodes) {
      if (inner.id === inputNode.id)
        continue
      for (const [innerInputName, ref] of Object.entries(inner.data.input_bindings ?? {})) {
        if (ref !== targetRef)
          continue
        expected.push(...collectExpectedInputSchemasInternal(inner, innerInputName, visited))
      }
    }
    return expected
  }

  const concrete = getConcretePortSchema(nodeName, 'inputs', inputName)
  return concrete ? [concrete] : []
}

function getSubworkflowPorts(
  node: PortNode,
  direction: 'inputs' | 'outputs',
  context?: PortResolutionContext,
): PortInfo[] {
  const innerNodes = node.data?.subworkflow?.nodes ?? []

  if (direction === 'inputs') {
    return innerNodes
      .filter(inner => inner.data.nodeName === 'subworkflow_input')
      .map(readMetaPortName)
      .filter((name): name is string => name !== null)
      .map(name => ({
        name,
        schema: getExpectedInputSchemas(node, name)[0],
        label: formatLabel(name),
        description: '',
      }))
  }

  const outputNode = innerNodes.find(inner => inner.data.nodeName === 'subworkflow_output')
  const name = outputNode ? readMetaPortName(outputNode) : null
  if (!name)
    return []

  return [{
    name,
    schema: getOutputSchema(node, name, context),
    label: formatLabel(name),
    description: '',
  }]
}

function getMetaNodePorts(
  node: PortNode,
  direction: 'inputs' | 'outputs',
  context?: PortResolutionContext,
): PortInfo[] | null {
  const nodeName = node.data?.nodeName
  const isSource = nodeName === 'subworkflow_input' && direction === 'outputs'
  const isSink = nodeName === 'subworkflow_output' && direction === 'inputs'
  if (!isSource && !isSink)
    return null

  const name = readMetaPortName(node)
  if (!name)
    return []

  return [{
    name,
    schema: isSource ? context?.parentInputSchemas?.[name] : undefined,
    label: formatLabel(name),
    description: '',
  }]
}

export function getNodeInputPorts(
  node: PortNode,
  context?: PortResolutionContext,
): PortInfo[] {
  const metaPorts = getMetaNodePorts(node, 'inputs', context)
  if (metaPorts)
    return metaPorts
  if (node.data?.nodeName === 'subworkflow')
    return getSubworkflowPorts(node, 'inputs', context)
  return getSchemaPorts(node.data?.nodeName ?? '', 'inputs')
}

export function getNodeOutputPorts(
  node: PortNode,
  context?: PortResolutionContext,
): PortInfo[] {
  const metaPorts = getMetaNodePorts(node, 'outputs', context)
  if (metaPorts)
    return metaPorts
  if (node.data?.nodeName === 'subworkflow')
    return getSubworkflowPorts(node, 'outputs', context)
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
  if (!nodeName || isSubworkflowMetaNode(nodeName))
    return []

  const required = NODE_SCHEMA_MAP[nodeName]?.properties?.inputs?.required
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

export function getOutputSchema(
  node: PortNode,
  outputName: string,
  context?: PortResolutionContext,
): JsonSchema | undefined {
  return resolveOutputSchemaInternal(node, outputName, context, new Set())
}

export function getExpectedInputSchemas(
  node: PortNode,
  inputName: string,
): JsonSchema[] {
  return collectExpectedInputSchemasInternal(node, inputName, new Set())
}

export function getInputSchema(
  node: PortNode,
  inputName: string,
): JsonSchema | undefined {
  return getExpectedInputSchemas(node, inputName)[0]
}

const MODEL_SLUG_PREFIX = 'model_slug'

/**
 * A model input is a consumer's model selection, typically fed by a File Input
 * node's `model_slug` output. Editor UX only (auto-binding preferences and
 * labels) — compatibility itself is decided structurally from JSON Schema.
 */
export function isModelInput(inputName: string): boolean {
  return inputName.startsWith(MODEL_SLUG_PREFIX)
}

function hasInputPort(node: PortNode, inputName: string): boolean {
  return getNodeInputs(node).includes(inputName)
}

function hasOutputPort(node: PortNode, outputName: string): boolean {
  return getNodeOutputs(node).includes(outputName)
}

/**
 * Whether a source node's output may feed a target node's input.
 * Uses the exact same structural JSON Schema rules as the Python runner;
 * pass-through subworkflow ports without concrete endpoints remain permissive
 * until wired to concrete nodes.
 */
export function arePortsCompatible(
  targetNode: PortNode,
  inputName: string,
  sourceNode: PortNode,
  outputName: string,
  context?: PortResolutionContext,
): boolean {
  if (!hasInputPort(targetNode, inputName) || !hasOutputPort(sourceNode, outputName))
    return false

  const outputSchema = getOutputSchema(sourceNode, outputName, context)
  if (!outputSchema)
    return isSubworkflowMetaNode(sourceNode.data?.nodeName)

  const expectedInputs = getExpectedInputSchemas(targetNode, inputName)
  if (expectedInputs.length === 0)
    return isSubworkflowMetaNode(targetNode.data?.nodeName)

  return expectedInputs.every(expected => isSchemaAssignable(outputSchema, expected))
}

/**
 * Return the concrete `(sourceSchema, targetSchema)` pair that failed
 * compatibility, for accurate warning messages (including subworkflow fan-out).
 */
export function findPortMismatchSchemas(
  targetNode: PortNode,
  inputName: string,
  sourceNode: PortNode,
  outputName: string,
  context?: PortResolutionContext,
): { sourceSchema?: JsonSchema, targetSchema?: JsonSchema } {
  const sourceSchema = getOutputSchema(sourceNode, outputName, context)
  const expectedInputs = getExpectedInputSchemas(targetNode, inputName)
  if (sourceSchema && expectedInputs.length > 0) {
    const failing = expectedInputs.find(expected => !isSchemaAssignable(sourceSchema, expected))
    return { sourceSchema, targetSchema: failing ?? expectedInputs[0] }
  }
  return { sourceSchema, targetSchema: expectedInputs[0] }
}

/**
 * Resolve the enclosing `parentInputSchemas` context for the currently open
 * subworkflow scope by walking down `scopeStack` from root to active frame.
 */
export function resolveScopeContext(
  scopeStack: ReadonlyArray<Pick<ScopeFrame, 'nodeId' | 'nodes'>>,
  activeNodes?: ReadonlyArray<Pick<StoredNode, 'id' | 'data'>>,
): PortResolutionContext {
  let context: PortResolutionContext = {}
  for (let i = 1; i < scopeStack.length; i++) {
    const parentFrame = scopeStack[i - 1]!
    const currentFrame = scopeStack[i]!
    if (!currentFrame.nodeId) {
      context = {}
      continue
    }
    const parentNode = parentFrame.nodes.find(entry => entry.id === currentFrame.nodeId)
    if (!parentNode) {
      context = {}
      continue
    }
    context = resolveSubworkflowParentContext(parentNode, parentFrame.nodes, context)
  }
  return {
    ...context,
    siblingNodes: activeNodes ?? scopeStack.at(-1)?.nodes,
  }
}

function resolveSubworkflowParentContextInternal(
  subworkflowNode: Pick<StoredNode, 'data'>,
  siblingNodes: ReadonlyArray<Pick<StoredNode, 'id' | 'data'>>,
  outerContext: PortResolutionContext | undefined,
  visited: Set<object>,
): PortResolutionContext {
  const nodeById = new Map(siblingNodes.map(entry => [entry.id, entry]))
  const parentInputSchemas: Record<string, JsonSchema | undefined> = {}
  const outerWithSiblings: PortResolutionContext = { ...outerContext, siblingNodes }

  for (const [portName, reference] of Object.entries(subworkflowNode.data.input_bindings ?? {})) {
    const parsed = splitPortRef(reference)
    if (!parsed)
      continue
    const [sourceId, sourcePort] = parsed
    const sourceNode = nodeById.get(sourceId)
    if (sourceNode)
      parentInputSchemas[portName] = resolveOutputSchemaInternal({ data: sourceNode.data }, sourcePort, outerWithSiblings, visited)
  }

  return { parentInputSchemas }
}

/**
 * Resolve `parentInputSchemas` for a `subworkflow` node from its
 * `input_bindings` within `siblingNodes`.
 */
export function resolveSubworkflowParentContext(
  subworkflowNode: Pick<StoredNode, 'data'>,
  siblingNodes: ReadonlyArray<Pick<StoredNode, 'id' | 'data'>>,
  outerContext?: PortResolutionContext,
): PortResolutionContext {
  return resolveSubworkflowParentContextInternal(subworkflowNode, siblingNodes, outerContext, new Set())
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

/**
 * Derive output socket target badges (e.g. `'bcf'`) directly from the target
 * node's required input JSON Schema, using the same structural assignability
 * check as port validation.
 */
export function getOutputSocketTargets(
  node: PortNode,
  context?: PortResolutionContext,
): OutputSocketTarget[] {
  const nodeName = node.data?.nodeName
  if (!nodeName || nodeName === 'bcf_output')
    return []

  const outputSchemas = getNodeOutputPorts(node, context)
    .map(port => port.schema)
    .filter((schema): schema is JsonSchema => schema !== undefined && !isUnconstrained(normalizeNullable(schema)))
  if (outputSchemas.length === 0)
    return []

  const bcfInputSchemas = getSchemaFieldMap('bcf_output', 'inputs')
  const requiredBcfInputs = getRequiredNodeInputs({ data: { nodeName: 'bcf_output', label: 'bcf_output' } })
  const bcfSchemas = requiredBcfInputs
    .map(name => bcfInputSchemas[name])
    .filter((schema): schema is JsonSchema => schema !== undefined)

  const matchesBcf = bcfSchemas.some(inputSchema =>
    outputSchemas.some(outputSchema => isSchemaAssignable(outputSchema, inputSchema)),
  )

  return matchesBcf ? ['bcf'] : []
}

export function formatLabel(str: string): string {
  return str
    .replace(CAMEL_BOUNDARY_RE, '$1 $2')
    .replace(ACRONYM_BOUNDARY_RE, '$1 $2')
    .replace(UPPERCASE_DIGIT_RE, '$1 $2')
    .replace(DIGIT_UPPERCASE_RE, '$1 $2')
    .trim()
}
