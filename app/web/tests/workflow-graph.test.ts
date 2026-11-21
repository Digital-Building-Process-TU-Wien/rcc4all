import type { StoredEdge, StoredNode } from '../app/utils/nodes'
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { extractSubworkflowGraph } from '../app/utils/subworkflow-graph'
import { hydrateWorkflow, serializeScope } from '../app/utils/workflow-serialization'

function makeNode(
  id: string,
  nodeName: string,
  x: number,
  bindings: Record<string, string> = {},
): StoredNode {
  return {
    id,
    position: { x, y: 100 },
    data: {
      label: nodeName,
      nodeName,
      settings: {},
      input_bindings: { ...bindings },
    },
  }
}

test('serializeScope and hydrateWorkflow round-trip graphs and subworkflow handles', () => {
  const nodes: StoredNode[] = [
    makeNode('file1', 'file_input', 0),
    makeNode('f1', 'ifc_element_filter', 240, { model_slug: 'file1.model_slug' }),
    makeNode('preview', 'JsonOutput', 480),
  ]
  const edges: StoredEdge[] = [
    { id: 'e1', source: 'file1', target: 'f1', sourceHandle: 'output', targetHandle: 'input' },
    { id: 'e2', source: 'f1', target: 'preview', sourceHandle: 'output', targetHandle: 'input' },
  ]

  const serialized = serializeScope(nodes, edges)
  assert.deepEqual(serialized.nodes.map(n => n.id), ['file1', 'f1'])
  assert.deepEqual(serialized.edges, [{ source: 'file1', target: 'f1' }])

  const hydrated = hydrateWorkflow({
    files: [{ slug: 'arch', path: 'arch.ifc' }],
    nodes: serialized.nodes,
    edges: serialized.edges,
  })
  assert.deepEqual(hydrated.files.map(f => f.slug), ['main', 'arch'])
  assert.equal(hydrated.rootFrame.nodes[0]?.data.noInput, true)
  assert.equal(hydrated.rootFrame.edges[0]?.sourceHandle, 'output')
  assert.equal(hydrated.rootFrame.edges[0]?.targetHandle, 'input')
})

test('extractSubworkflowGraph extracts selected nodes with typed boundary ports', () => {
  const nodes: StoredNode[] = [
    makeNode('f1', 'ifc_element_filter', 0),
    makeNode('l1', 'loi_check', 240, { express_ids: 'f1.express_ids' }),
    makeNode('b1', 'bcf_output', 480, { elements: 'l1.elements' }),
  ]
  const edges: StoredEdge[] = [
    { id: 'e1', source: 'f1', target: 'l1', sourceHandle: 'output', targetHandle: 'input' },
    { id: 'e2', source: 'l1', target: 'b1', sourceHandle: 'output', targetHandle: 'input' },
  ]

  let seq = 0
  const result = extractSubworkflowGraph(nodes, edges, ['l1'], 'LOI Sub', () => `gen-${++seq}`)
  assert.equal(result.ok, true)
  if (!result.ok)
    return

  assert.deepEqual(result.removedNodeIds, ['l1'])
  assert.deepEqual(result.subworkflowNode.data.input_bindings, {
    express_ids: 'f1.express_ids',
  })
  assert.deepEqual(result.reboundParents, [
    { nodeId: 'b1', bindings: { elements: `${result.subworkflowNode.id}.elements` } },
  ])
  assert.equal(result.remainingEdges.length, 2)
  assert.equal(result.remainingEdges[0]?.targetHandle, 'input:express_ids')
  assert.equal(result.remainingEdges[1]?.sourceHandle, 'output:elements')

  const inner = result.subworkflowNode.data.subworkflow!
  assert.equal(inner.nodes.some(n => n.data.nodeName === 'subworkflow_input'), true)
  assert.equal(inner.nodes.some(n => n.data.nodeName === 'subworkflow_output'), true)
})

test('extractSubworkflowGraph rejects empty selection and multi-output conflicts', () => {
  const nodes: StoredNode[] = [
    makeNode('l1', 'loi_check', 0),
    makeNode('b1', 'bcf_output', 240, { elements: 'l1.elements' }),
    makeNode('f1', 'ifc_element_filter', 240, { express_ids: 'l1.failed_express_ids' }),
  ]
  assert.deepEqual(extractSubworkflowGraph(nodes, [], [], 'Empty'), {
    ok: false,
    reason: 'empty',
    details: [],
  })

  const conflict = extractSubworkflowGraph(nodes, [], ['l1'], 'Conflict')
  assert.equal(conflict.ok, false)
  if (!conflict.ok) {
    assert.equal(conflict.reason, 'output-conflict')
    assert.deepEqual(conflict.details, ['l1.elements', 'l1.failed_express_ids'])
  }
})
