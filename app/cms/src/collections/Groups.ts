import type { Access, CollectionConfig, Where } from 'payload'

import { getAdminGroupIds } from '../helper/access'

type AccessArgs = Parameters<Access>[0]

export const Groups: CollectionConfig = {
  slug: 'groups',
  admin: {
    useAsTitle: 'title',
  },
  access: {
    read: groupReadAccess,
    create: groupWriteAccess,
    update: groupWriteAccess,
    delete: groupWriteAccess,
  },
  fields: [
    {
      name: 'title',
      type: 'text',
      required: true,
      index: true,
    },
    {
      name: 'parent',
      type: 'relationship',
      relationTo: 'groups',
    },
    {
      name: 'admins',
      type: 'relationship',
      relationTo: 'users',
      hasMany: true,
    },
    {
      name: 'users',
      type: 'relationship',
      relationTo: 'users',
      hasMany: true,
    },
  ],
  timestamps: true,
}

export async function groupReadAccess({ req }: AccessArgs): Promise<boolean | Where> {
  const { user, payload } = req
  if (user?.roles?.includes('super-admin')) return true

  if (!user) {
    // Allow seeing public group?
    return { title: { equals: 'public' } }
  }

  const adminGroupIds = await getAdminGroupIds(user, payload)

  return {
    or: [
      { users: { contains: user.id } },
      { id: { in: adminGroupIds } },
      { title: { equals: 'public' } },
    ],
  }
}

export async function groupWriteAccess({ req, id, data }: AccessArgs) {
  const { user, payload } = req
  if (user?.roles?.includes('super-admin')) return true

  if (!user) return false

  const adminGroupIds = await getAdminGroupIds(user, payload)

  if (id) {
    return adminGroupIds.includes(Number(id))
  }

  if (data && data.parent) {
    return adminGroupIds.includes(data.parent as number)
  }

  return false // Only super admin creates root groups
}
