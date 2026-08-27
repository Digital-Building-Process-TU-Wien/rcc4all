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

function requoteDoubleQuoted(_: string, content: string): string {
  const escaped = content.replaceAll(SINGLE_QUOTE, `\\${SINGLE_QUOTE}`)
  return `${SINGLE_QUOTE}${escaped}${SINGLE_QUOTE}`
}

function toSingleQuoted(input: string): string {
  return input.replace(/"((?:[^"\\]|\\.)*)"/g, requoteDoubleQuoted)
}

async function generate() {
  const schemaPath = resolve(__dirname, 'schema.json')
  const outputPath = resolve(__dirname, 'schema.d.ts')

  const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'))
  let ts = await compile(schema, 'WorkflowSchema', { additionalProperties: true })

  ts = toSingleQuoted(ts)

  writeFileSync(outputPath, GENERATED_HEADER + ts)
  console.warn('✅ Generated schema.d.ts')
}

generate().catch(console.error)
