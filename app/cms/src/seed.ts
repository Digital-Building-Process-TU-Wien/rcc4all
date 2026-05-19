import 'dotenv/config'
import { consola } from 'consola'
import { existsSync } from 'fs'
import fs from 'fs/promises'
import path from 'path'
import { getPayload, Payload, Where } from 'payload'
import { fileURLToPath } from 'url'
import config from './payload.config'
import { getHomePageData } from './page-data'

import type { FileEntry, FileRevision, Group, Page, Project, User } from './payload-types'

type SeedFileType = 'IFC' | 'IDS' | 'CSV' | 'Image' | 'Workflow JSON'

async function getPayloadInstance() {
  const payloadConfig = await config
  return getPayload({ config: payloadConfig })
}

function resolveDatabasePath(databaseUrl: string | undefined) {
  if (!databaseUrl) return undefined

  if (databaseUrl.startsWith('file:')) {
    const filePath = databaseUrl.replace(/^file:/, '')
    if (filePath.startsWith('//')) {
      return fileURLToPath(databaseUrl)
    }

    return path.resolve(process.cwd(), filePath)
  }

  return databaseUrl
}

async function confirmDatabaseReset() {
  const databasePath = resolveDatabasePath(process.env.DATABASE_URL)
  if (!databasePath) return

  if (!databasePath.endsWith('.db')) return
  if (!existsSync(databasePath)) return
  if (!process.stdin.isTTY || !process.stdout.isTTY) return

  const confirmed = await consola.prompt(
    `Database file found at ${databasePath}. Delete it? A .bkp file will be created first.`,
    {
      type: 'confirm',
      initial: false,
    },
  )

  if (!confirmed) return

  const backupPath = `${databasePath}.bkp`
  await fs.copyFile(databasePath, backupPath)
  await fs.unlink(databasePath)
}

async function findUserByEmail(payload: Payload, email: string) {
  const existing = await payload.find({
    collection: 'users',
    where: { email: { equals: email } },
    depth: 0,
    limit: 1,
    overrideAccess: true,
  })
  return existing.docs[0] as User | undefined
}

async function ensureSuperAdmin(payload: Payload) {
  const existing = await findUserByEmail(payload, 'super@test.com')
  if (existing) return existing

  const created = await payload.create({
    collection: 'users',
    data: {
      name: 'Super Admin',
      email: 'super@test.com',
      password: '1234',
      roles: ['super-admin'],
    },
    overrideAccess: true,
  })

  return created as User
}

async function ensureUser(
  payload: Payload,
  args: { name: string; email: string; password: string; roles: User['roles'] },
) {
  const existing = await findUserByEmail(payload, args.email)
  if (existing) return existing

  const created = await payload.create({
    collection: 'users',
    data: {
      name: args.name,
      email: args.email,
      password: args.password,
      roles: args.roles,
    },
    overrideAccess: true,
  })

  return created as User
}

async function findGroupByTitle(payload: Payload, title: string, parentId?: number) {
  const where: Where = parentId
    ? { and: [{ title: { equals: title } }, { parent: { equals: parentId } }] }
    : { title: { equals: title } }

  const existing = await payload.find({
    collection: 'groups',
    where,
    depth: 0,
    limit: 1,
    overrideAccess: true,
  })

  return existing.docs[0] as Group | undefined
}

async function ensureGroup(
  payload: Payload,
  args: { title: string; parentId?: number; adminId?: number; userId?: number },
) {
  const existing = await findGroupByTitle(payload, args.title, args.parentId)
  if (existing) return existing

  const created = await payload.create({
    collection: 'groups',
    data: {
      title: args.title,
      parent: args.parentId,
      admins: args.adminId ? [args.adminId] : undefined,
      users: args.userId ? [args.userId] : undefined,
    },
    overrideAccess: true,
  })

  return created as Group
}

function extractUserIds(values?: (number | User)[] | null) {
  if (!values) return []
  return values.map((value) => (typeof value === 'number' ? value : value.id))
}

function mergeUniqueIds(existing: number[], additions: number[]) {
  return Array.from(new Set([...existing, ...additions]))
}

async function ensureGroupMembers(
  payload: Payload,
  args: { groupId: number; adminIds?: number[]; userIds?: number[] },
) {
  const group = (await payload.findByID({
    collection: 'groups',
    id: args.groupId,
    depth: 0,
    overrideAccess: true,
  })) as Group

  const adminIds = mergeUniqueIds(extractUserIds(group.admins), args.adminIds ?? [])
  const userIds = mergeUniqueIds(extractUserIds(group.users), args.userIds ?? [])

  await payload.update({
    collection: 'groups',
    id: args.groupId,
    data: {
      admins: adminIds,
      users: userIds,
    },
    overrideAccess: true,
  })
}

async function findFileEntryByKey(payload: Payload, entryKey: string, projectId: number) {
  const existing = await payload.find({
    collection: 'file-entry',
    where: {
      and: [{ entryKey: { equals: entryKey } }, { project: { equals: projectId } }],
    },
    depth: 0,
    limit: 1,
    overrideAccess: true,
  })

  return existing.docs[0] as FileEntry | undefined
}

