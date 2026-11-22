import type { JsonSchema, WorkflowDefinition } from '../app/schemas'
import type { StoredNode } from '../app/utils/nodes'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  arePortsCompatible,
  findPortMismatchSchemas,
  getOutputSchema,
  getOutputSocketTargets,
  getRegisteredNodeNames,
  isSchemaAssignable,
  resolveScopeContext,
  SubworkflowPortSchema,
  WorkflowDefinitionSchema,
} from '../app/schemas'

test('generated zod accepts a valid workflow and name-only subworkflow ports', () => {
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

  assert.equal(WorkflowDefinitionSchema.safeParse(workflow).success, true)
  assert.equal(WorkflowDefinitionSchema.safeParse({ ...workflow, nope: true }).success, false)

  // SubworkflowPort is name-only; extra keys like `type` are rejected strictly.
  assert.equal(SubworkflowPortSchema.safeParse({ name: 'value' }).success, true)
  assert.equal(SubworkflowPortSchema.safeParse({ name: 'value', type: { type: 'string' } }).success, false)
  assert.equal(SubworkflowPortSchema.safeParse({}).success, false)
})

test('isSchemaAssignable enforces JSON Schema structural assignability rules', () => {
  const cases: Array<[JsonSchema, JsonSchema, boolean, string]> = [
    [{ type: 'string' }, { type: 'string' }, true, 'string -> string'],
    [{ type: 'integer' }, { type: 'number' }, true, 'integer -> number'],
    [{ type: 'number' }, { type: 'integer' }, false, 'number -> integer'],
    [{ type: 'string' }, { type: 'integer' }, false, 'string -> integer'],
    [{}, { type: 'array', items: { type: 'string' } }, true, 'any -> string[]'],
    [{ type: 'array', items: { type: 'string' } }, { type: 'array', items: {} }, true, 'string[] -> any[]'],
    [{ type: 'array', items: { type: 'integer' } }, { type: 'array', items: { type: 'number' } }, true, 'integer[] -> number[]'],
    [{ type: 'array', items: { type: 'number' } }, { type: 'array', items: { type: 'integer' } }, false, 'number[] -> integer[]'],
    [{ anyOf: [{ type: 'string' }, { type: 'null' }] }, { type: 'string' }, true, 'string | null -> string'],
    [{ anyOf: [{ type: 'integer' }, { type: 'number' }] }, { type: 'number' }, true, 'integer | number -> number'],
    [{ type: 'string' }, { anyOf: [{ type: 'integer' }, { type: 'string' }] }, true, 'string -> integer | string'],
    [{ enum: ['volume', 'area'] }, { type: 'string' }, true, 'string enum -> string'],
    [{ enum: ['volume'] }, { enum: ['volume', 'area'] }, true, 'subset enum -> superset enum'],
    [{ type: 'string' }, { enum: ['volume', 'area'] }, false, 'string -> narrow enum'],
    [{ const: true }, { type: 'integer' }, false, 'boolean const -> integer'],
    [
      { type: 'object', properties: { id: { type: 'string' }, value: { type: 'integer' } }, required: ['id', 'value'] },
      { type: 'object', properties: { id: { type: 'string' }, value: { type: 'number' } }, required: ['id'] },
      true,
      'object with superset required fields and widened property',
    ],
    [
      { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
      { type: 'object', properties: { id: { type: 'string' }, value: { type: 'number' } }, required: ['id', 'value'] },
      false,
      'object missing required field',
    ],
    [
      { type: 'object', properties: { id: { type: 'string' }, value: { type: 'string' } }, required: ['id', 'value'] },
      { type: 'object', properties: { id: { type: 'string' }, value: { type: 'number' } }, required: ['id', 'value'] },
      false,
      'object with incompatible property type',
    ],
    [
      { type: 'object', additionalProperties: { anyOf: [{ type: 'string' }, { type: 'null' }] } },
      {
        anyOf: [
          { type: 'array', items: { type: 'string' } },
          { type: 'object', additionalProperties: { anyOf: [{ type: 'string' }, { type: 'null' }] } },
        ],
      },
      true,
      'record -> array | record union',
    ],
  ]

  for (const [output, input, expected, label] of cases)
    assert.equal(isSchemaAssignable(output, input), expected, label)
})

test('arePortsCompatible resolves per-node schemas and rejects missing ports', () => {
  assert.ok(getRegisteredNodeNames().length > 0)

  const node = (nodeName: string) => ({ data: { label: nodeName, nodeName } })

  assert.equal(arePortsCompatible(node('bcf_output'), 'elements', node('loi_check'), 'elements'), true)
  assert.equal(arePortsCompatible(node('bcf_output'), 'elements', node('get_property'), 'elements'), false)
  assert.equal(arePortsCompatible(node('bcf_output'), 'elements', node('get_property'), 'does_not_exist'), false)
  assert.equal(arePortsCompatible(node('bcf_output'), 'does_not_exist', node('loi_check'), 'elements'), false)
})

test('pass-through subworkflow ports stay permissive when unwired and resolve from concrete endpoints when wired', () => {
  const filter: StoredNode = {
    id: 'f1',
    position: { x: 0, y: 0 },
    data: { label: 'Filter', nodeName: 'ifc_element_filter' },
  }
  const bcf: StoredNode = {
    id: 'b1',
    position: { x: 0, y: 0 },
    data: { label: 'BCF', nodeName: 'bcf_output' },
  }
  const concat: StoredNode = {
    id: 'c1',
    position: { x: 0, y: 0 },
    data: { label: 'Concat', nodeName: 'concat_string' },
  }

  // Unwired pass-through ports accept any concrete connection until wired.
  const unwiredSub: StoredNode = {
    id: 'unwired',
    position: { x: 0, y: 0 },
    data: {
      label: 'Unwired',
      nodeName: 'subworkflow',
      subworkflow: {
        name: 'Unwired',
        nodes: [
          { id: 'u-in', position: { x: 0, y: 0 }, data: { label: 'x', nodeName: 'subworkflow_input', settings: { port: { name: 'x' } } } },
          { id: 'u-out', position: { x: 200, y: 0 }, data: { label: 'y', nodeName: 'subworkflow_output', settings: { port: { name: 'y' } } } },
        ],
        edges: [],
      },
    },
  }
  assert.equal(arePortsCompatible(unwiredSub, 'x', concat, 'value'), true)
  assert.equal(arePortsCompatible(bcf, 'elements', unwiredSub, 'y'), true)

  const subworkflow: StoredNode = {
    id: 'sw1',
    position: { x: 0, y: 0 },
    data: {
      label: 'Check Sub',
      nodeName: 'subworkflow',
      input_bindings: { ids: 'c1.value' },
      subworkflow: {
        name: 'Check Sub',
        nodes: [
          {
            id: 'in1',
            position: { x: 0, y: 0 },
            data: { label: 'ids', nodeName: 'subworkflow_input', settings: { port: { name: 'ids' } } },
          },
          {
            id: 'loi1',
            position: { x: 200, y: 0 },
            data: {
              label: 'LOI',
              nodeName: 'loi_check',
              input_bindings: { express_ids: 'in1.ids' },
            },
          },
          {
            id: 'out1',
            position: { x: 400, y: 0 },
            data: {
              label: 'checked',
              nodeName: 'subworkflow_output',
              settings: { port: { name: 'checked' } },
              input_bindings: { checked: 'loi1.elements' },
            },
          },
        ],
        edges: [],
      },
    },
  }

  // Outer -> subworkflow input checks against concrete inner consumer (`loi_check.express_ids`).
  assert.equal(arePortsCompatible(subworkflow, 'ids', filter, 'express_ids'), true)
  assert.equal(arePortsCompatible(subworkflow, 'ids', concat, 'value'), false)

  const mismatch = findPortMismatchSchemas(subworkflow, 'ids', concat, 'value')
  assert.ok(mismatch.sourceSchema && mismatch.targetSchema)
  assert.equal(isSchemaAssignable(mismatch.sourceSchema, mismatch.targetSchema), false)

  // Subworkflow output resolves through `subworkflow_output` to `loi_check.elements`.
  assert.ok(getOutputSchema(subworkflow, 'checked'))
  assert.equal(arePortsCompatible(bcf, 'elements', subworkflow, 'checked'), true)
  assert.equal(arePortsCompatible(concat, 'values', subworkflow, 'checked'), false)
  assert.deepEqual(getOutputSocketTargets(subworkflow), ['bcf'])

  // Inside the subworkflow, scope context propagates the parent's concrete outer schema.
  const scopeContext = resolveScopeContext([
    { nodeId: null, nodes: [concat, subworkflow] },
    { nodeId: 'sw1', nodes: subworkflow.data.subworkflow!.nodes },
  ])
  const innerInput = subworkflow.data.subworkflow!.nodes[0]!
  const innerLoi = subworkflow.data.subworkflow!.nodes[1]!
  assert.equal(arePortsCompatible(innerLoi, 'express_ids', innerInput, 'ids', scopeContext), false)

  // Pure pass-through subworkflow (`subworkflow_input -> subworkflow_output`) resolves outer producer via siblingNodes.
  const passthrough: StoredNode = {
    id: 'pt1',
    position: { x: 0, y: 0 },
    data: {
      label: 'Pass',
      nodeName: 'subworkflow',
      input_bindings: { x: 'f1.express_ids' },
      subworkflow: {
        name: 'Pass',
        nodes: [
          {
            id: 'pt-in',
            position: { x: 0, y: 0 },
            data: { label: 'x', nodeName: 'subworkflow_input', settings: { port: { name: 'x' } } },
          },
          {
            id: 'pt-out',
            position: { x: 200, y: 0 },
            data: {
              label: 'y',
              nodeName: 'subworkflow_output',
              settings: { port: { name: 'y' } },
              input_bindings: { y: 'pt-in.x' },
            },
          },
        ],
        edges: [],
      },
    },
  }
  const rootContext = { siblingNodes: [filter, passthrough, bcf, concat] }
  assert.equal(arePortsCompatible(concat, 'values', passthrough, 'y', rootContext), true)
  assert.equal(arePortsCompatible(bcf, 'elements', passthrough, 'y', rootContext), false)
})
