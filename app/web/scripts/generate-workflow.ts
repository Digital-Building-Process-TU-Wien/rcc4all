// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { readFileSync, writeFileSync } from 'node:fs'
// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { dirname, resolve } from 'node:path'
// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { fileURLToPath } from 'node:url'
import { compile } from 'json-schema-to-typescript-lite'

/**
 * Generate the workflow-file types and zod schemas from the `x-workflows`
 * section of `schema.json`. Both artifacts are derived from the Pydantic
 * models in `app/runner`, so adding a node never means editing either file.
 */

const __dirname = dirname(fileURLToPath(import.meta.url))

const GENERATED_HEADER = '/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */\n\n'

interface JsonSchema {
  $ref?: string
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
  minItems?: number
}

interface WorkflowSection {
  schema: JsonSchema & { $defs?: Record<string, JsonSchema> }
}

const IDENTIFIER_RE = /^[A-Z_$][\w$]*$/i
const REF_PREFIX = '#/$defs/'
const SINGLE_QUOTE = String.fromCharCode(39)
const DOUBLE_QUOTED_RE = /"((?:[^"\\]|\\.)*)"/g

function requoteDoubleQuoted(_: string, content: string): string {
  const escaped = content.replaceAll(SINGLE_QUOTE, `\\${SINGLE_QUOTE}`)
  return `${SINGLE_QUOTE}${escaped}${SINGLE_QUOTE}`
}

function toSingleQuoted(input: string): string {
  return input.replace(DOUBLE_QUOTED_RE, requoteDoubleQuoted)
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

async function generate() {
  const schemaPath = resolve(__dirname, 'schema.json')
  const typesPath = resolve(__dirname, 'workflow-schema.d.ts')
  const zodPath = resolve(__dirname, 'workflow-schema.zod.ts')

  const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'))
  const section = schema['x-workflows'] as WorkflowSection | undefined
  if (!section)
    throw new Error('schema.json has no x-workflows section.')

  const { $defs = {}, ...rootSchema } = section.schema
  const definitions = { ...$defs, WorkflowDefinition: rootSchema }

  // Compile through a wrapper so every model is reachable, including
  // SubworkflowPort, which the workflow file itself never references.
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
  writeFileSync(typesPath, toSingleQuoted(GENERATED_HEADER + typesSource))

  const typeNames = Object.keys(definitions).sort()
  const lines: string[] = [
    // GENERATED_HEADER already ends with a blank line; trim it so join('\n')
    // produces exactly one, keeping the output lint-clean.
    GENERATED_HEADER.trimEnd(),
    '',
    // Recursive zod schemas reference each other by name; every reference sits
    // inside z.lazy, so evaluation order is safe.
    '/* eslint-disable ts/no-use-before-define */',
    '',
    `import type { ${typeNames.join(', ')} } from './workflow-schema'`,
    `import { z } from 'zod'`,
    '',
  ]

  for (const name of typeNames) {
    lines.push(
      `export const ${name}Schema: z.ZodType<${name}> = z.lazy(() => ${zodExpression(definitions[name]!)})`,
      '',
    )
  }

  writeFileSync(zodPath, toSingleQuoted(lines.join('\n')))
  console.warn('✅ Generated workflow-schema.d.ts and workflow-schema.zod.ts')
}

generate().catch(console.error)
