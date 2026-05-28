import { readdir } from 'node:fs/promises'
import { join } from 'node:path'
import process from 'node:process'

export default defineEventHandler(async () => {
  if (!import.meta.dev) {
    throw createError({
      statusCode: 404,
      statusMessage: 'Not Found',
    })
  }

  const devFilesDirectory = join(process.cwd(), '.dev-files')

  try {
    const entries = await readdir(devFilesDirectory, { withFileTypes: true })

    return {
      files: entries
        .filter(entry => entry.isFile())
        .map(entry => entry.name)
        .sort((left, right) => left.localeCompare(right)),
    }
  }
  catch (error) {
    if (
      typeof error === 'object'
      && error !== null
      && 'code' in error
      && (error.code === 'ENOENT' || error.code === 'ENOTDIR')
    ) {
      throw createError({
        statusCode: 404,
        statusMessage: '.dev-files folder not found',
      })
    }

    throw error
  }
})
