import type { Block } from 'payload'

export const CardBlock: Block = {
  slug: 'card',
  interfaceName: 'CardBlock',
  labels: {
    singular: 'Card',
    plural: 'Cards',
  },
  admin: {
    group: 'Layout',
    disableBlockName: true,
  },
  fields: [
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
      name: 'icon',
      type: 'text',
    },
    {
      name: 'badge',
      type: 'text',
    },
    {
      name: 'link',
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
}
