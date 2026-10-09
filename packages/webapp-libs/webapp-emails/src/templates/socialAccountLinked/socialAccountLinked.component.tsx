import { useGenerateAbsoluteLocalePath } from '@sb/webapp-core/hooks';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { FormattedMessage, useIntl } from 'react-intl';

import { Button, Layout } from '../../base';
import { EmailComponentProps } from '../../types';

export type SocialAccountLinkedProps = EmailComponentProps & {
  provider: string;
};

const PROVIDER_LABELS: Record<string, string> = {
  'google-oauth2': 'Google',
  facebook: 'Facebook',
};

export const Template = ({ provider }: SocialAccountLinkedProps) => {
  const intl = useIntl();
  const generateLocalePath = useGenerateAbsoluteLocalePath();
  const url = generateLocalePath(RoutesConfig.passwordReset.index);
  const providerLabel = PROVIDER_LABELS[provider] ?? provider;

  const preheaderText = intl.formatMessage({
    defaultMessage: "If this wasn't you, reset your password right away.",
    id: 'Email / Social Account Linked / Preheader',
  });

  return (
    <Layout
      preheader={preheaderText}
      title={
        <FormattedMessage
          defaultMessage="{provider} sign-in was connected to your account"
          id="Email / Social Account Linked / Title"
          values={{ provider: providerLabel }}
        />
      }
      text={
        <FormattedMessage
          defaultMessage="You can now sign in with {provider} using this email address. If you made this change, no further action is needed. If you didn't connect {provider}, reset your password immediately and contact support."
          id="Email / Social Account Linked / Text"
          values={{ provider: providerLabel }}
        />
      }
      footer={{
        companyName: 'Klarvido',
      }}
    >
      <Button linkTo={url}>
        <FormattedMessage defaultMessage="Reset your password" id="Email / Social Account Linked / Link label" />
      </Button>
    </Layout>
  );
};

export const Subject = () => (
  <FormattedMessage defaultMessage="A new sign-in method was added to your account" id="Email / Social Account Linked / Subject" />
);
