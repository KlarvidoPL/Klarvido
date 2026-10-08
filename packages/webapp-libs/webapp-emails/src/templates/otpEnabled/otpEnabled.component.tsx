import { useGenerateAbsoluteLocalePath } from '@sb/webapp-core/hooks';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { FormattedMessage, useIntl } from 'react-intl';

import { Button, Layout } from '../../base';
import { EmailComponentProps } from '../../types';

export type OtpEnabledProps = EmailComponentProps;

export const Template = () => {
  const intl = useIntl();
  const generateLocalePath = useGenerateAbsoluteLocalePath();
  const url = generateLocalePath(RoutesConfig.profile);

  const preheaderText = intl.formatMessage({
    defaultMessage: "If this wasn't you, review your account security right away.",
    id: 'Email / OTP Enabled / Preheader',
  });

  return (
    <Layout
      preheader={preheaderText}
      title={<FormattedMessage defaultMessage="Two-factor authentication was enabled" id="Email / OTP Enabled / Title" />}
      text={
        <FormattedMessage
          defaultMessage="Two-factor authentication is now protecting your account - a verification code will be required in addition to your password when signing in. If you made this change, no further action is needed. If you didn't, review your account security immediately and contact support."
          id="Email / OTP Enabled / Text"
        />
      }
      footer={{
        companyName: 'Klarvido',
      }}
    >
      <Button linkTo={url}>
        <FormattedMessage defaultMessage="Review account security" id="Email / OTP Enabled / Link label" />
      </Button>
    </Layout>
  );
};

export const Subject = () => (
  <FormattedMessage defaultMessage="Two-factor authentication was enabled on your account" id="Email / OTP Enabled / Subject" />
);
