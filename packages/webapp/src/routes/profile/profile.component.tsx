import { useMutation } from '@apollo/client/react';
import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Paragraph } from '@sb/webapp-core/components/typography';
import { Badge } from '@sb/webapp-core/components/ui/badge';
import { Button } from '@sb/webapp-core/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { Separator } from '@sb/webapp-core/components/ui/separator';
import { useToast } from '@sb/webapp-core/toast/useToast';
import {
  AlertTriangle,
  Crown,
  Fingerprint,
  Link2,
  Lock,
  Mail,
  Monitor,
  RefreshCw,
  Shield,
  User,
  UserCircle,
} from 'lucide-react';
import { Helmet } from 'react-helmet-async';
import { FormattedMessage, useIntl } from 'react-intl';

import { ActiveSessions } from '../../shared/components/auth/activeSessions';
import { AvatarForm } from '../../shared/components/auth/avatarForm';
import { ChangePasswordForm } from '../../shared/components/auth/changePasswordForm';
import { EditProfileForm } from '../../shared/components/auth/editProfileForm';
import { PasskeysForm } from '../../shared/components/auth/passkeysForm';
import { SocialAccounts } from '../../shared/components/auth/socialAccounts/socialAccounts.component';
import { TwoFactorAuthForm } from '../../shared/components/auth/twoFactorAuthForm';
import { useAuth } from '../../shared/hooks';
import { profileResendConfirmationEmailMutation } from './profile.graphql';

