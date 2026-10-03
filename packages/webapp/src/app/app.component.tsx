import { TenantBackupSettings } from '@sb/webapp-backup';
import { DemoItem, DemoItems, PrivacyPolicy, TermsAndConditions } from '@sb/webapp-contentful/routes';
import { DEFAULT_LOCALE } from '@sb/webapp-core/config/i18n';
import { DynamicIntlProvider } from '@sb/webapp-core/providers';
import { CrudDemoItem } from '@sb/webapp-crud-demo/routes';
import { Documents } from '@sb/webapp-documents/routes';
import { ActiveSubscriptionContext } from '@sb/webapp-finances/components/activeSubscriptionContext';
import {
  CancelSubscription,
  CurrentSubscriptionContent,
  EditPaymentMethod,
  EditSubscription,
  PaymentConfirm,
  PaymentMethodContent,
  Subscriptions,
  TransactionHistory,
  TransactionsHistoryContent,
} from '@sb/webapp-finances/routes';
import { SaasIdeas } from '@sb/webapp-generative-ai/routes';
import { OnboardingCompletionRoute } from '@sb/webapp-tenants/components/routes/onboardingCompletionRoute';
import { PermissionAuthRoute } from '@sb/webapp-tenants/components/routes/permissionAuthRoute';
import {
  AccessDenied,
  AddTenantForm,
  OrganizationOnboarding,
  TenantActivityLogs,
  TenantGeneralSettings,
  TenantInvitation,
  TenantMembers,
  TenantRoles,
  TenantSecuritySettings,
  TenantSettings,
} from '@sb/webapp-tenants/routes';
import { Route, Routes } from 'react-router-dom';

import { Role } from '../modules/auth/auth.types';
import { Admin } from '../routes/admin';
import { PasswordReset } from '../routes/auth/passwordReset';
import ValidateOtp from '../routes/auth/validateOtp';
import { AnonymousRoute, AuthRoute } from '../shared/components/routes';
import {
  ConfirmEmail,
  Home,
  Login,
  Logout,
  NotFound,
  OAuthCallback,
  Profile,
  SSOCallback,
  SSOError,
  SSOLogin,
  Signup,
} from './asyncComponents';
import { LANG_PREFIX, RoutesConfig, TENANT_PREFIX } from './config/routes';
import { ValidRoutesProviders } from './providers';

