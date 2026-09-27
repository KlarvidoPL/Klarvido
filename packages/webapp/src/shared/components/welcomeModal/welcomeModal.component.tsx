import { Button } from '@sb/webapp-core/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@sb/webapp-core/components/ui/dialog';
import confetti from 'canvas-confetti';
import { ArrowRight, CheckCircle2, Mail, Rocket, User } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { FormattedMessage } from 'react-intl';

const CONFETTI_COLORS = ['#FFFE25', '#42F272', '#71F85D', '#A0FA4B', '#D4F81D'];
const STORAGE_KEY = 'sb_show_welcome_modal';
// Matches settings.NEW_SIGNUP_COOKIE - a short-lived, non-httponly cookie set by
// the backend only on a brand new OAuth signup. Unlike the password-signup flow
// (a client-side mutation that can call triggerWelcomeModal() directly), OAuth
// signup is a full backend redirect that can land on any page depending on the
// auth-route bounce logic, so a cookie is used instead of a query param, which a
// client-side redirect could easily drop along the way.
const OAUTH_NEW_SIGNUP_COOKIE = 'new_signup';

const hasOAuthNewSignupCookie = () =>
  document.cookie.split('; ').some((cookie) => cookie.split('=')[0] === OAUTH_NEW_SIGNUP_COOKIE);

// The backend sets this cookie scoped to the shared parent domain (e.g.
// .klarvido.com), not just this page's own host, since it's set from a response
// on the API's subdomain but read here on the webapp's subdomain. Clearing it
// without matching that same domain would just set an unrelated, host-scoped
// cookie instead of removing the original - it'd still be visible (and reopen
// the modal) on a refresh until its own short max-age expires server-side.
const getCookieClearDomain = () => {
  const { hostname } = window.location;
  if (hostname === 'localhost' || /^\d+\.\d+\.\d+\.\d+$/.test(hostname)) return '';
  const labels = hostname.split('.');
  return labels.length > 2 ? `.${labels.slice(-2).join('.')}` : `.${hostname}`;
};

const clearOAuthNewSignupCookie = () => {
  const domain = getCookieClearDomain();
  document.cookie = `${OAUTH_NEW_SIGNUP_COOKIE}=; path=/; max-age=0${domain ? `; domain=${domain}` : ''}`;
};

