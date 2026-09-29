import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@sb/webapp-core/components/ui/card';
import { TabsContent } from '@sb/webapp-core/components/ui/tabs';
import { Users } from 'lucide-react';
import { FormattedMessage } from 'react-intl';

import { TenantMembersList } from '../../../components/tenantMembersList';
import { RoutesConfig } from '../../../config/routes';
import { useGenerateTenantPath, usePermissionCheck } from '../../../hooks';
import { InvitationForm } from './invitationForm';

export const TenantMembers = () => {
  const generateTenantPath = useGenerateTenantPath();

  // Permission checks
  const { hasPermission: canInvite } = usePermissionCheck('members.invite');

  return (
    <TabsContent value={generateTenantPath(RoutesConfig.tenant.settings.members)}>
      <div className="space-y-6">
        <div data-testid="tenant-members-list" className="space-y-6">
          {/* Show invitation form only if user has members.invite permission */}
          {canInvite && <InvitationForm />}
          <Card>
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10">
                    <Users className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">
                      <FormattedMessage defaultMessage="Members" id="Tenant Members / Header" />
                    </CardTitle>
                    <CardDescription className="mt-0.5">
                      <FormattedMessage
                        defaultMessage="View and manage organization members"
                        id="Tenant Members / Subheader"
                      />
                    </CardDescription>
                  </div>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <TenantMembersList />
            </CardContent>
          </Card>
        </div>
      </div>
    </TabsContent>
  );
};
