import { csrfFetch } from '@sb/webapp-api-client/api/csrf';
import { Button } from '@sb/webapp-core/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@sb/webapp-core/components/ui/dialog';
import { Input } from '@sb/webapp-core/components/ui/input';
import { Label } from '@sb/webapp-core/components/ui/label';
import { OtpInput } from '@sb/webapp-core/components/ui/otpInput';
import { ENV } from '@sb/webapp-core/config/env';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { getPasskeyAuthorizationErrorMessage, useWebAuthn } from '@sb/webapp-sso/hooks';
import { Link2 } from 'lucide-react';
import { useEffect, useId, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router-dom';

import { RoutesConfig } from '../../../../app/config/routes';
import { GoogleIcon } from '../../../../images/icons';

type SocialAccount = { id: string; provider: string; canUnlink: boolean };
type SocialAccountState = { accounts: SocialAccount[]; hasPasskey: boolean; hasPassword: boolean; otpEnabled: boolean };
const providers: Record<string, string> = { 'google-oauth2': 'Google', facebook: 'Facebook' };
const providerIcons: Record<string, typeof GoogleIcon> = { 'google-oauth2': GoogleIcon };

export const SocialAccounts = () => {
  const intl = useIntl();
  const navigate = useNavigate();
  const localePath = useGenerateLocalePath();
  const { toast } = useToast();
  const passwordId = useId();
  const { unlinkSocialAccount, isSupported } = useWebAuthn();
  const [data, setData] = useState<SocialAccountState | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [selected, setSelected] = useState<SocialAccount | null>(null);
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let active = true;
    csrfFetch(`${ENV.BASE_API_URL}/auth/social-accounts/`)
      .then(async (response) => {
        if (!response.ok) throw new Error('Unable to load accounts');
        const result = await response.json();
        if (active) setData(result);
      })
      .catch(() => {
        if (active) setLoadFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const close = () => {
    setSelected(null);
    setPassword('');
    setOtp('');
  };
  const unlink = async (withPassword: boolean) => {
    if (!selected || busy) return;
    setBusy(true);
    try {
      await unlinkSocialAccount(
        selected.id,
        withPassword ? password : undefined,
        withPassword && data?.otpEnabled ? otp : undefined
      );
      close();
      toast({
        variant: 'success',
        description: intl.formatMessage({
          id: 'Social accounts / Disconnected',
          defaultMessage: 'Social sign-in disconnected. Please sign in again.',
        }),
      });
      navigate(localePath(RoutesConfig.logout), { replace: true });
    } catch (error) {
      toast({ variant: 'destructive', description: intl.formatMessage(getPasskeyAuthorizationErrorMessage(error)) });
      setPassword('');
      setOtp('');
    } finally {
      setBusy(false);
    }
  };

  if (loadFailed)
    return (
      <p role="alert">
        <FormattedMessage
          id="Social accounts / Load failed"
          defaultMessage="Unable to load connected accounts. Please refresh and try again."
        />
      </p>
    );
  if (!data)
    return (
      <p role="status">
        <FormattedMessage id="Social accounts / Loading" defaultMessage="Loading connected accounts…" />
      </p>
    );

  return (
    <div className="space-y-4">
      {data.accounts.length === 0 && (
        <div className="rounded-lg border border-dashed border-muted-foreground/30 p-6 text-center">
          <Link2 className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            <FormattedMessage id="Social accounts / Empty" defaultMessage="No social sign-in accounts are connected." />
          </p>
        </div>
      )}
      {data.accounts.map((account) => {
        const ProviderIcon = providerIcons[account.provider];
        return (
          <div key={account.id} className="flex items-center justify-between gap-4 rounded-lg border p-4">
            <span className="flex items-center gap-2">
              {ProviderIcon && <ProviderIcon size={18} className="h-[18px] w-[18px]" />}
              {providers[account.provider] ?? account.provider}
            </span>
            <Button variant="outline" disabled={!account.canUnlink} onClick={() => setSelected(account)}>
              <FormattedMessage id="Social accounts / Disconnect" defaultMessage="Disconnect" />
            </Button>
          </div>
        );
      })}
      {data.accounts.some((account) => !account.canUnlink) && (
        <p className="text-sm text-muted-foreground">
          <FormattedMessage
            id="Social accounts / Last method"
            defaultMessage="Add a password or passkey before disconnecting your last sign-in method."
          />
        </p>
      )}
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open && !busy) close();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              <FormattedMessage id="Social accounts / Confirm title" defaultMessage="Disconnect social sign-in" />
            </DialogTitle>
            <DialogDescription>
              <FormattedMessage
                id="Social accounts / Confirm description"
                defaultMessage="Confirm with your account password and two-factor code if enabled, or a passkey. Disconnecting signs you out on all devices."
              />
            </DialogDescription>
          </DialogHeader>
          {data.hasPasskey && isSupported && ENV.ENABLE_PASSKEYS && (
            <Button disabled={busy} onClick={() => unlink(false)}>
              <FormattedMessage
                id="Passkeys / Reauthenticate passkey"
                defaultMessage="Verify with an existing passkey"
              />
            </Button>
          )}
          {data.hasPassword ? (
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void unlink(true);
              }}
            >
              <div className="space-y-2">
                <Label htmlFor={passwordId}>
                  <FormattedMessage id="Passkeys / Account password" defaultMessage="Account password" />
                </Label>
                <Input
                  id={passwordId}
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={busy}
                />
              </div>
              {data.otpEnabled && (
                <OtpInput
                  value={otp}
                  onValueChange={setOtp}
                  disabled={busy}
                  label={intl.formatMessage({ id: 'Passkeys / Two-factor code', defaultMessage: 'Two-factor code' })}
                />
              )}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="outline" onClick={close} disabled={busy}>
                  <FormattedMessage id="Common / Cancel" defaultMessage="Cancel" />
                </Button>
                <Button type="submit" disabled={busy || !password || (data.otpEnabled && otp.length !== 6)}>
                  <FormattedMessage id="Social accounts / Disconnect" defaultMessage="Disconnect" />
                </Button>
              </div>
            </form>
          ) : (
            <p className="text-sm text-muted-foreground">
              <FormattedMessage
                id="Social accounts / Password needed"
                defaultMessage="Use an existing passkey, or set a password through password reset before disconnecting."
              />
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
