import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateAbsoluteLocalePath } from '@sb/webapp-core/hooks';
import { FormattedMessage, useIntl } from 'react-intl';

import { Button, Layout } from '../../base';

export const Template = () => {
  const intl = useIntl();
  const path = useGenerateAbsoluteLocalePath();
  return (
    <Layout
      preheader={intl.formatMessage({
        defaultMessage: 'Account sign-in instructions',
        id: 'Email / SignupGuidance / Title',
      })}
      title={<FormattedMessage defaultMessage="Account sign-in instructions" id="Email / SignupGuidance / Title" />}
      text={
        <FormattedMessage
          defaultMessage="An account already uses this email address. Sign in with your existing password or passkey. If you forgot your password, use password reset on the sign-in page. If your email is not verified yet, sign in and request a verification email before connecting Google. This request did not change your account."
          id="Email / SignupGuidance / Text"
        />
      }
      footer={{ companyName: 'Klarvido' }}
    >
      <Button linkTo={path(RoutesConfig.login)}>
        <FormattedMessage defaultMessage="Sign in" id="Auth / Signup / login link" />
      </Button>
    </Layout>
  );
};

export const Subject = () => (
  <FormattedMessage defaultMessage="Account sign-in instructions" id="Email / SignupGuidance / Title" />
);
