import { useGenerateAbsoluteLocalePath } from '@sb/webapp-core/hooks';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { FormattedMessage, useIntl } from 'react-intl';

import { Button, Layout } from '../../base';
import { EmailComponentProps } from '../../types';

export type OtpDisabledProps = EmailComponentProps;

export const Template = () => {
  const intl = useIntl();
  const generateLocalePath = useGenerateAbsoluteLocalePath();
  const url = generateLocalePath(RoutesConfig.passwordReset.index);

  const preheaderText = intl.formatMessage({
    defaultMessage: "If this wasn't you, reset your password right away.",
    id: 'Email / OTP Disabled / Preheader',
  });

  return (
    <Layout
      preheader={preheaderText}
      title={<FormattedMessage defaultMessage="Two-factor authentication was disabled" id="Email / OTP Disabled / Title" />}
      text={
        <FormattedMessage
          defaultMessage="Two-factor authentication was just turned off for your account. If you made this change, no further action is needed. If you didn't, reset your password immediately and contact support."
          id="Email / OTP Disabled / Text"
        />
      }
      footer={{
        companyName: 'Klarvido',
      }}
    >
      <Button linkTo={url}>
        <FormattedMessage defaultMessage="Reset your password" id="Email / OTP Disabled / Link label" />
      </Button>
    </Layout>
  );
};

export const Subject = () => (
  <FormattedMessage defaultMessage="Two-factor authentication was disabled on your account" id="Email / OTP Disabled / Subject" />
);
