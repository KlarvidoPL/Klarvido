import { Button } from '@sb/webapp-core/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@sb/webapp-core/components/ui/dropdown-menu';
import { Input } from '@sb/webapp-core/components/ui/input';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@sb/webapp-core/components/ui/tooltip';
import { cn } from '@sb/webapp-core/lib/utils';
import {
  BarChart3,
  Building2,
  CheckCircle2,
  ChevronDown,
  CircleDot,
  Database,
  Home,
  LogOut,
  Menu,
  MoreVertical,
  ReceiptText,
  RefreshCw,
  Send,
  Settings,
  Sparkles,
  UserRound,
  X,
} from 'lucide-react';
import { FormEvent, useCallback, useMemo, useRef, useState } from 'react';
import { useIntl } from 'react-intl';

import { KLARVIDO_LOGO_URL, KLARVIDO_SYMBOL_URL } from '../../klarvidoAssets';
import './klarvidoShell.css';
import { KlarvidoShellProps } from './klarvidoShell.types';

type ProductRoute =
  | 'today'
  | 'decisions'
  | 'analysis'
  | 'actions'
  | 'invoices'
  | 'sources'
  | 'settings';

const MOCKUP_BRIDGE_STYLE_ID = 'klarvido-react-shell-bridge';

const routeFromHash = (hash: string): ProductRoute => {
  const route = hash.replace(/^#\/?/, '').split(/[/?]/)[0];
  if (route === 'decisions' || route === 'workspace') return 'decisions';
  if (
    [
      'analysis',
      'detail',
      'clients',
      'suppliers',
      'costs',
      'market',
      'scenarios',
    ].includes(route)
  ) {
    return 'analysis';
  }
  if (route === 'actions' || route === 'action') return 'actions';
  if (route === 'invoices' || route === 'invoice') return 'invoices';
  if (route === 'sources') return 'sources';
  if (route === 'settings' || route === 'notifications') return 'settings';
  return 'today';
};

const initialsFor = (
  firstName?: string | null,
  lastName?: string | null,
  email?: string,
) => {
  const initials = [firstName, lastName]
    .filter(Boolean)
    .map((part) => part?.trim().charAt(0).toUpperCase())
    .join('');
  return initials || email?.charAt(0).toUpperCase() || 'K';
};

export const KlarvidoShell = ({
  companyName,
  contentUrl = '/klarvido/mockup.html',
  onLogout,
  user,
}: KlarvidoShellProps) => {
  const intl = useIntl();
  const frameRef = useRef<HTMLIFrameElement>(null);
  const [activeRoute, setActiveRoute] = useState<ProductRoute>('today');
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);
  const [assistantQuestion, setAssistantQuestion] = useState('');
  const [lastQuestion, setLastQuestion] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);

  const displayName =
    [user.firstName, user.lastName].filter(Boolean).join(' ') || user.email;
  const initials = initialsFor(user.firstName, user.lastName, user.email);
  const displayedCompany =
    companyName ||
    intl.formatMessage({
      id: 'klarvido.company.demo',
      defaultMessage: 'Meble Kowalski Sp. z o.o.',
    });

  const navItems = useMemo(
    () => [
      {
        route: 'today' as const,
        label: intl.formatMessage({
          id: 'klarvido.nav.start',
          defaultMessage: 'Start',
        }),
        icon: Home,
      },
      {
        route: 'decisions' as const,
        label: intl.formatMessage({
          id: 'klarvido.nav.decisions',
          defaultMessage: 'Decyzje',
        }),
        icon: CircleDot,
        badge: '0/5',
      },
      {
        route: 'analysis' as const,
        label: intl.formatMessage({
          id: 'klarvido.nav.analysis',
          defaultMessage: 'Analiza',
        }),
        icon: BarChart3,
      },
      {
        route: 'actions' as const,
        label: intl.formatMessage({
          id: 'klarvido.nav.actions',
          defaultMessage: 'Działania',
        }),
        icon: CheckCircle2,
      },
      {
        route: 'invoices' as const,
        label: intl.formatMessage({
          id: 'klarvido.nav.invoices',
          defaultMessage: 'Faktury',
        }),
        icon: ReceiptText,
        badge: '1',
      },
      {
        route: 'sources' as const,
        label: intl.formatMessage({
          id: 'klarvido.nav.sources',
          defaultMessage: 'Źródła danych',
        }),
        icon: Database,
      },
      {
        route: 'settings' as const,
        label: intl.formatMessage({
          id: 'klarvido.nav.settings',
          defaultMessage: 'Ustawienia',
        }),
        icon: Settings,
      },
    ],
    [intl],
  );

  const navigateContent = useCallback((route: ProductRoute | string) => {
    const frameWindow = frameRef.current?.contentWindow;
    if (frameWindow) frameWindow.location.hash = `#/${route}`;
    setActiveRoute(routeFromHash(`#/${route}`));
    setIsMobileMenuOpen(false);
  }, []);

  const prepareContentFrame = useCallback(() => {
    const frameWindow = frameRef.current?.contentWindow;
    const frameDocument = frameRef.current?.contentDocument;
    if (!frameWindow || !frameDocument) return;

    if (!frameDocument.getElementById(MOCKUP_BRIDGE_STYLE_ID)) {
      const style = frameDocument.createElement('style');
      style.id = MOCKUP_BRIDGE_STYLE_ID;
      style.textContent = `
        .sidebar, .topbar, .chat-fab { display: none !important; }
        .main { margin-left: 0 !important; width: 100% !important; min-height: 100vh !important; }
        .content { max-width: 1440px !important; padding: 28px 30px 48px !important; }
        @media (max-width: 767px) {
          .content { padding: 20px 16px 36px !important; }
          .page-header { grid-template-columns: 1fr !important; }
        }
      `;
      frameDocument.head.appendChild(style);
    }

    const syncRoute = () =>
      setActiveRoute(routeFromHash(frameWindow.location.hash));
    syncRoute();
    if (!frameWindow.document.documentElement.dataset.klarvidoReactShell) {
      frameWindow.document.documentElement.dataset.klarvidoReactShell = 'true';
      frameWindow.addEventListener('hashchange', syncRoute);
    }
  }, []);

  const synchronize = () => {
    setIsSyncing(true);
    window.setTimeout(() => setIsSyncing(false), 900);
  };

  const submitQuestion = (event: FormEvent) => {
    event.preventDefault();
    const value = assistantQuestion.trim();
    if (!value) return;
    setLastQuestion(value);
    setAssistantQuestion('');
  };

  const nav = (
    <>
      <div className="flex h-[86px] items-center border-b border-[#E4EAF1] px-4 min-[1051px]:px-[18px]">
        <img
          src={KLARVIDO_LOGO_URL}
          alt="Klarvido - Widzisz więcej"
          className="klarvido-full-logo hidden h-auto w-[188px] min-[1051px]:block"
        />
        <img
          src={KLARVIDO_SYMBOL_URL}
          alt="Klarvido"
          className="klarvido-symbol-logo mx-auto h-10 w-10 min-[1051px]:hidden"
        />
      </div>
      <nav
        className="flex-1 overflow-y-auto px-3 py-4"
        aria-label={intl.formatMessage({
          id: 'klarvido.nav.ariaLabel',
          defaultMessage: 'Nawigacja główna',
        })}
      >
        {navItems.map((item, index) => {
          const Icon = item.icon;
          const button = (
            <button
              key={item.route}
              type="button"
              onClick={() => navigateContent(item.route)}
              className={cn(
                'klarvido-nav-button relative mb-1 flex h-11 w-full items-center gap-3 rounded-lg px-3 text-sm font-semibold text-[#4F6075] transition-colors hover:bg-[#EEF3F8] hover:text-[#0B2545] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#143A66]',
                activeRoute === item.route && 'bg-[#E9F0F8] text-[#0B2545]',
                index === 5 &&
                  'mt-4 before:absolute before:-top-[9px] before:left-0 before:right-0 before:h-px before:bg-[#E4EAF1]',
                'max-[1050px]:justify-center max-[1050px]:px-0 min-[1051px]:justify-start',
              )}
              aria-current={activeRoute === item.route ? 'page' : undefined}
            >
              <Icon className="h-5 w-5 shrink-0" strokeWidth={1.9} />
              <span className="klarvido-nav-label max-[1050px]:hidden">
                {item.label}
              </span>
              {item.badge && (
                <span className="klarvido-nav-badge ml-auto flex min-w-5 items-center justify-center rounded-full bg-[#F59E0B] px-1.5 py-0.5 text-[11px] font-bold text-white max-[1050px]:absolute max-[1050px]:right-1 max-[1050px]:top-1">
                  {item.badge}
                </span>
              )}
            </button>
          );

          return (
            <Tooltip key={item.route} delayDuration={300}>
              <TooltipTrigger asChild>{button}</TooltipTrigger>
              <TooltipContent
                side="right"
                className="hidden max-[1050px]:block"
              >
                {item.label}
              </TooltipContent>
            </Tooltip>
          );
        })}
      </nav>
      <div className="border-t border-[#E4EAF1] p-3">
        <button
          type="button"
          onClick={() => navigateContent('settings')}
          className="flex h-12 w-full items-center gap-3 rounded-lg px-2 text-left hover:bg-[#EEF3F8] max-[1050px]:justify-center"
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#0B2545] text-xs font-bold text-white">
            {user.avatar ? (
              <img
                src={user.avatar}
                alt=""
                className="h-full w-full object-cover"
              />
            ) : (
              initials
            )}
          </span>
          <span className="klarvido-profile-copy min-w-0 max-[1050px]:hidden">
            <b className="block truncate text-sm text-[#0B2545]">
              {displayName}
            </b>
            <small className="block truncate text-xs text-[#6B7C93]">
              {user.email}
            </small>
          </span>
        </button>
      </div>
    </>
  );

  return (
    <TooltipProvider delayDuration={300}>
      <div className="klarvido-shell fixed inset-0 z-[70] font-sans">
        <aside className="fixed inset-y-0 left-0 z-40 hidden w-[84px] flex-col border-r border-[#E4EAF1] bg-[#FBFCFE] md:flex min-[1051px]:w-[232px]">
          {nav}
        </aside>

        {isMobileMenuOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            <button
              type="button"
              aria-label={intl.formatMessage({
                id: 'klarvido.mobileMenu.close',
                defaultMessage: 'Zamknij menu',
              })}
              className="absolute inset-0 bg-[#0B2545]/35"
              onClick={() => setIsMobileMenuOpen(false)}
            />
            <aside className="relative flex h-full w-[min(86vw,300px)] flex-col border-r border-[#E4EAF1] bg-[#FBFCFE] shadow-xl [&_.klarvido-full-logo]:!block [&_.klarvido-nav-badge]:!static [&_.klarvido-nav-badge]:!ml-auto [&_.klarvido-nav-button]:!justify-start [&_.klarvido-nav-button]:!px-3 [&_.klarvido-nav-label]:!block [&_.klarvido-profile-copy]:!block [&_.klarvido-symbol-logo]:!hidden">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="absolute right-2 top-3 z-10 text-[#0B2545]"
                onClick={() => setIsMobileMenuOpen(false)}
                aria-label={intl.formatMessage({
                  id: 'klarvido.mobileMenu.close',
                  defaultMessage: 'Zamknij menu',
                })}
              >
                <X className="h-5 w-5" />
              </Button>
              {nav}
            </aside>
          </div>
        )}

        <div className="flex h-full min-w-0 flex-col md:ml-[84px] min-[1051px]:ml-[232px]">
          <header className="relative z-30 flex h-[68px] shrink-0 items-center gap-2 border-b border-[#E4EAF1] bg-white/95 px-3 backdrop-blur md:px-5 min-[1051px]:px-[26px]">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-10 w-10 shrink-0 text-[#0B2545] md:hidden"
              onClick={() => setIsMobileMenuOpen(true)}
              aria-label={intl.formatMessage({
                id: 'klarvido.mobileMenu.open',
                defaultMessage: 'Otwórz menu',
              })}
            >
              <Menu className="h-5 w-5" />
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  type="button"
                  variant="outline"
                  className="h-10 min-w-0 max-w-[300px] justify-start border-[#DDE5EE] bg-white px-3 text-[#0B2545] hover:bg-[#F5F8FB]"
                >
                  <Building2 className="h-4 w-4 shrink-0" />
                  <span className="truncate max-sm:max-w-[105px]">
                    {displayedCompany}
                  </span>
                  <ChevronDown className="ml-auto h-4 w-4 shrink-0 text-[#6B7C93]" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                className="w-[280px] border-[#E4EAF1]"
              >
                <DropdownMenuLabel>
                  {intl.formatMessage({
                    id: 'klarvido.company.active',
                    defaultMessage: 'Aktywna firma',
                  })}
                </DropdownMenuLabel>
                <DropdownMenuItem onSelect={() => navigateContent('today')}>
                  <Building2 className="h-4 w-4" />
                  <span className="truncate">{displayedCompany}</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <div className="hidden items-center gap-2 lg:flex">
              <span className="flex h-9 items-center gap-2 rounded-lg border border-[#E4EAF1] bg-[#F8FAFC] px-3 text-xs font-semibold text-[#52667E]">
                <span className="h-2 w-2 rounded-full bg-[#F59E0B]" />
                {isSyncing
                  ? intl.formatMessage({
                      id: 'klarvido.data.syncing',
                      defaultMessage: 'Synchronizacja...',
                    })
                  : intl.formatMessage({
                      id: 'klarvido.data.demo',
                      defaultMessage: 'KSeF niepołączony · dane demo',
                    })}
              </span>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="h-9 w-9 text-[#52667E]"
                    aria-label={intl.formatMessage({
                      id: 'klarvido.ksef.options',
                      defaultMessage: 'Opcje KSeF',
                    })}
                  >
                    <MoreVertical className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="start"
                  className="w-52 border-[#E4EAF1]"
                >
                  <DropdownMenuItem onSelect={synchronize}>
                    <RefreshCw
                      className={cn('h-4 w-4', isSyncing && 'animate-spin')}
                    />
                    {intl.formatMessage({
                      id: 'klarvido.ksef.syncNow',
                      defaultMessage: 'Synchronizuj teraz',
                    })}
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => navigateContent('sources')}>
                    <Database className="h-4 w-4" />
                    {intl.formatMessage({
                      id: 'klarvido.ksef.manage',
                      defaultMessage: 'Zarządzaj połączeniem',
                    })}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>

            <div className="ml-auto flex items-center gap-1.5">
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    size="icon"
                    className="relative h-10 w-10 border-[#DDE5EE] bg-white"
                    onClick={() => navigateContent('notifications')}
                    aria-label={intl.formatMessage({
                      id: 'klarvido.notifications.label',
                      defaultMessage: 'Powiadomienia',
                    })}
                  >
                    <img
                      src={KLARVIDO_SYMBOL_URL}
                      alt=""
                      className="h-[21px] w-[21px] object-contain"
                    />
                    <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full border-2 border-white bg-[#F59E0B]" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  {intl.formatMessage({
                    id: 'klarvido.notifications.label',
                    defaultMessage: 'Powiadomienia',
                  })}
                </TooltipContent>
              </Tooltip>

              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="ghost"
                    className="h-11 min-w-0 gap-2 px-1.5 text-[#0B2545] hover:bg-[#F5F8FB] sm:px-2"
                  >
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-full bg-[#0B2545] text-xs font-bold text-white">
                      {user.avatar ? (
                        <img
                          src={user.avatar}
                          alt=""
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        initials
                      )}
                    </span>
                    <span className="max-w-[150px] truncate text-sm font-semibold max-lg:hidden">
                      {displayName}
                    </span>
                    <ChevronDown className="h-4 w-4 text-[#6B7C93] max-lg:hidden" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  align="end"
                  className="w-64 border-[#E4EAF1]"
                >
                  <DropdownMenuLabel className="font-normal">
                    <span className="block truncate font-semibold text-[#0B2545]">
                      {displayName}
                    </span>
                    <span className="block truncate text-xs text-[#6B7C93]">
                      {user.email}
                    </span>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem
                    onSelect={() => navigateContent('settings')}
                  >
                    <UserRound className="h-4 w-4" />
                    {intl.formatMessage({
                      id: 'klarvido.account.settings',
                      defaultMessage: 'Ustawienia konta',
                    })}
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={onLogout}>
                    <LogOut className="h-4 w-4" />
                    {intl.formatMessage({
                      id: 'klarvido.account.logout',
                      defaultMessage: 'Wyloguj się',
                    })}
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </header>

          <main className="relative min-h-0 flex-1 overflow-hidden bg-[#F7F9FC]">
            <iframe
              ref={frameRef}
              title={intl.formatMessage({
                id: 'klarvido.workspace.title',
                defaultMessage: 'Obszar roboczy Klarvido',
              })}
              src={`${contentUrl}#/today`}
              className="h-full w-full border-0 bg-[#F7F9FC]"
              allow="clipboard-write"
              onLoad={prepareContentFrame}
            />

            {!isAssistantOpen && (
              <Button
                type="button"
                onClick={() => setIsAssistantOpen(true)}
                className="absolute right-4 top-5 h-11 rounded-full bg-[#0B2545] px-4 text-white shadow-[0_12px_28px_rgba(11,37,69,0.25)] hover:bg-[#143A66] md:right-6 md:top-[38px]"
              >
                <Sparkles className="h-4 w-4 text-[#F59E0B]" />
                <span className="max-sm:hidden">
                  {intl.formatMessage({
                    id: 'klarvido.assistant.ask',
                    defaultMessage: 'Zapytaj Klarvido',
                  })}
                </span>
              </Button>
            )}
          </main>
        </div>

        {isAssistantOpen && (
          <aside
            className="fixed inset-y-0 right-0 z-[80] flex w-full max-w-[390px] flex-col border-l border-[#E4EAF1] bg-white shadow-2xl"
            aria-label={intl.formatMessage({
              id: 'klarvido.assistant.label',
              defaultMessage: 'Asystent Klarvido',
            })}
          >
            <div className="flex h-[68px] items-center gap-3 border-b border-[#E4EAF1] px-5">
              <img src={KLARVIDO_SYMBOL_URL} alt="" className="h-8 w-8" />
              <b className="text-base text-[#0B2545]">Klarvido</b>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="ml-auto text-[#52667E]"
                onClick={() => setIsAssistantOpen(false)}
                aria-label={intl.formatMessage({
                  id: 'klarvido.assistant.close',
                  defaultMessage: 'Zamknij asystenta',
                })}
              >
                <X className="h-5 w-5" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <span className="inline-flex rounded-full bg-[#EDF3F8] px-3 py-1.5 text-xs font-semibold text-[#52667E]">
                {intl.formatMessage({
                  id: 'klarvido.assistant.context',
                  defaultMessage: 'Kontekst: bieżący ekran i dane firmy',
                })}
              </span>
              <div className="mt-5 max-w-[88%] rounded-lg bg-[#F3F6F9] p-4 text-sm leading-6 text-[#354A62]">
                <b className="block text-[#0B2545]">
                  {intl.formatMessage({
                    id: 'klarvido.assistant.welcome',
                    defaultMessage: 'Z czym mogę Ci pomóc?',
                  })}
                </b>
                {intl.formatMessage({
                  id: 'klarvido.assistant.description',
                  defaultMessage:
                    'Znam kontekst bieżącego ekranu i dane demonstracyjne firmy.',
                })}
              </div>
              {lastQuestion && (
                <div className="ml-auto mt-3 max-w-[88%] rounded-lg bg-[#0B2545] p-4 text-sm leading-6 text-white">
                  {lastQuestion}
                </div>
              )}
            </div>
            <form
              onSubmit={submitQuestion}
              className="flex gap-2 border-t border-[#E4EAF1] p-4"
            >
              <Input
                value={assistantQuestion}
                onChange={(event) => setAssistantQuestion(event.target.value)}
                placeholder={intl.formatMessage({
                  id: 'klarvido.assistant.placeholder',
                  defaultMessage: 'Napisz swoje pytanie...',
                })}
                className="h-11 border-[#DDE5EE]"
              />
              <Button
                type="submit"
                size="icon"
                className="h-11 w-11 shrink-0 bg-[#0B2545] hover:bg-[#143A66]"
              >
                <Send className="h-4 w-4" />
                <span className="sr-only">
                  {intl.formatMessage({
                    id: 'klarvido.assistant.send',
                    defaultMessage: 'Wyślij pytanie',
                  })}
                </span>
              </Button>
            </form>
          </aside>
        )}
      </div>
    </TooltipProvider>
  );
};
