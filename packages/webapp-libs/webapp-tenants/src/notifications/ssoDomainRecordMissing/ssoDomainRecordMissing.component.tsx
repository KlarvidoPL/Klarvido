import { Notification, NotificationType } from '@sb/webapp-notifications';
import { AlertTriangle } from 'lucide-react';
import { FormattedMessage } from 'react-intl';

export type SSODomainRecordMissingProps = NotificationType<{
  domain: string;
  tenant_name: string;
  grace_days: number;
}>;

export const SSODomainRecordMissing = ({
  data: { domain, tenant_name, grace_days },
  ...restProps
}: SSODomainRecordMissingProps) => {
  return (
    <Notification
      {...restProps}
      icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}
      iconClassName="bg-amber-500/10"
      title={
        <FormattedMessage
          defaultMessage="SSO domain verification record missing"
          id="Notifications / SSO Domain Record Missing / Title"
        />
      }
      content={
        <FormattedMessage
          defaultMessage='The verification record for "{domain}" ({tenant_name}) is missing. SSO for this domain will be deactivated in {grace_days} days unless the record is restored.'
          id="Notifications / SSO Domain Record Missing / Content"
          values={{ domain, tenant_name, grace_days }}
        />
      }
    />
  );
};
