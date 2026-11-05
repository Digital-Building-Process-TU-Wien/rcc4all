import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { assertDevOnly, isMissingPathError } from '../utils/dev-files'
import { resolveInDevFiles } from '../utils/workflow-files'

export default defineEventHandler(async (event) => {
  assertDevOnly()

  const { name } = getQuery(event)
  if (typeof name !== 'string' || !name) {
    throw createError({
      statusCode: 400,
      statusMessage: 'A file name is required',
    })
  }

  const { absolute } = resolveInDevFiles(name)

  try {
    const content = await readFile(absolute)
    return {
      hash: createHash('sha256').update(content).digest('hex'),
    }
  }
  catch (error) {
    if (isMissingPathError(error)) {
      throw createError({
        statusCode: 404,
        statusMessage: 'File not found',
      })
    }
    throw error
  }
})
