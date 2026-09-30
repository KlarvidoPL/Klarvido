import { NotificationTypes } from '@sb/webapp-notifications';
import { Meta, StoryFn, StoryObj } from '@storybook/react';

import { withProviders } from '../../utils/storybook';
import { TenantDeleted, TenantDeletedProps } from './tenantDeleted.component';

const Template: StoryFn<TenantDeletedProps> = (args: TenantDeletedProps) => {
  return <TenantDeleted {...args} />;
};

const meta: Meta = {
  title: 'Tenants / Notifications / TenantDeleted',
  component: Template,
};

export default meta;

export const Default: StoryObj<TenantDeletedProps> = {
  args: {
    type: NotificationTypes.TENANT_DELETED,
    readAt: null,
    createdAt: '2021-06-17T11:45:33',

    data: {
      name: 'User Name',
      tenant_name: 'Lorem ipsum',
    },
    issuer: {
      id: 'mock-user-uuid',
      email: 'example@example.com',
      avatar: 'https://picsum.photos/24/24',
    },
  },

  decorators: [withProviders()],
};
