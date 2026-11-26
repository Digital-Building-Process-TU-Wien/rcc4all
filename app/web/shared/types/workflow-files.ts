/** Every workflow file endpoint is scoped to this folder. */
export const DEV_FILES_LABEL = 'web/.dev-files'

/** Default folder for named workflows, relative to `.dev-files`. */
export const DEFAULT_WORKFLOW_DIR = 'workflow'

export const WORKFLOW_FILE_EXTENSION = '.json'

export interface WorkflowFileEntry {
  name: string
  path: string
  modifiedAt: string
}

export interface WorkflowDirectoryEntry {
  name: string
  path: string
}

export interface WorkflowDirectoryListing {
  dir: string
  parent: string | null
  directories: WorkflowDirectoryEntry[]
  files: WorkflowFileEntry[]
}

/**
 * The runner payload. `openbim_runner` forbids unknown keys, so this is also the
 * exact shape that may be written to disk.
 */
export interface WorkflowPayload {
  files?: unknown[]
  nodes: unknown[]
  edges: unknown[]
}
