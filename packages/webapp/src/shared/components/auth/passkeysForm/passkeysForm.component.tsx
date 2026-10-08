import { getFragmentData } from '@sb/webapp-api-client/graphql';
import { commonQueryCurrentUserFragment, useCommonQuery } from '@sb/webapp-api-client/providers';
import { Button } from '@sb/webapp-core/components/buttons';
import { Input } from '@sb/webapp-core/components/forms';
import { Badge } from '@sb/webapp-core/components/ui/badge';
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
import { ENV } from '@sb/webapp-core/config/env';
import { useOpenState } from '@sb/webapp-core/hooks';
import { useToast } from '@sb/webapp-core/toast/useToast';
import { getPasskeyAuthorizationErrorMessage, useWebAuthn } from '@sb/webapp-sso/hooks';
import { useTenantPasskeys } from '@sb/webapp-tenants/hooks';
import { CheckCircle2, Fingerprint, Key, Loader2, Plus, Shield, Smartphone, Trash2, XCircle } from 'lucide-react';
import { useCallback, useId, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';

interface Passkey {
  id: string;
  name: string;
  authenticatorType: string;
  createdAt: string;
  lastUsedAt: string | null;
  useCount: number;
}

type RegistrationStep = 'name' | 'register' | 'success' | 'error';

const getAuthenticatorIcon = (type: string) => {
  switch (type) {
    case 'platform':
      return <Smartphone className="h-4 w-4" />;
    case 'cross-platform':
      return <Key className="h-4 w-4" />;
    default:
      return <Fingerprint className="h-4 w-4" />;
  }
};

export const PasskeysForm = () => {
  const intl = useIntl();
  const passwordInputId = useId();
  const { data: commonData } = useCommonQuery();
  const otpEnabled = getFragmentData(commonQueryCurrentUserFragment, commonData?.currentUser)?.otpEnabled === true;
  const { toast } = useToast();
  const { isOpen: isModalOpen, setIsOpen: setIsModalOpen } = useOpenState(false);

  const [deleting, setDeleting] = useState<string | null>(null);
  const [pendingChange, setPendingChange] = useState<{ action: 'register' | 'delete'; passkeyId?: string } | null>(
    null
  );
  const [password, setPassword] = useState('');
  const [otpToken, setOtpToken] = useState('');
  const [isAuthorizing, setIsAuthorizing] = useState(false);
  const { authorizePasskeyChange, registerPasskey } = useWebAuthn();

  const [passkeyName, setPasskeyName] = useState('');
  const [step, setStep] = useState<RegistrationStep>('name');
  const [isRegistering, setIsRegistering] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const isSupported = ENV.ENABLE_PASSKEYS && typeof window !== 'undefined' && !!window.PublicKeyCredential;

  const { passkeys, loading, refetch, deletePasskey } = useTenantPasskeys();

  const handleDeletePasskey = async (passkeyId: string, authorization: string) => {
    setDeleting(passkeyId);
    try {
      await deletePasskey({
        variables: { input: { id: passkeyId } },
        context: { headers: { 'X-Passkey-Authorization': authorization } },
      });
      toast({
        description: intl.formatMessage({
          defaultMessage: 'Passkey deleted.',
          id: 'Passkeys / Delete success',
        }),
        variant: 'success',
      });
    } catch {
      toast({
        description: intl.formatMessage({
          defaultMessage: 'Failed to delete passkey.',
          id: 'Passkeys / Delete error',
        }),
        variant: 'destructive',
      });
    } finally {
      setDeleting(null);
    }
  };

  const openModal = useCallback(() => {
    setPasskeyName('');
    setStep('name');
    setErrorMessage('');
    setIsModalOpen(true);
  }, [setIsModalOpen]);

  const closeModal = useCallback(() => {
    setIsModalOpen(false);
  }, [setIsModalOpen]);

  const handleContinue = () => {
    if (!passkeyName.trim()) return;
    setIsModalOpen(false);
    setPendingChange({ action: 'register' });
  };

  const handleRegister = useCallback(
    async (authorization: string) => {
      // Check if WebAuthn is supported
      if (!window.PublicKeyCredential) {
        setStep('error');
        setErrorMessage(
          intl.formatMessage({
            defaultMessage: 'Your browser does not support passkeys (WebAuthn).',
            id: 'Add Passkey Modal / Not Supported',
          })
        );
        return;
      }

      setIsRegistering(true);
      setErrorMessage('');

      try {
        if (!(await registerPasskey(passkeyName, authorization))) {
          throw new Error('Registration failed');
        }

        // Success!
        setStep('success');
        toast({
          description: intl.formatMessage({
            defaultMessage: 'Passkey registered successfully!',
            id: 'Add Passkey Modal / Success',
          }),
          variant: 'success',
        });

        // Refresh passkeys list and close modal after a delay
        setTimeout(() => {
          refetch();
          closeModal();
        }, 1500);
      } catch (error) {
        console.error('Passkey registration error:', error);
        setStep('error');

        let message = intl.formatMessage({
          defaultMessage: 'Failed to register passkey. Please try again.',
          id: 'Add Passkey Modal / Error Generic',
        });

        if (error instanceof Error) {
          if (error.name === 'NotAllowedError') {
            message = intl.formatMessage({
              defaultMessage: 'Registration was cancelled or timed out. Please try again.',
              id: 'Add Passkey Modal / Error Cancelled',
            });
          } else if (error.name === 'InvalidStateError') {
            message = intl.formatMessage({
              defaultMessage: 'This authenticator is already registered.',
              id: 'Add Passkey Modal / Error Already Registered',
            });
          } else if (error.name === 'NotSupportedError') {
            message = intl.formatMessage({
              defaultMessage: 'This authenticator type is not supported.',
              id: 'Add Passkey Modal / Error Not Supported',
            });
          }
        }

        setErrorMessage(message);
      } finally {
        setIsRegistering(false);
      }
    },
    [passkeyName, intl, toast, refetch, closeModal, registerPasskey]
  );

  const closeAuthorization = () => {
    setPendingChange(null);
    setPassword('');
    setOtpToken('');
  };

  const confirmChange = async (usePassword: boolean) => {
    if (!pendingChange || isAuthorizing) return;
    setIsAuthorizing(true);
    try {
      const authorization = await authorizePasskeyChange(
        pendingChange.action,
        pendingChange.passkeyId,
        usePassword ? password : undefined,
        usePassword && otpEnabled ? otpToken : undefined
      );
      const change = pendingChange;
      closeAuthorization();
      if (change.action === 'register') {
        setStep('register');
        setIsModalOpen(true);
        await handleRegister(authorization);
      } else {
        await handleDeletePasskey(change.passkeyId!, authorization);
      }
    } catch (error) {
      toast({
        variant: 'destructive',
        description: intl.formatMessage(getPasskeyAuthorizationErrorMessage(error)),
      });
      setPassword('');
      setOtpToken('');
    } finally {
      setIsAuthorizing(false);
    }
  };

  const handleRetry = () => {
    setStep('name');
    setErrorMessage('');
  };

  if (!isSupported) {
    return (
      <div className="rounded-lg border border-muted bg-muted/30 p-4 text-center">
        <Shield className="mx-auto mb-2 h-8 w-8 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">
          <FormattedMessage
            defaultMessage="Passkeys are not supported in this browser or have been disabled."
            id="Passkeys / Not supported"
          />
        </p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <>
      <Dialog
        open={pendingChange !== null}
        onOpenChange={(open) => {
          if (!open && !isAuthorizing) closeAuthorization();
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              <FormattedMessage defaultMessage="Verify your identity" id="Passkeys / Reauthentication title" />
            </DialogTitle>
            <DialogDescription>
              <FormattedMessage
                defaultMessage="To add or remove a passkey, verify an existing passkey or enter your account password and two-factor code if enabled. If you only use social login, set an account password using password reset first."
                id="Passkeys / Reauthentication description"
              />
            </DialogDescription>
          </DialogHeader>
          {passkeys.length > 0 && (
            <Button onClick={() => confirmChange(false)} disabled={isAuthorizing}>
              <FormattedMessage
                defaultMessage="Verify with an existing passkey"
                id="Passkeys / Verify existing passkey"
              />
            </Button>
          )}
          {passkeys.length > 0 && (
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <div className="h-px flex-1 bg-border" />
              <FormattedMessage defaultMessage="or" id="Passkeys / Or" />
              <div className="h-px flex-1 bg-border" />
            </div>
          )}
          <div className="space-y-3">
            <Label htmlFor={passwordInputId}>
              <FormattedMessage defaultMessage="Account password" id="Passkeys / Account password" />
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
              label={intl.formatMessage({ defaultMessage: 'Two-factor code', id: 'Passkeys / Two-factor code' })}
            />
          )}
          <DialogFooter>
            <Button variant="outline" onClick={closeAuthorization} disabled={isAuthorizing}>
              <FormattedMessage defaultMessage="Cancel" id="Common / Cancel" />
            </Button>
            <Button
              onClick={() => confirmChange(true)}
              disabled={isAuthorizing || !password || (otpEnabled && otpToken.length !== 6)}
            >
              <FormattedMessage defaultMessage="Verify with password" id="Passkeys / Verify password" />
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">
          <FormattedMessage
            defaultMessage="Passkeys let you sign in securely using your fingerprint, face, or device PIN - no password required."
            id="Passkeys / Description"
          />
        </p>

        {passkeys.length === 0 ? (
          <div className="rounded-lg border border-dashed border-muted-foreground/30 p-6 text-center">
            <Fingerprint className="mx-auto mb-3 h-10 w-10 text-muted-foreground" />
            <p className="mb-4 text-sm text-muted-foreground">
              <FormattedMessage
                defaultMessage="You haven't registered any passkeys yet. Add one for faster, more secure sign-in."
                id="Passkeys / Empty state"
              />
            </p>
            <Button onClick={openModal}>
              <Plus className="mr-2 h-4 w-4" />
              <FormattedMessage defaultMessage="Add Passkey" id="Passkeys / Add button" />
            </Button>
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {passkeys.map((passkey) => (
                <div key={passkey.id} className="flex items-center justify-between gap-3 rounded-lg border bg-card p-4">
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
                      {getAuthenticatorIcon(passkey.authenticatorType)}
                    </div>
                    <div className="min-w-0">
                      <div className="mb-1.5 flex min-w-0 items-center gap-2">
                        <p className="min-w-0 truncate font-medium" title={passkey.name}>
                          {passkey.name}
                        </p>
                        <Badge variant="outline" className="shrink-0 text-xs">
                          {passkey.authenticatorType === 'platform' ? (
                            <FormattedMessage defaultMessage="This device" id="Passkeys / Platform" />
                          ) : (
                            <FormattedMessage defaultMessage="Security key" id="Passkeys / Cross-platform" />
                          )}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                        <span>
                          <FormattedMessage
                            defaultMessage="Created {date}"
                            id="Passkeys / Created date"
                            values={{ date: intl.formatDate(passkey.createdAt as string) }}
                          />
                        </span>
                        <span>•</span>
                        <span>
                          {passkey.lastUsedAt != null ? (
                            <FormattedMessage
                              defaultMessage="Last used {date}"
                              id="Passkeys / Last used date"
                              values={{ date: intl.formatDate(passkey.lastUsedAt as string) }}
                            />
                          ) : (
                            <FormattedMessage defaultMessage="Never used" id="Passkeys / Never used" />
                          )}
                        </span>
                      </div>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    aria-label={intl.formatMessage({
                      defaultMessage: 'Remove passkey?',
                      id: 'Passkeys / Delete confirm title',
                    })}
                    onClick={() => setPendingChange({ action: 'delete', passkeyId: passkey.id })}
                    disabled={deleting === passkey.id || isAuthorizing}
                    className="shrink-0 text-destructive hover:bg-destructive/10 hover:text-destructive dark:text-red-400"
                  >
                    {deleting === passkey.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              ))}
            </div>

            <Button variant="outline" onClick={openModal}>
              <Plus className="mr-2 h-4 w-4" />
              <FormattedMessage defaultMessage="Add another passkey" id="Passkeys / Add another" />
            </Button>
          </>
        )}
      </div>

      {/* Add Passkey Modal */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-[450px]" aria-describedby="passkey-dialog-description">
          {/* Visually hidden but accessible title and description for screen readers */}
          <DialogTitle className="sr-only">
            <FormattedMessage defaultMessage="Register a Passkey" id="Add Passkey Modal / Title" />
          </DialogTitle>
          <DialogDescription id="passkey-dialog-description" className="sr-only">
            <FormattedMessage defaultMessage="Secure, passwordless sign-in" id="Add Passkey Modal / Subtitle" />
          </DialogDescription>
          <div className="-m-6 flex h-[85vh] max-h-[500px] flex-col overflow-hidden sm:rounded-lg">
            {/* Fixed Header */}
            <div className="flex shrink-0 items-center gap-3 border-b bg-background px-6 py-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10">
                <Fingerprint className="h-5 w-5 text-primary" />
              </div>
              <div className="mr-8">
                <h2 className="text-lg font-semibold" aria-hidden="true">
                  <FormattedMessage defaultMessage="Register a Passkey" id="Add Passkey Modal / Title" />
                </h2>
                <p className="text-sm text-muted-foreground" aria-hidden="true">
                  <FormattedMessage defaultMessage="Secure, passwordless sign-in" id="Add Passkey Modal / Subtitle" />
                </p>
              </div>
            </div>

            {/* Scrollable Content */}
            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              {step === 'name' && (
                <div className="space-y-6">
                  {/* Benefits */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="flex flex-col items-center rounded-lg bg-muted/30 p-3 text-center">
                      <Fingerprint className="mb-2 h-6 w-6 text-primary" />
                      <span className="text-xs font-medium">
                        <FormattedMessage defaultMessage="Biometrics" id="Add Passkey Modal / Biometrics" />
                      </span>
                    </div>
                    <div className="flex flex-col items-center rounded-lg bg-muted/30 p-3 text-center">
                      <Shield className="mb-2 h-6 w-6 text-primary" />
                      <span className="text-xs font-medium">
                        <FormattedMessage defaultMessage="Phishing-Proof" id="Add Passkey Modal / Phishing Proof" />
                      </span>
                    </div>
                    <div className="flex flex-col items-center rounded-lg bg-muted/30 p-3 text-center">
                      <Key className="mb-2 h-6 w-6 text-primary" />
                      <span className="text-xs font-medium">
                        <FormattedMessage defaultMessage="No Password" id="Add Passkey Modal / No Password" />
                      </span>
                    </div>
                  </div>

                  {/* Name Input */}
                  <div className="space-y-3">
                    <Label htmlFor="passkey-name" className="text-sm font-medium">
                      <FormattedMessage defaultMessage="Give your passkey a name" id="Add Passkey Modal / Name Label" />
                    </Label>
                    <Input
                      id="passkey-name"
                      placeholder={intl.formatMessage({
                        defaultMessage: 'e.g., MacBook Touch ID, iPhone Face ID',
                        id: 'Add Passkey Modal / Name Placeholder',
                      })}
                      value={passkeyName}
                      onChange={(e) => setPasskeyName(e.target.value)}
                      autoFocus
                    />
                    <p className="text-xs text-muted-foreground">
                      <FormattedMessage
                        defaultMessage="This helps you identify your passkeys if you have multiple devices."
                        id="Add Passkey Modal / Name Help"
                      />
                    </p>
                  </div>

                  {/* Supported Devices */}
                  <div className="rounded-lg border bg-muted/30 p-4">
                    <div className="flex gap-3">
                      <Smartphone className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                      <div className="text-sm text-muted-foreground">
                        <p className="mb-1 font-medium text-foreground">
                          <FormattedMessage defaultMessage="Works with" id="Add Passkey Modal / Works With" />
                        </p>
                        <FormattedMessage
                          defaultMessage="Touch ID, Face ID, Windows Hello, Android Fingerprint, and hardware security keys like YubiKey."
                          id="Add Passkey Modal / Works With Description"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {step === 'register' && (
                <div className="flex h-full flex-col items-center justify-center space-y-6 py-8">
                  <div className="flex h-24 w-24 animate-pulse items-center justify-center rounded-full bg-primary/10">
                    <Fingerprint className="h-12 w-12 text-primary" />
                  </div>
                  <div className="space-y-2 text-center">
                    <h3 className="text-lg font-semibold">
                      <FormattedMessage
                        defaultMessage="Complete registration on your device"
                        id="Add Passkey Modal / Register Title"
                      />
                    </h3>
                    <p className="max-w-[300px] text-sm text-muted-foreground">
                      <FormattedMessage
                        defaultMessage="When prompted, use Touch ID, Face ID, or your security key to register."
                        id="Add Passkey Modal / Register Description"
                      />
                    </p>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <span className="rounded bg-muted px-2 py-1 font-mono text-xs">{passkeyName}</span>
                  </div>
                  {isRegistering && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <FormattedMessage
                        defaultMessage="Waiting for authenticator..."
                        id="Add Passkey Modal / Waiting"
                      />
                    </div>
                  )}
                </div>
              )}

              {step === 'success' && (
                <div className="flex h-full flex-col items-center justify-center space-y-6 py-8">
                  <div className="flex h-24 w-24 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
                    <CheckCircle2 className="h-12 w-12 text-green-600 dark:text-green-400" />
                  </div>
                  <div className="space-y-2 text-center">
                    <h3 className="text-lg font-semibold text-green-700 dark:text-green-300">
                      <FormattedMessage defaultMessage="Passkey Registered!" id="Add Passkey Modal / Success Title" />
                    </h3>
                    <p className="max-w-[300px] text-sm text-muted-foreground">
                      <FormattedMessage
                        defaultMessage="You can now use this passkey to sign in securely without a password."
                        id="Add Passkey Modal / Success Description"
                      />
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Key className="h-4 w-4 text-muted-foreground" />
                    <span className="text-sm font-medium">{passkeyName}</span>
                  </div>
                </div>
              )}

              {step === 'error' && (
                <div className="flex h-full flex-col items-center justify-center space-y-6 py-8">
                  <div className="flex h-24 w-24 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
                    <XCircle className="h-12 w-12 text-red-600 dark:text-red-400" />
                  </div>
                  <div className="space-y-2 text-center">
                    <h3 className="text-lg font-semibold text-red-700 dark:text-red-300">
                      <FormattedMessage defaultMessage="Registration Failed" id="Add Passkey Modal / Error Title" />
                    </h3>
                    <p className="max-w-[300px] text-sm text-muted-foreground">{errorMessage}</p>
                  </div>
                </div>
              )}
            </div>

            {/* Fixed Footer */}
            <div className="flex shrink-0 gap-3 border-t bg-background px-6 py-4">
              {step === 'name' && (
                <>
                  <Button type="button" variant="outline" onClick={closeModal} className="flex-1">
                    <FormattedMessage defaultMessage="Cancel" id="Add Passkey Modal / Cancel Button" />
                  </Button>
                  <Button type="button" onClick={handleContinue} className="flex-1" disabled={!passkeyName.trim()}>
                    <FormattedMessage defaultMessage="Continue" id="Add Passkey Modal / Continue Button" />
                  </Button>
                </>
              )}

              {step === 'register' && (
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setStep('name')}
                  className="w-full"
                  disabled={isRegistering}
                >
                  <FormattedMessage defaultMessage="Cancel" id="Add Passkey Modal / Cancel Registration" />
                </Button>
              )}

              {step === 'success' && (
                <Button type="button" onClick={closeModal} className="w-full">
                  <FormattedMessage defaultMessage="Done" id="Add Passkey Modal / Done Button" />
                </Button>
              )}

              {step === 'error' && (
                <>
                  <Button type="button" variant="outline" onClick={closeModal} className="flex-1">
                    <FormattedMessage defaultMessage="Cancel" id="Add Passkey Modal / Cancel Error" />
                  </Button>
                  <Button type="button" onClick={handleRetry} className="flex-1">
                    <FormattedMessage defaultMessage="Try Again" id="Add Passkey Modal / Retry Button" />
                  </Button>
                </>
              )}
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};
