import { Meta, StoryFn, StoryObj } from '@storybook/react';

import { withProviders } from '../../utils/storybook';
import { PrivacyPolicy } from './privacyPolicy.component';

const Template: StoryFn = () => <PrivacyPolicy />;

const meta: Meta = {
  title: 'Routes/PrivacyPolicy',
  component: PrivacyPolicy,
};

export default meta;

export const Default: StoryObj<typeof meta> = {
  render: Template,
  decorators: [withProviders()],
};
