import { Notification, NotificationType } from '@sb/webapp-notifications';
import { AlertTriangle } from 'lucide-react';
import { FormattedMessage } from 'react-intl';

export type SSODomainLapsedProps = NotificationType<{
  domain: string;
  tenant_name: string;
  connection_names: string[];
}>;

export const SSODomainLapsed = ({
  data: { domain, tenant_name, connection_names },
  ...restProps
}: SSODomainLapsedProps) => {
  return (
    <Notification
      {...restProps}
      icon={<AlertTriangle className="h-4 w-4 text-destructive" />}
      iconClassName="bg-destructive/10"
      title={<FormattedMessage defaultMessage="SSO Domain Lapsed" id="Notifications / SSO Domain Lapsed / Title" />}
      content={
        connection_names.length > 0 ? (
          <FormattedMessage
            defaultMessage='The domain "{domain}" for "{tenant_name}" is no longer verified because its verification record is missing. Connections deactivated: {connections}.'
            id="Notifications / SSO Domain Lapsed / Content"
            values={{ domain, tenant_name, connections: connection_names.join(', ') }}
          />
        ) : (
          <FormattedMessage
            defaultMessage='The domain "{domain}" for "{tenant_name}" is no longer verified because its verification record is missing.'
            id="Notifications / SSO Domain Lapsed / Content without connections"
            values={{ domain, tenant_name }}
          />
        )
      }
    />
  );
};
