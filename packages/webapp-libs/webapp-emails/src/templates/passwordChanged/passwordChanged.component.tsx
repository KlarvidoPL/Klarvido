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
        defaultMessage: 'Your password was changed',
        id: 'Email / PasswordChanged / Title',
      })}
      title={<FormattedMessage defaultMessage="Your password was changed" id="Email / PasswordChanged / Title" />}
      text={
        <FormattedMessage
          defaultMessage="Your account password was changed or reset. If you made this change, no further action is needed. If this was not you, reset your password immediately and contact support."
          id="Email / PasswordChanged / Text"
        />
      }
      footer={{ companyName: 'Klarvido' }}
    >
      <Button linkTo={path(RoutesConfig.profile)}>
        <FormattedMessage defaultMessage="Review account security" id="Email / OTP Enabled / Link label" />
      </Button>
    </Layout>
  );
};

export const Subject = () => (
  <FormattedMessage defaultMessage="Your password was changed" id="Email / PasswordChanged / Title" />
);
