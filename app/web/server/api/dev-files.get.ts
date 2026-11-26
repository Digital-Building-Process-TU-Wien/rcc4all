import { readdir } from 'node:fs/promises'
import { assertDevOnly, DEV_FILES_DIRECTORY, isMissingPathError } from '../utils/dev-files'

export default defineEventHandler(async () => {
  assertDevOnly()

  try {
    const entries = await readdir(DEV_FILES_DIRECTORY, { withFileTypes: true })

    return {
      files: entries
        .filter(entry => entry.isFile())
        .map(entry => entry.name)
        .sort((left, right) => left.localeCompare(right)),
    }
  }
  catch (error) {
    if (isMissingPathError(error)) {
      throw createError({
        statusCode: 404,
        statusMessage: '.dev-files folder not found',
      })
    }

    throw error
  }
})
