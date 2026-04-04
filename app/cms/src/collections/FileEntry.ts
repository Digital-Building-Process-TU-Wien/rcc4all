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

const fileTypeOptions = [
  { label: 'IFC', value: 'IFC' },
  { label: 'IDS', value: 'IDS' },
  { label: 'CSV', value: 'CSV' },
  { label: 'Image', value: 'Image' },
  { label: 'Workflow JSON', value: 'Workflow JSON' },
]

export const FileEntry: CollectionConfig = {
  slug: 'file-entry',
  access: {
    read: fileEntryReadAccess,
    create: fileEntryCreateAccess,
    update: fileEntryUpdateAccess,
    delete: fileEntryDeleteAccess,
  },
  fields: [
    {
      name: 'project',
      type: 'relationship',
      relationTo: 'projects',
      required: true,
      index: true,
    },
    {
      name: 'entryKey',
      type: 'text',
      required: true,
      index: true,
    },
    {
      name: 'type',
      type: 'select',
      required: true,
      options: fileTypeOptions,
    },
    {
      name: 'meta',
      type: 'json',
    },
    {
      name: 'latestRevision',
      type: 'relationship',
      relationTo: 'file-revisions',
      index: true,
    },
  ],
  timestamps: true,
}

async function canManageFileEntryByID(
  req: Parameters<Access>[0]['req'],
  id: number | string,
): Promise<boolean> {
  const entry = await req.payload.findByID({
    collection: 'file-entry',
    id,
    depth: 0,
    overrideAccess: true,
  })
  if (!entry) return false
  return canManageProjectByID(req, getRelationID(entry.project))
}

export async function fileEntryReadAccess({ req }: AccessArgs): Promise<boolean | Where> {
  const { user, payload } = req

  if (isSuperAdmin({ req })) return true

  if (!user) {
    return { 'project.group.title': { equals: 'public' } }
  }

  const adminGroupIds = await getAdminGroupIds(user, payload)
  return buildGroupReadWhere('project.group', user.id, adminGroupIds)
}

export async function fileEntryCreateAccess({ req, data }: AccessArgs): Promise<boolean> {
  if (isSuperAdmin({ req })) return true
  if (!req.user) return false

  return canManageProjectByID(req, getRelationID(data?.project))
}

export async function fileEntryUpdateAccess(args: AccessArgs): Promise<boolean | Where> {
  const { req, id } = args

  if (isSuperAdmin({ req })) return true
  if (!req.user) return false

  if (id) return canManageFileEntryByID(req, id)

  const adminGroupIds = await getAdminGroupIds(req.user, req.payload)
  return buildGroupWriteWhere('project.group', req.user.id, adminGroupIds)
}

export async function fileEntryDeleteAccess(args: AccessArgs): Promise<boolean | Where> {
  const { req, id } = args

  if (isSuperAdmin({ req })) return true
  if (!req.user) return false

  if (id) return canManageFileEntryByID(req, id)

  const adminGroupIds = await getAdminGroupIds(req.user, req.payload)
  return buildGroupWriteWhere('project.group', req.user.id, adminGroupIds)
}
