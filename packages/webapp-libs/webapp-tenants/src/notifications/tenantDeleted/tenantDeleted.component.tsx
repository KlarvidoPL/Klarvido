import { Notification, NotificationType } from '@sb/webapp-notifications';
import { FormattedMessage } from 'react-intl';

export type TenantDeletedProps = NotificationType<{
  tenant_name: string;
  name: string;
}>;

export const TenantDeleted = ({ data: { tenant_name, name }, issuer, ...restProps }: TenantDeletedProps) => {
  const displayName = name || issuer?.email || '';

  return (
    <Notification
      {...restProps}
      avatar={issuer?.avatar}
      title={issuer?.email}
      content={
        <FormattedMessage
          defaultMessage='Organization "{tenant_name}" was deleted by "{name}"'
          id="Notifications / Tenant / Deleted"
          values={{ tenant_name, name: displayName }}
        />
      }
    />
  );
};
