import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateAbsoluteLocalePath } from '@sb/webapp-core/hooks';
import { FormattedMessage, useIntl } from 'react-intl';

import { Button, Layout, Text } from '../../base';
import { EmailComponentProps } from '../../types';

export type SSODomainLapsedProps = EmailComponentProps & {
  domain: string;
  tenantName: string;
  graceDays: number;
};

export const Template = ({ domain, tenantName, graceDays }: SSODomainLapsedProps) => {
  const intl = useIntl();
  const generateLocalePath = useGenerateAbsoluteLocalePath();
  const url = generateLocalePath(RoutesConfig.home);

  const preheaderText = intl.formatMessage(
    { defaultMessage: 'SSO for {domain} has been deactivated', id: 'Email / SSODomainLapsed / Preheader' },
    { domain }
  );

  return (
    <Layout
      preheader={preheaderText}
      title={<FormattedMessage defaultMessage="SSO deactivated for your domain" id="Email / SSODomainLapsed / Title" />}
      text={
        <FormattedMessage
          defaultMessage='The verification record for "{domain}" at {tenantName} has been missing for {graceDays} days, so SSO for this domain has been deactivated. Users can no longer sign in with it.'
          id="Email / SSODomainLapsed / Text"
          values={{ domain, tenantName, graceDays }}
        />
      }
      footer={{
        companyName: 'Klarvido',
      }}
    >
      <Text>
        <FormattedMessage
          defaultMessage="Put the record back, verify the domain and reactivate the SSO connection in the security settings."
          id="Email / SSODomainLapsed / Action"
        />
      </Text>
      <Button linkTo={url}>
        <FormattedMessage defaultMessage="Go to Klarvido" id="Email / SSODomainLapsed / Button" />
      </Button>
    </Layout>
  );
};

export const Subject = ({ domain }: SSODomainLapsedProps) => (
  <FormattedMessage
    defaultMessage='SSO deactivated for "{domain}"'
    id="Email / SSODomainLapsed / Subject"
    values={{ domain }}
  />
);
