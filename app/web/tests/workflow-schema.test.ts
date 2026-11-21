import type { PortType, WorkflowDefinition } from '../scripts/workflow-schema'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  areTypesCompatible,
  getInputLabel,
  getNodeInputPorts,
  getNodeOutputPorts,
  jsonSchemaToPortType,
} from '../app/utils/schema-helpers'
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

test('jsonSchemaToPortType maps JSON Schema shapes to PortType', () => {
  assert.deepEqual(jsonSchemaToPortType({}), { type: 'any' })
  assert.deepEqual(jsonSchemaToPortType({ type: 'string' }), { type: 'string' })
  assert.deepEqual(jsonSchemaToPortType({ type: 'integer' }), { type: 'integer' })
  assert.deepEqual(jsonSchemaToPortType({ type: 'number' }), { type: 'number' })
  assert.deepEqual(jsonSchemaToPortType({ type: 'boolean' }), { type: 'boolean' })
  assert.deepEqual(jsonSchemaToPortType({ type: 'object', additionalProperties: { type: 'string' } }), { type: 'object' })

  assert.deepEqual(jsonSchemaToPortType({ type: 'array', items: { type: 'string' } }), {
    type: 'array',
    items: { type: 'string' },
  })
  assert.deepEqual(jsonSchemaToPortType({ type: 'array' }), {
    type: 'array',
    items: { type: 'any' },
  })

  // Nullable unions drop null and unwrap singletons.
  assert.deepEqual(jsonSchemaToPortType({ anyOf: [{ type: 'string' }, { type: 'null' }] }), { type: 'string' })
  assert.deepEqual(jsonSchemaToPortType({ type: ['integer', 'null'] }), { type: 'integer' })

  // Multi-branch unions deduplicate structurally and preserve distinct members.
  assert.deepEqual(
    jsonSchemaToPortType({
      anyOf: [
        { type: 'array', items: { type: 'string' } },
        { type: 'object', additionalProperties: { anyOf: [{ type: 'string' }, { type: 'null' }] } },
        { type: 'array', items: { type: 'string' } },
        { type: 'null' },
      ],
    }),
    {
      type: 'union',
      members: [
        { type: 'array', items: { type: 'string' } },
        { type: 'object' },
      ],
    },
  )

  // Const and untyped enums collapse or union by JSON value type.
  assert.deepEqual(jsonSchemaToPortType({ const: 'auto' }), { type: 'string' })
  assert.deepEqual(jsonSchemaToPortType({ enum: ['a', 'b', null] }), { type: 'string' })
  assert.deepEqual(jsonSchemaToPortType({ enum: [1, 'a'] }), {
    type: 'union',
    members: [{ type: 'integer' }, { type: 'string' }],
  })
})

test('node ports are derived directly from node schemas without x-ports', () => {
  assert.equal('x-ports' in schemaJson, false)

  const node = (nodeName: string) => ({ data: { label: nodeName, nodeName } })

  // Nullable output: get_property.elements (list[Element] | None -> array<object>)
  const getPropElements = getNodeOutputPorts(node('get_property')).find(port => port.name === 'elements')
  assert.deepEqual(getPropElements?.type, { type: 'array', items: { type: 'object' } })

  // Nullable list items: concat_string.values (list[str | None] -> array<string>)
  const concatValues = getNodeInputPorts(node('concat_string')).find(port => port.name === 'values')
  assert.deepEqual(concatValues?.type, { type: 'array', items: { type: 'string' } })

  // Wildcard list items: generate_3d_cube.elements (list[Any] -> array<any>)
  const cubeElements = getNodeInputPorts(node('generate_3d_cube')).find(port => port.name === 'elements')
  assert.deepEqual(cubeElements?.type, { type: 'array', items: { type: 'any' } })

  // Union input: measurement.list_a (list[str] | dict[str, str | None] | None)
  const measurementListA = getNodeInputPorts(node('measurement')).find(port => port.name === 'list_a')
  assert.deepEqual(measurementListA?.type, {
    type: 'union',
    members: [
      { type: 'array', items: { type: 'string' } },
      { type: 'object' },
    ],
  })

  // Field(title=...) survives in schema.json and feeds port labels.
  assert.equal(getInputLabel(node('measurement'), 'list_a'), 'List A')
  assert.equal(getInputLabel(node('concat_string'), 'values'), 'Input values')
})
