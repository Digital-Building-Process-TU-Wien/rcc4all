import type { StoredNode } from '../app/utils/nodes'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { arePortsCompatible } from '../app/schemas'
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
  inputPorts: Array<{ name: string, consumer?: { nodeName: string, input: string } }>,
  bindings: Record<string, string> = {},
): StoredNode {
  const innerNodes: StoredNode[] = []
  for (const [idx, port] of inputPorts.entries()) {
    const inputNodeId = `${id}-in-${idx}`
    innerNodes.push({
      id: inputNodeId,
      position: { x: 0, y: idx * 80 },
      data: {
        label: port.name,
        nodeName: 'subworkflow_input',
        settings: { port: { name: port.name } },
      },
    })
    if (port.consumer) {
      innerNodes.push({
        id: `${id}-consumer-${idx}`,
        position: { x: 240, y: idx * 80 },
        data: {
          label: port.consumer.nodeName,
          nodeName: port.consumer.nodeName,
          input_bindings: { [port.consumer.input]: `${inputNodeId}.${port.name}` },
        },
      })
    }
  }

  return {
    id,
    position: { x: 0, y: 0 },
    data: {
      label: 'Sub',
      nodeName: 'subworkflow',
      input_bindings: { ...bindings },
      subworkflow: {
        name: 'Sub',
        nodes: innerNodes,
        edges: [],
      },
    },
  }
}

function makeMetaNode(
  id: string,
  kind: 'input' | 'output',
  name: string,
): StoredNode {
  return {
    id,
    position: { x: 0, y: 0 },
    data: {
      label: name,
      nodeName: kind === 'input' ? 'subworkflow_input' : 'subworkflow_output',
      settings: { port: { name } },
      input_bindings: {},
    },
  }
}

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

test('resolveAutoBindings binds model slots, exact names, and unique type matches', () => {
  const file = makeNode('file1', 'file_input')
  const filter = makeNode('f1', 'ifc_element_filter')
  const loi = makeNode('l1', 'loi_check')
  const measurement = makeNode('m1', 'measurement')
  const comparison = makeNode('cmp1', 'comparison')

  // File Input binds model_slug, replaces on rewire, and ignores non-model string inputs.
  assert.deepEqual(resolveAutoBindings('file1', file, filter), {
    bindings: { model_slug: 'file1.model_slug' },
    status: 'bound',
    ambiguousInputs: [],
    ambiguousOutputs: [],
  })
  const boundFilter = makeNode('f1', 'ifc_element_filter', { model_slug: 'file1.model_slug' })
  assert.deepEqual(resolveAutoBindings('file2', makeNode('file2', 'file_input'), boundFilter).bindings, {
    model_slug: 'file2.model_slug',
  })
  assert.equal(resolveAutoBindings('file1', file, comparison).status, 'incompatible')

  // Exact name match.
  assert.deepEqual(resolveAutoBindings('f1', filter, loi).bindings, {
    express_ids: 'f1.express_ids',
  })

  // Exact name (`unit`) + unique remaining types (`values`, `check_parameter`).
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
})

