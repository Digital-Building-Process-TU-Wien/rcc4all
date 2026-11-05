import { assertDevOnly } from '../../utils/dev-files'
import { listWorkflowDirectory } from '../../utils/workflow-files'

export default defineEventHandler(async (event) => {
  assertDevOnly()

  const { dir } = getQuery(event)
  return await listWorkflowDirectory(dir)
})
