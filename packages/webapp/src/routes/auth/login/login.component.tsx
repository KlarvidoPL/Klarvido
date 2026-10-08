import { csrfFetch } from '@sb/webapp-api-client/api/csrf';
import { Button } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { Separator } from '@sb/webapp-core/components/ui/separator';
import { ENV } from '@sb/webapp-core/config/env';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { MailCheck, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { FormattedMessage } from 'react-intl';
import { Link, useLocation, useNavigate } from 'react-router-dom';

import { RoutesConfig } from '../../../app/config/routes';
import { AuthLogo } from '../../../shared/components/auth/authLogo';
import { FloatingThemeToggle } from '../../../shared/components/auth/floatingThemeToggle';
import { LoginForm } from '../../../shared/components/auth/loginForm';
import { PasskeyLoginButton } from '../../../shared/components/auth/passkeyLoginButton';
import { SocialLoginButtons } from '../../../shared/components/auth/socialLoginButtons';
import { SignupButtonsVariant } from '../../../shared/components/auth/socialLoginButtons/socialLoginButtons.component';

export const Login = () => {
  const generateLocalePath = useGenerateLocalePath();
  const { search } = useLocation();
  const navigate = useNavigate();
  const socialStatus = new URLSearchParams(search).get('social');
  const linking = socialStatus === 'link_required';
  const [canceling, setCanceling] = useState(false);
  const [cancelFailed, setCancelFailed] = useState(false);

  const cancelLink = async () => {
    setCanceling(true);
    setCancelFailed(false);
    try {
      const response = await csrfFetch(`${ENV.BASE_API_URL}/auth/social-link/cancel/`, { method: 'POST' });
      if (!response.ok) throw new Error('Cancellation failed');
      navigate(generateLocalePath(RoutesConfig.login), { replace: true });
    } catch {
      setCancelFailed(true);
    } finally {
      setCanceling(false);
    }
  };

  const showSocialLogin = ENV.ENABLE_SOCIAL_LOGIN && !linking;
  const showPasskeyLogin = ENV.ENABLE_PASSKEYS;
  const showPasswordLogin = ENV.ENABLE_PASSWORD_LOGIN;
  const hasMultipleAuthMethods = [showSocialLogin, showPasskeyLogin, showPasswordLogin].filter(Boolean).length > 1;

  return (
    <>
      <FloatingThemeToggle />
      <div className="container flex min-h-screen items-center justify-center px-4 py-8">
        <Card className="w-full max-w-md">
          <CardHeader className="space-y-4 text-center">
            <div className="flex justify-center">
              <AuthLogo />
            </div>
            <CardTitle className="text-3xl font-semibold tracking-tight">
              <FormattedMessage defaultMessage="Welcome back" id="Auth / Login / heading" />
            </CardTitle>
            <CardDescription>
              <FormattedMessage defaultMessage="Sign in to your account to continue" id="Auth / Login / description" />
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {linking && (
              <section
                className="space-y-4 rounded-xl border bg-muted/40 p-4"
                role="status"
                aria-labelledby="social-link-title"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-background text-primary">
                    <ShieldCheck className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div className="min-w-0 space-y-2">
                    <h2 id="social-link-title" className="text-sm font-semibold">
                      <FormattedMessage
                        defaultMessage="Connect Google to your account"
                        id="Auth / Social linking / Heading"
                      />
                    </h2>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      <FormattedMessage
                        defaultMessage="Sign in below with your password and a two-factor code if enabled, or use a passkey."
                        id="Auth / Social linking / Confirm account"
                      />
                    </p>
                    <p className="text-sm leading-relaxed text-muted-foreground">
                      <FormattedMessage
                        defaultMessage="This confirms the account is yours and connects Google for future sign-ins. Your two-factor authentication settings stay unchanged."
                        id="Auth / Social linking / Why confirm"
                      />
                    </p>
                  </div>
                </div>
                <div className="border-t pt-3">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-auto whitespace-normal px-2 py-1.5 text-muted-foreground"
                    onClick={cancelLink}
                    disabled={canceling}
                  >
                    <FormattedMessage defaultMessage="Cancel linking" id="Auth / Social linking / Cancel" />
                  </Button>
                </div>
                {cancelFailed && (
                  <p className="text-sm text-destructive" role="alert">
                    <FormattedMessage
                      defaultMessage="Unable to cancel. Please try again."
                      id="Auth / Social linking / Cancel failed"
                    />
                  </p>
                )}
              </section>
            )}
            {socialStatus === 'unconfirmed_account' && (
              <section
                className="space-y-4 rounded-xl border bg-muted/40 p-4 text-sm"
                role="status"
                aria-labelledby="social-verify-title"
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-background text-primary">
                    <MailCheck className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <div className="min-w-0 space-y-2">
                    <h2 id="social-verify-title" className="font-semibold">
                      <FormattedMessage
                        defaultMessage="Verify your email before connecting Google"
                        id="Auth / Social linking / Verify heading"
                      />
                    </h2>
                    <p className="leading-relaxed text-muted-foreground">
                      <FormattedMessage
                        defaultMessage="An account with this email already exists but hasn't been verified yet."
                        id="Auth / Social linking / Unconfirmed account"
                      />
                    </p>
                  </div>
                </div>
                <div className="space-y-3">
                  <p className="leading-relaxed">
                    <FormattedMessage
                      defaultMessage="If this is your account, sign in below and verify your email, then try connecting Google again."
                      id="Auth / Social linking / Unconfirmed account - owner"
                    />
                  </p>
                  {showPasswordLogin && (
                    <Button variant="link" className="h-auto whitespace-normal p-0 text-sm" asChild>
                      <Link to={generateLocalePath(RoutesConfig.passwordReset.index)}>
                        <FormattedMessage
                          defaultMessage="Forgot your password?"
                          id="Auth / login / reset password link"
                        />
                      </Link>
                    </Button>
                  )}
                </div>
                <p className="border-t pt-3 leading-relaxed text-muted-foreground">
                  {ENV.SUPPORT_EMAIL ? (
                    <FormattedMessage
                      defaultMessage="If you didn't create this account, contact us at {supportEmail} and we'll help verify ownership."
                      id="Auth / Social linking / Unconfirmed account - not owner"
                      values={{
                        supportEmail: (
                          <a
                            className="break-all font-medium text-foreground underline underline-offset-4"
                            href={`mailto:${ENV.SUPPORT_EMAIL}`}
                          >
                            {ENV.SUPPORT_EMAIL}
                          </a>
                        ),
                      }}
                    />
                  ) : (
                    <FormattedMessage
                      defaultMessage="If you didn't create this account, contact support and we'll help verify ownership."
                      id="Auth / Social linking / Unconfirmed account - not owner no email"
                    />
                  )}
                </p>
              </section>
            )}
            {socialStatus === 'failed' && (
              <p className="rounded-lg border p-4 text-sm text-destructive" role="alert">
                <FormattedMessage
                  defaultMessage="Social sign-in could not be completed. Please sign in with your password or passkey, or try again."
                  id="Auth / Social linking / Failed"
                />
              </p>
            )}
            {/* Passkey Login - top priority for enterprise users */}
            {showPasskeyLogin && <PasskeyLoginButton />}

            {/* Social Login Buttons */}
            {showSocialLogin && <SocialLoginButtons variant={SignupButtonsVariant.LOGIN} />}

            {/* Separator - only show if we have multiple auth methods */}
            {hasMultipleAuthMethods && showPasswordLogin && (
              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <Separator />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-background px-2 text-muted-foreground">
                    <FormattedMessage defaultMessage="Or continue with email" id="Auth / Login / or" />
                  </span>
                </div>
              </div>
            )}

            {/* Email/Password Login Form */}
            {showPasswordLogin && <LoginForm />}

            <div className="flex flex-col gap-2 text-center text-sm">
              {showPasswordLogin && (
                <div className="flex flex-row items-center justify-center gap-4">
                  <Button variant="link" className="h-auto p-0 text-sm" asChild>
                    <Link to={generateLocalePath(RoutesConfig.passwordReset.index)}>
                      <FormattedMessage
                        defaultMessage="Forgot your password?"
                        id="Auth / login / reset password link"
                      />
                    </Link>
                  </Button>
                </div>
              )}
              <div className="text-muted-foreground">
                <FormattedMessage defaultMessage="Don't have an account?" id="Auth / Login / signup prompt" />{' '}
                <Button variant="link" className="h-auto p-0 text-sm font-semibold" asChild>
                  <Link to={generateLocalePath(RoutesConfig.signup)}>
                    <FormattedMessage defaultMessage="Sign up" id="Auth / Login / signup link" />
                  </Link>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
};
