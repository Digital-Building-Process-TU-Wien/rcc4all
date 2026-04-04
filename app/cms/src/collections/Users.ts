import type { Access, CollectionConfig, Where } from 'payload'

import { getRelationID, isGroupAdmin, isSuperAdmin } from '../helper/access'

type AccessArgs = Parameters<Access>[0]

export const Users: CollectionConfig = {
  slug: 'users',
  admin: {
    useAsTitle: 'email',
  },
  auth: true,
  access: {
    read: userReadAccess,
    create: (req) => isSuperAdmin(req) || isGroupAdmin(req),
    update: userUpdateAccess,
    delete: userDeleteAccess,
  },
  fields: [
    {
      name: 'name',
      type: 'text',
      required: true,
    },
    {
      name: 'roles',
      type: 'select',
      hasMany: true,
      options: ['super-admin', 'group-admin', 'user'],
      defaultValue: ['user'],
      required: true,
      saveToJWT: true,
      access: {
        create: ({ req }) => isSuperAdmin({ req }) || isGroupAdmin({ req }),
        update: ({ req }) => isSuperAdmin({ req }) || isGroupAdmin({ req }),
      },
    },
  ],
  hooks: {
    beforeChange: [
      ({ data, req }) => {
        if (
          Array.isArray(data.roles) &&
          data.roles.includes('super-admin') &&
          req.user &&
          !isSuperAdmin({ req })
        ) {
          throw new Error('Forbidden: Only super-admins can assign the super-admin role')
        }
        return data
      },
    ],
  },
}

// Any authenticated user who shares at least one group with the target user can read their profile.
export async function userReadAccess({ req }: AccessArgs): Promise<boolean | Where> {
  const { user, payload } = req

  if (isSuperAdmin({ req })) return true
  if (!user) return false

  // Find all groups the current user belongs to (as member or admin).
  const groups = await payload.find({
    collection: 'groups',
    where: { or: [{ users: { contains: user.id } }, { admins: { contains: user.id } }] },
    depth: 1,
    limit: 1000,
    overrideAccess: true,
  })

  const visibleUserIds = new Set<number>([user.id])
  for (const group of groups.docs) {
    const members = (group.users ?? []) as unknown[]
    const admins = (group.admins ?? []) as unknown[]
    for (const u of [...members, ...admins]) {
      const user_id = getRelationID(u)
      if (user_id !== null) visibleUserIds.add(user_id)
    }
  }

  return { id: { in: [...visibleUserIds] } }
}

// Users can update their own profile; super-admins can update anyone.
// Group admins can update users in their groups as long as the target is not a super-admin or group-admin.
export async function userUpdateAccess({ req, id }: AccessArgs): Promise<boolean | Where> {
  if (isSuperAdmin({ req })) return true
  if (!req.user) return false

  const { user, payload } = req

  if (id && Number(id) === user.id) return true

  if (isGroupAdmin({ req })) {
    if (id) {
      const targetUser = await payload.findByID({
        collection: 'users',
        id,
        overrideAccess: true,
      })
      const targetRoles = (targetUser?.roles ?? []) as string[]
      if (targetRoles.includes('super-admin') || targetRoles.includes('group-admin')) return false

      const groups = await payload.find({
        collection: 'groups',
        where: {
          and: [{ admins: { contains: user.id } }, { users: { contains: Number(id) } }],
        },
        limit: 1,
        overrideAccess: true,
      })
      return groups.totalDocs > 0
    }

    // No id: build a Where constraint for group members who are not privileged
    const adminGroups = await payload.find({
      collection: 'groups',
      where: { admins: { contains: user.id } },
      depth: 1,
      limit: 1000,
      overrideAccess: true,
    })

    const updatableUserIds = new Set<number>([user.id])
    for (const group of adminGroups.docs) {
      const members = (group.users ?? []) as unknown[]
      for (const u of members) {
        const uid = getRelationID(u)
        if (uid !== null) updatableUserIds.add(uid)
      }
    }

    return {
      and: [
        { id: { in: [...updatableUserIds] } },
        { roles: { not_in: ['super-admin', 'group-admin'] } },
      ],
    }
  }

  return { id: { equals: user.id } }
}

// Only super-admins may delete user accounts.
export function userDeleteAccess({ req }: AccessArgs): boolean {
  return isSuperAdmin({ req })
}
