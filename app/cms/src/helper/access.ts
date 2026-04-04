import type { Access, Payload, Where } from 'payload'
import type { User } from '../payload-types'

type AccessArgs = Parameters<Access>[0]

export function isAuthenticated({ req }: AccessArgs) {
  return Boolean(req.user)
}

export function isSuperAdmin({ req }: AccessArgs) {
  return Boolean(req.user?.roles?.includes('super-admin'))
}

export function isGroupAdmin({ req }: AccessArgs) {
  return Boolean(req.user?.roles?.includes('group-admin'))
}

// Helper to get all Group IDs a user is admin of (including descendants)
export async function getAdminGroupIds(
  user: User | null | undefined,
  payload: Payload,
): Promise<number[]> {
  if (!user) return []

  // 1. Find direct admin groups
  const directAdminGroups = await payload.find({
    collection: 'groups',
    where: { admins: { contains: user.id } },
    depth: 0,
    limit: 1000,
    overrideAccess: true,
  })

  let adminIds = directAdminGroups.docs.map((g) => g.id)

  // 2. Find descendants recursively
  let currentLevelIds = [...adminIds]
  while (currentLevelIds.length > 0) {
    const children = await payload.find({
      collection: 'groups',
      where: { parent: { in: currentLevelIds } },
      depth: 0,
      limit: 1000,
      overrideAccess: true,
      // select: { id: true },
    })
    const childIds = children.docs.map((g) => g.id).filter((id) => !adminIds.includes(id))

    if (childIds.length === 0) break

    adminIds = [...adminIds, ...childIds]
    currentLevelIds = childIds
  }
  return adminIds
}

// Extract a numeric ID from either a raw number or a populated relationship object.
export function getRelationID(value: unknown): number | null {
  if (typeof value === 'number') return value

  if (value && typeof value === 'object' && 'id' in value) {
    const relation = value as { id?: unknown }
    if (typeof relation.id === 'number') return relation.id
  }

  return null
}

// Returns true when the current user owns or is the group-admin of the given project.
export async function canManageProjectByID(
  req: Parameters<Access>[0]['req'],
  projectId: number | string | null | undefined,
): Promise<boolean> {
  const { user, payload } = req

  if (!user || !projectId) return false

  const project = await payload.findByID({
    collection: 'projects',
    id: projectId,
    depth: 0,
    overrideAccess: true,
    trash: true,
  })

  if (!project) return false

  const ownerId = getRelationID(project.creator)
  if (ownerId === user.id) return true

  const adminGroupIds = await getAdminGroupIds(user, payload)
  const projectGroupId = getRelationID(project.group)

  if (!projectGroupId) return false

  return adminGroupIds.includes(projectGroupId)
}

// Builds the standard triple-OR read Where for group-scoped collections.
// groupBasePath is the dot-path prefix to the group record, e.g. 'group', 'project.group'.
export function buildGroupReadWhere(
  groupBasePath: string,
  userId: number,
  adminGroupIds: number[],
): Where {
  return {
    or: [
      { [`${groupBasePath}.title`]: { equals: 'public' } },
      { [`${groupBasePath}.users`]: { contains: userId } },
      { [`${groupBasePath}.id`]: { in: adminGroupIds } },
    ],
  } as Where
}

// Builds the standard bulk-write Where for group-scoped collections.
// Optionally adds a creator-equality condition when creatorPath is provided.
export function buildGroupWriteWhere(
  groupBasePath: string,
  userId: number,
  adminGroupIds: number[],
  creatorPath?: string,
): Where {
  const conditions = [
    { [`${groupBasePath}.id`]: { in: adminGroupIds } },
    ...(creatorPath ? [{ [creatorPath]: { equals: userId } }] : []),
  ]
  return { or: conditions } as Where
}
