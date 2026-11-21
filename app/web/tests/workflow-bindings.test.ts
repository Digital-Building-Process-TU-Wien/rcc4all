import type { StoredNode } from '../app/utils/nodes'
import type { PortType } from '../scripts/workflow-schema'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { getRequiredNodeInputs } from '../app/utils/schema-helpers'
import {
  matchCompatibleOutput,
  pruneBindingsForRemovedEdges,
  resolveAutoBindings,
} from '../app/utils/workflow-bindings'

function makeNode(
  id: string,
  nodeName: string,
  bindings: Record<string, string> = {},
): StoredNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: {
      label: nodeName,
      nodeName,
      input_bindings: { ...bindings },
    },
  }
}

function makeSubworkflowNode(
  id: string,
  inputPorts: Array<{ name: string, type: PortType }>,
  bindings: Record<string, string> = {},
): StoredNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: {
      label: 'Sub',
      nodeName: 'subworkflow',
      input_bindings: { ...bindings },
      subworkflow: {
        name: 'Sub',
        nodes: inputPorts.map((port, idx) => ({
          id: `${id}-in-${idx}`,
          position: { x: 0, y: idx * 80 },
          data: {
            label: port.name,
            nodeName: 'subworkflow_input',
            settings: { port },
          },
        })),
        edges: [],
      },
    },
  }
}

function makeMetaNode(
  id: string,
  kind: 'input' | 'output',
  name: string,
  type: PortType,
): StoredNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: {
      label: name,
      nodeName: kind === 'input' ? 'subworkflow_input' : 'subworkflow_output',
      settings: { port: { name, type } },
      input_bindings: {},
    },
  }
}

test('getRequiredNodeInputs mirrors Python schema required inputs', () => {
  assert.deepEqual(getRequiredNodeInputs(makeNode('b', 'bcf_output')), ['elements'])
  assert.deepEqual(getRequiredNodeInputs(makeNode('c', 'collision')), ['list_a', 'list_b'])
  assert.deepEqual(getRequiredNodeInputs(makeNode('l', 'loi_check')), ['express_ids'])
  assert.deepEqual(getRequiredNodeInputs(makeNode('f', 'ifc_element_filter')), [])
  assert.deepEqual(getRequiredNodeInputs(makeNode('cmp', 'comparison')), [])
})

test('matchCompatibleOutput prefers exact name, allows unique type, and flags ambiguity', () => {
  const filter = makeNode('f1', 'ifc_element_filter')
  const loi = makeNode('l1', 'loi_check')
  const collision = makeNode('c1', 'collision')
  const bcf = makeNode('b1', 'bcf_output')
  const concat = makeNode('s1', 'concat_string')

  assert.deepEqual(
    matchCompatibleOutput(filter, loi, 'express_ids'),
    { kind: 'matched', output: 'express_ids' },
  )
  assert.deepEqual(
    matchCompatibleOutput(loi, bcf, 'elements'),
    { kind: 'matched', output: 'elements' },
  )
  assert.deepEqual(
    matchCompatibleOutput(filter, collision, 'list_a'),
    { kind: 'ambiguous', candidates: ['express_ids', 'guids'] },
  )
  assert.deepEqual(
    matchCompatibleOutput(concat, bcf, 'elements'),
    { kind: 'incompatible' },
  )
})

