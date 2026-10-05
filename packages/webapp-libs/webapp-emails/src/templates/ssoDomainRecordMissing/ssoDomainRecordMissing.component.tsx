import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateAbsoluteLocalePath } from '@sb/webapp-core/hooks';
import { FormattedMessage, useIntl } from 'react-intl';

import { Button, Layout, Text } from '../../base';
import { EmailComponentProps } from '../../types';

export type SSODomainRecordMissingProps = EmailComponentProps & {
  domain: string;
  tenantName: string;
  graceDays: number;
};

export const Template = ({ domain, tenantName, graceDays }: SSODomainRecordMissingProps) => {
  const intl = useIntl();
  const generateLocalePath = useGenerateAbsoluteLocalePath();
  const url = generateLocalePath(RoutesConfig.home);

  const preheaderText = intl.formatMessage(
    {
      defaultMessage: 'The SSO verification record for {domain} is missing',
      id: 'Email / SSODomainRecordMissing / Preheader',
    },
    { domain }
  );

  return (
    <Layout
      preheader={preheaderText}
      title={
        <FormattedMessage
          defaultMessage="SSO verification record missing"
          id="Email / SSODomainRecordMissing / Title"
        />
      }
      text={
        <FormattedMessage
          defaultMessage='The DNS record that proves you own "{domain}" for {tenantName} is missing. SSO for this domain will be deactivated in {graceDays} days unless the record is restored.'
          id="Email / SSODomainRecordMissing / Text"
          values={{ domain, tenantName, graceDays }}
        />
      }
      footer={{
        companyName: 'Klarvido',
      }}
    >
      <Text>
        <FormattedMessage
          defaultMessage="Open the security settings of your organization to see the record and put it back."
          id="Email / SSODomainRecordMissing / Action"
        />
      </Text>
      <Button linkTo={url}>
        <FormattedMessage defaultMessage="Go to Klarvido" id="Email / SSODomainRecordMissing / Button" />
      </Button>
    </Layout>
  );
};

export const Subject = ({ domain }: SSODomainRecordMissingProps) => (
  <FormattedMessage
    defaultMessage='SSO verification record missing for "{domain}"'
    id="Email / SSODomainRecordMissing / Subject"
    values={{ domain }}
  />
);
