import { Notification, NotificationType } from '@sb/webapp-notifications';
import { ShieldOff } from 'lucide-react';
import { FormattedMessage } from 'react-intl';

export type SSOConnectionDeactivatedProps = NotificationType<{
  connection_name: string;
  connection_type: string;
  tenant_name: string;
}>;

export const SSOConnectionDeactivated = ({
  data: { connection_name, connection_type, tenant_name },
  ...restProps
}: SSOConnectionDeactivatedProps) => {
  return (
    <Notification
      {...restProps}
      icon={<ShieldOff className="h-4 w-4 text-muted-foreground" />}
      iconClassName="bg-muted"
      title={
        <FormattedMessage
          defaultMessage="SSO Connection Deactivated"
          id="Notifications / SSO Connection Deactivated / Title"
        />
      }
      content={
        <FormattedMessage
          defaultMessage='{connection_type} connection "{connection_name}" for "{tenant_name}" was deactivated.'
          id="Notifications / SSO Connection Deactivated / Content"
          values={{ connection_name, connection_type, tenant_name }}
        />
      }
    />
  );
};
