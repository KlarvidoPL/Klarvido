import { VariantProps } from 'class-variance-authority';
import { MouseEvent, PropsWithChildren, ReactNode, useCallback, useEffect, useState } from 'react';
import { FormattedMessage } from 'react-intl';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '../ui/alert-dialog';
import { buttonVariants } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';

export interface ConfirmDialogProps extends PropsWithChildren {
  onContinue: (e: MouseEvent<HTMLButtonElement>) => void | Promise<boolean | void>;
  content?: ReactNode;
  additionalAction?: ReactNode;
  additionalActionSeparator?: ReactNode;
  feedback?: ReactNode;
  hideContinue?: boolean;
  continueDisabled?: boolean;
  closeOnContinue?: boolean;
  onCancel?: (e: MouseEvent<HTMLButtonElement>) => void;
  title: ReactNode;
  description?: ReactNode;
  continueLabel?: ReactNode;
  cancelLabel?: ReactNode;
  variant?: VariantProps<typeof buttonVariants>['variant'];
  /** Controlled open state */
  open?: boolean;
  /** Controlled open change handler */
  onOpenChange?: (open: boolean) => void;
  /**
   * When provided, the user must type this exact text before Continue becomes enabled.
   * Intended for highly destructive actions (e.g. "DELETE my-org-name").
   */
  confirmationText?: string;
  /** Overrides the default "Type {confirmationText} to confirm" label. */
  confirmationLabel?: ReactNode;
}

export const ConfirmDialog = ({
  children,
  title,
  description,
  continueLabel,
  cancelLabel,
  onCancel,
  onContinue,
  variant = 'default',
  open: controlledOpen,
  onOpenChange: controlledOnOpenChange,
  confirmationText,
  confirmationLabel,
  content,
  additionalAction,
  additionalActionSeparator,
  feedback,
  hideContinue = false,
  continueDisabled = false,
  closeOnContinue = true,
}: ConfirmDialogProps) => {
  const [internalOpen, setInternalOpen] = useState(false);
  const [confirmationInput, setConfirmationInput] = useState('');

  // Support both controlled and uncontrolled modes
  const isControlled = controlledOpen !== undefined;
  const open = isControlled ? controlledOpen : internalOpen;
  const setOpen = useCallback(
    (value: boolean) => {
      if (!isControlled) setInternalOpen(value);
      controlledOnOpenChange?.(value);
    },
    [isControlled, controlledOnOpenChange]
  );

  // Reset the typed confirmation whenever the dialog closes, so reopening starts fresh.
  useEffect(() => {
    if (!open) {
      setConfirmationInput('');
    }
  }, [open]);

  const isConfirmationRequired = confirmationText !== undefined;
  const isConfirmed = !isConfirmationRequired || confirmationInput === confirmationText;

  const onClick = (e: MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    e.preventDefault();
    setOpen(true);
  };
  const handleCancel = useCallback(
    (e: MouseEvent<HTMLButtonElement>) => {
      setOpen(false);
      onCancel?.(e);
    },
    [onCancel, setOpen]
  );
  const handleContinue = useCallback(
    async (e: MouseEvent<HTMLButtonElement>) => {
      if (closeOnContinue) {
        setOpen(false);
        onContinue(e);
      } else {
        e.preventDefault();
        if (await onContinue(e)) setOpen(false);
      }
    },
    [onContinue, setOpen, closeOnContinue]
  );

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      {/* Only render trigger when in uncontrolled mode with children */}
      {!isControlled && children && (
        <AlertDialogTrigger asChild onClick={onClick}>
          {children}
        </AlertDialogTrigger>
      )}
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {description && <AlertDialogDescription>{description}</AlertDialogDescription>}
        </AlertDialogHeader>
        {isConfirmationRequired && (
          <div className="space-y-2">
            <Label htmlFor="confirm-dialog-confirmation-input">
              {confirmationLabel ?? (
                <FormattedMessage
                  id="Confirm Dialog / Confirmation input label"
                  defaultMessage="Type {confirmationText} to confirm"
                  values={{ confirmationText: <strong>{confirmationText}</strong> }}
                />
              )}
            </Label>
            <Input
              id="confirm-dialog-confirmation-input"
              value={confirmationInput}
              onChange={(e) => setConfirmationInput(e.target.value)}
              autoComplete="off"
              autoFocus
            />
          </div>
        )}
        {content}
        {additionalAction && (
          <div className="space-y-4">
            <div className="flex items-center gap-3" aria-hidden={!additionalActionSeparator}>
              <span className="bg-border h-px flex-1" />
              {additionalActionSeparator && (
                <span className="text-muted-foreground text-sm">{additionalActionSeparator}</span>
              )}
              <span className="bg-border h-px flex-1" />
            </div>
            {additionalAction}
          </div>
        )}
        {feedback}
        <AlertDialogFooter>
          <AlertDialogCancel onClick={handleCancel}>
            {cancelLabel ?? <FormattedMessage id="Confirm Dialog / Cancel label" defaultMessage="Cancel" />}
          </AlertDialogCancel>
          {!hideContinue && (
            <AlertDialogAction
              className={buttonVariants({ variant })}
              onClick={handleContinue}
              disabled={!isConfirmed || continueDisabled}
            >
              {continueLabel ?? <FormattedMessage id="Confirm Dialog / Continue label" defaultMessage="Continue" />}
            </AlertDialogAction>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
