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

async function getProjectUpdateWhere({ req }: AccessArgs): Promise<Where | false> {
  const { user, payload } = req

  if (!user) return false

  const adminGroupIds = await getAdminGroupIds(user, payload)
  return buildGroupWriteWhere('group', user.id, adminGroupIds, 'creator')
}

export const Projects: CollectionConfig = {
  slug: 'projects',
  trash: true,
  admin: {
    useAsTitle: 'title',
  },
  access: {
    read: projectReadAccess,
    create: projectCreateAccess,
    update: projectUpdateAccess,
    delete: projectDeleteAccess,
  },
  fields: [
    {
      name: 'title',
      type: 'text',
      required: true,
      index: true,
    },
    {
      name: 'description',
      type: 'textarea',
    },
    {
      name: 'images',
      type: 'relationship',
      relationTo: 'file-revisions',
      hasMany: true,
    },
    {
      name: 'titleImage',
      type: 'relationship',
      relationTo: 'file-revisions',
    },
    {
      name: 'group',
      type: 'relationship',
      relationTo: 'groups',
      required: true,
      index: true,
    },
    {
      name: 'creator',
      type: 'relationship',
      relationTo: 'users',
    },
  ],
  timestamps: true,
}

export async function projectReadAccess({ req }: AccessArgs): Promise<boolean | Where> {
  const { user, payload } = req

  if (isSuperAdmin({ req })) return true

  if (!user) {
    return { 'group.title': { equals: 'public' } }
  }

  const adminGroupIds = await getAdminGroupIds(user, payload)
  return buildGroupReadWhere('group', user.id, adminGroupIds)
}

export async function projectCreateAccess({ req, data }: AccessArgs) {
  const { user, payload } = req

  if (isSuperAdmin({ req })) return true

  if (!user) return false

  const adminGroupIds = await getAdminGroupIds(user, payload)

  if (data?.group) {
    const groupId = getRelationID(data.group)
    return groupId !== null && adminGroupIds.includes(groupId)
  }

  return adminGroupIds.length > 0
}

export async function projectUpdateAccess(args: AccessArgs): Promise<boolean | Where> {
  const { req, id } = args

  if (isSuperAdmin({ req })) return true

  if (!req.user) return false

  if (id) {
    return canManageProjectByID(req, id)
  }

  return getProjectUpdateWhere(args)
}

export async function projectDeleteAccess(args: AccessArgs): Promise<boolean> {
  const { req, id } = args
  const { user } = req

  if (isSuperAdmin({ req })) return true

  if (!user) return false

  // Hard delete is a real DELETE operation (or targeted delete-by-id in Local API)
  // and must stay super-admin only.
  if (req.method === 'DELETE' || id) {
    return false
  }

  // Soft-delete protection inside update operations is additionally scoped by
  // `projectUpdateAccess`, which checks admin-group or owner permissions.
  return true
}
