import { createHash } from 'node:crypto'
import { readFile } from 'node:fs/promises'
import { join, normalize } from 'node:path'
import process from 'node:process'

export default defineEventHandler(async (event) => {
  if (!import.meta.dev) {
    throw createError({
      statusCode: 404,
      statusMessage: 'Not Found',
    })
  }

  const { name } = getQuery(event)
  if (typeof name !== 'string' || !name) {
    throw createError({
      statusCode: 400,
      statusMessage: 'A file name is required',
    })
  }

  const devFilesDirectory = normalize(join(process.cwd(), '.dev-files'))
  const target = normalize(join(devFilesDirectory, name))
  if (!target.startsWith(devFilesDirectory)) {
    throw createError({
      statusCode: 400,
      statusMessage: 'Invalid file name',
    })
  }

  try {
    const content = await readFile(target)
    return {
      hash: createHash('sha256').update(content).digest('hex'),
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
        statusMessage: 'File not found',
      })
    }
    throw error
  }
})
