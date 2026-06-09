// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { readFileSync, writeFileSync } from 'node:fs'
// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { dirname, resolve } from 'node:path'
// @ts-expect-error - This script is meant to be run with Node.js, not bundled for the browser.
import { fileURLToPath } from 'node:url'
import { compile } from 'json-schema-to-typescript-lite'

const __dirname = dirname(fileURLToPath(import.meta.url))

async function generate() {
  const schemaPath = resolve(__dirname, 'schema.json')
  const outputPath = resolve(__dirname, 'schema.d.ts')

  const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'))
  const ts = await compile(schema, 'WorkflowSchema', { additionalProperties: true })

  writeFileSync(outputPath, ts)
  console.warn('✅ Generated schema.d.ts')
}

generate().catch(console.error)