export const WelcomeModal = () => {
  const [isOpen, setIsOpen] = useState(false);
  const hasPlayedConfetti = useRef(false);

  // Check if we should show the modal on mount
  useEffect(() => {
    const shouldShow = sessionStorage.getItem(STORAGE_KEY) === 'true' || hasOAuthNewSignupCookie();
    if (shouldShow) {
      setIsOpen(true);
      sessionStorage.removeItem(STORAGE_KEY);
      clearOAuthNewSignupCookie();
    }
  }, []);

  // Play confetti when modal opens
  useEffect(() => {
    if (!isOpen || hasPlayedConfetti.current) return;
    hasPlayedConfetti.current = true;

    // Small delay to let the modal animate in
    const timeout = setTimeout(() => {
      const leftBurst = () => {
        confetti({
          particleCount: 60,
          angle: 60,
          spread: 55,
          origin: { x: 0, y: 0.6 },
          colors: CONFETTI_COLORS,
          startVelocity: 40,
          gravity: 0.9,
          drift: 1,
          ticks: 250,
          disableForReducedMotion: true,
        });
      };

      const rightBurst = () => {
        confetti({
          particleCount: 60,
          angle: 120,
          spread: 55,
          origin: { x: 1, y: 0.6 },
          colors: CONFETTI_COLORS,
          startVelocity: 40,
          gravity: 0.9,
          drift: -1,
          ticks: 250,
          disableForReducedMotion: true,
        });
      };

      const centerBurst = () => {
        confetti({
          particleCount: 80,
          spread: 100,
          origin: { x: 0.5, y: 0.35 },
          colors: CONFETTI_COLORS,
          startVelocity: 35,
          gravity: 1,
          ticks: 200,
          disableForReducedMotion: true,
        });
      };

      leftBurst();
      rightBurst();

      setTimeout(() => {
        centerBurst();
      }, 100);

      setTimeout(() => {
        leftBurst();
        rightBurst();
      }, 300);
    }, 200);

    return () => clearTimeout(timeout);
  }, [isOpen]);

  const handleClose = useCallback(() => {
    setIsOpen(false);
  }, []);

  if (!isOpen) return null;

  return (
    <Dialog open={isOpen} onOpenChange={setIsOpen}>
      <DialogContent className="sm:max-w-lg p-0 sm:p-0 gap-0 sm:gap-0 overflow-hidden">
        {/* Header */}
        <div className="px-6 pt-8 pb-6 text-center bg-muted/50">
          {/* Success icon */}
          <div className="flex justify-center mb-4">
            <div
              className="flex h-16 w-16 items-center justify-center rounded-full shadow-md"
              style={{ background: 'linear-gradient(135deg, #FFFE25, #42F272)' }}
            >
              <CheckCircle2 className="h-8 w-8 text-gray-900" strokeWidth={2.5} />
            </div>
          </div>

          <DialogHeader className="items-center">
            <DialogTitle className="text-2xl font-bold tracking-tight text-foreground text-center">
              <FormattedMessage
                defaultMessage="Welcome aboard!"
                id="Welcome Modal / heading"
              />
            </DialogTitle>
            <DialogDescription className="text-base text-muted-foreground mt-2 text-center">
              <FormattedMessage
                defaultMessage="Your account has been created successfully. Let's get you started!"
                id="Welcome Modal / subheading"
              />
            </DialogDescription>
          </DialogHeader>
        </div>

        {/* Content */}
        <div className="px-6 pb-6 space-y-5">
          {/* Email verification notice */}
          <div className="rounded-lg border bg-card p-4">
            <div className="flex gap-3">
              <div
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg shadow-sm"
                style={{ background: 'linear-gradient(135deg, #FFFE25, #42F272)' }}
              >
                <Mail className="h-5 w-5 text-gray-900" />
              </div>
              <div className="space-y-0.5">
                <h3 className="font-semibold text-sm text-foreground">
                  <FormattedMessage
                    defaultMessage="Verify your email"
                    id="Welcome Modal / email title"
                  />
                </h3>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  <FormattedMessage
                    defaultMessage="Check your inbox for a confirmation link to unlock all features."
                    id="Welcome Modal / email description"
                  />
                </p>
              </div>
            </div>
          </div>

          {/* Quick start tips */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-foreground">
              <FormattedMessage
                defaultMessage="Quick start"
                id="Welcome Modal / tips title"
              />
            </h4>
            <div className="grid gap-2">
              <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <User className="h-4 w-4 text-muted-foreground" />
                </div>
                <span className="text-sm text-muted-foreground">
                  <FormattedMessage
                    defaultMessage="Complete your profile for a personalized experience"
                    id="Welcome Modal / tip 1"
                  />
                </span>
              </div>
              <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/50 hover:bg-muted transition-colors">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
                  <Rocket className="h-4 w-4 text-muted-foreground" />
                </div>
                <span className="text-sm text-muted-foreground">
                  <FormattedMessage
                    defaultMessage="Explore the dashboard to discover all features"
                    id="Welcome Modal / tip 2"
                  />
                </span>
              </div>
            </div>
          </div>

          {/* CTA Button */}
          <Button
            size="lg"
            onClick={handleClose}
            className="w-full"
          >
            <FormattedMessage
              defaultMessage="Start Exploring"
              id="Welcome Modal / cta button"
            />
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

// Helper function to trigger the modal (call after signup)
export const triggerWelcomeModal = () => {
  sessionStorage.setItem(STORAGE_KEY, 'true');
};
