# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Klarvido is built on Apptension's **SaaS Boilerplate**: an Nx/pnpm monorepo with a React/TypeScript frontend, a Django/GraphQL backend, Celery + event-driven workers, and infra-as-code that can deploy to AWS, Render.com, or a plain VPS. Requirements: Docker, Node 20+, pnpm 9+ (Python 3.11 + `uv` only needed if running backend/workers outside Docker).

**Before building a new feature or modifying existing functionality, consult <https://docs.demo.saas.apptoku.com/working-with-sb/>** — the upstream boilerplate's own "working with SB" documentation. It covers the intended workflow for extending the boilerplate (module structure, GraphQL/CRUD generators, permissions, notifications, etc.) in more depth than this file, and following it keeps the codebase upgradeable against future upstream boilerplate releases.

## Commands

### Setup & local dev

```sh
pnpm install                                    # also builds the `sb` CLI (postinstall)
cp .env.shared .env
cp packages/backend/.env.shared packages/backend/.env

pnpm saas up            # backend + webapp + deps (db, redis, mailcatcher, stripe-mock, mcp-server)
pnpm saas backend up    # backend only
pnpm saas webapp up     # webapp only
pnpm saas docs up       # local docs site (localhost:3006)
pnpm saas down          # stop everything
```

Local URLs: webapp `:3000`, backend/GraphQL `:5001`, admin `admin.localhost:5001`, Mailcatcher `:1080`, workers trigger server `:3005`, Flower (Celery) `:5555`.

`pnpm saas <area> <action>` (the `@sb/cli` in `packages/internal/cli`) is the standard entrypoint for nearly everything — Docker Compose orchestration, migrations, secrets, and deploys. Prefer it over raw `docker compose`/`nx` calls when a subcommand exists.

`.env` files have distinct roles, per package: `.env` (real secrets, per-environment, **never committed**) vs `.env.shared` (committed, non-secret defaults e.g. `PROJECT_NAME`) vs `.env.test` (CI test-run overrides). The first superuser is created automatically from the initial backend migration **if `ADMIN_EMAIL` + `ADMIN_DEFAULT_PASSWORD` are set** at first `migrate` — not a separate seed command; change the password immediately outside local dev (the shared default in `.env.shared` is dev-only).

### Fresh local instance (manual reset)

When asked for a fresh local instance, provide commands for the user to run;
do not execute the reset unless explicitly asked. Do not add a committed reset
script. This procedure permanently deletes development data and must never be
used on a VPS/production host or against a remote Docker context. Check
`docker context show` and any `DOCKER_HOST`/`DOCKER_CONTEXT` overrides first.

Stop the running `pnpm saas up` process. From the repository root, resolve the
actual database volume name using the local files explicitly (do not assume
`PROJECT_NAME` or let `COMPOSE_FILE` select production configuration):

```sh
docker compose --env-file .env -f docker-compose.yml -f docker-compose.local.yml config --format json | node -e 'let s=""; process.stdin.on("data", c => s += c); process.stdin.on("end", () => console.log(JSON.parse(s).volumes.web_backend_db_data.name));'
```

Then substitute the printed name for `<local-db-volume>` below. The current
development name is `Klarvido-web-backend-db-data`, but verify it each time.

```sh
docker compose --env-file .env -f docker-compose.yml -f docker-compose.local.yml down --volumes --remove-orphans
docker volume rm <local-db-volume>
docker volume create <local-db-volume>
pnpm saas up
```

Postgres is an **external volume**, so `down --volumes` alone does not reset
users or business data. The commands also clear Redis, generated static files,
anonymous volumes, and container-held LocalStack uploads/Mailcatcher emails.
They retain images, build caches, source, `.env` files, and the `/tmp/localstack`
host scratch bind (the local configuration does not mount LocalStack's persistent
`/var/lib/localstack` directory). If `STORAGE_BACKEND=local`, also provide a
separate command to remove the verified local upload directory (normally
`packages/backend/media`) before restarting; inspect a custom `MEDIA_ROOT` first.
Externally hosted storage is not cleared by this procedure.

Ensure `ADMIN_EMAIL` and `ADMIN_DEFAULT_PASSWORD` are set in
`packages/backend/.env` before restarting. The initial migration recreates that
admin; startup also initializes permissions, locales, translations, and configured
Contentful/Stripe data. A fresh instance therefore has no previous users/business
data, but still contains normal system records. Remind the user to clear browser
site data (cookies/local storage) for `localhost:3000` and
`admin.localhost:5001` to discard stale sessions and organization selections.

### Lint / type-check / test (frontend — per-package, via Nx)

Every `webapp` and `webapp-libs/*` package has `lint`, `type-check`, `test` targets even though `project.json` often shows `"targets": {}` (they're added by inferred Nx plugins — use `pnpm nx show project <name>` if unsure what's available).

```sh
pnpm nx run <package>:lint
pnpm nx run <package>:type-check
pnpm nx run <package>:test --watchAll=false
pnpm nx run <package>:test --watchAll=false -- <path/to/file.spec.tsx>   # single test file
pnpm nx run <package>:test --watchAll=false --updateSnapshot             # update snapshots

pnpm nx run webapp:build                        # verifies the app actually builds

# Multiple packages at once
pnpm nx run-many --target=lint,type-check --projects=webapp,webapp-tenants,webapp-core --parallel=3
```

Always scope checks to the package(s) you actually touched (see table of `webapp-libs/*` packages below) — don't run the whole workspace by default.

**Don't run `lint`/`type-check`/`test` proactively after every change.** Only run them when needed to verify a specific change you're unsure about, and if it's unclear whether a run is warranted, ask the user first rather than running it — PR CI already runs the full suite, so local runs should stay narrow and intentional, not duplicated for speed.

