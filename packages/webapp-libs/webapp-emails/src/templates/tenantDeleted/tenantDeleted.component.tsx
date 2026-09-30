import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateAbsoluteLocalePath } from '@sb/webapp-core/hooks';
import { FormattedMessage, useIntl } from 'react-intl';

import { Button, Layout, Text } from '../../base';
import { EmailComponentProps } from '../../types';

export type TenantDeletedProps = EmailComponentProps & {
  tenantName: string;
  deletedBy: string;
  /** The member who deleted it gets a confirmation, everyone else a heads-up */
  isDeleter: boolean;
};

export const Template = ({ tenantName, deletedBy, isDeleter }: TenantDeletedProps) => {
  const intl = useIntl();
  const generateLocalePath = useGenerateAbsoluteLocalePath();
  const url = generateLocalePath(RoutesConfig.home);

  const preheaderText = intl.formatMessage(
    { defaultMessage: 'Organization "{tenantName}" has been deleted', id: 'Email / TenantDeleted / Preheader' },
    { tenantName }
  );

  return (
    <Layout
      preheader={preheaderText}
      title={<FormattedMessage defaultMessage="Organization deleted" id="Email / TenantDeleted / Title" />}
      text={
        isDeleter ? (
          <FormattedMessage
            defaultMessage={
              'You deleted the organization "{tenantName}". If this wasn\'t you, change your password and contact us right away.'
            }
            id="Email / TenantDeleted / Text deleter"
            values={{ tenantName }}
          />
        ) : (
          <FormattedMessage
            defaultMessage='The organization "{tenantName}" was deleted by {deletedBy}. You no longer have access to it.'
            id="Email / TenantDeleted / Text member"
            values={{ tenantName, deletedBy }}
          />
        )
      }
      footer={{
        companyName: 'Klarvido',
      }}
    >
      <Text>
        <FormattedMessage
          defaultMessage="All of its data, including backups and files, has been permanently removed and can't be restored."
          id="Email / TenantDeleted / Data removed"
        />
      </Text>
      <Button linkTo={url}>
        <FormattedMessage defaultMessage="Go to Klarvido" id="Email / TenantDeleted / Button" />
      </Button>
    </Layout>
  );
};

export const Subject = ({ tenantName }: TenantDeletedProps) => (
  <FormattedMessage
    defaultMessage='Organization "{tenantName}" has been deleted'
    id="Email / TenantDeleted / Subject"
    values={{ tenantName }}
  />
);