test('resolveAutoBindings leaves ambiguous routings blank and resolves once disambiguated', () => {
  const filter = makeNode('f1', 'ifc_element_filter')
  const collision = makeNode('col1', 'collision')
  const measurement = makeNode('m1', 'measurement')
  const cube = makeNode('cube1', 'generate_3d_cube')

  // M x N ambiguity stays blank.
  const filterToCol = resolveAutoBindings('f1', filter, collision)
  assert.equal(filterToCol.status, 'ambiguous')
  assert.deepEqual(filterToCol.bindings, {})
  assert.deepEqual(filterToCol.ambiguousInputs, ['list_a', 'list_b'])

  // Binding one slot disambiguates the remaining slot.
  assert.equal(resolveAutoBindings('cube1', cube, collision).status, 'ambiguous')
  const halfBoundCol = makeNode('col1', 'collision', { list_a: 'f1.express_ids' })
  assert.deepEqual(resolveAutoBindings('cube1', cube, halfBoundCol), {
    bindings: { list_b: 'cube1.object_ids' },
    status: 'bound',
    ambiguousInputs: [],
    ambiguousOutputs: [],
  })

  // Partial match binds unambiguous ports while flagging remaining ambiguity.
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

  assert.deepEqual(resolveAutoBindings('s1', concat, bcf), {
    bindings: {},
    status: 'incompatible',
    ambiguousInputs: [],
    ambiguousOutputs: [],
  })

  // Arbitrary string output does not hijack ifc_element_filter.model_slug.
  assert.equal(resolveAutoBindings('s1', concat, filter).status, 'incompatible')

  // A subworkflow_input named model_slug CAN bind to ifc_element_filter.model_slug.
  const modelMeta = makeMetaNode('in1', 'input', 'model_slug')
  assert.deepEqual(
    resolveAutoBindings('in1', modelMeta, filter, { explicitOutput: 'model_slug' }).bindings,
    { model_slug: 'in1.model_slug' },
  )

  const sub = makeSubworkflowNode('sub1', [
    { name: 'model', consumer: { nodeName: 'ifc_element_filter', input: 'model_slug' } },
    { name: 'items', consumer: { nodeName: 'bcf_output', input: 'elements' } },
    { name: 'ids', consumer: { nodeName: 'loi_check', input: 'express_ids' } },
  ])
  assert.deepEqual(
    resolveAutoBindings('file1', file, sub, { explicitInput: 'model' }).bindings,
    { model: 'file1.model_slug' },
  )
  assert.deepEqual(
    resolveAutoBindings('l1', loi, sub, { explicitInput: 'items' }).bindings,
    { items: 'l1.elements' },
  )

  // Multi-output source -> pass-through subworkflow_output is ambiguous.
  const anyOut = makeMetaNode('out1', 'output', 'result')
  const loiToAnyOut = resolveAutoBindings('l1', loi, anyOut, { explicitInput: 'result' })
  assert.equal(loiToAnyOut.status, 'ambiguous')
  assert.deepEqual(loiToAnyOut.bindings, {})

  // Explicit port-to-port mismatch (`output:a` -> `input:b`) stays bound so the port warning displays.
  const strIn = makeMetaNode('in2', 'input', 'text')
  const mismatchContext = { parentInputSchemas: { text: { type: 'string' } } }
  assert.equal(arePortsCompatible(sub, 'ids', strIn, 'text', mismatchContext), false)
  assert.deepEqual(
    resolveAutoBindings('in2', strIn, sub, {
      explicitOutput: 'text',
      explicitInput: 'ids',
      context: mismatchContext,
    }),
    {
      bindings: { ids: 'in2.text' },
      status: 'bound',
      ambiguousInputs: [],
      ambiguousOutputs: [],
    },
  )

  // Generic output -> incompatible explicit input port stays blank + incompatible.
  const concatToIdsPort = resolveAutoBindings('s1', concat, sub, { explicitInput: 'ids' })
  assert.equal(concatToIdsPort.status, 'incompatible')
  assert.deepEqual(concatToIdsPort.bindings, {})
})

test('pruneBindingsForRemovedEdges clears stale bindings without disturbing kept edges', () => {
  const loi = makeNode('l1', 'loi_check', { express_ids: 'f1.express_ids' })
  const sub = makeSubworkflowNode(
    'sub1',
    [
      { name: 'a' },
      { name: 'b' },
    ],
    { a: 's1.value', b: 's1.value' },
  )
  const nodesById = { l1: loi, sub1: sub }

  pruneBindingsForRemovedEdges(
    nodesById,
    [{ source: 'f1', target: 'l1', targetHandle: 'input' }],
    [],
  )
  assert.deepEqual(loi.data.input_bindings, {})

  pruneBindingsForRemovedEdges(
    nodesById,
    [{ source: 's1', target: 'sub1', targetHandle: 'input:a' }],
    [{ source: 's1', target: 'sub1', targetHandle: 'input:b' }],
  )
  assert.deepEqual(sub.data.input_bindings, { b: 's1.value' })
})