export const App = () => {
  return (
    <Routes>
      <Route element={<ValidRoutesProviders />}>
        <Route path={LANG_PREFIX}>
          <Route path={RoutesConfig.logout} element={<Logout />} />
          {/* Not under AnonymousRoute: the backend has already set auth cookies by
              the time the browser lands here, so the app's own "who am I" query
              resolves as logged-in almost immediately - AnonymousRoute would bounce
              the user away before this page's effect (which fetches tokens into
              localStorage) ever got a chance to run. Same reasoning as Logout above. */}
          <Route path={RoutesConfig.oauthCallback} element={<OAuthCallback />} />

          <Route element={<AnonymousRoute />}>
            <Route path={RoutesConfig.signup} element={<Signup />} />
            <Route path={RoutesConfig.login} element={<Login />} />
            <Route path={RoutesConfig.validateOtp} element={<ValidateOtp />} />
            {/* SSO routes - accessible without authentication */}
            <Route path={RoutesConfig.ssoLogin} element={<SSOLogin />} />
            <Route path={RoutesConfig.ssoCallback} element={<SSOCallback />} />
            <Route path={RoutesConfig.ssoError} element={<SSOError />} />
            <Route path="*" element={<NotFound />} />
          </Route>

          <Route path={TENANT_PREFIX} element={<AuthRoute />}>
            <Route element={<PermissionAuthRoute permissions="org.settings.edit" requiresOrganization />}>
              <Route path={RoutesConfig.tenant.onboarding} element={<OrganizationOnboarding />} />
            </Route>
            <Route index element={<Home />} />
            {/* Organization Settings - each sub-route has its own permission check */}
            <Route element={<PermissionAuthRoute permissions={['org.settings.view', 'members.view', 'org.roles.view', 'security.view', 'security.logs.view']} mode="any" requiresOrganization />}>
              <Route element={<TenantSettings />}>
                {/* Members route - requires members.view */}
                <Route element={<PermissionAuthRoute permissions="members.view" />}>
                  <Route path={RoutesConfig.tenant.settings.members} element={<TenantMembers />} />
                </Route>
                {/* General settings - requires org.settings.view */}
                <Route element={<PermissionAuthRoute permissions="org.settings.view" />}>
                  <Route path={RoutesConfig.tenant.settings.general} element={<TenantGeneralSettings />} />
                </Route>
                {/* Security settings - requires security.view */}
                <Route element={<PermissionAuthRoute permissions="security.view" />}>
                  <Route path={RoutesConfig.tenant.settings.security} element={<TenantSecuritySettings />} />
                </Route>
                {/* Activity logs - requires security.logs.view */}
                <Route element={<PermissionAuthRoute permissions="security.logs.view" />}>
                  <Route path={RoutesConfig.tenant.settings.activityLogs} element={<TenantActivityLogs />} />
                </Route>
                {/* Roles management - requires org.roles.view to see, org.roles.manage to edit */}
                <Route element={<PermissionAuthRoute permissions="org.roles.view" />}>
                  <Route path={RoutesConfig.tenant.settings.roles} element={<TenantRoles />} />
                </Route>
                {/* Backup settings - requires backup.view */}
                <Route element={<PermissionAuthRoute permissions="backup.view" />}>
                  <Route path={RoutesConfig.tenant.settings.backup} element={<TenantBackupSettings />} />
                </Route>
              </Route>
            </Route>
            {/* Billing/Subscriptions - requires billing.view */}
            <Route element={<PermissionAuthRoute permissions="billing.view" requiresOrganization />}>
              <Route element={<ActiveSubscriptionContext />}>
                <Route element={<Subscriptions />}>
                  <Route index path={RoutesConfig.subscriptions.index} element={<CurrentSubscriptionContent />} />
                  <Route path={RoutesConfig.subscriptions.paymentMethods.index} element={<PaymentMethodContent />} />
                  <Route
                    path={RoutesConfig.subscriptions.transactionHistory.index}
                    element={<TransactionsHistoryContent />}
                  />
                </Route>
                {/* Plan/payment-method changes - require billing.manage, not just billing.view */}
                <Route element={<PermissionAuthRoute permissions="billing.manage" />}>
                  <Route path={RoutesConfig.subscriptions.currentSubscription.edit} element={<EditSubscription />} />
                  <Route
                    path={RoutesConfig.subscriptions.currentSubscription.cancel}
                    element={<CancelSubscription />}
                  />
                  <Route path={RoutesConfig.subscriptions.paymentMethods.edit} element={<EditPaymentMethod />} />
                </Route>
              </Route>
              {/* One-time payment flow - also a billing-management action, requires billing.manage */}
              <Route element={<PermissionAuthRoute permissions="billing.manage" />}>
                <Route path={RoutesConfig.finances.paymentConfirm} element={<PaymentConfirm />} />
              </Route>
              <Route path={RoutesConfig.subscriptions.transactionHistory.history} element={<TransactionHistory />} />
            </Route>
            {/* Content Items - protected by features.content.view */}
            <Route element={<PermissionAuthRoute permissions="features.content.view" requiresOrganization />}>
              <Route path={RoutesConfig.demoItems} element={<DemoItems />} />
              <Route path={RoutesConfig.demoItem} element={<DemoItem routesConfig={{ notFound: RoutesConfig.notFound, list: RoutesConfig.demoItems }} />} />
            </Route>
            {/* CRUD Demo - protected by features.crud.view */}
            <Route element={<PermissionAuthRoute permissions="features.crud.view" requiresOrganization />}>
              <Route path={RoutesConfig.crudDemoItem.index} element={<CrudDemoItem routesConfig={RoutesConfig} />} />
            </Route>
            {/* Documents - protected by features.documents.view */}
            <Route element={<PermissionAuthRoute permissions="features.documents.view" requiresOrganization />}>
              <Route path={RoutesConfig.documents} element={<Documents />} />
            </Route>
            {/* OpenAI Integration - protected by features.ai.use */}
            <Route element={<PermissionAuthRoute permissions="features.ai.use" requiresOrganization />}>
              <Route path={RoutesConfig.saasIdeas} element={<SaasIdeas />} />
            </Route>
            <Route path={RoutesConfig.tenant.accessDenied} element={<AccessDenied />} />
            <Route element={<OnboardingCompletionRoute />}>
              <Route index element={<Home />} />
              {/* Organization Settings - each sub-route has its own permission check */}
              <Route
                element={
                  <PermissionAuthRoute
                    permissions={[
                      'org.settings.view',
                      'members.view',
                      'org.roles.view',
                      'security.view',
                      'security.logs.view',
                    ]}
                    mode="any"
                    requiresOrganization
                  />
                }
              >
                <Route element={<TenantSettings />}>
                  {/* Members route - requires members.view */}
                  <Route element={<PermissionAuthRoute permissions="members.view" />}>
                    <Route path={RoutesConfig.tenant.settings.members} element={<TenantMembers />} />
                  </Route>
                  {/* General settings - requires org.settings.view */}
                  <Route element={<PermissionAuthRoute permissions="org.settings.view" />}>
                    <Route path={RoutesConfig.tenant.settings.general} element={<TenantGeneralSettings />} />
                  </Route>
                  {/* Security settings - requires security.view */}
                  <Route element={<PermissionAuthRoute permissions="security.view" />}>
                    <Route path={RoutesConfig.tenant.settings.security} element={<TenantSecuritySettings />} />
                  </Route>
                  {/* Activity logs - requires security.logs.view */}
                  <Route element={<PermissionAuthRoute permissions="security.logs.view" />}>
                    <Route path={RoutesConfig.tenant.settings.activityLogs} element={<TenantActivityLogs />} />
                  </Route>
                  {/* Roles management - requires org.roles.view to see, org.roles.manage to edit */}
                  <Route element={<PermissionAuthRoute permissions="org.roles.view" />}>
                    <Route path={RoutesConfig.tenant.settings.roles} element={<TenantRoles />} />
                  </Route>
                  {/* Backup settings - requires backup.view */}
                  <Route element={<PermissionAuthRoute permissions="backup.view" />}>
                    <Route path={RoutesConfig.tenant.settings.backup} element={<TenantBackupSettings />} />
                  </Route>
                </Route>
              </Route>
              {/* Billing/Subscriptions - requires billing.view */}
              <Route element={<PermissionAuthRoute permissions="billing.view" requiresOrganization />}>
                <Route element={<ActiveSubscriptionContext />}>
                  <Route element={<Subscriptions />}>
                    <Route index path={RoutesConfig.subscriptions.index} element={<CurrentSubscriptionContent />} />
                    <Route path={RoutesConfig.subscriptions.paymentMethods.index} element={<PaymentMethodContent />} />
                    <Route
                      path={RoutesConfig.subscriptions.transactionHistory.index}
                      element={<TransactionsHistoryContent />}
                    />
                  </Route>
                  <Route path={RoutesConfig.subscriptions.currentSubscription.edit} element={<EditSubscription />} />
                  <Route
                    path={RoutesConfig.subscriptions.currentSubscription.cancel}
                    element={<CancelSubscription />}
                  />
                  <Route path={RoutesConfig.subscriptions.paymentMethods.edit} element={<EditPaymentMethod />} />
                </Route>
                <Route path={RoutesConfig.finances.paymentConfirm} element={<PaymentConfirm />} />
                <Route path={RoutesConfig.subscriptions.transactionHistory.history} element={<TransactionHistory />} />
              </Route>
              {/* Content Items - protected by features.content.view */}
              <Route element={<PermissionAuthRoute permissions="features.content.view" requiresOrganization />}>
                <Route path={RoutesConfig.demoItems} element={<DemoItems />} />
                <Route
                  path={RoutesConfig.demoItem}
                  element={
                    <DemoItem routesConfig={{ notFound: RoutesConfig.notFound, list: RoutesConfig.demoItems }} />
                  }
                />
              </Route>
              {/* CRUD Demo - protected by features.crud.view */}
              <Route element={<PermissionAuthRoute permissions="features.crud.view" requiresOrganization />}>
                <Route path={RoutesConfig.crudDemoItem.index} element={<CrudDemoItem routesConfig={RoutesConfig} />} />
              </Route>
              {/* Documents - protected by features.documents.view */}
              <Route element={<PermissionAuthRoute permissions="features.documents.view" requiresOrganization />}>
                <Route path={RoutesConfig.documents} element={<Documents />} />
              </Route>
              {/* OpenAI Integration - protected by features.ai.use */}
              <Route element={<PermissionAuthRoute permissions="features.ai.use" requiresOrganization />}>
                <Route path={RoutesConfig.saasIdeas} element={<SaasIdeas />} />
              </Route>
              <Route path="*" element={<NotFound />} />
            </Route>
          </Route>

          <Route element={<AuthRoute />}>
            <Route path={RoutesConfig.profile} element={<Profile />} />
            <Route path={RoutesConfig.addTenant} element={<AddTenantForm />} />
            <Route path={RoutesConfig.tenantInvitation} element={<TenantInvitation />} />
            <Route path="*" element={<NotFound />} />
          </Route>

          <Route element={<AuthRoute allowedRoles={Role.ADMIN} />}>
            <Route path={RoutesConfig.admin} element={<Admin />} />
          </Route>

          <Route path={RoutesConfig.confirmEmail} element={<ConfirmEmail />} />
          <Route path={RoutesConfig.privacyPolicy} element={<PrivacyPolicy />} />
          <Route path={RoutesConfig.termsAndConditions} element={<TermsAndConditions />} />
          <Route path={RoutesConfig.passwordReset.index} element={<PasswordReset />} />
        </Route>

        {/* <-- INJECT ROUTE --> */}

        <Route
          path="*"
          element={
            <DynamicIntlProvider locale={DEFAULT_LOCALE}>
              <NotFound />
            </DynamicIntlProvider>
          }
        />
      </Route>
    </Routes>
  );
};

export default App;
