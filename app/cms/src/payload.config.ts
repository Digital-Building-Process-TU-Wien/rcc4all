import { sqliteAdapter } from '@payloadcms/db-sqlite'
import { lexicalEditor } from '@payloadcms/richtext-lexical'
import path from 'path'
import { buildConfig } from 'payload'
import { fileURLToPath } from 'url'
import sharp from 'sharp'

import { Users } from './collections/Users'
import { Groups } from './collections/Groups'
import { FileEntry } from './collections/FileEntry'
import { FileRevisions } from './collections/FileRevisions'
import { Projects } from './collections/Projects'
import { WorkflowRuns } from './collections/WorkflowRuns'

const filename = fileURLToPath(import.meta.url)
const dirname = path.dirname(filename)

function parseOriginsFromEnv(value: string | undefined): string[] {
  if (!value) {
    return []
  }

  return value
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean)
}

export default buildConfig({
  cors: parseOriginsFromEnv(process.env.PAYLOAD_CORS_ORIGINS),
  csrf: parseOriginsFromEnv(process.env.PAYLOAD_CSRF_ORIGINS),
  admin: {
    user: Users.slug,
    importMap: {
      baseDir: path.resolve(dirname),
    },
  },
  collections: [Users, Groups, FileEntry, FileRevisions, Projects, WorkflowRuns],
  editor: lexicalEditor(),
  secret: process.env.PAYLOAD_SECRET || '',
  typescript: {
    outputFile: path.resolve(dirname, 'payload-types.ts'),
  },
  db: sqliteAdapter({
    client: {
      url: process.env.DATABASE_URL || '',
    },
  }),
  sharp,
  plugins: [],
  serverURL: process.env.PAYLOAD_SERVER_URL || 'http://localhost:3000',
})
