import type { Block } from 'payload'

import { CardBlock } from './CardBlock'

export const PageSectionBlock: Block = {
  slug: 'page-section',
  interfaceName: 'PageSectionBlock',
  labels: {
    singular: 'Page section',
    plural: 'Page sections',
  },
  admin: {
    group: 'Layout',
  },
  fields: [
    {
      name: 'anchor',
      type: 'text',
      index: true,
    },
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
    },
    {
      name: 'display',
      type: 'select',
      required: true,
      defaultValue: 'grid',
      options: [
        {
          label: 'Grid',
          value: 'grid',
        },
        {
          label: 'Rows',
          value: 'rows',
        },
      ],
    },
    {
      name: 'cards',
      type: 'blocks',
      minRows: 1,
      blocks: [CardBlock],
      admin: {
        initCollapsed: true,
      },
    },
  ],
}
