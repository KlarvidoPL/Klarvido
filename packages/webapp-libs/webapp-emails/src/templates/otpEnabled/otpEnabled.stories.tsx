import { Meta, StoryFn, StoryObj } from '@storybook/react';

import { EmailStory } from '../../emailStory/emailStory.component';
import { EmailTemplateType } from '../../types';
import { Template as OtpEnabledEmail, OtpEnabledProps, Subject as OtpEnabledSubject } from './otpEnabled.component';

const Template: StoryFn<OtpEnabledProps> = (args: OtpEnabledProps) => (
  <EmailStory type={EmailTemplateType.OTP_ENABLED} subject={<OtpEnabledSubject />} emailData={args}>
    <OtpEnabledEmail {...args} />
  </EmailStory>
);

const meta: Meta<typeof OtpEnabledEmail> = {
  title: 'Emails/OtpEnabled',
  component: OtpEnabledEmail,
  parameters: {
    docs: {
      description: {
        component: 'Sent after two-factor authentication is enabled or its secret replaced, so the owner notices if it was not them.',
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof OtpEnabledEmail>;

export const Primary: Story = {
  render: Template,
};

export const Mobile: Story = {
  render: Template,
  parameters: {
    viewport: {
      defaultViewport: 'mobile1',
    },
  },
};
