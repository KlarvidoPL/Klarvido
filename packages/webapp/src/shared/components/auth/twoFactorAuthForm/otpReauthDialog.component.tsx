import { getFragmentData } from '@sb/webapp-api-client/graphql';
import { commonQueryCurrentUserFragment, useCommonQuery } from '@sb/webapp-api-client/providers';
import { Button } from '@sb/webapp-core/components/buttons';
import { Input } from '@sb/webapp-core/components/forms';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@sb/webapp-core/components/ui/dialog';
import { Label } from '@sb/webapp-core/components/ui/label';
import { OtpInput } from '@sb/webapp-core/components/ui/otpInput';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { getPasskeyAuthorizationErrorMessage, useWebAuthn } from '@sb/webapp-sso/hooks';
import { useTenantPasskeys } from '@sb/webapp-tenants/hooks';
import { useId, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

export type OtpManagementAction = 'otp_setup' | 'otp_disable';

export type OtpReauthDialogProps = {
  open: boolean;
  action: OtpManagementAction;
  onClose: () => void;
  onAuthorized: (authorization: string) => void;
};

/**
 * Fresh-auth gate shared by 2FA enable/replace and disable. Mirrors the dialog in
 * PasskeysForm: password (+ current code, if one is already active) or an existing
 * passkey. An account with neither a password nor a passkey can only prove its
 * current, already-active OTP code - shown as a reduced, code-only variant.
 */
export const OtpReauthDialog = ({ open, action, onClose, onAuthorized }: OtpReauthDialogProps) => {
  const intl = useIntl();
  const passwordInputId = useId();
  const { toast } = useToast();
  const { data: commonData } = useCommonQuery();
  const currentUser = getFragmentData(commonQueryCurrentUserFragment, commonData?.currentUser);
  const otpEnabled = currentUser?.otpEnabled === true;
  const hasUsablePassword = currentUser?.hasUsablePassword === true;
  const { passkeys } = useTenantPasskeys();
  const { authorizePasskeyChange, authorizeOtpOnly } = useWebAuthn();

  const [password, setPassword] = useState('');
  const [otpToken, setOtpToken] = useState('');
  const [isAuthorizing, setIsAuthorizing] = useState(false);

  const canReauthenticate = hasUsablePassword || passkeys.length > 0;

  const reset = () => {
    setPassword('');
    setOtpToken('');
  };

  const close = () => {
    if (isAuthorizing) return;
    reset();
    onClose();
  };

  const submit = async (usePasskey: boolean) => {
    if (isAuthorizing) return;
    setIsAuthorizing(true);
    try {
      const authorization = canReauthenticate
        ? await authorizePasskeyChange(action, undefined, usePasskey ? undefined : password, otpEnabled ? otpToken : undefined)
        : await authorizeOtpOnly(action, otpToken);
      reset();
      onAuthorized(authorization);
    } catch (error) {
      toast({
        variant: 'destructive',
        description: intl.formatMessage(getPasskeyAuthorizationErrorMessage(error)),
      });
      setOtpToken('');
    } finally {
      setIsAuthorizing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(isOpen) => !isOpen && close()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            <FormattedMessage defaultMessage="Verify your identity" id="Auth / Two-factor / Reauth title" />
          </DialogTitle>
          <DialogDescription>
            {canReauthenticate ? (
              <FormattedMessage
                defaultMessage="Verify an existing passkey or enter your account password{otp} to continue."
                id="Auth / Two-factor / Reauth description"
                values={{
                  otp: otpEnabled
                    ? intl.formatMessage({
                        defaultMessage: ' and two-factor code',
                        id: 'Auth / Two-factor / Reauth description and code',
                      })
                    : '',
                }}
              />
            ) : (
              <FormattedMessage
                defaultMessage="Enter your current two-factor code to continue."
                id="Auth / Two-factor / Reauth otp-only description"
              />
            )}
          </DialogDescription>
        </DialogHeader>
        {canReauthenticate ? (
          <>
            {passkeys.length > 0 && (
              <Button onClick={() => submit(true)} disabled={isAuthorizing}>
                <FormattedMessage
                  defaultMessage="Verify with an existing passkey"
                  id="Auth / Two-factor / Reauth verify passkey"
                />
              </Button>
            )}
            {passkeys.length > 0 && (
              <div className="flex items-center gap-3 text-sm text-muted-foreground">
                <div className="h-px flex-1 bg-border" />
                <FormattedMessage defaultMessage="or" id="Auth / Two-factor / Reauth or" />
                <div className="h-px flex-1 bg-border" />
              </div>
            )}
            <div className="space-y-3">
              <Label htmlFor={passwordInputId}>
                <FormattedMessage defaultMessage="Account password" id="Auth / Two-factor / Reauth password label" />
              </Label>
              <Input
                id={passwordInputId}
                type="password"
                autoComplete="current-password"
                value={password}
                disabled={isAuthorizing}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {otpEnabled && (
              <OtpInput
                value={otpToken}
                onValueChange={setOtpToken}
                disabled={isAuthorizing}
                label={intl.formatMessage({
                  defaultMessage: 'Current two-factor code',
                  id: 'Auth / Two-factor / Reauth otp label',
                })}
              />
            )}
            <DialogFooter>
              <Button variant="outline" onClick={close} disabled={isAuthorizing}>
                <FormattedMessage defaultMessage="Cancel" id="Common / Cancel" />
              </Button>
              <Button
                onClick={() => submit(false)}
                disabled={isAuthorizing || !password || (otpEnabled && otpToken.length !== 6)}
              >
                <FormattedMessage defaultMessage="Verify with password" id="Auth / Two-factor / Reauth verify password" />
              </Button>
            </DialogFooter>
          </>
        ) : (
          <>
            <OtpInput
              value={otpToken}
              onValueChange={setOtpToken}
              disabled={isAuthorizing}
              label={intl.formatMessage({
                defaultMessage: 'Current two-factor code',
                id: 'Auth / Two-factor / Reauth otp label',
              })}
            />
            <DialogFooter>
              <Button variant="outline" onClick={close} disabled={isAuthorizing}>
                <FormattedMessage defaultMessage="Cancel" id="Common / Cancel" />
              </Button>
              <Button onClick={() => submit(false)} disabled={isAuthorizing || otpToken.length !== 6}>
                <FormattedMessage defaultMessage="Verify" id="Auth / Two-factor / Reauth verify otp only" />
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
