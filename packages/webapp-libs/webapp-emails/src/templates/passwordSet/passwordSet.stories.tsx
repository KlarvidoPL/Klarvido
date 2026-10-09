import { Meta, StoryFn, StoryObj } from '@storybook/react';

import { EmailStory } from '../../emailStory/emailStory.component';
import { EmailTemplateType } from '../../types';
import { Template as PasswordSetEmail, PasswordSetProps, Subject as PasswordSetSubject } from './passwordSet.component';

const Template: StoryFn<PasswordSetProps> = (args: PasswordSetProps) => (
  <EmailStory type={EmailTemplateType.PASSWORD_SET} subject={<PasswordSetSubject />} emailData={args}>
    <PasswordSetEmail {...args} />
  </EmailStory>
);

const meta: Meta<typeof PasswordSetEmail> = {
  title: 'Emails/PasswordSet',
  component: PasswordSetEmail,
  parameters: {
    docs: {
      description: {
        component:
          'Email sent to a passwordless account (no password, no passkey, no 2FA) that requested to set its first password.',
      },
    },
  },
  argTypes: {
    token: {
      description: 'Password set/reset token',
      control: 'text',
    },
    userId: {
      description: 'User ID for the set-password link',
      control: 'text',
    },
  },
};

export default meta;
type Story = StoryObj<typeof PasswordSetEmail>;

export const Primary: Story = {
  render: Template,
  args: {
    token: 'set-token-xyz789',
    userId: 'user-12345',
  },
};

export const Mobile: Story = {
  render: Template,
  args: {
    token: 'set-token-xyz789',
    userId: 'user-12345',
  },
  parameters: {
    viewport: {
      defaultViewport: 'mobile1',
    },
  },
};
