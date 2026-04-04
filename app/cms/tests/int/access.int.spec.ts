import { getPayload } from 'payload'
import config from '@/payload.config'
import { describe, it, beforeAll, expect } from 'vitest'
import type { Payload } from 'payload'
import { isAccessError, reqAsUser } from './helpers/testFixtures'

let payload: Payload

let rootGroupId: number
let childGroupId: number
let publicGroupId: number

let superAdminId: number
let rootAdminId: number
let unrelatedAdminId: number
let regularUserId: number
let strangerUserId: number

let childProjectID: number
let publicProjectID: number
let ownerProjectID: number

describe('Access Control Integration Tests', () => {
  beforeAll(async () => {
    const payloadConfig = await config
    payload = await getPayload({ config: payloadConfig, key: 'access' })

    // 1. Create Users
    const superAdmin = await payload.create({
      collection: 'users',
      data: {
        name: 'Super Admin',
        email: 'super-admin@test.com',
        password: 'password123',
        roles: ['super-admin'],
      },
    })
    superAdminId = superAdmin.id

    const rootAdmin = await payload.create({
      collection: 'users',
      data: {
        name: 'Root Admin',
        email: 'root-admin@test.com',
        password: 'password123',
        roles: ['group-admin'],
      },
    })
    rootAdminId = rootAdmin.id

    const unrelatedAdmin = await payload.create({
      collection: 'users',
      data: {
        name: 'Unrelated Admin',
        email: 'unrelated-admin@test.com',
        password: 'password123',
        roles: ['group-admin'],
      },
    })
    unrelatedAdminId = unrelatedAdmin.id

    const regularUser = await payload.create({
      collection: 'users',
      data: {
        name: 'Regular User',
        email: 'regular-user@test.com',
        password: 'password123',
        roles: ['user'],
      },
    })
    regularUserId = regularUser.id

    const strangerUser = await payload.create({
      collection: 'users',
      data: {
        name: 'Stranger User',
        email: 'stranger-user@test.com',
        password: 'password123',
        roles: ['user'],
      },
    })
    strangerUserId = strangerUser.id

    // 2. Create Groups Hierarchy
    const rootGroup = await payload.create({
      collection: 'groups',
      data: {
        title: 'Root Group',
        admins: [rootAdminId],
      },
    })
    rootGroupId = rootGroup.id

    const childGroup = await payload.create({
      collection: 'groups',
      data: {
        title: 'Child Group',
        parent: rootGroupId,
        users: [regularUserId],
      },
    })
    childGroupId = childGroup.id

    const publicGroup = await payload.create({
      collection: 'groups',
      data: {
        title: 'public',
      },
    })
    publicGroupId = publicGroup.id

    // 3. Create Projects
    const childProject = await payload.create({
      collection: 'projects',
      data: {
        title: 'Child Project',
        group: childGroupId,
        creator: rootAdminId,
      },
      overrideAccess: true,
    })
    childProjectID = childProject.id

    const publicProject = await payload.create({
      collection: 'projects',
      data: {
        title: 'Public Project',
        group: publicGroupId,
        creator: superAdminId,
      },
      overrideAccess: true,
    })
    publicProjectID = publicProject.id

    const ownerProject = await payload.create({
      collection: 'projects',
      data: {
        title: 'Owner Project',
        group: childGroupId,
        creator: regularUserId,
      },
      overrideAccess: true,
    })
    ownerProjectID = ownerProject.id
  })

  // --- Tests ---

  it('Inheritance: Root Group Admin should be able to update Child Group', async () => {
    const rootAdmin = await payload.findByID({ collection: 'users', id: rootAdminId })
    try {
      const updated = await payload.update({
        collection: 'groups',
        id: childGroupId,
        data: { title: 'Child Group Updated by Root' },
        req: reqAsUser(payload, rootAdmin),
        overrideAccess: false,
      })
      expect(updated.title).toBe('Child Group Updated by Root')
    } catch (e: any) {
      throw new Error(`Access denied or error: ${e.message}`)
    }
  })

  it('Isolation: Unrelated Group Admin should NOT be able to update Child Group', async () => {
    const unrelatedAdmin = await payload.findByID({ collection: 'users', id: unrelatedAdminId })

    try {
      await payload.update({
        collection: 'groups',
        id: childGroupId,
        data: { title: 'Child Group Manipulated' },
        req: reqAsUser(payload, unrelatedAdmin),
        overrideAccess: false,
      })

      expect.fail('Unrelated admin was able to update child group')
    } catch (e: any) {
      // Expected Forbidden or Access Denied
      // We check if it is explicitly a forbidden error to avoid masking DB errors
      if (!isAccessError(e)) {
        throw e
      }
      expect(e.message).toBeDefined()
    }

    const unchanged = await payload.findByID({
      collection: 'groups',
      id: childGroupId,
      overrideAccess: true,
    })
    expect(unchanged.title).not.toBe('Child Group Manipulated')
  })

  it('Scoping: Regular User should see project in their group', async () => {
    const regularUser = await payload.findByID({ collection: 'users', id: regularUserId })

    const results = await payload.find({
      collection: 'projects',
      where: {
        id: { equals: childProjectID },
      },
      req: reqAsUser(payload, regularUser),
      overrideAccess: false,
    })

    expect(results.totalDocs).toBe(1)
  })

  it('Scoping: Stranger User should NOT see project in child group', async () => {
    const strangerUser = await payload.findByID({ collection: 'users', id: strangerUserId })

    const results = await payload.find({
      collection: 'projects',
      where: {
        id: { equals: childProjectID },
      },
      req: reqAsUser(payload, strangerUser),
      overrideAccess: false,
    })

    expect(results.totalDocs).toBe(0)
  })

  it('Public Access: Anonymous users should see public projects', async () => {
    const results = await payload.find({
      collection: 'projects',
      where: {
        id: { equals: publicProjectID },
      },
      req: reqAsUser(payload, null), // No user passed
      overrideAccess: false,
    })

    expect(results.totalDocs).toBe(1)
  })

  it('Authorization: Regular user should NOT update group', async () => {
    const regularUser = await payload.findByID({ collection: 'users', id: regularUserId })

    try {
      await payload.update({
        collection: 'groups',
        id: childGroupId,
        data: { title: 'Child Group Updated by Regular User' },
        req: reqAsUser(payload, regularUser),
        overrideAccess: false,
      })
      expect.fail('Regular user was able to update group')
    } catch (e: any) {
      if (!isAccessError(e)) throw e
    }
  })

  it('Authorization: Regular user should NOT update project', async () => {
    const regularUser = await payload.findByID({ collection: 'users', id: regularUserId })

    try {
      await payload.update({
        collection: 'projects',
        id: childProjectID,
        data: { title: 'Project Updated by Regular User' },
        req: reqAsUser(payload, regularUser),
        overrideAccess: false,
      })
      expect.fail('Regular user was able to update project')
    } catch (e: any) {
      if (!isAccessError(e)) throw e
    }
  })

  it('Soft Delete: Project owner should soft delete and restore own project', async () => {
    const regularUser = await payload.findByID({ collection: 'users', id: regularUserId })

    const softDeleted = await payload.update({
      collection: 'projects',
      id: ownerProjectID,
      data: { deletedAt: new Date().toISOString() },
      req: reqAsUser(payload, regularUser),
      overrideAccess: false,
    })

    expect(softDeleted.deletedAt).toBeTruthy()

    const hiddenInNormalFind = await payload.find({
      collection: 'projects',
      where: { id: { equals: ownerProjectID } },
      req: reqAsUser(payload, regularUser),
      overrideAccess: false,
    })

    expect(hiddenInNormalFind.totalDocs).toBe(0)

    const restored = await payload.update({
      collection: 'projects',
      id: ownerProjectID,
      data: { deletedAt: null },
      req: reqAsUser(payload, regularUser),
      overrideAccess: false,
      trash: true,
    })

    expect(restored.deletedAt).toBeFalsy()
  })

  it('Hard Delete: Group admin should NOT permanently delete a project', async () => {
    const rootAdmin = await payload.findByID({ collection: 'users', id: rootAdminId })

    try {
      await payload.delete({
        collection: 'projects',
        id: ownerProjectID,
        req: reqAsUser(payload, rootAdmin),
        overrideAccess: false,
      })

      expect.fail('Group admin was able to permanently delete a project')
    } catch (e: any) {
      if (!isAccessError(e)) throw e
    }
  })

  it('Hard Delete: Super admin should permanently delete a project', async () => {
    const superAdmin = await payload.findByID({ collection: 'users', id: superAdminId })

    const deleted = await payload.delete({
      collection: 'projects',
      id: ownerProjectID,
      req: reqAsUser(payload, superAdmin),
      overrideAccess: false,
    })

    expect(deleted.id).toBe(ownerProjectID)

    const afterDelete = await payload.find({
      collection: 'projects',
      where: { id: { equals: ownerProjectID } },
      overrideAccess: true,
      trash: true,
    })

    expect(afterDelete.totalDocs).toBe(0)
  })
})
