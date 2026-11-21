// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { readFileSync, writeFileSync } from 'node:fs'
// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { dirname, resolve } from 'node:path'
// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { fileURLToPath } from 'node:url'
import { compile } from 'json-schema-to-typescript-lite'

const __dirname = dirname(fileURLToPath(import.meta.url))

const GENERATED_HEADER = '/* GENERATED FILE - DO NOT EDIT. Regenerate with `npm run generate:schema`. */\n\n'

/**
 * The generator emits double-quoted string literals, which conflict with the
 * project's single-quote eslint style when the file is linted. Convert
 * double-quoted literals to single-quoted (escaping any interior apostrophes)
 * so the committed file is lint-clean and deterministic.
 */
const SINGLE_QUOTE = String.fromCharCode(39)

const DOUBLE_QUOTED_RE = /"((?:[^"\\]|\\.)*)"/g

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

/**
 * Strip `title` from nested node schemas so `json-schema-to-typescript-lite`
 * inlines them instead of hoisting top-level `export type` aliases.
 * Top-level registry and node titles stay intact to preserve interface names.
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

async function generate() {
  const schemaPath = resolve(__dirname, 'schema.json')
  const outputPath = resolve(__dirname, 'schema.d.ts')

  const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'))

  // The node registry is the only part of `schema.json` this file compiles.
  // `x-workflows` has its own `$defs` document and its own generator, and the
  // ref parser would otherwise resolve its refs against the wrong root.
  delete schema['x-workflows']

  if (isRecord(schema.properties)) {
    for (const nodeSchema of Object.values(schema.properties)) {
      if (!isRecord(nodeSchema) || !isRecord(nodeSchema.properties))
        continue
      for (const section of Object.values(nodeSchema.properties))
        stripSchemaTitles(section)
    }
  }

  let ts = await compile(schema, 'WorkflowSchema', { additionalProperties: true })

  ts = toSingleQuoted(ts)

  writeFileSync(outputPath, GENERATED_HEADER + ts)
  console.warn('✅ Generated schema.d.ts')
}

generate().catch(console.error)
