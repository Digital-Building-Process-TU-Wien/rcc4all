import { getPayload } from 'payload'
import config from '@/payload.config'
import { describe, it, beforeAll, expect } from 'vitest'
import type { Payload } from 'payload'
import { reqAsUser, isAccessError } from './helpers/testFixtures'

/**
 * Focused fixtures for user access tests.
 *
 * Group structure:
 *   managedGroup  →  admins: [groupAdmin]  |  users: [managedUser]
 *   otherGroup    →  admins: [anotherGroupAdmin]
 *
 * Actors:
 *   superAdmin       – role: super-admin
 *   groupAdmin       – role: group-admin, admins managedGroup
 *   anotherGroupAdmin – role: group-admin, admins a different group
 *   managedUser      – role: user, member of managedGroup
 *   outsideUser      – role: user, no shared groups
 */

interface UserFixtures {
  superAdminId: number
  groupAdminId: number
  anotherGroupAdminId: number
  managedUserId: number
  outsideUserId: number
  managedGroupId: number
}

let payload: Payload
let f: UserFixtures

describe('User Collection Access Control', () => {
  beforeAll(async () => {
    const payloadConfig = await config
    payload = await getPayload({ config: payloadConfig, key: 'user-access' })

    const superAdmin = await payload.create({
      collection: 'users',
      data: {
        name: 'Super Admin',
        email: 'ua-super@test.com',
        password: 'password123',
        roles: ['super-admin'],
      },
    })

    const groupAdmin = await payload.create({
      collection: 'users',
      data: {
        name: 'Group Admin',
        email: 'ua-groupadmin@test.com',
        password: 'password123',
        roles: ['group-admin'],
      },
    })

    const anotherGroupAdmin = await payload.create({
      collection: 'users',
      data: {
        name: 'Another Group Admin',
        email: 'ua-anothergroupadmin@test.com',
        password: 'password123',
        roles: ['group-admin'],
      },
    })

    const managedUser = await payload.create({
      collection: 'users',
      data: {
        name: 'Managed User',
        email: 'ua-managed@test.com',
        password: 'password123',
        roles: ['user'],
      },
    })

    const outsideUser = await payload.create({
      collection: 'users',
      data: {
        name: 'Outside User',
        email: 'ua-outside@test.com',
        password: 'password123',
        roles: ['user'],
      },
    })

    const managedGroup = await payload.create({
      collection: 'groups',
      data: {
        title: 'Managed Group',
        admins: [groupAdmin.id],
        users: [managedUser.id],
      },
    })

    // otherGroup exists only to give anotherGroupAdmin a group to admin
    await payload.create({
      collection: 'groups',
      data: {
        title: 'Other Group',
        admins: [anotherGroupAdmin.id],
      },
    })

    f = {
      superAdminId: superAdmin.id,
      groupAdminId: groupAdmin.id,
      anotherGroupAdminId: anotherGroupAdmin.id,
      managedUserId: managedUser.id,
      outsideUserId: outsideUser.id,
      managedGroupId: managedGroup.id,
    }
  })

  // ---------------------------------------------------------------------------
  // CREATE
  // ---------------------------------------------------------------------------

  describe('create', () => {
    it('super admin can create a user', async () => {
      const superAdmin = await payload.findByID({ collection: 'users', id: f.superAdminId })
      const created = await payload.create({
        collection: 'users',
        data: {
          name: 'Created by SA',
          email: 'created-by-sa@test.com',
          password: 'password123',
          roles: ['user'],
        },
        req: reqAsUser(payload, superAdmin),
        overrideAccess: false,
      })
      expect(created.id).toBeDefined()
    })

    it('group admin can create a user', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      const created = await payload.create({
        collection: 'users',
        data: {
          name: 'Created by GA',
          email: 'created-by-ga@test.com',
          password: 'password123',
          roles: ['user'],
        },
        req: reqAsUser(payload, groupAdmin),
        overrideAccess: false,
      })
      expect(created.id).toBeDefined()
    })

    it('regular user cannot create a user', async () => {
      const managedUser = await payload.findByID({ collection: 'users', id: f.managedUserId })
      try {
        await payload.create({
          collection: 'users',
          data: {
            name: 'Sneaky New User',
            email: 'sneaky@test.com',
            password: 'password123',
            roles: ['user'],
          },
          req: reqAsUser(payload, managedUser),
          overrideAccess: false,
        })
        expect.fail('Regular user was able to create a user')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('unauthenticated request cannot create a user', async () => {
      try {
        await payload.create({
          collection: 'users',
          data: {
            name: 'Anon New User',
            email: 'anon@test.com',
            password: 'password123',
            roles: ['user'],
          },
          req: reqAsUser(payload, null),
          overrideAccess: false,
        })
        expect.fail('Unauthenticated request was able to create a user')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })
  })

  // ---------------------------------------------------------------------------
  // UPDATE
  // ---------------------------------------------------------------------------

  describe('update', () => {
    it('super admin can update a regular user', async () => {
      const superAdmin = await payload.findByID({ collection: 'users', id: f.superAdminId })
      const updated = await payload.update({
        collection: 'users',
        id: f.managedUserId,
        data: { name: 'Managed User (SA update)' },
        req: reqAsUser(payload, superAdmin),
        overrideAccess: false,
      })
      expect(updated.name).toBe('Managed User (SA update)')
    })

    it('super admin can update another super admin', async () => {
      const superAdmin = await payload.findByID({ collection: 'users', id: f.superAdminId })
      const updated = await payload.update({
        collection: 'users',
        id: f.superAdminId,
        data: { name: 'Super Admin (self SA update)' },
        req: reqAsUser(payload, superAdmin),
        overrideAccess: false,
      })
      expect(updated.name).toBe('Super Admin (self SA update)')
    })

    it('super admin can update a group admin', async () => {
      const superAdmin = await payload.findByID({ collection: 'users', id: f.superAdminId })
      const updated = await payload.update({
        collection: 'users',
        id: f.groupAdminId,
        data: { name: 'Group Admin (SA update)' },
        req: reqAsUser(payload, superAdmin),
        overrideAccess: false,
      })
      expect(updated.name).toBe('Group Admin (SA update)')
    })

    it('group admin can update a managed user in their group', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      const updated = await payload.update({
        collection: 'users',
        id: f.managedUserId,
        data: { name: 'Managed User (GA update)' },
        req: reqAsUser(payload, groupAdmin),
        overrideAccess: false,
      })
      expect(updated.name).toBe('Managed User (GA update)')
    })

    it('group admin can update themselves', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      const updated = await payload.update({
        collection: 'users',
        id: f.groupAdminId,
        data: { name: 'Group Admin (self update)' },
        req: reqAsUser(payload, groupAdmin),
        overrideAccess: false,
      })
      expect(updated.name).toBe('Group Admin (self update)')
    })

    it('group admin cannot update a super admin', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      try {
        await payload.update({
          collection: 'users',
          id: f.superAdminId,
          data: { name: 'Super Admin (GA attack)' },
          req: reqAsUser(payload, groupAdmin),
          overrideAccess: false,
        })
        expect.fail('Group admin was able to update a super admin')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('group admin cannot update another group admin', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      try {
        await payload.update({
          collection: 'users',
          id: f.anotherGroupAdminId,
          data: { name: 'Another Group Admin (GA attack)' },
          req: reqAsUser(payload, groupAdmin),
          overrideAccess: false,
        })
        expect.fail('Group admin was able to update another group admin')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('group admin cannot update a user outside their group', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      try {
        await payload.update({
          collection: 'users',
          id: f.outsideUserId,
          data: { name: 'Outside User (GA attack)' },
          req: reqAsUser(payload, groupAdmin),
          overrideAccess: false,
        })
        expect.fail('Group admin was able to update a user outside their group')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('regular user can update themselves', async () => {
      const managedUser = await payload.findByID({ collection: 'users', id: f.managedUserId })
      const updated = await payload.update({
        collection: 'users',
        id: f.managedUserId,
        data: { name: 'Managed User (self update)' },
        req: reqAsUser(payload, managedUser),
        overrideAccess: false,
      })
      expect(updated.name).toBe('Managed User (self update)')
    })

    it('regular user cannot update another user', async () => {
      const managedUser = await payload.findByID({ collection: 'users', id: f.managedUserId })
      try {
        await payload.update({
          collection: 'users',
          id: f.outsideUserId,
          data: { name: 'Outside User (regular attack)' },
          req: reqAsUser(payload, managedUser),
          overrideAccess: false,
        })
        expect.fail('Regular user was able to update another user')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })
  })

  // ---------------------------------------------------------------------------
  // PRIVILEGE ESCALATION
  // ---------------------------------------------------------------------------

  describe('privilege escalation', () => {
    it('group admin cannot escalate a managed user role to super-admin', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      try {
        await payload.update({
          collection: 'users',
          id: f.managedUserId,
          data: { roles: ['super-admin'] },
          req: reqAsUser(payload, groupAdmin),
          overrideAccess: false,
        })
        expect.fail('Group admin was able to escalate a user to super-admin')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('group admin can promote a managed user (in their group) to group-admin', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      const result = await payload.update({
        collection: 'users',
        id: f.managedUserId,
        data: { roles: ['group-admin'] },
        req: reqAsUser(payload, groupAdmin),
        overrideAccess: false,
      })
      expect(result.roles).toContain('group-admin')
      // restore so subsequent tests see managedUser as a plain user
      await payload.update({
        collection: 'users',
        id: f.managedUserId,
        data: { roles: ['user'] },
        overrideAccess: true,
      })
    })

    it('group admin cannot promote a user outside their group to group-admin', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      try {
        await payload.update({
          collection: 'users',
          id: f.outsideUserId,
          data: { roles: ['group-admin'] },
          req: reqAsUser(payload, groupAdmin),
          overrideAccess: false,
        })
        expect.fail('Group admin was able to promote a user outside their group to group-admin')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('regular user cannot escalate their own roles to super-admin', async () => {
      const managedUser = await payload.findByID({ collection: 'users', id: f.managedUserId })
      const result = await payload.update({
        collection: 'users',
        id: f.managedUserId,
        data: { roles: ['super-admin'] },
        req: reqAsUser(payload, managedUser),
        overrideAccess: false,
      })
      expect(result.roles).not.toContain('super-admin')
    })

    it('regular user cannot escalate their own roles to group-admin', async () => {
      const managedUser = await payload.findByID({ collection: 'users', id: f.managedUserId })
      const result = await payload.update({
        collection: 'users',
        id: f.managedUserId,
        data: { roles: ['group-admin'] },
        req: reqAsUser(payload, managedUser),
        overrideAccess: false,
      })
      expect(result.roles).not.toContain('group-admin')
    })

    it('group admin cannot create a user with super-admin role', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      try {
        await payload.create({
          collection: 'users',
          data: {
            name: 'Escalation Attempt',
            email: 'escalation-sa@test.com',
            password: 'password123',
            roles: ['super-admin'],
          },
          req: reqAsUser(payload, groupAdmin),
          overrideAccess: false,
        })
        expect.fail('Group admin was able to create a user with super-admin role')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('group admin can create a user with group-admin role', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      const created = await payload.create({
        collection: 'users',
        data: {
          name: 'GA Created Group Admin',
          email: 'escalation-ga@test.com',
          password: 'password123',
          roles: ['group-admin'],
        },
        req: reqAsUser(payload, groupAdmin),
        overrideAccess: false,
      })
      expect(created.roles).toContain('group-admin')
    })

    it('super admin can change a user role to group-admin', async () => {
      const superAdmin = await payload.findByID({ collection: 'users', id: f.superAdminId })
      const result = await payload.update({
        collection: 'users',
        id: f.managedUserId,
        data: { roles: ['group-admin'] },
        req: reqAsUser(payload, superAdmin),
        overrideAccess: false,
      })
      expect(result.roles).toContain('group-admin')
      // restore
      await payload.update({
        collection: 'users',
        id: f.managedUserId,
        data: { roles: ['user'] },
        overrideAccess: true,
      })
    })
  })

  // ---------------------------------------------------------------------------
  // DELETE
  // ---------------------------------------------------------------------------

  describe('delete', () => {
    it('super admin can delete a user', async () => {
      // Create a disposable user to delete
      const disposable = await payload.create({
        collection: 'users',
        data: {
          name: 'Disposable User',
          email: 'disposable@test.com',
          password: 'password123',
          roles: ['user'],
        },
      })

      const superAdmin = await payload.findByID({ collection: 'users', id: f.superAdminId })
      const deleted = await payload.delete({
        collection: 'users',
        id: disposable.id,
        req: reqAsUser(payload, superAdmin),
        overrideAccess: false,
      })

      expect(deleted.id).toBe(disposable.id)
    })

    it('group admin cannot delete a user', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      try {
        await payload.delete({
          collection: 'users',
          id: f.managedUserId,
          req: reqAsUser(payload, groupAdmin),
          overrideAccess: false,
        })
        expect.fail('Group admin was able to delete a user')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('group admin cannot delete another group admin', async () => {
      const groupAdmin = await payload.findByID({ collection: 'users', id: f.groupAdminId })
      try {
        await payload.delete({
          collection: 'users',
          id: f.anotherGroupAdminId,
          req: reqAsUser(payload, groupAdmin),
          overrideAccess: false,
        })
        expect.fail('Group admin was able to delete another group admin')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('regular user cannot delete themselves', async () => {
      const managedUser = await payload.findByID({ collection: 'users', id: f.managedUserId })
      try {
        await payload.delete({
          collection: 'users',
          id: f.managedUserId,
          req: reqAsUser(payload, managedUser),
          overrideAccess: false,
        })
        expect.fail('Regular user was able to delete themselves')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })

    it('regular user cannot delete another user', async () => {
      const managedUser = await payload.findByID({ collection: 'users', id: f.managedUserId })
      try {
        await payload.delete({
          collection: 'users',
          id: f.outsideUserId,
          req: reqAsUser(payload, managedUser),
          overrideAccess: false,
        })
        expect.fail('Regular user was able to delete another user')
      } catch (e: any) {
        if (!isAccessError(e)) throw e
      }
    })
  })
})
