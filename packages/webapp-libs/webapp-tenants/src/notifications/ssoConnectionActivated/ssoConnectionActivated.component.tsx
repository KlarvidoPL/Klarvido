import { Notification, NotificationType } from '@sb/webapp-notifications';
import { ShieldCheck } from 'lucide-react';
import { FormattedMessage } from 'react-intl';

export type SSOConnectionActivatedProps = NotificationType<{
  connection_name: string;
  connection_type: string;
  tenant_name: string;
}>;

export const SSOConnectionActivated = ({
  data: { connection_name, connection_type, tenant_name },
  ...restProps
}: SSOConnectionActivatedProps) => {
  return (
    <Notification
      {...restProps}
      icon={<ShieldCheck className="h-4 w-4 text-emerald-600" />}
      iconClassName="bg-emerald-100"
      title={
        <FormattedMessage
          defaultMessage="SSO Connection Activated"
          id="Notifications / SSO Connection Activated / Title"
        />
      }
      content={
        <FormattedMessage
          defaultMessage='{connection_type} connection "{connection_name}" for "{tenant_name}" is now active.'
          id="Notifications / SSO Connection Activated / Content"
          values={{ connection_name, connection_type, tenant_name }}
        />
      }
    />
  );
};
