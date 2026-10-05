# Company selection

The authenticated `/[language]/companies` page lists accepted organization memberships, with pending invitations shown separately. The existing sidebar switcher includes **All companies**. Cards navigate to an explicit organization URL; their separate default button changes only the user's preference.

`UserProfile.default_organization` is nullable and uses `SET_NULL`. Apply migrations with `pnpm saas backend migrate`. No existing localStorage values are migrated. `currentUser.defaultOrganizationId` and `setDefaultOrganization(input: { organizationId })` use the same Relay ID format as `currentUser.tenants[].id`; `null` clears the preference. Reads and writes enforce accepted organization access, the existing superuser bypass and password-session SSO restrictions. A revoked membership makes the preference resolve to null without exposing the organization.

On the authenticated application home page, an accessible default organization takes priority; otherwise one organization opens directly, multiple organizations open Companies, and no organizations open the existing add-organization flow. Explicit organization URLs retain priority and existing onboarding guards. Switching manually does not change the preference. The last-used organization remains useful for tenant navigation but does not control this home decision.

Sales, active decisions and company health remain neutral unavailable placeholders. The layout uses the existing components and theme, with one, two or three columns according to the viewport. All new messages use react-intl and the existing translation catalog.

## Verification

- Docker: `docker compose exec -T backend pytest apps/users/tests/test_default_organization.py apps/users/tests/test_schema.py`
- Frontend: companySelection component and utility tests cover home routing, persisted defaults versus last-used state, inaccessible links, onboarding, invitations, search, mutation errors and keyboard navigation.
- Application TypeScript check, scoped ESLint, Python Ruff, migration consistency and Vite production build.
- Local browser check: Companies cards, persisted default badge, root redirect to the default dashboard and sidebar All companies navigation.

This branch starts from local master and intentionally does not include the independent KSeF invoice feature. No push, merge or deployment is required for reviewing this change.
