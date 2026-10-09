import { useGenerateAbsoluteLocalePath } from '@sb/webapp-core/hooks';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { FormattedMessage, useIntl } from 'react-intl';

import { Button, Layout } from '../../base';
import { EmailComponentProps } from '../../types';

export type PasswordSetProps = EmailComponentProps & {
  userId: string;
  token: string;
};

export const Template = ({ userId, token }: PasswordSetProps) => {
  const intl = useIntl();
  const generateLocalePath = useGenerateAbsoluteLocalePath();
  // Same confirm route as a normal password reset - the token is bound to the account's
  // current (unusable) password hash exactly like a reset token, so it works identically.
  const url = generateLocalePath(RoutesConfig.passwordReset.confirm, {
    token,
    user: userId,
  });

  const preheaderText = intl.formatMessage({
    defaultMessage: 'This link expires in 1 hour for your security',
    id: 'Email / Set Password / Preheader',
  });

  return (
    <Layout
      preheader={preheaderText}
      title={<FormattedMessage defaultMessage="Set your password" id="Email / Set Password / Title" />}
      text={
        <FormattedMessage
          defaultMessage="You requested to set a password for your account. Click the button below to choose one. If you didn't make this request, you can safely ignore this email."
          id="Email / Set Password / Text"
        />
      }
      footer={{
        companyName: 'Klarvido',
      }}
    >
      <Button linkTo={url}>
        <FormattedMessage defaultMessage="Set password" id="Email / Set Password / Link label" />
      </Button>
    </Layout>
  );
};

export const Subject = () => (
  <FormattedMessage defaultMessage="Set your password" id="Email / Set Password / Subject" />
);
