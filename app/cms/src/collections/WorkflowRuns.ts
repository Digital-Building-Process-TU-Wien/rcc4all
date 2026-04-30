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
type BeforeValidateArgs = Parameters<
  NonNullable<NonNullable<CollectionConfig['hooks']>['beforeValidate']>[number]
>[0]

async function canManageWorkflowRunByID({ req, id }: AccessArgs): Promise<boolean> {
  const { payload } = req

  if (!id) return false

  const workflowRun = await payload.findByID({
    collection: 'workflow-runs',
    id,
    depth: 0,
    overrideAccess: true,
  })

  if (!workflowRun) return false

  const projectId = getRelationID(workflowRun.project)
  if (!projectId) return false

  return canManageProjectByID(req, projectId)
}

async function getWorkflowRunWriteWhere({ req }: AccessArgs): Promise<Where | false> {
  const { user, payload } = req

  if (!user) return false

  const adminGroupIds = await getAdminGroupIds(user, payload)
  return buildGroupWriteWhere('project.group', user.id, adminGroupIds, 'project.creator')
}

export const WorkflowRuns: CollectionConfig = {
  slug: 'workflow-runs',
  admin: {
    useAsTitle: 'name',
  },
  access: {
    read: workflowRunReadAccess,
    create: workflowRunCreateAccess,
    update: workflowRunUpdateAccess,
    delete: workflowRunDeleteAccess,
  },
  fields: [
    {
      name: 'name',
      type: 'text',
      required: true,
      index: true,
    },
    {
      name: 'timestamp',
      type: 'date',
      required: true,
      defaultValue: () => new Date().toISOString(),
      index: true,
    },
    {
      name: 'project',
      type: 'relationship',
      relationTo: 'projects',
      required: true,
      index: true,
    },
    {
      name: 'inputFiles',
      type: 'relationship',
      relationTo: 'file-revisions',
      hasMany: true,
    },
    {
      name: 'outputFiles',
      type: 'relationship',
      relationTo: 'file-revisions',
      hasMany: true,
    },
  ],
  hooks: {
    beforeValidate: [enforceProjectScopedFiles],
  },
  timestamps: true,
}

export async function workflowRunReadAccess({ req }: AccessArgs): Promise<boolean | Where> {
  const { user, payload } = req

  if (isSuperAdmin({ req })) return true

  if (!user) {
    return { 'project.group.title': { equals: 'public' } }
  }

  const adminGroupIds = await getAdminGroupIds(user, payload)
  return buildGroupReadWhere('project.group', user.id, adminGroupIds)
}

export async function workflowRunCreateAccess({ req, data }: AccessArgs) {
  if (isSuperAdmin({ req })) return true

  const projectId = getRelationID(data?.project)
  if (!projectId) return false

  return canManageProjectByID(req, projectId)
}

export async function workflowRunUpdateAccess(args: AccessArgs): Promise<boolean | Where> {
  const { req, id } = args

  if (isSuperAdmin({ req })) return true

  if (!req.user) return false

  if (id) {
    return canManageWorkflowRunByID(args)
  }

  return getWorkflowRunWriteWhere(args)
}

export async function workflowRunDeleteAccess(args: AccessArgs): Promise<boolean | Where> {
  const { req, id } = args

  if (isSuperAdmin({ req })) return true

  if (!req.user) return false

  if (id) {
    return canManageWorkflowRunByID(args)
  }

  return getWorkflowRunWriteWhere(args)
}

async function enforceProjectScopedFiles({ data, req, originalDoc }: BeforeValidateArgs) {
  const projectValue = data?.project ?? originalDoc?.project
  const projectId = getRelationID(projectValue)

  if (!projectId) {
    return data
  }

  const inputIds = (data?.inputFiles ?? originalDoc?.inputFiles ?? [])
    .map(getRelationID)
    .filter((value: number | null): value is number => value !== null)
  const outputIds = (data?.outputFiles ?? originalDoc?.outputFiles ?? [])
    .map(getRelationID)
    .filter((value: number | null): value is number => value !== null)

  const fileIds = Array.from(new Set([...inputIds, ...outputIds]))

  if (!fileIds.length) {
    return data
  }

  const revisions = await req.payload.find({
    collection: 'file-revisions',
    where: { id: { in: fileIds } },
    depth: 1,
    limit: fileIds.length,
    overrideAccess: true,
    req,
  })

  const mismatchedRevision = revisions.docs.find((revision) => {
    const fileEntryId = getRelationID(revision.fileEntry)
    if (!fileEntryId) return true

    const fileEntry =
      typeof revision.fileEntry === 'object' && revision.fileEntry !== null
        ? revision.fileEntry
        : null

    if (!fileEntry) return true

    const entryProjectId = getRelationID(fileEntry.project)
    return entryProjectId !== projectId
  })

  if (mismatchedRevision) {
    throw new Error('All workflow run files must belong to the selected project.')
  }

  return data
}