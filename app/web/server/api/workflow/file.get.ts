import { toDevFilesRelativeModelPaths } from '#shared/utils/dev-paths'
import { assertDevOnly, DEV_FILES_DIRECTORY } from '../../utils/dev-files'
import {
  ensureJsonExtension,
  readWorkflowFile,
  resolveInDevFiles,
} from '../../utils/workflow-files'

export default defineEventHandler(async (event) => {
  assertDevOnly()

  const { path } = getQuery(event)
  if (typeof path !== 'string' || !path.trim()) {
    throw createError({
      statusCode: 400,
      statusMessage: 'A file path is required',
    })
  }

  const requested = ensureJsonExtension(path)
  const workflow = await readWorkflowFile(requested)
  if (!workflow) {
    throw createError({
      statusCode: 404,
      statusMessage: 'Workflow file not found',
    })
  }

  const { absolute, relative } = resolveInDevFiles(requested)
  return {
    path: relative,
    workflow: toDevFilesRelativeModelPaths(workflow, absolute, DEV_FILES_DIRECTORY),
  }
})
