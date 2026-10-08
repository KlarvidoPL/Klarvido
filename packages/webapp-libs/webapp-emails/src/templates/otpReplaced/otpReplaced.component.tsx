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
        defaultMessage: 'Your two-factor authentication was replaced',
        id: 'Email / OtpReplaced / Title',
      })}
      title={
        <FormattedMessage
          defaultMessage={'Your two-factor authentication was replaced'}
          id="Email / OtpReplaced / Title"
        />
      }
      text={
        <FormattedMessage
          defaultMessage={
            'The authenticator protecting your account was replaced. If you made this change, no further action is needed. If this was not you, reset your password immediately and contact support.'
          }
          id="Email / OtpReplaced / Text"
        />
      }
      footer={{ companyName: 'Klarvido' }}
    >
      <Button linkTo={path(RoutesConfig.profile)}>
        <FormattedMessage defaultMessage={'Review account security'} id="Email / OTP Enabled / Link label" />
      </Button>
    </Layout>
  );
};

export const Subject = () => (
  <FormattedMessage defaultMessage={'Your two-factor authentication was replaced'} id="Email / OtpReplaced / Title" />
);