async function findRevisionByFileName(payload: Payload, filename: string, fileEntryId: number) {
  const existing = await payload.find({
    collection: 'file-revisions',
    where: {
      and: [{ filename: { equals: filename } }, { fileEntry: { equals: fileEntryId } }],
    },
    depth: 0,
    limit: 1,
    overrideAccess: true,
  })

  return existing.docs[0] as FileRevision | undefined
}

async function ensureFileEntry(
  payload: Payload,
  args: { entryKey: string; type: SeedFileType; sourcePath: string; projectId: number },
) {
  const existing = await findFileEntryByKey(payload, args.entryKey, args.projectId)
  if (existing) return existing

  const created = await payload.create({
    collection: 'file-entry',
    data: {
      project: args.projectId,
      entryKey: args.entryKey,
      type: args.type,
      meta: {
        sourcePath: args.sourcePath,
      },
    },
    overrideAccess: true,
  })

  return created as FileEntry
}

async function ensureFileRevision(
  payload: Payload,
  args: {
    fileEntryId: number
    filename: string
    revisionNumber: number
    sourcePath: string
  },
) {
  const existing = await findRevisionByFileName(payload, args.filename, args.fileEntryId)
  if (existing) return existing

  const data = Buffer.from(`Seed placeholder for ${args.filename}`)

  const created = await payload.create({
    collection: 'file-revisions',
    data: {
      fileEntry: args.fileEntryId,
      revisionNumber: args.revisionNumber,
      meta: {
        sourcePath: args.sourcePath,
        note: 'linked to non-existent source file',
      },
    },
    file: {
      data,
      name: args.filename,
      mimetype: 'text/plain',
      size: data.length,
    },
    overrideAccess: true,
  })

  return created as FileRevision
}

async function findProjectByTitle(payload: Payload, title: string, groupId: number) {
  const existing = await payload.find({
    collection: 'projects',
    where: {
      and: [{ title: { equals: title } }, { group: { equals: groupId } }],
    },
    depth: 0,
    limit: 1,
    overrideAccess: true,
  })

  return existing.docs[0] as Project | undefined
}

async function ensureProject(
  payload: Payload,
  args: { title: string; description?: string; groupId: number; creatorId?: number },
) {
  const existing = await findProjectByTitle(payload, args.title, args.groupId)
  if (existing) return existing

  const created = await payload.create({
    collection: 'projects',
    data: {
      title: args.title,
      description: args.description,
      group: args.groupId,
      creator: args.creatorId,
    },
    overrideAccess: true,
  })

  return created as Project
}

async function findPageBySlug(payload: Payload, slug: string) {
  const existing = await payload.find({
    collection: 'pages',
    where: {
      slug: { equals: slug },
    },
    depth: 0,
    limit: 1,
    locale: 'en',
    fallbackLocale: false,
    overrideAccess: true,
  })

  return existing.docs[0] as Page | undefined
}

async function ensureHomePage(payload: Payload) {
  const existing = await findPageBySlug(payload, 'home')

  if (!existing) {
    const created = await payload.create({
      collection: 'pages',
      locale: 'en',
      fallbackLocale: false,
      data: {
        slug: 'home',
        ...getHomePageData('en'),
      },
      overrideAccess: true,
    })

    await payload.update({
      collection: 'pages',
      id: created.id,
      locale: 'de',
      fallbackLocale: false,
      data: getHomePageData('de'),
      overrideAccess: true,
    })

    return created as Page
  }

  await payload.update({
    collection: 'pages',
    id: existing.id,
    locale: 'en',
    fallbackLocale: false,
    data: getHomePageData('en'),
    overrideAccess: true,
  })

  return payload.update({
    collection: 'pages',
    id: existing.id,
    locale: 'de',
    fallbackLocale: false,
    data: getHomePageData('de'),
    overrideAccess: true,
  }) as Promise<Page>
}

async function ensureWorkflowRun(
  payload: Payload,
  args: {
    name: string
    projectId: number
    timestamp: string
    inputFiles: number[]
    outputFiles: number[]
  },
) {
  const existing = await payload.find({
    collection: 'workflow-runs',
    where: {
      and: [{ name: { equals: args.name } }, { project: { equals: args.projectId } }],
    },
    depth: 0,
    limit: 1,
    overrideAccess: true,
  })

  if (existing.docs.length) return existing.docs[0]

  return payload.create({
    collection: 'workflow-runs',
    data: {
      name: args.name,
      project: args.projectId,
      timestamp: args.timestamp,
      inputFiles: args.inputFiles,
      outputFiles: args.outputFiles,
    },
    overrideAccess: true,
  })
}

