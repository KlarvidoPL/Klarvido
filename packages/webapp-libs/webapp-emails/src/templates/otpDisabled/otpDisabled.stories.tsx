import { Meta, StoryFn, StoryObj } from '@storybook/react';

import { EmailStory } from '../../emailStory/emailStory.component';
import { EmailTemplateType } from '../../types';
import { Template as OtpDisabledEmail, OtpDisabledProps, Subject as OtpDisabledSubject } from './otpDisabled.component';

const Template: StoryFn<OtpDisabledProps> = (args: OtpDisabledProps) => (
  <EmailStory type={EmailTemplateType.OTP_DISABLED} subject={<OtpDisabledSubject />} emailData={args}>
    <OtpDisabledEmail {...args} />
  </EmailStory>
);

const meta: Meta<typeof OtpDisabledEmail> = {
  title: 'Emails/OtpDisabled',
  component: OtpDisabledEmail,
  parameters: {
    docs: {
      description: {
        component: 'Sent after two-factor authentication is disabled, so the owner notices if it was not them.',
      },
    },
  },
};

export default meta;
type Story = StoryObj<typeof OtpDisabledEmail>;

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
