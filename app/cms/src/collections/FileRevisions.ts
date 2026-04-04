import type { Access, CollectionConfig, Where } from 'payload'

import {
  buildGroupReadWhere,
  buildGroupWriteWhere,
  canManageProjectByID,
  getAdminGroupIds,
  getRelationID,
  isSuperAdmin,
} from '../helper/access'

type AccessArgs = Parameters<Access>[0]

export const FileRevisions: CollectionConfig = {
  slug: 'file-revisions',
  access: {
    read: fileRevisionReadAccess,
    create: fileRevisionCreateAccess,
    update: fileRevisionUpdateAccess,
    delete: fileRevisionDeleteAccess,
  },
  upload: {
    staticDir: process.env.UPLOAD_DIR || './.uploads',
  },
  fields: [
    {
      name: 'fileEntry',
      type: 'relationship',
      relationTo: 'file-entry',
      required: true,
      index: true,
    },
    {
      name: 'revisionNumber',
      type: 'number',
      required: true,
      index: true,
      min: 1,
    },
    {
      name: 'meta',
      type: 'json',
    },
  ],
  timestamps: true,
}

// Resolves the project that owns a given revision by expanding its fileEntry (depth 1).
async function canManageFileRevisionByID(
  req: Parameters<Access>[0]['req'],
  id: number | string,
): Promise<boolean> {
  const revision = await req.payload.findByID({
    collection: 'file-revisions',
    id,
    depth: 1,
    overrideAccess: true,
  })
  if (!revision) return false
  const fileEntry = typeof revision.fileEntry === 'object' ? revision.fileEntry : null
  if (!fileEntry) return false
  return canManageProjectByID(req, getRelationID(fileEntry.project))
}

export async function fileRevisionReadAccess({ req }: AccessArgs): Promise<boolean | Where> {
  const { user, payload } = req

  if (isSuperAdmin({ req })) return true

  if (!user) {
    // 3-level deep join: fileEntry → project → group
    return { 'fileEntry.project.group.title': { equals: 'public' } }
  }

  const adminGroupIds = await getAdminGroupIds(user, payload)
  return buildGroupReadWhere('fileEntry.project.group', user.id, adminGroupIds)
}

export async function fileRevisionCreateAccess({ req, data }: AccessArgs): Promise<boolean> {
  if (isSuperAdmin({ req })) return true
  if (!req.user) return false

  const fileEntryId = getRelationID(data?.fileEntry)
  if (!fileEntryId) return false

  const fileEntry = await req.payload.findByID({
    collection: 'file-entry',
    id: fileEntryId,
    depth: 0,
    overrideAccess: true,
  })
  if (!fileEntry) return false

  return canManageProjectByID(req, getRelationID(fileEntry.project))
}

export async function fileRevisionUpdateAccess(args: AccessArgs): Promise<boolean | Where> {
  const { req, id } = args

  if (isSuperAdmin({ req })) return true
  if (!req.user) return false

  if (id) return canManageFileRevisionByID(req, id)

  const adminGroupIds = await getAdminGroupIds(req.user, req.payload)
  return buildGroupWriteWhere('fileEntry.project.group', req.user.id, adminGroupIds)
}

export async function fileRevisionDeleteAccess(args: AccessArgs): Promise<boolean | Where> {
  const { req, id } = args

  if (isSuperAdmin({ req })) return true
  if (!req.user) return false

  if (id) return canManageFileRevisionByID(req, id)

  const adminGroupIds = await getAdminGroupIds(req.user, req.payload)
  return buildGroupWriteWhere('fileEntry.project.group', req.user.id, adminGroupIds)
}
