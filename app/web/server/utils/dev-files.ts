import { resolve } from 'node:path'
import process from 'node:process'

export const DEV_FILES_DIRECTORY = resolve(process.cwd(), '.dev-files')

/** Every `.dev-files` endpoint is a local development convenience only. */
export function assertDevOnly(): void {
  if (!import.meta.dev) {
    throw createError({
      statusCode: 404,
      statusMessage: 'Not Found',
    })
  }
}

/** `true` for ENOENT/ENOTDIR, the two "this path is not there" errors. */
export function isMissingPathError(error: unknown): boolean {
  return typeof error === 'object'
    && error !== null
    && 'code' in error
    && (error.code === 'ENOENT' || error.code === 'ENOTDIR')
}
