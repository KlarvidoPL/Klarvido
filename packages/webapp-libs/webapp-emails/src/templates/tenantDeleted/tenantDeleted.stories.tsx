import { Meta, StoryFn, StoryObj } from '@storybook/react';

import { EmailStory } from '../../emailStory/emailStory.component';
import { EmailTemplateType } from '../../types';
import {
  Template as TenantDeletedEmail,
  TenantDeletedProps,
  Subject as TenantDeletedSubject,
} from './tenantDeleted.component';

const Template: StoryFn<TenantDeletedProps> = (args: TenantDeletedProps) => (
  <EmailStory type={EmailTemplateType.TENANT_DELETED} subject={<TenantDeletedSubject {...args} />} emailData={args}>
    <TenantDeletedEmail {...args} />
  </EmailStory>
);

const meta: Meta<typeof TenantDeletedEmail> = {
  title: 'Emails/TenantDeleted',
  component: TenantDeletedEmail,
  parameters: {
    docs: {
      description: {
        component:
          'Email sent to every member when an organization is deleted: a heads-up for the others, a confirmation for the member who deleted it.',
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof TenantDeletedEmail>;

export const Member: Story = {
  render: Template,
  args: { tenantName: 'Acme sp. z o.o.', deletedBy: 'Jan Kowalski', isDeleter: false },
};

export const Deleter: Story = {
  render: Template,
  args: { tenantName: 'Acme sp. z o.o.', deletedBy: 'Jan Kowalski', isDeleter: true },
};
