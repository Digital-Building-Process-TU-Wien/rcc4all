const BACKSLASH_RE = /\\/g

/**
 * Path helpers that only manipulate posix strings. They are imported by browser
 * code, so this module must stay free of `node:path`.
 */

export function toPosixPath(value: string): string {
  return value.replace(BACKSLASH_RE, '/')
}

export function parentDirectory(dir: string): string | null {
  if (!dir)
    return null
  const segments = dir.split('/').filter(Boolean)
  segments.pop()
  return segments.join('/')
}

export function joinPosix(directory: string, name: string): string {
  return directory ? `${directory}/${name}` : name
}
