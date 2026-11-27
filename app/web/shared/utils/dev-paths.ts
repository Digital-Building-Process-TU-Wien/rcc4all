import type { WorkflowPayload } from '../types/workflow-files'
import { dirname, isAbsolute, relative, resolve } from 'node:path'
import { toPosixPath } from './posix-paths'

const PARENT_SEGMENT_RE = /[/\\]/
const LEADING_SLASH_RE = /^\/+/
const DRIVE_LETTER_RE = /^[a-z]:[\\/]/i

export interface ResolvedPath {
  absolute: string
  relative: string
}

function escapesRoot(root: string, absolutePath: string): boolean {
  const relativeToRoot = relative(root, absolutePath)
  return isAbsolute(relativeToRoot) || relativeToRoot.split(PARENT_SEGMENT_RE)[0] === '..'
}

/**
 * Resolve a user-supplied path against `root`, refusing anything that would end up
 * outside of it (absolute paths, `..` segments, NUL bytes). `null` means rejected.
 */
export function resolveRelativeIn(root: string, rawPath: string): ResolvedPath | null {
  if (rawPath.includes('\0'))
    return null

  const relativePath = toPosixPath(rawPath.trim()).replace(LEADING_SLASH_RE, '')
  const absolute = resolve(root, relativePath)
  if (escapesRoot(root, absolute))
    return null

  return { absolute, relative: toPosixPath(relative(root, absolute)) }
}

function isPortableRelativePath(value: string): boolean {
  return !isAbsolute(value) && !DRIVE_LETTER_RE.test(value)
}

function mapModelPaths(
  workflow: WorkflowPayload,
  transform: (modelPath: string) => string,
): WorkflowPayload {
  if (!Array.isArray(workflow.files))
    return workflow

  return {
    ...workflow,
    files: workflow.files.map((entry) => {
      if (!entry || typeof entry !== 'object' || Array.isArray(entry))
        return entry
      const file = entry as Record<string, unknown>
      if (typeof file.path !== 'string' || !file.path || !isPortableRelativePath(file.path))
        return entry
      return { ...file, path: transform(file.path) }
    }),
  }
}

/**
 * The runner resolves model paths against the workflow file itself. Translate the
 * editor's `root`-relative paths into that native form before writing. Paths that
 * already sit outside `root` are left untouched, which makes this idempotent.
 */
export function toWorkflowRelativeModelPaths(
  workflow: WorkflowPayload,
  workflowAbsolutePath: string,
  root: string,
): WorkflowPayload {
  const workflowDir = dirname(workflowAbsolutePath)
  return mapModelPaths(workflow, (modelPath) => {
    const modelAbsolutePath = resolve(root, modelPath)
    if (escapesRoot(root, modelAbsolutePath))
      return modelPath
    return toPosixPath(relative(workflowDir, modelAbsolutePath))
  })
}

/**
 * Inverse of `toWorkflowRelativeModelPaths`: the editor addresses models relative
 * to `root`, so resolve the stored paths back into it. Paths that leave `root`
 * stay untouched.
 */
export function toDevFilesRelativeModelPaths(
  workflow: WorkflowPayload,
  workflowAbsolutePath: string,
  root: string,
): WorkflowPayload {
  const workflowDir = dirname(workflowAbsolutePath)
  return mapModelPaths(workflow, (modelPath) => {
    const modelAbsolutePath = resolve(workflowDir, modelPath)
    if (escapesRoot(root, modelAbsolutePath))
      return modelPath
    return toPosixPath(relative(root, modelAbsolutePath))
  })
}
