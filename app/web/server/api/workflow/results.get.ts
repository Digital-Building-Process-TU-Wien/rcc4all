import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import process from 'node:process'

export default defineEventHandler(async (event) => {
  const query = getQuery(event)
  const filename = query.file as string

  if (!filename) {
    throw createError({
      statusCode: 400,
      statusMessage: 'File parameter is required',
    })
  }

  const devFilesDir = join(process.cwd(), '.dev-files')
  const filepath = join(devFilesDir, filename)

  try {
    const content = await readFile(filepath, 'utf-8')
    return JSON.parse(content)
  }
  catch (error: any) {
    if (error.code === 'ENOENT') {
      throw createError({
        statusCode: 404,
        statusMessage: 'Results file not found',
      })
    }

    throw createError({
      statusCode: 500,
      statusMessage: 'Failed to read results file',
    })
  }
})
