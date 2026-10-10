import { Notification, NotificationType } from '@sb/webapp-notifications';
import { FormattedMessage } from 'react-intl';

export const MemberAccountDeleted = ({
  data: { name, tenant_name },
  ...props
}: NotificationType<{ name: string; tenant_name: string }>) => (
  <Notification
    {...props}
    title={tenant_name}
    content={
      <FormattedMessage
        id="Notifications / Member account deleted"
        defaultMessage="{name} deleted their account and left {tenant_name}."
        values={{ name, tenant_name }}
      />
    }
  />
);
