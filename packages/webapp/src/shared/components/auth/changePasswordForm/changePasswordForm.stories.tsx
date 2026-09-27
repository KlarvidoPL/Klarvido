import { StoryFn } from '@storybook/react';

import { withProviders } from '../../../utils/storybook';
import { ChangePasswordForm, ChangePasswordFormProps } from './changePasswordForm.component';

const Template: StoryFn<ChangePasswordFormProps> = (args) => {
  return (
    <div className="mx-auto w-full max-w-2xl px-4 lg:px-10">
      <ChangePasswordForm {...args} />
    </div>
  );
};

export default {
  title: 'Shared/Auth/ChangePasswordForm',
  component: ChangePasswordForm,
};

export const Default = {
  render: Template,
  args: { hasUsablePassword: true },
  decorators: [withProviders({})],
};

export const SetPassword = {
  render: Template,
  args: { hasUsablePassword: false },
  decorators: [withProviders({})],
};
