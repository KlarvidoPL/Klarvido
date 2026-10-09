import { useOAuthLogin } from '@sb/webapp-api-client/api/auth';
import { Button } from '@sb/webapp-core/components/ui/button';
import { HTMLAttributes, useState } from 'react';
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
  const [pending, setPending] = useState(false);
  const [failed, setFailed] = useState(false);
  const handleGoogleLogin = async () => {
    setPending(true);
    setFailed(false);
    try {
      await oAuthLogin(OAuthProvider.Google);
    } catch {
      setFailed(true);
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="flex w-full flex-col gap-4" {...props}>
      <Button variant="outline" size="lg" className="w-full" onClick={handleGoogleLogin} disabled={pending}>
        <GoogleIcon size={20} className="h-5 w-5" />
        {variant === SignupButtonsVariant.LOGIN ? (
          <FormattedMessage defaultMessage="Log in with Google" id="Auth / Login / Google login button" />
        ) : (
          <FormattedMessage defaultMessage="Sign up with Google" id="Auth / Signup / Google signup button" />
        )}
      </Button>
      {failed && (
        <p role="alert" className="text-sm text-destructive">
          <FormattedMessage
            defaultMessage="Unable to start Google sign-in. Please try again."
            id="Auth / Social / Start failed"
          />
        </p>
      )}
    </div>
  );
};