### Backend (Python/Django)

```sh
pnpm nx run backend:test                        # docker compose run --rm backend ./scripts/runtime/run_tests.sh
                                                 # (runs ruff, black, makemigrations --check, then pytest --cov)

docker compose run --rm backend pytest path/to/test_file.py::TestClass::test_method   # single test, skips lint/black/migration checks

pnpm saas backend migrate
pnpm saas backend makemigrations
pnpm saas backend shell
pnpm saas backend black          # pnpm nx run backend:lint:js is for JS/infra files inside backend, not Python
pnpm saas backend ruff
pnpm saas backend stripe sync
```

Backend tests run **inside Docker**, not on the host — the backend container must be buildable/running.

### GraphQL schema workflow (required after any backend schema change)

The **backend must be running** for schema download.

```sh
pnpm nx run webapp-api-client:graphql:download-schema   # introspects running backend -> graphql/schema/api.graphql
pnpm nx run webapp-api-client:graphql:generate-types    # generates TS types from schema + *.graphql.ts operations
```

Never hand-edit `api.graphql` or the generated types. Frontend `.graphql.ts` files define operations; running `generate-types` produces the typed hooks.

### Docs

```sh
pnpm nx run docs:lint
pnpm nx run docs:build
```

### Scaffolding new features (Plop generators)

Run from `packages/webapp`: `pnpm plop` (interactive menu) or `pnpm plop <generator>` directly (e.g. `pnpm plop component`, `pnpm plop notification <type>`, `pnpm plop email MyEmailName`). Prefer these over hand-rolling boilerplate.

| Generator                                                     | Scaffolds                                                                                             |
| ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `component` / `hook` / `page` / `modal` / `table` / `context` | Frontend pieces (component+tests+Storybook, hook, route page, dialog, data table, context provider)   |
| `form`                                                        | react-hook-form + validation + optional GraphQL mutation; has entity templates (Product, Task, etc.)  |
| `backend`                                                     | Django app: model, serializers, GraphQL schema, admin, tests                                          |
| `crud`                                                        | Full-stack, tenant-aware CRUD (frontend + optional Django backend)                                    |
| `icon`                                                        | Registers a custom SVG from `src/images/icons/`                                                       |
| `notification`                                                | Notification component under `src/shared/components/notifications/templates/<type>/`, auto-registered |
| `email`                                                       | `@react-email` template (see Emails below for the manual pieces this automates)                       |

After generating `backend`/`crud`: add the app to `INSTALLED_APPS`, register its schema in `packages/backend/config/schema.py`, then `pnpm saas backend makemigrations && pnpm saas backend migrate`, then `pnpm saas webapp graphql download-schema` (+ generate-types). Plop won't overwrite existing files — delete/rename first if regenerating. If `pnpm plop` isn't found, run it from `packages/webapp` with deps installed, not the repo root.

### Coding standards (tooling config, not just style)

- **Black** (`packages/backend/pyproject.toml`): `line-length=120`, `skip-string-normalization=true` (preserves original quote style), excludes `migrations|libs|docs|data`.
- **Ruff** (same file): several rules are intentionally ignored — don't "fix" these if seen: `S101` (assert), `A002`/`A003` (builtin shadowing), `S105` (hardcoded-password false positives), `SIM105` (contextlib.suppress), `B904` (raise-from), `PLR0913` (too many args).
- **Prettier** (root `.prettierrc`): just `{"singleQuote": true}`. Plugins: `@trivago/prettier-plugin-sort-imports` (the import-order convention already noted above is enforced by this, not manual) and `prettier-plugin-tailwindcss` (sorts Tailwind classes).
- **Stylelint** also runs on CSS/Tailwind as part of `pnpm nx run webapp:lint` (`packages/webapp/.stylelintrc`).

## Architecture

### Monorepo layout

| Package                                                                                                                    | Role                                                                         |
| -------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `packages/webapp`                                                                                                          | Main React app: routes, app shell, wires together `webapp-libs`              |
| `packages/webapp-libs/webapp-core`                                                                                         | Shared UI (shadcn-based), hooks, theme, toast, forms                         |
| `packages/webapp-libs/webapp-api-client`                                                                                   | Apollo/GraphQL client, generated schema + types, codegen config              |
| `packages/webapp-libs/webapp-tenants`                                                                                      | Multi-tenancy: current tenant context, roles, permission hooks               |
| `packages/webapp-libs/webapp-*` (finances, notifications, documents, emails, generative-ai, crud-demo, contentful, backup) | Feature modules, each paired with a backend Django app of the same name      |
| `packages/backend`                                                                                                         | Django 5 + DRF + Graphene (GraphQL) + Celery + Channels (WebSockets)         |
| `packages/workers`                                                                                                         | Event-driven background jobs (separate from Celery)                          |
| `packages/infra/{infra-core,infra-shared}`                                                                                 | AWS CDK stacks (VPC, ECS Fargate, RDS, ElastiCache, CloudFront, ACM)         |
| `packages/mcp-server`                                                                                                      | Apollo MCP server exposing GraphQL operations as MCP tools                   |
| `packages/contentful`                                                                                                      | CMS content model                                                            |
| `packages/internal/cli`                                                                                                    | The `@sb/cli` (`pnpm saas ...`) tool; also docs site source and `ssm-editor` |

### Backend patterns

