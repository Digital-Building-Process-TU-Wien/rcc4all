// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { mkdirSync, readdirSync, readFileSync, unlinkSync, writeFileSync } from 'node:fs'
// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { dirname, relative, resolve } from 'node:path'
// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { fileURLToPath } from 'node:url'
import { compile } from 'json-schema-to-typescript-lite'

/**
 * Generate all TypeScript artifacts from the shared JSON Schema folder
 * (`../../shared/schemas/`) into `app/schemas/generated/`:
 *
 * - `nodes/<name>.d.ts` + `nodes/index.d.ts` (`NodeRegistrySchema`)
 * - `registry.ts` (static ESM imports of every per-node `.schema.json`)
 * - `workflow.d.ts` and `workflow.zod.ts` (from `workflow.schema.json`)
 */

const __dirname = dirname(fileURLToPath(import.meta.url))
const SCHEMAS_DIR = resolve(__dirname, '../../../shared/schemas')
const GENERATED_DIR = resolve(__dirname, '../app/schemas/generated')
const GENERATED_NODES_DIR = resolve(GENERATED_DIR, 'nodes')

const GENERATED_HEADER = '/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */\n\n'
const IDENTIFIER_RE = /^[A-Z_$][\w$]*$/i
const REF_PREFIX = '#/$defs/'
const SINGLE_QUOTE = String.fromCharCode(39)
const DOUBLE_QUOTED_RE = /"((?:[^"\\]|\\.)*)"/g
const DIGIT_LOWERCASE_RE = /(\d)([a-z])/g

interface SchemaManifest {
  workflow: string
  nodes: Record<string, string>
}

interface JsonSchema {
  $schema?: string
  $id?: string
  $ref?: string
  $defs?: Record<string, JsonSchema>
  type?: string | string[]
  title?: string
  enum?: unknown[]
  const?: unknown
  properties?: Record<string, JsonSchema>
  required?: string[]
  items?: JsonSchema
  additionalProperties?: boolean | JsonSchema
  anyOf?: JsonSchema[]
  oneOf?: JsonSchema[]
  allOf?: JsonSchema[]
  minItems?: number
}

function requoteDoubleQuoted(_: string, content: string): string {
  const escaped = content.replaceAll(SINGLE_QUOTE, `\\${SINGLE_QUOTE}`)
  return `${SINGLE_QUOTE}${escaped}${SINGLE_QUOTE}`
}

