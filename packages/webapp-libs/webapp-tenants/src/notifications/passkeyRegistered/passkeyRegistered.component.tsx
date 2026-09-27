import { Notification, NotificationType } from '@sb/webapp-notifications';
import { KeyRound } from 'lucide-react';
import { FormattedMessage } from 'react-intl';

export type PasskeyRegisteredProps = NotificationType<{
  passkey_name: string;
  authenticator_type: string;
}>;

export const PasskeyRegistered = ({
  data: { passkey_name },
  ...restProps
}: PasskeyRegisteredProps) => {
  return (
    <Notification
      {...restProps}
      icon={<KeyRound className="h-4 w-4 text-emerald-600" />}
      iconClassName="bg-emerald-100"
      title={<FormattedMessage defaultMessage="Passkey Registered" id="Notifications / Passkey Registered / Title" />}
      content={
        <FormattedMessage
          defaultMessage='A new passkey "{passkey_name}" was added to your account.'
          id="Notifications / Passkey Registered / Content"
          values={{ passkey_name }}
        />
      }
    />
  );
};
