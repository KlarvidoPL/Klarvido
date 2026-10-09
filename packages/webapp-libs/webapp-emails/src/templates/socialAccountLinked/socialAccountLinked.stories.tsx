import { Meta, StoryFn, StoryObj } from '@storybook/react';

import { EmailStory } from '../../emailStory/emailStory.component';
import { EmailTemplateType } from '../../types';
import {
  Template as SocialAccountLinkedEmail,
  SocialAccountLinkedProps,
  Subject as SocialAccountLinkedSubject,
} from './socialAccountLinked.component';

const Template: StoryFn<SocialAccountLinkedProps> = (args: SocialAccountLinkedProps) => (
  <EmailStory type={EmailTemplateType.SOCIAL_ACCOUNT_LINKED} subject={<SocialAccountLinkedSubject />} emailData={args}>
    <SocialAccountLinkedEmail {...args} />
  </EmailStory>
);

const meta: Meta<typeof SocialAccountLinkedEmail> = {
  title: 'Emails/SocialAccountLinked',
  component: SocialAccountLinkedEmail,
  parameters: {
    docs: {
      description: {
        component: 'Sent after a social provider (e.g. Google) is linked to an existing account, so the owner notices if it was not them.',
      },
    },
  },
  argTypes: {
    provider: {
      description: 'Social provider backend name (e.g. "google-oauth2")',
      control: 'text',
    },
  },
};

export default meta;
type Story = StoryObj<typeof SocialAccountLinkedEmail>;

export const Primary: Story = {
  render: Template,
  args: {
    provider: 'google-oauth2',
  },
};

export const Mobile: Story = {
  render: Template,
  args: {
    provider: 'google-oauth2',
  },
  parameters: {
    viewport: {
      defaultViewport: 'mobile1',
    },
  },
};