function toSingleQuoted(input: string): string {
  return input.replace(DOUBLE_QUOTED_RE, requoteDoubleQuoted)
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function toPascalCase(name: string): string {
  return name
    .split('_')
    .filter(Boolean)
    .map((part) => {
      const normalized = part.replace(DIGIT_LOWERCASE_RE, (_, digit: string, letter: string) => digit + letter.toUpperCase())
      return normalized.charAt(0).toUpperCase() + normalized.slice(1)
    })
    .join('')
}

function toCamelCase(name: string): string {
  const pascal = toPascalCase(name)
  return pascal.charAt(0).toLowerCase() + pascal.slice(1)
}

function toPosixPath(path: string): string {
  return path.replaceAll('\\', '/')
}

/**
 * Strip `title` from nested node schemas so `json-schema-to-typescript-lite`
 * inlines them instead of hoisting duplicate top-level `export type` aliases.
 */
function stripSchemaTitles(node: unknown): void {
  if (!isRecord(node))
    return

  delete node.title

  if (isRecord(node.properties)) {
    for (const propSchema of Object.values(node.properties))
      stripSchemaTitles(propSchema)
  }

  if (isRecord(node.items))
    stripSchemaTitles(node.items)
  else if (Array.isArray(node.items))
    node.items.forEach(stripSchemaTitles)

  if (isRecord(node.additionalProperties))
    stripSchemaTitles(node.additionalProperties)

  for (const key of ['anyOf', 'oneOf', 'allOf'] as const) {
    const branches = node[key]
    if (Array.isArray(branches))
      branches.forEach(stripSchemaTitles)
  }
}

function quoteProperty(name: string): string {
  return IDENTIFIER_RE.test(name) ? name : JSON.stringify(name)
}

function refName(ref: string): string {
  if (!ref.startsWith(REF_PREFIX))
    throw new Error(`Unsupported $ref '${ref}'. Expected '${REF_PREFIX}<Name>'.`)
  return ref.slice(REF_PREFIX.length)
}

function zodObject(schema: JsonSchema): string {
  const properties = schema.properties
  if (!properties) {
    const additional = schema.additionalProperties
    if (additional && typeof additional === 'object')
      return `z.record(z.string(), ${zodExpression(additional)})`
    return 'z.record(z.string(), z.unknown())'
  }

  const required = new Set(schema.required ?? [])
  const fields = Object.entries(properties).map(([name, property]) => {
    const expression = zodExpression(property)
    const optional = required.has(name) ? expression : `${expression}.optional()`
    return `${quoteProperty(name)}: ${optional}`
  })

  const object = `z.object({ ${fields.join(', ')} })`
  return schema.additionalProperties === false ? `${object}.strict()` : object
}

function zodExpression(schema: JsonSchema): string {
  if (schema.$ref)
    return `${refName(schema.$ref)}Schema`

  if (schema.const !== undefined)
    return `z.literal(${JSON.stringify(schema.const)})`

  if (schema.enum) {
    const values = schema.enum.map(value => JSON.stringify(value)).join(', ')
    return `z.enum([${values}])`
  }

  const variants = schema.oneOf ?? schema.anyOf
  if (variants) {
    const parts = variants.map(zodExpression)
    return parts.length === 1 ? parts[0]! : `z.union([${parts.join(', ')}])`
  }

  switch (Array.isArray(schema.type) ? schema.type[0] : schema.type) {
    case 'string':
      return 'z.string()'
    case 'integer':
    case 'number':
      return 'z.number()'
    case 'boolean':
      return 'z.boolean()'
    case 'null':
      return 'z.null()'
    case 'array': {
      const items = schema.items ? zodExpression(schema.items) : 'z.unknown()'
      const minimum = schema.minItems ? `.min(${schema.minItems})` : ''
      return `z.array(${items})${minimum}`
    }
    case 'object':
      return zodObject(schema)
    default:
      throw new Error(`Unsupported workflow schema: ${JSON.stringify(schema)}`)
  }
}

function writeUtf8(path: string, content: string): void {
  const normalized = content.replaceAll('\r\n', '\n')
  writeFileSync(path, normalized.endsWith('\n') ? normalized : `${normalized}\n`, 'utf-8')
}

async function generateNodeTypes(manifest: SchemaManifest): Promise<string[]> {
  mkdirSync(GENERATED_NODES_DIR, { recursive: true })

  const nodeNames = Object.keys(manifest.nodes).sort()
  const expectedFiles = new Set<string>(['index.d.ts'])

  for (const nodeName of nodeNames) {
    const relPath = manifest.nodes[nodeName]!
    const schemaPath = resolve(SCHEMAS_DIR, relPath)
    const raw = JSON.parse(readFileSync(schemaPath, 'utf-8')) as JsonSchema
    const cloned = structuredClone(raw)

    // Strip draft/id and nested titles so each file exports one clean interface.
    delete cloned.$schema
    delete cloned.$id
    const interfaceName = `${toPascalCase(nodeName)}NodeSchema`
    cloned.title = interfaceName

    if (isRecord(cloned.properties)) {
      for (const section of Object.values(cloned.properties))
        stripSchemaTitles(section)
    }

    const compiled = await compile(cloned, interfaceName, { additionalProperties: true })
    const fileName = `${nodeName}.d.ts`
    expectedFiles.add(fileName)
    writeUtf8(resolve(GENERATED_NODES_DIR, fileName), toSingleQuoted(GENERATED_HEADER + compiled))
  }

  // Prune stale `.d.ts` files for removed nodes.
  for (const entry of readdirSync(GENERATED_NODES_DIR)) {
    if (entry.endsWith('.d.ts') && !expectedFiles.has(entry))
      unlinkSync(resolve(GENERATED_NODES_DIR, entry))
  }

  const indexLines: string[] = [
    GENERATED_HEADER.trimEnd(),
    '',
    ...nodeNames.map(name => `import type { ${toPascalCase(name)}NodeSchema } from './${name}'`),
    '',
    'export interface NodeRegistrySchema {',
    ...nodeNames.map(name => `  ${name}: ${toPascalCase(name)}NodeSchema`),
    '}',
  ]
  writeUtf8(resolve(GENERATED_NODES_DIR, 'index.d.ts'), indexLines.join('\n'))

  return nodeNames
}

function generateRegistry(manifest: SchemaManifest, nodeNames: string[]): void {
  const imports = nodeNames.map((name) => {
    const targetPath = resolve(SCHEMAS_DIR, manifest.nodes[name]!)
    const importPath = toPosixPath(relative(GENERATED_DIR, targetPath))
    return `import ${toCamelCase(name)}Schema from '${importPath}'`
  })

  const entries = nodeNames.map(name => `  ${name}: ${toCamelCase(name)}Schema,`)

  const lines: string[] = [
    GENERATED_HEADER.trimEnd(),
    '',
    ...imports,
    '',
    'export const NODE_SCHEMAS = {',
    ...entries,
    '} as const',
  ]

  writeUtf8(resolve(GENERATED_DIR, 'registry.ts'), lines.join('\n'))
}

async function generateWorkflowArtifacts(manifest: SchemaManifest): Promise<void> {
  const workflowSchemaPath = resolve(SCHEMAS_DIR, manifest.workflow)
  const rawWorkflowSchema = JSON.parse(readFileSync(workflowSchemaPath, 'utf-8')) as JsonSchema

  const { $defs = {}, $schema: _draft, $id: _id, ...rootSchema } = rawWorkflowSchema
  const definitions: Record<string, JsonSchema> = { ...$defs, WorkflowDefinition: rootSchema }

  // Compile through a wrapper so every model is reachable, including
  // SubworkflowPort, which the workflow file itself never references directly.
  const wrapper = {
    $defs: definitions,
    type: 'object',
    properties: {
      workflow: { $ref: '#/$defs/WorkflowDefinition' },
      port: { $ref: '#/$defs/SubworkflowPort' },
    },
  }
  const typesSource = await compile(wrapper, 'WorkflowModels', {
    additionalProperties: true,
  })
  writeUtf8(resolve(GENERATED_DIR, 'workflow.d.ts'), toSingleQuoted(GENERATED_HEADER + typesSource))

  const typeNames = Object.keys(definitions).sort()
  const zodLines: string[] = [
    GENERATED_HEADER.trimEnd(),
    '',
    '/* eslint-disable ts/no-use-before-define */',
    '',
    `import type { ${typeNames.join(', ')} } from './workflow'`,
    `import { z } from 'zod'`,
    '',
  ]

  for (const name of typeNames) {
    zodLines.push(
      `export const ${name}Schema: z.ZodType<${name}> = z.lazy(() => ${zodExpression(definitions[name]!)})`,
      '',
    )
  }

  writeUtf8(resolve(GENERATED_DIR, 'workflow.zod.ts'), toSingleQuoted(zodLines.join('\n')))
}

async function generate() {
  mkdirSync(GENERATED_DIR, { recursive: true })
  const manifest = JSON.parse(
    readFileSync(resolve(SCHEMAS_DIR, 'index.json'), 'utf-8'),
  ) as SchemaManifest

  const nodeNames = await generateNodeTypes(manifest)
  generateRegistry(manifest, nodeNames)
  await generateWorkflowArtifacts(manifest)

  console.warn(`✅ Generated TS schemas for ${nodeNames.length} nodes and workflow models`)
}

generate().catch((error) => {
  console.error(error)
  throw error
})