async function main() {
  await confirmDatabaseReset()
  const payload = await getPayloadInstance()

  const superAdmin = await ensureSuperAdmin(payload)

  await ensureUser(payload, {
    name: 'Demo Admin',
    email: 'admin@test.com',
    password: '1234',
    roles: ['super-admin'],
  })

  const testGroup = await ensureGroup(payload, {
    title: 'test',
    adminId: superAdmin.id,
    userId: superAdmin.id,
  })

  const testSubA = await ensureGroup(payload, {
    title: 'test-sub-a',
    parentId: testGroup.id,
    adminId: superAdmin.id,
    userId: superAdmin.id,
  })

  const groupAdmin = await ensureUser(payload, {
    name: 'Group Admin',
    email: 'group@test.com',
    password: '1234',
    roles: ['group-admin'],
  })

  const groupUser = await ensureUser(payload, {
    name: 'Group User',
    email: 'user@test.com',
    password: '1234',
    roles: ['user'],
  })

  await ensureGroupMembers(payload, {
    groupId: testGroup.id,
    adminIds: [groupAdmin.id],
  })

  await ensureGroupMembers(payload, {
    groupId: testSubA.id,
    userIds: [groupUser.id],
  })

  await ensureGroup(payload, {
    title: 'test-sub-a-child',
    parentId: testSubA.id,
    adminId: superAdmin.id,
    userId: superAdmin.id,
  })

  await ensureGroup(payload, {
    title: 'test-sub-b',
    parentId: testGroup.id,
    adminId: superAdmin.id,
    userId: superAdmin.id,
  })

  const publicGroup = await ensureGroup(payload, {
    title: 'public',
  })

  const publicProject = await ensureProject(payload, {
    title: 'Public Seed Project',
    description: 'Public test project seeded for development.',
    groupId: publicGroup.id,
    creatorId: superAdmin.id,
  })

  const publicFileEntryA = await ensureFileEntry(payload, {
    entryKey: 'public-seed-a.txt',
    type: 'CSV',
    sourcePath: 'non-existent://public-seed-a.txt',
    projectId: publicProject.id,
  })

  const publicFileEntryB = await ensureFileEntry(payload, {
    entryKey: 'public-seed-b.txt',
    type: 'CSV',
    sourcePath: 'non-existent://public-seed-b.txt',
    projectId: publicProject.id,
  })

  const publicFileA = await ensureFileRevision(payload, {
    fileEntryId: publicFileEntryA.id,
    filename: 'public-seed-a.txt',
    revisionNumber: 1,
    sourcePath: 'non-existent://public-seed-a.txt',
  })

  const publicFileB = await ensureFileRevision(payload, {
    fileEntryId: publicFileEntryB.id,
    filename: 'public-seed-b.txt',
    revisionNumber: 1,
    sourcePath: 'non-existent://public-seed-b.txt',
  })

  await payload.update({
    collection: 'file-entry',
    id: publicFileEntryA.id,
    data: { latestRevision: publicFileA.id },
    overrideAccess: true,
  })

  await payload.update({
    collection: 'file-entry',
    id: publicFileEntryB.id,
    data: { latestRevision: publicFileB.id },
    overrideAccess: true,
  })

  await ensureWorkflowRun(payload, {
    name: 'Public baseline run',
    projectId: publicProject.id,
    timestamp: new Date().toISOString(),
    inputFiles: [publicFileA.id],
    outputFiles: [publicFileB.id],
  })

  const privateProject = await ensureProject(payload, {
    title: 'Private Seed Project',
    description: 'Private subgroup project seeded for development.',
    groupId: testSubA.id,
    creatorId: superAdmin.id,
  })

  const privateFileEntryA = await ensureFileEntry(payload, {
    entryKey: 'private-seed-a.txt',
    type: 'IFC',
    sourcePath: 'non-existent://private-seed-a.txt',
    projectId: privateProject.id,
  })

  const privateFileEntryB = await ensureFileEntry(payload, {
    entryKey: 'private-seed-b.txt',
    type: 'IFC',
    sourcePath: 'non-existent://private-seed-b.txt',
    projectId: privateProject.id,
  })

  const privateFileA = await ensureFileRevision(payload, {
    fileEntryId: privateFileEntryA.id,
    filename: 'private-seed-a.txt',
    revisionNumber: 1,
    sourcePath: 'non-existent://private-seed-a.txt',
  })

  const privateFileB = await ensureFileRevision(payload, {
    fileEntryId: privateFileEntryB.id,
    filename: 'private-seed-b.txt',
    revisionNumber: 1,
    sourcePath: 'non-existent://private-seed-b.txt',
  })

  await payload.update({
    collection: 'file-entry',
    id: privateFileEntryA.id,
    data: { latestRevision: privateFileA.id },
    overrideAccess: true,
  })

  await payload.update({
    collection: 'file-entry',
    id: privateFileEntryB.id,
    data: { latestRevision: privateFileB.id },
    overrideAccess: true,
  })

  await ensureWorkflowRun(payload, {
    name: 'Private import validation',
    projectId: privateProject.id,
    timestamp: new Date().toISOString(),
    inputFiles: [privateFileA.id],
    outputFiles: [privateFileB.id],
  })

  await ensureWorkflowRun(payload, {
    name: 'Private consistency validation',
    projectId: privateProject.id,
    timestamp: new Date(Date.now() + 1000).toISOString(),
    inputFiles: [privateFileA.id],
    outputFiles: [privateFileB.id],
  })

  await ensureHomePage(payload)
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
