import { useMutation } from '@apollo/client/react';
import { getFragmentData } from '@sb/webapp-api-client';
import {
  commonQueryCurrentUserFragment,
  commonQueryMembershipFragment,
  useCommonQuery,
} from '@sb/webapp-api-client/providers';
import { Button } from '@sb/webapp-core/components/buttons';
import { PageLayout } from '@sb/webapp-core/components/pageLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { RoutesConfig } from '@sb/webapp-core/config/routes';
import { useGenerateLocalePath } from '@sb/webapp-core/hooks';
import { trackEvent } from '@sb/webapp-core/services/analytics';
import { useToast } from '@sb/webapp-core/toast';
import { MailOpen } from 'lucide-react';
import { useCallback, useEffect } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';

import { useGenerateTenantPath, useTenants } from '../../hooks';
import { acceptTenantInvitationMutation, declineTenantInvitationMutation } from './tenantInvitation.graphql';

export type InvitationPathParams = {
  token: string;
};

export const TenantInvitation = () => {
  const params = useParams<InvitationPathParams>();
  const { data, reload: reloadCommonQuery } = useCommonQuery();
  const currentUser = getFragmentData(commonQueryCurrentUserFragment, data?.currentUser);
  const isConfirmed = !!currentUser?.isConfirmed;
  const [searchParams] = useSearchParams();
  const membershipId = searchParams.get('membershipId');
  const tenants = useTenants();
  const navigate = useNavigate();
  const generateTenantPath = useGenerateTenantPath();
  const generateLocalePath = useGenerateLocalePath();
  const { toast } = useToast();
  const intl = useIntl();
  const { token } = params;

  const acceptSuccessMessage = intl.formatMessage({
    id: 'Tenant Invitation / Accept / Success message',
    defaultMessage: 'Invitation accepted!',
  });

  const declineSuccessMessage = intl.formatMessage({
    id: 'Tenant Invitation / Decline / Success message',
    defaultMessage: 'Invitation declined.',
  });

  const invitationNoLongerValidMessage = intl.formatMessage({
    id: 'Tenant Invitation / Error message',
    defaultMessage: 'This invitation is no longer valid.',
  });

  const tenant = tenants.find((t) => {
    const membership = getFragmentData(commonQueryMembershipFragment, t?.membership);
    return membershipId ? membership?.id === membershipId : !!token && membership?.invitationToken === token;
  });
  const tenantMembership = getFragmentData(commonQueryMembershipFragment, tenant?.membership);
  const tenantMembershipId = tenantMembership?.id || '';
  const acceptanceToken = tenantMembership?.invitationToken;

  const [commitAcceptMutation, { loading: acceptLoading }] = useMutation(acceptTenantInvitationMutation, {
    onCompleted: () => {
      reloadCommonQuery();
      trackEvent('tenantInvitation', 'accept', tenant?.id);
      toast({ description: acceptSuccessMessage, variant: 'success' });
      if (tenant) navigate(generateTenantPath(RoutesConfig.home, { tenantId: tenant?.id }));
    },
    onError: () => {
      reloadCommonQuery();
      toast({ description: invitationNoLongerValidMessage, variant: 'destructive' });
      navigate(generateLocalePath(RoutesConfig.home));
    },
  });

  const handleAccept = useCallback(() => {
    if (!isConfirmed || !acceptanceToken || !tenant) return;
    commitAcceptMutation({
      variables: {
        input: {
          token: acceptanceToken,
          id: tenantMembershipId,
        },
      },
    });
  }, [isConfirmed, acceptanceToken, commitAcceptMutation, tenant, tenantMembershipId]);

  const [commitDeclineMutation, { loading: declineLoading }] = useMutation(declineTenantInvitationMutation, {
    onCompleted: () => {
      reloadCommonQuery();
      trackEvent('tenantInvitation', 'decline', tenant?.id);
      toast({ description: declineSuccessMessage, variant: 'info' });
      navigate(generateLocalePath(RoutesConfig.home));
    },
    onError: () => {
      reloadCommonQuery();
      toast({ description: invitationNoLongerValidMessage, variant: 'destructive' });
      navigate(generateLocalePath(RoutesConfig.home));
    },
  });

  const handleDecline = useCallback(() => {
    if (!tenant) return;
    commitDeclineMutation({
      variables: {
        input: {
          ...(tenantMembership?.invitationToken ? { token: tenantMembership.invitationToken } : {}),
          id: tenantMembershipId,
        },
      },
    });
  }, [tenantMembership, commitDeclineMutation, tenant, tenantMembershipId]);

  useEffect(() => {
    const refresh = () => reloadCommonQuery();
    window.addEventListener('focus', refresh);
    return () => window.removeEventListener('focus', refresh);
  }, [reloadCommonQuery]);

  let redirectPath: string | null = null;

  if (!tenant) {
    redirectPath = generateLocalePath(RoutesConfig.home);
  } else if (tenantMembership?.invitationAccepted) {
    redirectPath = generateTenantPath(RoutesConfig.home, { tenantId: tenant.id });
  }

  useEffect(() => {
    if (redirectPath) {
      navigate(redirectPath);
    }
  }, [redirectPath, navigate]);

  if (!tenant || redirectPath) {
    return null;
  }

  const isLoading = acceptLoading || declineLoading;

  return (
    <PageLayout>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MailOpen className="h-5 w-5" />
            <FormattedMessage defaultMessage="Organization Invitation" id="Tenant Invitation / Page headline" />
          </CardTitle>
          <CardDescription>
            <FormattedMessage
              defaultMessage="You've been invited to join an organization"
              id="Tenant Invitation / Card description"
            />
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-lg border bg-muted/50 p-4">
            <p className="text-sm text-muted-foreground mb-1">
              <FormattedMessage defaultMessage="Organization" id="Tenant Invitation / Organization label" />
            </p>
            <p className="text-lg font-medium">{tenant.name}</p>
          </div>
          {!isConfirmed && (
            <p className="text-sm text-muted-foreground" id="invitation-verification-message">
              <FormattedMessage
                defaultMessage="Verify your email address before accepting this invitation."
                id="Tenant Invitation / Email verification required"
              />
            </p>
          )}
          <div className="flex gap-3">
            <Button
              onClick={handleAccept}
              disabled={isLoading || !isConfirmed || !acceptanceToken}
              className={!isConfirmed ? 'bg-muted text-muted-foreground' : undefined}
              aria-describedby={!isConfirmed ? 'invitation-verification-message' : undefined}
            >
              <FormattedMessage defaultMessage="Accept invitation" id="Tenant Invitation / Accept button" />
            </Button>
            <Button variant="outline" onClick={handleDecline} disabled={isLoading}>
              <FormattedMessage defaultMessage="Decline" id="Tenant Invitation / Decline button" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </PageLayout>
  );
};