test('resolveAutoBindings binds unambiguous checking and measurement chains', () => {
  const file = makeNode('file1', 'file_input')
  const filter = makeNode('f1', 'ifc_element_filter')
  const loi = makeNode('l1', 'loi_check')
  const tilt = makeNode('t1', 'tilt_of_components')
  const bcf = makeNode('b1', 'bcf_output')
  const measurement = makeNode('m1', 'measurement')
  const comparison = makeNode('cmp1', 'comparison')
  const pos = makeNode('p1', 'set_3d_position_rotation')
  const cube = makeNode('c1', 'generate_3d_cube')

  assert.deepEqual(resolveAutoBindings('file1', file, filter), {
    bindings: { model_slug: 'file1.model_slug' },
    status: 'bound',
    ambiguousInputs: [],
    ambiguousOutputs: [],
  })

  // Rewiring a second file_input replaces the single model_slug slot.
  const boundFilter = makeNode('f1', 'ifc_element_filter', { model_slug: 'file1.model_slug' })
  assert.deepEqual(resolveAutoBindings('file2', makeNode('file2', 'file_input'), boundFilter), {
    bindings: { model_slug: 'file2.model_slug' },
    status: 'bound',
    ambiguousInputs: [],
    ambiguousOutputs: [],
  })

  // file_input does not falsely bind string inputs on non-model nodes.
  assert.equal(resolveAutoBindings('file1', file, comparison).status, 'incompatible')

  // Filter -> LOI -> BCF binds express_ids and elements cleanly.
  assert.deepEqual(resolveAutoBindings('f1', filter, loi).bindings, {
    express_ids: 'f1.express_ids',
  })
  assert.deepEqual(resolveAutoBindings('l1', loi, bcf).bindings, {
    elements: 'l1.elements',
  })
  assert.deepEqual(resolveAutoBindings('t1', tilt, bcf).bindings, {
    elements: 't1.elements',
  })

  // Measurement -> Comparison binds unit by name, then values and check_parameter uniquely.
  assert.deepEqual(resolveAutoBindings('m1', measurement, comparison), {
    bindings: {
      unit: 'm1.unit',
      values: 'm1.measurements',
      check_parameter: 'm1.type',
    },
    status: 'bound',
    ambiguousInputs: [],
    ambiguousOutputs: [],
  })
  assert.deepEqual(resolveAutoBindings('cmp1', comparison, bcf).bindings, {
    elements: 'cmp1.elements',
  })

  // Position -> Cube binds elements by name + array<object> -> array<any>.
  assert.deepEqual(resolveAutoBindings('p1', pos, cube).bindings, {
    elements: 'p1.elements',
  })
})

test('resolveAutoBindings leaves ambiguous routings blank and reports ambiguity', () => {
  const filter = makeNode('f1', 'ifc_element_filter')
  const collision = makeNode('col1', 'collision')
  const loi = makeNode('l1', 'loi_check')
  const measurement = makeNode('m1', 'measurement')
  const getProp = makeNode('gp1', 'get_property')
  const comparison = makeNode('cmp1', 'comparison')
  const cube = makeNode('cube1', 'generate_3d_cube')

  // Filter -> Collision: 2 compatible outputs (express_ids, guids) x 2 inputs (list_a, list_b).
  const filterToCol = resolveAutoBindings('f1', filter, collision)
  assert.equal(filterToCol.status, 'ambiguous')
  assert.deepEqual(filterToCol.bindings, {})
  assert.deepEqual(filterToCol.ambiguousInputs, ['list_a', 'list_b'])

  // Cube -> Collision with both list_a and list_b unbound is ambiguous.
  const cubeToEmptyCol = resolveAutoBindings('cube1', cube, collision)
  assert.equal(cubeToEmptyCol.status, 'ambiguous')
  assert.deepEqual(cubeToEmptyCol.bindings, {})

  // Once list_a is bound, Cube -> Collision unambiguously binds list_b.
  const halfBoundCol = makeNode('col1', 'collision', { list_a: 'f1.express_ids' })
  assert.deepEqual(resolveAutoBindings('cube1', cube, halfBoundCol), {
    bindings: { list_b: 'cube1.object_ids' },
    status: 'bound',
    ambiguousInputs: [],
    ambiguousOutputs: [],
  })

  // LOI -> Filter: passed_express_ids vs failed_express_ids is ambiguous.
  const loiToFilter = resolveAutoBindings('l1', loi, filter)
  assert.equal(loiToFilter.status, 'ambiguous')
  assert.deepEqual(loiToFilter.bindings, {})
  assert.deepEqual(loiToFilter.ambiguousOutputs, ['passed_express_ids', 'failed_express_ids'])

  // Collision -> Measurement: collisions vs intersection_meshes is ambiguous.
  const colToMeas = resolveAutoBindings('col1', collision, measurement)
  assert.equal(colToMeas.status, 'ambiguous')
  assert.deepEqual(colToMeas.bindings, {})

  // Get Property -> Comparison: elements vs classes, and mode vs unit/check_parameter.
  const propToCmp = resolveAutoBindings('gp1', getProp, comparison)
  assert.equal(propToCmp.status, 'ambiguous')
  assert.deepEqual(propToCmp.bindings, {})

  // Measurement -> Comparison when unit is already bound: values binds uniquely,
  // check_parameter is flagged ambiguous (type vs unit).
  const partialCmp = makeNode('cmp1', 'comparison', { unit: 'other.value' })
  const measToPartialCmp = resolveAutoBindings('m1', measurement, partialCmp)
  assert.equal(measToPartialCmp.status, 'ambiguous')
  assert.deepEqual(measToPartialCmp.bindings, { values: 'm1.measurements' })
  assert.deepEqual(measToPartialCmp.ambiguousInputs, ['check_parameter'])
})

