import { mkdir, stat, writeFile } from 'node:fs/promises'
import { dirname } from 'node:path'
import { toWorkflowRelativeModelPaths } from '#shared/utils/dev-paths'
import { assertDevOnly, DEV_FILES_DIRECTORY, isMissingPathError } from '../../utils/dev-files'
import {
  ensureJsonExtension,
  isWorkflowPayload,
  resolveInDevFiles,
} from '../../utils/workflow-files'

export default defineEventHandler(async (event) => {
  assertDevOnly()

  const body = await readBody(event)
  if (!body || typeof body !== 'object') {
    throw createError({
      statusCode: 400,
      statusMessage: 'A workflow payload is required',
    })
  }

  const { path, workflow, overwrite } = body as {
    path?: unknown
    workflow?: unknown
    overwrite?: unknown
  }

  if (typeof path !== 'string' || !path.trim()) {
    throw createError({
      statusCode: 400,
      statusMessage: 'A file path is required',
    })
  }
  if (path.trim().endsWith('/') || path.trim().endsWith('\\')) {
    throw createError({
      statusCode: 400,
      statusMessage: 'A file name is required',
    })
  }
  if (!isWorkflowPayload(workflow)) {
    throw createError({
      statusCode: 400,
      statusMessage: 'A workflow with nodes and edges is required',
    })
  }

  const { absolute, relative } = resolveInDevFiles(ensureJsonExtension(path))

  const exists = await stat(absolute).then(() => true).catch((error: unknown) => {
    if (isMissingPathError(error))
      return false
    throw error
  })

  if (exists && overwrite !== true) {
    throw createError({
      statusCode: 409,
      statusMessage: 'A workflow file with this name already exists',
    })
  }

  await mkdir(dirname(absolute), { recursive: true })
  const payload = toWorkflowRelativeModelPaths(workflow, absolute, DEV_FILES_DIRECTORY)
  await writeFile(absolute, `${JSON.stringify(payload, null, 2)}\n`, 'utf-8')

  return { path: relative }
})
