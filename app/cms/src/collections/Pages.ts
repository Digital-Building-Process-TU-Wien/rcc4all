import type { Access, CollectionConfig } from 'payload'

import { PageSectionBlock } from '../blocks/PageSectionBlock'
import { isSuperAdmin } from '../helper/access'

type AccessArgs = Parameters<Access>[0]

export const Pages: CollectionConfig = {
  slug: 'pages',
  admin: {
    useAsTitle: 'slug',
  },
  access: {
    read: pageReadAccess,
    create: pageWriteAccess,
    update: pageWriteAccess,
    delete: pageWriteAccess,
  },
  fields: [
    {
      name: 'slug',
      type: 'text',
      required: true,
      unique: true,
      index: true,
    },
    {
      name: 'title',
      type: 'text',
      required: true,
      localized: true,
    },
    {
      name: 'hero',
      type: 'group',
      localized: true,
      fields: [
        {
          name: 'headline',
          type: 'text',
        },
        {
          name: 'title',
          type: 'text',
          required: true,
        },
        {
          name: 'description',
          type: 'textarea',
          required: true,
        },
        {
          name: 'badges',
          type: 'array',
          maxRows: 4,
          fields: [
            {
              name: 'label',
              type: 'text',
              required: true,
            },
          ],
        },
        {
          name: 'facts',
          type: 'array',
          maxRows: 4,
          fields: [
            {
              name: 'label',
              type: 'text',
              required: true,
            },
            {
              name: 'value',
              type: 'textarea',
              required: true,
            },
          ],
        },
        {
          name: 'primaryLink',
          type: 'group',
          fields: [
            {
              name: 'label',
              type: 'text',
            },
            {
              name: 'to',
              type: 'text',
            },
          ],
        },
        {
          name: 'secondaryLink',
          type: 'group',
          fields: [
            {
              name: 'label',
              type: 'text',
            },
            {
              name: 'to',
              type: 'text',
            },
          ],
        },
      ],
    },
    {
      name: 'layout',
      type: 'blocks',
      localized: true,
      minRows: 1,
      blocks: [PageSectionBlock],
      admin: {
        initCollapsed: true,
      },
    },
  ],
  timestamps: true,
}

export function pageReadAccess(): boolean {
  return true
}

export function pageWriteAccess({ req }: AccessArgs): boolean {
  return isSuperAdmin({ req })
}