test('resolveAutoBindings handles incompatible wires, model-slot guards, and subworkflow ports', () => {
  const concat = makeNode('s1', 'concat_string')
  const bcf = makeNode('b1', 'bcf_output')
  const filter = makeNode('f1', 'ifc_element_filter')
  const file = makeNode('file1', 'file_input')
  const loi = makeNode('l1', 'loi_check')

  // Completely incompatible standard nodes stay unbound.
  assert.deepEqual(resolveAutoBindings('s1', concat, bcf), {
    bindings: {},
    status: 'incompatible',
    ambiguousInputs: [],
    ambiguousOutputs: [],
  })

  // Arbitrary string output does not hijack ifc_element_filter.model_slug.
  assert.equal(resolveAutoBindings('s1', concat, filter).status, 'incompatible')

  // A subworkflow_input named model_slug CAN bind to ifc_element_filter.model_slug.
  const modelMeta = makeMetaNode('in1', 'input', 'model_slug', { type: 'string' })
  assert.deepEqual(
    resolveAutoBindings('in1', modelMeta, filter, { explicitOutput: 'model_slug' }).bindings,
    { model_slug: 'in1.model_slug' },
  )

  // File Input -> explicit subworkflow string input port binds cleanly.
  const sub = makeSubworkflowNode('sub1', [
    { name: 'model', type: { type: 'string' } },
    { name: 'items', type: { type: 'array', items: { type: 'object' } } },
    { name: 'count', type: { type: 'integer' } },
  ])
  assert.deepEqual(
    resolveAutoBindings('file1', file, sub, { explicitInput: 'model' }).bindings,
    { model: 'file1.model_slug' },
  )

  // LOI Check -> explicit array<object> subworkflow port picks unique `elements`.
  assert.deepEqual(
    resolveAutoBindings('l1', loi, sub, { explicitInput: 'items' }).bindings,
    { items: 'l1.elements' },
  )

  // LOI Check -> generic `any` subworkflow_output is ambiguous across 7 outputs.
  const anyOut = makeMetaNode('out1', 'output', 'result', { type: 'any' })
  const loiToAnyOut = resolveAutoBindings('l1', loi, anyOut, { explicitInput: 'result' })
  assert.equal(loiToAnyOut.status, 'ambiguous')
  assert.deepEqual(loiToAnyOut.bindings, {})

  // Explicit port-to-port mismatch (`output:a` -> `input:b`) stays bound so port warning displays.
  const strIn = makeMetaNode('in2', 'input', 'text', { type: 'string' })
  const intOut = makeMetaNode('out2', 'output', 'total', { type: 'integer' })
  assert.deepEqual(
    resolveAutoBindings('in2', strIn, intOut, {
      explicitOutput: 'text',
      explicitInput: 'total',
    }),
    {
      bindings: { total: 'in2.text' },
      status: 'bound',
      ambiguousInputs: [],
      ambiguousOutputs: [],
    },
  )

  // Generic output -> incompatible explicit input port stays blank + incompatible.
  const concatToIntPort = resolveAutoBindings('s1', concat, sub, { explicitInput: 'count' })
  assert.equal(concatToIntPort.status, 'incompatible')
  assert.deepEqual(concatToIntPort.bindings, {})
})

test('pruneBindingsForRemovedEdges clears stale bindings without disturbing kept edges', () => {
  const loi = makeNode('l1', 'loi_check', { express_ids: 'f1.express_ids' })
  const sub = makeSubworkflowNode(
    'sub1',
    [
      { name: 'a', type: { type: 'string' } },
      { name: 'b', type: { type: 'string' } },
    ],
    { a: 's1.value', b: 's1.value' },
  )
  const nodesById = { l1: loi, sub1: sub }

  // Deleting the only generic edge clears the binding so rewiring can auto-bind again.
  pruneBindingsForRemovedEdges(
    nodesById,
    [{ source: 'f1', target: 'l1', targetHandle: 'input' }],
    [],
  )
  assert.deepEqual(loi.data.input_bindings, {})

  // Deleting one explicit port edge leaves the sibling port binding intact.
  pruneBindingsForRemovedEdges(
    nodesById,
    [{ source: 's1', target: 'sub1', targetHandle: 'input:a' }],
    [{ source: 's1', target: 'sub1', targetHandle: 'input:b' }],
  )
  assert.deepEqual(sub.data.input_bindings, { b: 's1.value' })
})
