import type { PortType, WorkflowDefinition } from '../scripts/workflow-schema'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { areTypesCompatible, getOutputSocketTargets } from '../app/utils/schema-helpers'
import schemaJson from '../scripts/schema.json'
import { SubworkflowPortSchema, WorkflowDefinitionSchema } from '../scripts/workflow-schema.zod'

const WORKFLOW_SECTION = schemaJson as { 'x-workflows'?: { compatibility?: Record<string, string[]> } }
const COMPATIBILITY = WORKFLOW_SECTION['x-workflows']?.compatibility ?? {}

const SCALAR_NAMES = ['string', 'integer', 'number', 'boolean', 'object', 'any'] as const

function scalar(name: typeof SCALAR_NAMES[number]): PortType {
  return { type: name }
}

test('generated zod accepts a valid workflow and rejects a bad port type', () => {
  const workflow = {
    files: [{ path: 'model.ifc', slug: 'main' }],
    nodes: [
      {
        id: 'concat-1',
        type: 'concat_string',
        position: { x: 0, y: 0 },
        input_bindings: { values: 'files-1.models' },
      },
    ],
    edges: [{ source: 'files-1', target: 'concat-1' }],
  } satisfies WorkflowDefinition

  const valid = WorkflowDefinitionSchema.safeParse(workflow)
  assert.equal(valid.success, true)

  // Unknown top-level keys are rejected (the runner forbids them too).
  const unknownKey = WorkflowDefinitionSchema.safeParse({ ...workflow, nope: true })
  assert.equal(unknownKey.success, false)

  // A malformed port type never passes the generated schema.
  const badPort = SubworkflowPortSchema.safeParse({ name: 'value', type: { type: 'nonsense' } })
  assert.equal(badPort.success, false)

  const goodPort = SubworkflowPortSchema.safeParse({ name: 'value', type: { type: 'array', items: { type: 'string' } } })
  assert.equal(goodPort.success, true)
})

test('rule function gives the same answers as the exported table', () => {
  for (const source of SCALAR_NAMES) {
    const targets = COMPATIBILITY[source] ?? []
    for (const target of SCALAR_NAMES) {
      assert.equal(
        areTypesCompatible(scalar(source), scalar(target)),
        targets.includes(target),
        `table row '${source}': expected ${source} -> ${target} to be ${targets.includes(target)}`,
      )
    }
  }

  // The 'array' row is applied item-wise, like the runner does.
  const arrayOf = (name: typeof SCALAR_NAMES[number]): PortType => ({ type: 'array', items: scalar(name) })
  assert.equal(areTypesCompatible(arrayOf('string'), arrayOf('string')), true)
  assert.equal(areTypesCompatible(arrayOf('string'), arrayOf('integer')), false)
})

test('getOutputSocketTargets detects BCF-compatible outputs from bcf_output input schema', () => {
  const targetsFor = (nodeName: string) =>
    getOutputSocketTargets({ data: { label: nodeName, nodeName } })

  assert.deepEqual(targetsFor('loi_check'), ['bcf'])
  assert.deepEqual(targetsFor('tilt_of_components'), ['bcf'])
  assert.deepEqual(targetsFor('comparison'), ['bcf'])

  // Non-harmonized array<object> outputs and sinks must not be flagged as BCF-compatible.
  assert.deepEqual(targetsFor('get_property'), [])
  assert.deepEqual(targetsFor('set_3d_position_rotation'), [])
  assert.deepEqual(targetsFor('get_element_creation_position_door'), [])
  assert.deepEqual(targetsFor('ids_checker'), [])
  assert.deepEqual(targetsFor('collision'), [])
  assert.deepEqual(targetsFor('measurement'), [])
  assert.deepEqual(targetsFor('file_input'), [])
  assert.deepEqual(targetsFor('bcf_output'), [])
})
