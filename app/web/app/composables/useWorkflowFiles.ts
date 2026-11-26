import type { WorkflowDirectoryListing, WorkflowFileEntry } from '#shared/types/workflow-files'
import type { ExportedWorkflow } from '~/stores/flow'

export interface LoadedWorkflow {
  path: string
  workflow: ExportedWorkflow
}

export interface SaveWorkflowOptions {
  path: string
  workflow: ExportedWorkflow
  overwrite?: boolean
}

interface FetchFailure {
  statusCode?: unknown
  data?: { statusMessage?: unknown }
}

function asFetchFailure(cause: unknown): FetchFailure {
  return typeof cause === 'object' && cause !== null ? cause as FetchFailure : {}
}

/** One place that knows how a failed `$fetch` call reports its reason. */
export function workflowFileErrorMessage(cause: unknown, fallback: string): string {
  const message = asFetchFailure(cause).data?.statusMessage
  return typeof message === 'string' && message ? message : fallback
}

export function isWorkflowFileConflict(cause: unknown): boolean {
  return asFetchFailure(cause).statusCode === 409
}

export function useWorkflowFiles() {
  async function listDirectory(dir: string): Promise<WorkflowDirectoryListing> {
    return await $fetch<WorkflowDirectoryListing>('/api/workflow/files', {
      query: { dir },
    })
  }

  async function loadWorkflow(path: string): Promise<LoadedWorkflow> {
    return await $fetch<LoadedWorkflow>('/api/workflow/file', {
      query: { path },
    })
  }

  async function saveWorkflow(options: SaveWorkflowOptions): Promise<{ path: string }> {
    return await $fetch<{ path: string }>('/api/workflow/file', {
      method: 'POST',
      body: options,
    })
  }

  return {
    listDirectory,
    loadWorkflow,
    saveWorkflow,
  }
}

export type { WorkflowFileEntry }