- **GraphQL mutations are serializer-based**: DRF `Serializer` in `serializers.py` (validation + `create()`) → `mutations.SerializerMutation` subclass in `schema.py` → registered on a permission-gated mutation class (`TenantOwnerMutation`, `TenantAdminMutation`, etc. via `@permission_classes(policies.IsTenant...Access)`). Don't invent a different mutation shape.
- **For plain CRUD, prefer the generic model-mutation base classes over hand-writing a `SerializerMutation`**: `mutations.CreateModelMutation`/`UpdateModelMutation`/`DeleteModelMutation` wrap a `ModelSerializer` directly (`Meta.serializer_class`, `Meta.edge_class` — omitting `edge_class` means the `*Edge` field silently won't appear in the schema). Tenant-scoped models use the `*TenantDependentModelMutation` variants, which already carry a `tenant_id` input. Drop to manual `SerializerMutation` only once you need logic beyond a serializer's `create`/`update`.
- **Permissions are a plugin-style registry, not a central file.** Each Django app registers its own permissions via `register_permission_category`, `register_app_permissions`, `register_system_role_permissions` (see `apps/backup/permissions.py` as the reference implementation). **Never edit `multitenancy.permissions`, `multitenancy.constants`, or `ROLE_TEMPLATE_PERMISSIONS` directly** to add a new module's permissions — register from the module instead. Permissions get seeded via the module's own migration (`RunPython` + `get_all_permissions()`), not multitenancy's.
- **No inline imports in Python.** All imports at module top (exceptions: circular-import workarounds via `apps.get_model()` in migrations, or `TYPE_CHECKING` blocks).
- **Tests use pytest fixtures, not `django.test.TestCase`** (`TestCase` can cause `InterfaceError: connection already closed`). Mark with `pytestmark = pytest.mark.django_db`, use factories (`user_factory`, `tenant_factory`, ...). Factories that must not duplicate a row need `django_get_or_create` in `class Meta`. Factories become fixtures automatically via `pytest_factoryboy.register(...)` in each app's `tests/fixtures.py`, wired into `pytest_plugins` in the root `conftest.py` — that's why e.g. `product_factory`/`product` are available without importing them.
- Emails go through `common.emails.Email` subclasses (`.send()`), not raw SMTP calls — the subclass has a `name` (e.g. `'ACCOUNT_ACTIVATION'`) and a `serializer_class` (DRF serializer validating the template's `data` dict). In-app notifications go through `apps.notifications.sender.send_notification`; which channels actually fire is controlled by the `NOTIFICATIONS_STRATEGIES` setting (default in-app only) — add e.g. push/SMS by subclassing `BaseNotificationStrategy` in `apps/notifications/strategies.py`.
- **New Django app manually** (what `plop backend` automates): `pnpm saas backend shell` → `cd apps && django-admin startapp <name>`, fix `apps.py`'s `name = 'apps.<name>'`, add to `LOCAL_APPS` in `settings.py`. Model IDs conventionally use `hashid_field.HashidAutoField` (obfuscated, non-sequential).
- **Activity/audit logging is part of every new user-facing functionality**: whenever a feature adds or changes organization data, settings, memberships, permissions, billing, integrations, backups/restores, imports or exports, add the corresponding activity events as part of the implementation. Include user requests and background completion/failure outcomes where relevant; avoid logging ordinary page views/searches or successful events for failed operations. Preserve organization scope, stable entity IDs, useful old/new changes, and the correct user/AI/superuser/system actor. Respect `action_logging_enabled`; changes to the logging toggle must themselves be recorded with `force_log=True`.
- **Logging implementation**: use `@action_logged(...)` from `common.action_logging.decorators` for standard CRUD mutations. For custom request operations use `log_request_action(request, ...)` from `common.action_logging.service`; background jobs use `log_action(...)` with an explicit system actor. `compute_changes(...)` tracks old/new field values; `SENSITIVE_FIELDS` in that service excludes passwords, secrets and tokens from automatic snapshots. Add new sensitive fields there, and keep sensitive contents out of manually supplied changes/metadata too. Keep authentication/session events in security audit logs. Organization deletion needs an independent durable audit record because its activity logs are cascade-deleted.
- **Logging UI and tests**: add each new entity to the activity-log filter/label map, and translate event titles, actor labels, detail fields and enum values in all eight supported languages (`en`, `pl`, `de`, `fr`, `es`, `zh`, `hi`, `ar`). Preserve user-entered names; store/export stable raw values and translate only their display. Snapshot organization roles with their names and `system_role_type`, rather than mixing legacy membership roles with assigned roles. Add focused tests covering the actual operation, relevant failure outcomes, actor attribution, organization isolation, filters and translated display.
- **GraphQL error response shape** differs by error source — check both when handling errors on the frontend: field-validator errors come back as `extensions.<fieldName>`, object-level `validate()` errors as `extensions.non_field_errors`. Use the existing `extractGraphQLErrors` + `form.setApolloGraphQLResponseErrors` helpers rather than parsing `extensions` manually.

### Frontend patterns

- **Apollo hooks must be imported from `@apollo/client/react`**, not `@apollo/client` — the plain import compiles but fails at runtime. `gql` comes from `@sb/webapp-api-client/graphql`. (The upstream docs' own code samples still show the old no-`/react` import — that's stale; follow this repo's rule, not the docs' import lines, when copying a pattern from there.)
- **Multi-tenancy is pervasive**: most mutations/queries take a `tenantId`; use `useCurrentTenant()` / `useGenerateTenantPath()` from `@sb/webapp-tenants` rather than assuming a single-tenant context.
- **Permission-gated UI**: `PermissionGate` / `usePermissionCheck('<module>.<action>')` from `@sb/webapp-tenants/hooks` control rendering. Components under `PermissionGate` render nothing in tests unless it's mocked (see Testing below) — this is the single most common cause of "element not found" test failures in this repo.
- **Fragment masking**: codegen uses Apollo's fragment-masking preset, so a query result's fragment fields can't be read directly (TS error) — unwrap with `getFragmentData(fragmentDoc, data?.field)` from `@sb/webapp-api-client/graphql`.
- **shadcn/ui components must be added with a pinned CLI version**, not latest — `cd packages/webapp-libs/webapp-core && pnpm dlx shadcn@2.1.6 add <component>` (newer CLI versions break this repo's import-alias resolution). All shadcn components live centrally in `webapp-core/components/ui`, imported elsewhere as `@sb/webapp-core/components/ui/<name>`.
- **New route manually** (what `plop page` automates): routes are declared in a `RoutesConfig` map, not string literals; nested paths via the `nestedPath()` helper. Lazy-load with `asyncComponent(() => import(...))`. Access control is structural, not a rendered prop check: nest under `<Route element={<AuthRoute allowedRoles={Role.X} />}>` or `<Route element={<AnonymousRoute />}>` for logged-out-only pages — this is a _different, older_ authorization layer than `PermissionGate`/tenant permissions above (see Authorization below).
- File/naming convention per feature folder: `name.component.tsx`, `name.hook.ts`, `name.graphql.ts`, `name.stories.tsx`, tests in `__tests__/name.component.spec.tsx`, and a barrel `index.ts` re-exporting the public API.
- All user-facing text goes through `react-intl` (`FormattedMessage` / `useIntl().formatMessage`), with message IDs formatted as `"Section / description"`. No emojis in translated strings or toasts — toast icons are automatic based on `variant` (`success`, `destructive`, `warning`, `info`).

### Adding a new full-stack feature ("global module" pattern)

Reference implementation: the `backup` module (`packages/backend/apps/backup` + `packages/webapp-libs/webapp-backup`). A self-contained feature owns its own permissions, notification types, and GraphQL schema on both sides; the main app/shared libs only wire it in (route registration, merging notification templates). Same permission code strings must be used in the backend `requires()` check, the frontend `usePermissionCheck()`, and route guards. Don't put a module's notification types inside `webapp-notifications` — define them locally and have the main webapp merge the maps.

Scaffold the frontend package with `pnpm nx g @sb/tools:webapp-lib --directory webapp-libs mylib` (generator templates: `packages/internal/tools/src/generators/webapp-lib/files`), then manually: add the path alias to root `tsconfig.base.json` (`@sb/webapp-mylib` → `packages/webapp-libs/webapp-mylib/src/index.ts`, plus the `/*` wildcard variant), add the new package to the `@nx/enforce-module-boundaries` allow-list in root `eslint.config.js` (skip this and importing the new lib elsewhere fails lint), and add the dependency to the consuming package's `package.json` + `pnpm i`. Naming convention: package `webapp-{name}`, import path `@sb/webapp-{name}`.

**Three things are easy to silently skip when adding a new feature/mutation, because nothing fails loudly if you do — they only surface later as a real security or audit gap (this is how three separate privilege-escalation bugs ended up shipped and had to be retrofitted, see PR #57):**

1. **Permission registry — add a specific action, don't reuse a coarse one.** Every new tenant-scoped mutation (or sensitive query) needs its own permission code via `register_app_permissions` (reference: `apps/backup/permissions.py`), matched by `requires('<module>.<action>')` on the backend and `usePermissionCheck('<module>.<action>')`/`PermissionGate` on the frontend. Don't gate a new action on an existing coarser code (e.g. piggybacking on `*.manage` for something that's really a `*.view`) just because it's already there — that exact asymmetry caused the Backup Settings page to show an empty page to view-only users. And if the action grants/changes another user's permissions, role, or org membership, it must independently verify the _acting_ user is themselves authorized to grant what's being granted (mirror `AssignRolesToMemberMutation`'s pattern in `apps/multitenancy/schema.py`) — this is not automatically covered by the action just being permission-gated.
2. **Activity logging — log it if it's worth auditing.** Decide whether the new mutation should appear in the tenant's Activity Log: anything that changes permissions/roles/membership, billing, security settings (SSO/SCIM/passkeys), or deletes data almost always should. Wire it with the `@log_create`/`@log_update`/`@log_delete` decorators or manual `ActionLogService.log_action(...)` (`common.action_logging`) — a new sensitive mutation doesn't get this for free just because it's a `SerializerMutation`/`*ModelMutation`. Add any new sensitive field it touches to `EXCLUDED_LOGGING_FIELDS` so it's never logged in plaintext.
3. **Organization backup — verify inclusion, don't assume it.** `apps/backup` auto-discovers models for the per-tenant backup/restore feature by scanning every installed app for models that inherit `TenantDependentModelMixin` (`apps/backup/registry.py`, `modules.py`) — so a new tenant-scoped model is usually included automatically, grouped into a backup "module" per Django app, with no registration step needed. But check both directions when adding one: (a) if the model holds real tenant data and should be restorable, confirm it actually inherits `TenantDependentModelMixin` — a tenant-scoped model built on a different base won't be picked up and will silently never be backed up; (b) if it holds data that shouldn't be included (derived/cache data, something that must never be restored verbatim), opt it out explicitly with `_backup_excluded = True` rather than leaving it to be swept in by default.

### AI integrations — two distinct systems, don't conflate

1. **AI Agent (MCP)** — the chatbot/command-palette integration (`packages/mcp-server` + `@sb/webapp-ai-assistant`). New tools are `.graphql` operation files in `packages/mcp-server/operations/` with a `# @tool(name: "...", description: "...")` directive comment. `mutation_mode` in `packages/mcp-server/config.yaml` controls exposure: `none` (read-only) / `explicit` (only pre-defined mutation tools — production default) / `all` (dev/testing only). Every tool call is re-checked against a `TOOL_PERMISSIONS` map at execution time and activity-logged with `actor_type=AI_AGENT`.
2. **Simple OpenAI integration** — the "SaaS Ideas Generator" demo (`packages/backend/apps/integrations/openai/client.py` + `webapp-generative-ai`). `OpenAIClient` is a singleton with automatic model fallback (gpt-4 → gpt-4-turbo-preview → gpt-3.5-turbo) if the configured model is unavailable; its mutation uses `@ratelimit(key="ip", rate='3/min')` — copy this pattern for any new simple, non-agentic AI-backed mutation rather than the MCP tool pattern above.

### Authorization: two coexisting systems — don't conflate them

Besides the tenant-scoped permission registry above (`register_app_permissions`, `usePermissionCheck`, `PermissionGate` — org roles Owner/Admin/Member), there's a **separate, older, non-tenant global layer** still underneath it:

- Global Django `Group`s via `CommonGroups` (`common/acl/helpers.py`) — e.g. `User`, `Admin`, `Support`. New roles are added there plus a migration creating the `Group` row.
- `AccessPolicy` classes (`common/acl/policies.py`, via `rest_access_policy`) define statements like "Admin group → any action → allow", applied with `@permission_classes(policies.X)`. Default DRF permission is `IsAuthenticated`.
- Frontend equivalent is route-level: `<AuthRoute allowedRoles={Role.ADMIN} />`, driven by the `roles` field on `currentUser` — not `usePermissionCheck`/`PermissionGate`.

**Before adding an authorization check, identify which layer the resource belongs to**: a tenant/org-scoped feature → the permission-registry pattern; a global, non-tenant capability (internal support-only view, global admin action) → `AccessPolicy`/`CommonGroups`.

**Superuser cross-tenant bypass**: a Django superuser (`is_superuser=True`) gets automatic, owner-equivalent access to _every_ tenant, without a real `TenantMembership` row — implemented as a permission-layer bypass, not by creating memberships. Centralized in `apps/multitenancy/models.py` (`is_superuser_bypass_eligible`, `has_tenant_access`, `get_visible_tenants_for_user`) and wired into the tenant-resolution chokepoint (`apps/multitenancy/middleware.py::get_current_tenant_with_membership_check`), `common/acl/policies.py::TenantDependentAccess`, and the `*TenantDependentModelMutation` base classes (`common/graphql/mutations.py`). A superuser who's also a genuine member of a tenant keeps their real (possibly lower) role there — the bypass only fires when there's no real membership row. Every bypass access is audit-logged with `ActionActorType.SUPERUSER` (vs. the normal `USER`), via an `is_superuser_cross_tenant_access` flag the middleware sets on the GraphQL context — same pattern as the existing `is_ai_agent_request` flag. Don't add a new tenant-membership check anywhere without also considering whether it needs the same bypass (`has_tenant_access(user, tenant)` instead of a raw `TenantMembership.objects.filter(...).exists()`).

Other auth extension points: new OAuth provider → `SOCIAL_AUTH_<PROVIDER>_KEY`/`SECRET` in `settings.py` + add to the frontend `OAuthProvider` enum (`modules/auth/auth.types.ts`) + wire a button via `useOAuthLogin(provider)`; `SOCIAL_AUTH_ALLOWED_REDIRECT_HOSTS` is the allow-list for OAuth redirect targets. New profile field → add to `UserProfile` model + migration, thread through `UserManager.create_user`, `UserSignupSerializer`, `CurrentUserType` (custom `graphene.String()` + `resolve_<field>`), and `UserProfileSerializer` if user-editable post-signup.

### Enterprise SSO (disabled) & directory sync

A whole feature area, distinct from both authorization layers above: `apps.sso` (backend) + `@sb/webapp-sso` (frontend). Three independently-toggleable pieces:

1. **SAML 2.0 / OIDC SSO** — per-tenant `SSOConnection` records, configured by _tenant owners/admins_ in Organization Settings → Security (not by app developers — devs only gate the feature class via env vars). SP metadata auto-served at `/api/sso/saml/{connection_id}/metadata`. Supports JIT (just-in-time) provisioning and IdP-group → tenant-role mapping (e.g. `{"Admins": "OWNER", "_default": "MEMBER"}`).
2. **SCIM 2.0 directory sync** — provisioning/deprovisioning at `/api/sso/scim/v2/{Users,Groups}`, bearer-token auth (shown once on creation); requires an active SSO connection first. SCIM groups map read-only to tenant roles.
3. **WebAuthn/Passkeys** — **personal, not org-scoped**: a passkey authenticates the _user_ across all their tenant memberships, managed only from the user's own Profile — an org admin can't see/delete another user's passkey. Organization Settings → Security has no passkey section, and the `security.passkeys.manage` permission no longer exists. New passkey registrations notify only that user, never owners or admins. The same personal-vs-org distinction applies to session management (Profile → Active Sessions: each user manages only their own devices).

**Enterprise SSO and SCIM are currently disabled in code**, including REST/GraphQL entry points, organization configuration, `security.sso.manage`, and SSO notifications. Existing SSO JWTs are rejected. `VITE_ENABLE_SSO` cannot reactivate the feature. Retained code and archived `.disabled` tests are documented in `packages/backend/apps/sso/DISABLED.md`. Do not restore SSO without a security review. Keep `apps.sso` installed: passkeys, normal login sessions, device controls, and audit logs still use its shared models and services.

Supported login UI flags: `VITE_ENABLE_PASSKEYS`, `VITE_ENABLE_SOCIAL_LOGIN`, `VITE_ENABLE_PASSWORD_LOGIN` (default `true`).

Every SSO/SCIM/passkey event is auto-logged to `SSOAuditLog` (tenant-isolated, viewable at Organization Settings → Security → Audit Log or `GET /api/sso/tenant/{id}/audit-logs/`); extend event types in `apps/sso/constants.py`, log custom ones with `SSOAuditLog.log_event(...)`. Provider setup (Okta, Azure AD/Entra ID) follows the same shape: create app in IdP → point ACS URL (`/api/sso/saml/{id}/acs`) or OIDC redirect URI (`/api/sso/oidc/{id}/callback`) at this app → copy IdP metadata/cert into the tenant's SSO connection → optionally enable SCIM. Azure AD caps group claims at 200 groups; mapping by Group ID (stable, unreadable) vs. display name (readable, breaks on rename) is a real tradeoff.

### Async / background jobs

Controlled by `TASK_BACKEND` (`lambda` | `celery`, default `lambda`). Two systems depending on deploy target — **only relevant if you're on the AWS path**; Render/VPS have no Lambda equivalent, so background jobs there are Celery-only (`TASK_BACKEND=celery`) regardless of what an AWS-oriented guide says (consistent with the env-portability rule below).

- **Celery** (works everywhere, incl. Render/VPS) — `@shared_task` in `apps/*/tasks.py`, dispatched with `.delay(...)` or `.apply_async(...)`. Debug via **Flower** (`localhost:5555` locally, `http://flower.<stage-domain>` deployed); task results land in Postgres, browsable in Django admin at `/django_celery_results/taskresult/`.
- **Lambda tasks (AWS-only)** — a class subclassing `LambdaTask`, dispatched via `.apply(data=...)` through EventBridge. New Lambda worker modules register in `packages/workers/serverless.yml` (function → eventBridge trigger matching `source`), per-stage config in `packages/workers/workers.conf.yml` (can pull secrets from SSM via `${ssm:/${self:custom.ssmService}/KEY}`). Skip this path entirely outside AWS.

### Translations — dynamic, admin-published i18n

Distinct from typical static-JSON i18n: translations are edited in Django Admin and **published to a CDN at runtime** — no redeploy needed to ship a translation change. Code side is unchanged (`FormattedMessage`/`intl.formatMessage`, `"Section / Description"` ids).

```sh
cd packages/webapp
pnpm extract-intl:master          # -> packages/webapp-libs/webapp-core/src/translations/master.json
pnpm translations:sync            # or: pnpm translations:extract-and-sync
```

Sync also runs automatically on `pnpm saas up`. Translate & publish via Django Admin (`/admin/translations/`): Translation Keys → per-locale text, Draft/Published status → Locales → "Publish translations" pushes to S3/CloudFront (~30s cache invalidation); CLI equivalent `uv run python manage.py publish_translations <code>` (or `--all`). If `OPENAI_API_KEY` is set, Locales has an "AI Translate" admin action (CLI: `uv run python manage.py ai_translate en de --batch-size 20 [--overwrite] [--auto-publish]`), tracked under "AI Translation Jobs". New language: add a `Locale` row + a value in the frontend `Locale` enum (`webapp-core/src/config/i18n.ts`), then translate/publish. Every publish snapshots a version (Admin → "Translation Versions"); rollback = activate an old version, republish.

### Testing gotchas (frontend)

- Mock `PermissionGate`/`usePermissionCheck` at the top of test files when testing anything behind a permission check (very common — see `.cursor/rules/testing.mdc` for the exact mock).
- Mocked GraphQL mutation response keys **must match the mutation name exactly** (`composeMockedQueryResult`), not the mutation's semantic action.
- Components that render `<tr>` (table rows) must be wrapped in `<Table><TableBody>...</TableBody></Table>` in tests, or React DOM validation fails.
- CI runs on Linux (case-sensitive filesystem); macOS import paths that differ only by case will pass locally and fail in CI.
- Beyond `composeMockedQueryResult`/`composeMockedListQueryResult`: `createDeepFactory` (`@sb/webapp-api-client/tests/utils`) builds reusable mock-data factories, and a `fill*` naming convention (`fillCommonQueryWithUser`, `fillDocumentsListQuery`, ...) provides pre-built Apollo mocks for common queries — check for an existing `fill*` before hand-rolling one. `waitForApolloMocks()` (returned from the custom `render`) awaits all mocked requests before asserting.

### Deployment — three interchangeable targets

Same Docker images run against three different infra setups; only environment/config differs, driven via `pnpm saas <area> deploy`:

1. **AWS** — `packages/infra` CDK stacks (ECS Fargate, RDS, ElastiCache, CloudFront/ACM). Triggered via GitHub Actions `deploy-qa.yml`/`deploy-prod.yml` (`workflow_dispatch`).
2. **Render.com** — `render.yaml` blueprint (backend-api, webapp, celery-worker/beat, mcp-server, managed Postgres/Redis). Triggered via `.github/workflows/deploy-render.yml` (path-based selective deploys via per-service deploy hooks).
3. **VPS / self-hosted** — `docker-compose.prod.yml` + Traefik for automatic Let's Encrypt SSL, configured via `.env.prod` (copied from `.env.vps.example`). `pnpm saas vps setup|deploy|status|ssh`.

**Environment portability rule**: because VPS and AWS differ only in config, never bypass the existing abstraction layers when writing a feature:

- File I/O → always through Django's `default_storage` / the configured `STORAGE_BACKEND` (`local`, `s3`, `r2`, `b2`, `minio`), never a hardcoded local filesystem path assumed to persist. Use `get_default_storage_backend()`/`get_public_storage()` (`common/storages.py`) directly when you need the backend explicitly rather than via the model field default — `get_public_storage()` specifically for anything needing a public URL (avatars, etc.). Debug which backend is active: `default_storage.__class__.__name__` in `pnpm saas backend shell`.
- Email → always `django.core.mail` (`EMAIL_BACKEND` env-driven: SMTP, SES, SendGrid), never a direct provider SDK call.
- Background jobs → `TASK_BACKEND` (`lambda`/`celery`, see above) — write against Celery `@shared_task` for anything that must also run on Render/VPS.
- Tracing/observability → `TRACING_BACKEND` (`xray`/`otel`/`none`, default `xray`); AWS uses X-Ray, Render/VPS have no equivalent (Sentry there is error tracking only, not distributed tracing) — don't assume tracing spans exist outside AWS.
- Database connection config has two mutually exclusive forms and the backend branches on which is set — **don't set both**: `DATABASE_URL` (single connection string — Render/Railway-style) vs `DB_CONNECTION` (JSON blob — AWS RDS). On Render's basic Postgres plan (22-25 max connections), also set `DB_CONN_MAX_AGE=0` or you'll hit "too many connections" once backend + celery worker + celery beat replicas add up.
- Secrets/config → read via Django settings (`env(...)`), never hardcode something that would need to differ between environments.
- Cross-origin cookies: `COOKIE_SAMESITE=None` + `COOKIE_SECURE=True` (plus explicit `CORS_ALLOWED_ORIGINS`/`CSRF_TRUSTED_ORIGINS`, no wildcards) are required when frontend/backend sit on different subdomains (Render-style split-domain), vs. `COOKIE_SAMESITE=Lax` when they share a parent domain (VPS/AWS+CloudFront) — missing this is the single most common "login works locally, fails on Render" bug. Safari/iOS additionally gets an automatic `Authorization`-header fallback (token mirrored to `X-Auth-Token` response header + `localStorage`) when third-party cookies are blocked — don't "simplify" session code to cookie-only.
- Assume the container is stateless between deploys/restarts (matters more on AWS Fargate, but keeping it true everywhere avoids surprises when migrating from VPS to AWS later).
- If a feature genuinely needs environment-specific behavior, gate it behind a new env var following the `STORAGE_BACKEND`/`EMAIL_BACKEND`/`TASK_BACKEND` pattern rather than branching on a hardcoded assumption.

Rough cost/setup-time per target (own estimates from earlier in this project, broadly consistent with the upstream docs' comparison table): AWS ~2h setup, $85-500+/mo depending on tier (NAT Gateway ~$45/mo flat is the biggest fixed cost; Fargate isn't covered by AWS free tier); Render ~30min, ~$40-70/mo; VPS ~1h, ~$20-50/mo. Reinforces the earlier recommendation to start on VPS/Render pre-revenue.

### Dev tools & operational extras

- **Mailcatcher**: switch `EMAIL_BACKEND` in `packages/backend/.env` — `console.EmailBackend` writes emails to `docker compose logs celery_default` (emails send async via Celery, so check _worker_ logs, not backend logs); `smtp.EmailBackend` + `EMAIL_HOST=mailcatcher`/`EMAIL_PORT=1025` shows them at `localhost:1080`. Restart (`pnpm saas down && pnpm saas up`) after changing. Production uses `django_ses.SESBackend`. Storybook email templates have a "Send Email" button that dispatches straight to Mailcatcher. `EMAIL_FROM_ADDRESS` is the only required var for sending to work at all. Flower's UI is unauthenticated unless `FLOWER_BASIC_AUTH` (`user1:password1,...`) is set (or `FLOWER_AUTH_PROVIDER`/`FLOWER_OAUTH2_*` for OAuth2).
- **Sentry**: enable per-environment by setting `SENTRY_DSN` via `pnpm saas backend secrets` (after `pnpm saas aws set-env <stage>`) — AWS-specific activation path.
- **SSH into a deployed (AWS) container**: `pnpm saas backend remote-shell` wraps the cluster/task lookup + ECS Exec call — prefer it. Manual fallback (what it does under the hood, no bastion): `aws-vault exec <PROFILE> -- aws ecs execute-command --cluster <CLUSTER> --task <TASK_ID> --container <CONTAINER> --command "/bin/bash" --interactive`, requires the SSM Session Manager CLI plugin. Locally/VPS, just `pnpm saas backend shell`.
- **CLI telemetry**: the `saas` CLI collects anonymous usage telemetry; `SB_TELEMETRY_DEBUG=1 pnpm saas <cmd>` to inspect, `SB_TELEMETRY_DISABLED=1` to opt out.
- **Payments (one-time)**: reference implementation lives in `packages/backend/apps/finances/{serializers,schema}.py` + `packages/webapp-libs/webapp-finances/src/components/stripePayment.hooks.ts` — read those rather than re-deriving. `useStripePaymentIntent` (creates intent) + `useStripePayment` (confirms via `@stripe/react-stripe-js`). `SUBSCRIPTION_TRIAL_PERIOD_DAYS` (default 7) controls trial length with no code change.
- **Contentful sync**: `cd packages/contentful && node scripts/run_migrations.js` (needs `CONTENTFUL_SPACE_ID`/`CONTENTFUL_ACCESS_TOKEN`/`CONTENTFUL_ENVIRONMENT` in `packages/contentful/.env`). Manual/local only, not run in CI/CD.
- **Workers ↔ backend secret coupling**: workers' `JWT_SECRET` and `HASHID_SALT` must exactly equal backend's `DJANGO_SECRET_KEY` and `HASHID_FIELD_SALT` (shared token/hash-id encoding) — an easy cross-service break if rotating one side's secrets without the other.

### AWS deployment runbook

The condensed step sequence for an actual AWS deployment (beyond the one-line summary above):

**Prerequisites**: AWS account (admin), Docker Hub account (CodeBuild shares IPs across AWS customers and hits anonymous pull rate limits without it), `aws-cli`, `aws-vault` (encrypted credential storage), `chamber` (Parameter Store secrets), the SSM Session Manager plugin (only if using `remote-shell`/ECS Exec).

**Credentials & domain**: create an IAM role (`AdministratorAccess`) rather than using root/user creds directly; `aws-vault add <profile>`, link via `~/.aws/config` (`source_profile` + `role_arn`), set `AWS_VAULT_PROFILE` in `.env`. Get a Route 53 hosted zone (ID + name) — external DNS is possible but means managing ACM certs/CNAMEs by hand.

**Bootstrap + configure a stage** (once per account/region, then once per stage):

```sh
pnpm saas infra bootstrap                      # CDK bootstrap + KMS key for Chamber, once per account/region
pnpm saas aws set-env qa                       # sets terminal context to this stage (per-terminal-session only)
pnpm saas aws set-var SB_HOSTED_ZONE_ID Z0123456789ABCDEFGHIJ
pnpm saas aws set-var SB_HOSTED_ZONE_NAME example.com
pnpm saas aws set-var SB_DOMAIN_WEB_APP app.qa.example.com
pnpm saas aws set-var SB_DOMAIN_API api.qa.example.com
pnpm saas aws set-var SB_DOMAIN_ADMIN_PANEL admin.qa.example.com
pnpm saas aws set-var SB_DOMAIN_CDN cdn.qa.example.com
# optional: SB_DOMAIN_DOCS/SB_DOMAIN_FLOWER, SB_BASIC_AUTH user:pass (protect non-prod!),
# SB_CI_MODE simple (new accounts — avoids CodeBuild concurrency limits; "parallel" once established),
# SB_CERTIFICATE_DOMAIN example.com (only for prod serving from a bare root domain)
```

Variables persist in SSM Parameter Store (`/env-<PROJECT_NAME>-<stage>/*`), not locally.

**Deploy infra** (30-45 min; provisions VPC/RDS/ElastiCache/ECS/CloudFront/CodePipeline):

```sh
pnpm saas infra deploy --diff   # preview
pnpm saas infra deploy          # stacks in order: global -> main -> db -> ci -> components
pnpm saas infra deploy <stack>  # redeploy one stack only
```

Then add Docker Hub creds to the `GlobalBuildSecrets` entry in Secrets Manager manually (`{"DOCKER_USERNAME":..., "DOCKER_PASSWORD":...}`) — CI/CD builds fail intermittently without this.

**Secrets, then app deploy**:

```sh
pnpm saas backend secrets    # DJANGO_SECRET_KEY, HASHID_FIELD_SALT, ADMIN_EMAIL, ADMIN_DEFAULT_PASSWORD, FLOWER_BASIC_AUTH, STRIPE_*, SENTRY_DSN, SOCIAL_AUTH_*, OPENAI_API_KEY
pnpm saas workers secrets    # JWT_SECRET/HASHID_SALT must equal backend's above (see Dev tools note)
pnpm saas build && pnpm saas deploy   # everything; or per-service: backend deploy api/migrations, workers deploy, webapp deploy, backend deploy mcp-server
```

Changing a secret doesn't affect running containers until that service redeploys.

**Verify**: `https://api.<domain>/api/healthcheck/` → `{"status":"ok"}`; admin panel login; Flower online if enabled; CloudWatch log groups `/ecs/<project>-<stage>-api`, `/ecs/<project>-<stage>-celery-*`, `/aws/lambda/<project>-<stage>-*`.

**Tear down** (destructive, deletes the DB): `pnpm saas infra destroy components|ci|db|main`, in that reverse order.

**CI/CD**: needs an `external-ci` IAM user (auto-created by the infra stack) — its access key becomes `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` repo secrets, plus a GitHub Environment per stage with `SB_CI_ARTIFACTS_BUCKET` (get via `pnpm saas ci get-artifacts-bucket`) and `SB_DEPLOY_STAGE`. Flow: push → GitHub Actions builds/tests → uploads to the artifacts S3 bucket → CodePipeline detects it → CodeBuild deploys to ECS/Lambda/S3 (matches this repo's `deploy-qa.yml`/`deploy-prod.yml`, currently `workflow_dispatch`-only). Slack notifications go through AWS Chatbot (console-only config, no repo changes). Manual re-trigger: `gh workflow run deploy-qa.yml --ref <branch>`, or `aws codepipeline start-pipeline-execution --name <project>-<stage>-pipeline` to re-run the last build. Rollback: `git revert` + redeploy, or pick a prior ECS task definition revision in the console.

**Troubleshooting (non-obvious cases)**: cert covers `*.[stage].[domain]` by default — deploying prod on a bare root domain needs `SB_CERTIFICATE_DOMAIN` set explicitly. Cert stuck "Pending Validation" → check `SB_HOSTED_ZONE_ID` and DNS propagation. New accounts: SES sandbox (verified addresses only until production access requested), CodeBuild concurrency capped at 1 (`SB_CI_MODE=simple`). Stack stuck `ROLLBACK_COMPLETE` → delete it before retrying `infra deploy`. 502/503 right after deploy is normal for 2-5 min while ECS tasks pass health checks.

## Further reading in this repo

`.cursor/rules/*.mdc` has deeper, example-heavy versions of the above (GraphQL mutation walkthroughs, full test patterns, styling/icon/i18n conventions, CI preflight decision trees) — check the relevant file there if you need copy-pasteable examples rather than the summary above.

This file folds in the actionable parts of the **entire** upstream docs site (<https://docs.demo.saas.apptoku.com/>) — `working-with-sb/`, `getting-started/`, `introduction/`, `deployment/`, `aws/`, `features/enterprise-sso/`, plus the env-var/CLI-command pages under `api-reference/` — crawled and distilled page by page. Deliberately **not** crawled: `api-reference/*/generated/**`, which is Sphinx/TypeDoc output auto-generated straight from this repo's own source docstrings — reading the actual source is more current and authoritative than that mirror. For anything not covered here, or if the upstream docs have since changed, fetch the relevant page directly rather than assuming this file is exhaustive.
