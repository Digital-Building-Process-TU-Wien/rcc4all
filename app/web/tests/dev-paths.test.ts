import type { WorkflowPayload } from '../shared/types/workflow-files'
import assert from 'node:assert/strict'
import { resolve } from 'node:path'
import { test } from 'node:test'
import {
  resolveRelativeIn,
  toDevFilesRelativeModelPaths,
  toWorkflowRelativeModelPaths,
} from '../shared/utils/dev-paths'
import {
  joinPosix,
  parentDirectory,
} from '../shared/utils/posix-paths'

const root = resolve('dev-files-root')
const workflowPath = resolve(root, 'workflow', 'checks.json')

function modelPaths(workflow: WorkflowPayload): string[] {
  return (workflow.files ?? []).map((entry) => {
    const file = entry as { path?: string }
    return file.path ?? ''
  })
}

test('parentDirectory and joinPosix split posix paths', () => {
  assert.equal(parentDirectory('workflow/checks.json'), 'workflow')
  assert.equal(parentDirectory('checks.json'), '')
  assert.equal(parentDirectory(''), null)
  assert.equal(joinPosix('', 'checks.json'), 'checks.json')
  assert.equal(joinPosix('workflow', 'checks.json'), 'workflow/checks.json')
})

test('resolveRelativeIn accepts paths inside the root', () => {
  const resolved = resolveRelativeIn(root, 'workflow/checks.json')
  assert.ok(resolved)
  assert.equal(resolved.relative, 'workflow/checks.json')
  assert.equal(resolved.absolute, workflowPath)
})

test('resolveRelativeIn rejects paths that leave the root', () => {
  assert.equal(resolveRelativeIn(root, '../secret.json'), null)
  assert.equal(resolveRelativeIn(root, 'workflow/../../secret.json'), null)
  assert.equal(resolveRelativeIn(root, 'workflow/\0checks.json'), null)
})

test('model paths round-trip through a workflow file', () => {
  const payload: WorkflowPayload = {
    files: [{ slug: 'main', path: 'models/a.ifc', hash: 'abc' }],
    nodes: [],
    edges: [],
  }

  const stored = toWorkflowRelativeModelPaths(payload, workflowPath, root)
  assert.deepEqual(modelPaths(stored), ['../models/a.ifc'])

  const restored = toDevFilesRelativeModelPaths(stored, workflowPath, root)
  assert.deepEqual(modelPaths(restored), ['models/a.ifc'])
})

test('model paths outside the root are left untouched on save', () => {
  const payload: WorkflowPayload = {
    files: [{ slug: 'main', path: '../../shared/a.ifc' }],
    nodes: [],
    edges: [],
  }

  assert.deepEqual(
    modelPaths(toWorkflowRelativeModelPaths(payload, workflowPath, root)),
    ['../../shared/a.ifc'],
  )
})
