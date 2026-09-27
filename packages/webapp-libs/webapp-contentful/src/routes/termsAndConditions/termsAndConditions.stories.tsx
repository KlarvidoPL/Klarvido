import { Meta, StoryFn, StoryObj } from '@storybook/react';

import { withProviders } from '../../utils/storybook';
import { TermsAndConditions } from './termsAndConditions.component';

const Template: StoryFn = () => <TermsAndConditions />;

const meta: Meta = {
  title: 'Routes/TermsAndConditions',
  component: TermsAndConditions,
};

export default meta;

export const Default: StoryObj<typeof meta> = {
  render: Template,
  decorators: [withProviders()],
};
