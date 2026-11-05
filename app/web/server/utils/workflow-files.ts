import type { Dirent } from 'node:fs'
import type {
  WorkflowDirectoryListing,
  WorkflowFileEntry,
  WorkflowPayload,
} from '#shared/types/workflow-files'
import { readdir, readFile, stat } from 'node:fs/promises'
import { DEFAULT_WORKFLOW_DIR, WORKFLOW_FILE_EXTENSION } from '#shared/types/workflow-files'
import {
  resolveRelativeIn,
} from '#shared/utils/dev-paths'
import {
  joinPosix,
  parentDirectory,
} from '#shared/utils/posix-paths'
import { DEV_FILES_DIRECTORY, isMissingPathError } from './dev-files'

const JSON_EXTENSION_RE = /\.json$/i
const HIDDEN_FILE_RE = /^\./

export function resolveInDevFiles(rawPath: unknown): { absolute: string, relative: string } {
  const value = typeof rawPath === 'string' ? rawPath : ''
  const resolved = resolveRelativeIn(DEV_FILES_DIRECTORY, value)
  if (!resolved) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Invalid file path',
    })
  }
  return resolved
}

export function ensureJsonExtension(path: string): string {
  return JSON_EXTENSION_RE.test(path) ? path : `${path}${WORKFLOW_FILE_EXTENSION}`
}

export function isWorkflowPayload(value: unknown): value is WorkflowPayload {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    return false

  const candidate = value as Record<string, unknown>
  if (!Array.isArray(candidate.nodes) || !Array.isArray(candidate.edges))
    return false
  if (candidate.files !== undefined && !Array.isArray(candidate.files))
    return false

  return true
}

async function readWorkflowEntry(entry: Dirent, directory: string): Promise<WorkflowFileEntry | null> {
  if (!entry.isFile() || HIDDEN_FILE_RE.test(entry.name) || !JSON_EXTENSION_RE.test(entry.name))
    return null

  const path = joinPosix(directory, entry.name)
  const { absolute } = resolveInDevFiles(path)

  try {
    const [content, info] = await Promise.all([readFile(absolute, 'utf-8'), stat(absolute)])
    // Only files that actually look like a workflow belong in the chooser.
    if (!isWorkflowPayload(JSON.parse(content)))
      return null

    return { name: entry.name, path, modifiedAt: info.mtime.toISOString() }
  }
  catch {
    return null
  }
}

/** List subfolders and workflow JSON files of one directory inside `.dev-files`. */
export async function listWorkflowDirectory(rawDir: unknown): Promise<WorkflowDirectoryListing> {
  const requested = typeof rawDir === 'string'
    ? rawDir
    : DEFAULT_WORKFLOW_DIR
  const { absolute, relative: dir } = resolveInDevFiles(requested)

  let entries: Dirent[]
  try {
    entries = await readdir(absolute, { withFileTypes: true })
  }
  catch (error) {
    if (isMissingPathError(error))
      return { dir, parent: parentDirectory(dir), directories: [], files: [] }
    throw error
  }

  const directories = entries
    .filter(entry => entry.isDirectory() && !HIDDEN_FILE_RE.test(entry.name))
    .map(entry => ({ name: entry.name, path: joinPosix(dir, entry.name) }))
    .sort((left, right) => left.name.localeCompare(right.name))

  const files = (await Promise.all(
    entries.map(entry => readWorkflowEntry(entry, dir)),
  ))
    .filter((entry): entry is WorkflowFileEntry => entry !== null)
    .sort((left, right) => right.modifiedAt.localeCompare(left.modifiedAt))

  return { dir, parent: parentDirectory(dir), directories, files }
}

/** Read one workflow JSON file; `null` when it is missing or not a workflow. */
export async function readWorkflowFile(path: string): Promise<WorkflowPayload | null> {
  const { absolute } = resolveInDevFiles(path)

  try {
    const content = await readFile(absolute, 'utf-8')
    const parsed: unknown = JSON.parse(content)
    return isWorkflowPayload(parsed) ? parsed : null
  }
  catch (error) {
    if (isMissingPathError(error))
      return null
    throw error
  }
}
