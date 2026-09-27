import { useOAuthLogin } from '@sb/webapp-api-client/api/auth';
import { Button } from '@sb/webapp-core/components/ui/button';
import { HTMLAttributes } from 'react';
import { FormattedMessage } from 'react-intl';

import { GoogleIcon } from '../../../../images/icons';
import { OAuthProvider } from '../../../../modules/auth/auth.types';

export enum SignupButtonsVariant {
  LOGIN,
  SIGNUP,
}

export type SocialLoginButtonsProps = HTMLAttributes<HTMLDivElement> & {
  variant: SignupButtonsVariant;
};

// Facebook is deliberately hidden for now (app review/advanced access not done
// yet) - see AUTHENTICATION_BACKENDS in the backend settings, which also has the
// /auth/social/facebook/ endpoints disabled to match.
export const SocialLoginButtons = ({ variant, ...props }: SocialLoginButtonsProps) => {
  const oAuthLogin = useOAuthLogin();
  const handleGoogleLogin = () => oAuthLogin(OAuthProvider.Google);

  return (
    <div className="flex w-full flex-col gap-4" {...props}>
      <Button variant="outline" size="lg" className="w-full" onClick={handleGoogleLogin}>
        <GoogleIcon size={20} className="h-5 w-5" />
        {variant === SignupButtonsVariant.LOGIN ? (
          <FormattedMessage defaultMessage="Log in with Google" id="Auth / Login / Google login button" />
        ) : (
          <FormattedMessage defaultMessage="Sign up with Google" id="Auth / Signup / Google signup button" />
        )}
      </Button>
    </div>
  );
};
