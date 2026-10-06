# Company selection

The authenticated `/[language]/companies` page lists accepted organization memberships, with pending invitations shown separately. The existing sidebar switcher includes **All organizations**. Cards navigate to an explicit organization URL; their separate default button changes only the user's preference.

`UserProfile.default_organization` is nullable and uses `SET_NULL`. Apply migrations with `pnpm saas backend migrate`. No existing localStorage values are migrated. `currentUser.defaultOrganizationId` and `setDefaultOrganization(input: { organizationId })` use the same Relay ID format as `currentUser.tenants[].id`; `null` clears the preference. Reads and writes enforce accepted organization access, the existing superuser bypass and password-session SSO restrictions. A revoked membership makes the preference resolve to null without exposing the organization.

On the authenticated application home page, an accessible default organization takes priority; otherwise one organization opens directly, multiple organizations open Organizations, and no organizations open the existing add-organization flow. Explicit organization URLs retain priority and existing onboarding guards. Switching manually does not change the preference. The last-used organization remains useful for tenant navigation but does not control this home decision.

Sales and active decisions currently show example values (+10% and 0) for UI review; they are not connected to organization data. Health shows a no-data state. The canonical chooser URL is /:locale/organizations; /:locale/companies redirects to it. The layout uses the existing components and theme, with one, two or three columns according to the viewport. All new messages use react-intl and the existing translation catalog.

## Verification

- Docker: `docker compose exec -T backend pytest apps/users/tests/test_default_organization.py apps/users/tests/test_schema.py`
- Frontend: companySelection component and utility tests cover home routing, persisted defaults versus last-used state, inaccessible links, onboarding, invitations, search, mutation errors and keyboard navigation.
- Application TypeScript check, scoped ESLint, Python Ruff, migration consistency and Vite production build.
- Local browser check: Organization cards, persisted default badge, root redirect to the default dashboard and sidebar All organizations navigation.

This branch starts from local master and intentionally does not include the independent KSeF invoice feature. No push, merge or deployment is required for reviewing this change.

## Responsive browser review

Reviewed in Brave's device emulation using the actual CompanySelection, Layout, Header and Sidebar components with isolated Apollo test data (three companies, a long company name and a pending invitation). No administrator login or changes to real company preferences were used. This verifies responsive rendering and component interactions, not native iOS behavior or live backend integration.

| Viewport                             | Result                                                                                    |
| ------------------------------------ | ----------------------------------------------------------------------------------------- |
| Phone 375 × 667 and 667 × 375        | One column; search, invitation and default action remain usable                           |
| iPad 768 × 1024 and 1024 × 768       | Two columns; mobile menu opens and closes; All organizations closes the menu              |
| iPad Pro 1032 × 1376 and 1376 × 1032 | Two columns in portrait, three with desktop sidebar in landscape; long company names wrap |

The review found the shared mobile sidebar close button behind the sidebar because `z-60` is not defined by the Tailwind configuration. It now uses `z-[60]` and a theme-aware background so the control is visible above the overlay. Closing the menu and returning through All organizations were checked after the fix. Temporary preview files were removed after the review.