export const Profile = () => {
  const intl = useIntl();
  const { currentUser } = useAuth();
  const { toast } = useToast();

  const resendSuccessMessage = intl.formatMessage({
    defaultMessage: 'Verification email sent. Please check your inbox.',
    id: 'Profile / Email / Resend success',
  });
  const resendErrorMessage = intl.formatMessage({
    defaultMessage: 'Failed to send verification email. Please try again.',
    id: 'Profile / Email / Resend error',
  });

  const [commitResendConfirmationEmail, { loading: resendLoading }] = useMutation(
    profileResendConfirmationEmailMutation,
    {
      onCompleted: () => {
        toast({ description: resendSuccessMessage, variant: 'success' });
      },
      onError: () => {
        toast({ description: resendErrorMessage, variant: 'destructive' });
      },
    }
  );

  const resendConfirmationEmail = () => {
    commitResendConfirmationEmail({ variables: { input: {} } });
  };

  return (
    <PageLayout>
      <Helmet
        title={intl.formatMessage({
          defaultMessage: 'Profile Settings',
          id: 'Profile / page title',
        })}
      />

      <div className="mx-auto w-full max-w-5xl space-y-8">
        {/* Hero Section */}
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <User className="h-6 w-6 text-primary" />
            <h1 className="text-3xl font-bold tracking-tight">
              <FormattedMessage defaultMessage="User profile" id="Auth / Profile details / Header" />
            </h1>
          </div>
          <Paragraph className="text-lg text-muted-foreground">
            <FormattedMessage
              defaultMessage="Here you can find more information about your account and edit it"
              id="Auth / Profile details / Label"
            />
          </Paragraph>
        </div>

        {/* Profile Overview Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <UserCircle className="h-5 w-5" />
              <FormattedMessage defaultMessage="Profile Overview" id="Profile / Overview / Title" />
            </CardTitle>
            <CardDescription>
              <FormattedMessage defaultMessage="Your account information" id="Profile / Overview / Description" />
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex flex-col gap-6 sm:flex-row sm:items-start">
              <div className="flex-shrink-0">
                <AvatarForm />
              </div>
              <div className="flex-1 space-y-4">
                <div className="space-y-1">
                  <div className="text-sm font-medium text-muted-foreground">
                    <FormattedMessage defaultMessage="Name" id="Profile / Name / Label" />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Paragraph className="text-base">
                      {currentUser?.firstName} {currentUser?.lastName}
                    </Paragraph>
                    {currentUser?.isSuperuser && (
                      <Badge
                        variant="outline"
                        className="gap-1 border-violet-500/20 bg-violet-500/15 text-xs font-medium text-violet-700 dark:text-violet-400"
                      >
                        <Crown className="h-3 w-3" />
                        <FormattedMessage defaultMessage="Superuser" id="Profile / Name / Superuser badge" />
                      </Badge>
                    )}
                  </div>
                </div>
                <Separator />
                <div className="space-y-1">
                  <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                    <Mail className="h-4 w-4" />
                    <FormattedMessage defaultMessage="Email" id="Profile / Email / Label" />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Paragraph className="text-base">{currentUser?.email}</Paragraph>
                    {currentUser && !currentUser.isConfirmed && (
                      <>
                        <Badge
                          variant="outline"
                          className="gap-1 border-amber-500/20 bg-amber-500/15 text-xs font-medium text-amber-700 dark:text-amber-400"
                        >
                          <AlertTriangle className="h-3 w-3" />
                          <FormattedMessage defaultMessage="Not verified" id="Profile / Email / Not verified" />
                        </Badge>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-amber-700 hover:bg-amber-500/10 hover:text-amber-800 dark:text-amber-400 dark:hover:bg-amber-500/10 dark:hover:text-amber-300"
                          onClick={resendConfirmationEmail}
                          disabled={resendLoading}
                        >
                          <RefreshCw className={`mr-1.5 h-4 w-4 ${resendLoading ? 'animate-spin' : ''}`} />
                          <FormattedMessage
                            defaultMessage="Resend verification email"
                            id="Profile / Email / Resend verification"
                          />
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Personal Data Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <User className="h-5 w-5" />
              <FormattedMessage defaultMessage="Personal data" id="Auth / Profile details / Personal data header" />
            </CardTitle>
            <CardDescription>
              <FormattedMessage
                defaultMessage="Update your account details"
                id="Auth / Profile details / Personal data label"
              />
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EditProfileForm />
          </CardContent>
        </Card>

        {/* Change Password Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Lock className="h-5 w-5" />
              <FormattedMessage defaultMessage="Change password" id="Auth / Profile details / Change password header" />
            </CardTitle>
            <CardDescription>
              <FormattedMessage
                defaultMessage="Update your password"
                id="Auth / Profile details / Change password label"
              />
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ChangePasswordForm hasUsablePassword={currentUser?.hasUsablePassword ?? true} />
          </CardContent>
        </Card>

        {/* Two-Factor Authentication Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              <FormattedMessage
                defaultMessage="Two-factor Authentication"
                id="Auth / Profile details / Two-factor Authentication header"
              />
            </CardTitle>
            <CardDescription>
              <FormattedMessage
                defaultMessage="Enable 2FA on your account"
                id="Auth / Profile details / Two-factor Authentication label"
              />
            </CardDescription>
          </CardHeader>
          <CardContent>
            <TwoFactorAuthForm isEnabled={currentUser?.otpEnabled} />
          </CardContent>
        </Card>

        {/* Passkeys Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Fingerprint className="h-5 w-5" />
              <FormattedMessage defaultMessage="Passkeys" id="Auth / Profile details / Passkeys header" />
            </CardTitle>
            <CardDescription>
              <FormattedMessage
                defaultMessage="Sign in with your fingerprint, face, or device PIN"
                id="Auth / Profile details / Passkeys label"
              />
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PasskeysForm />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Link2 className="h-5 w-5" />
              <FormattedMessage id="Social accounts / Title" defaultMessage="Connected social accounts" />
            </CardTitle>
            <CardDescription>
              <FormattedMessage
                id="Social accounts / Description"
                defaultMessage="Manage Google sign-in for your account."
              />
            </CardDescription>
          </CardHeader>
          <CardContent>
            <SocialAccounts />
          </CardContent>
        </Card>

        {/* Active Sessions Card */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Monitor className="h-5 w-5" />
              <FormattedMessage defaultMessage="Active Sessions" id="Auth / Profile details / Sessions header" />
            </CardTitle>
            <CardDescription>
              <FormattedMessage
                defaultMessage="View and manage your active sign-in sessions across devices"
                id="Auth / Profile details / Sessions label"
              />
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ActiveSessions />
          </CardContent>
        </Card>
      </div>
    </PageLayout>
  );
};
