import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@sb/webapp-core/components/ui/tooltip';
import { AlertTriangle, X } from 'lucide-react';
import { FormattedMessage, useIntl } from 'react-intl';

interface TenantDomainStatus {
  domain: string;
  status: string;
}

// null while the tenant's domain list is still loading, so no badge flashes in
export const getDomainVerification = (
  tenantDomains: TenantDomainStatus[],
  loading: boolean,
  domain: string
): boolean | null => {
  if (loading) return null;
  return tenantDomains.some((item) => item.domain === domain && item.status.toLowerCase() === 'verified');
};

interface DomainChipProps {
  domain: string;
  verified: boolean | null;
  onRemove: () => void;
}

export const DomainChip = ({ domain, verified, onRemove }: DomainChipProps) => {
  const intl = useIntl();
  const intlLabel = intl.formatMessage({ id: 'SSO Form / Domain not verified', defaultMessage: 'Not verified' });
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
      {domain}
      {verified === false && (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <AlertTriangle aria-label={intlLabel} role="img" className="h-3.5 w-3.5 shrink-0 text-amber-500" />
            </TooltipTrigger>
            <TooltipContent>
              <FormattedMessage
                id="SSO Form / Domain not verified tooltip"
                defaultMessage="Verify this domain in Domain verification before the connection can be activated."
              />
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      )}
      <button
        type="button"
        onClick={onRemove}
        className="ml-1 rounded-full p-0.5 hover:bg-primary/20 transition-colors"
      >
        <X className="h-3 w-3" />
      </button>
    </span>
  );
};
