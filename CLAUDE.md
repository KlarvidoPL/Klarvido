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

Scaffold the frontend package with `pnpm nx g @sb/tools:webapp-lib --directory webapp-libs mylib` (generator templates: `packages/internal/tools/src/generators/webapp-lib/files`), then manually: add the path alias to root `tsconfig.base.json` (`@sb/webapp-mylib` → `packages/webapp-libs/webapp-mylib/src/index.ts`, plus the `/*` wildcard variant), and add the dependency to the consuming package's `package.json` + `pnpm i`. Naming convention: package `webapp-{name}`, import path `@sb/webapp-{name}`.

### Authorization: two coexisting systems — don't conflate them

Besides the tenant-scoped permission registry above (`register_app_permissions`, `usePermissionCheck`, `PermissionGate` — org roles Owner/Admin/Member), there's a **separate, older, non-tenant global layer** still underneath it:

- Global Django `Group`s via `CommonGroups` (`common/acl/helpers.py`) — e.g. `User`, `Admin`, `Support`. New roles are added there plus a migration creating the `Group` row.
- `AccessPolicy` classes (`common/acl/policies.py`, via `rest_access_policy`) define statements like "Admin group → any action → allow", applied with `@permission_classes(policies.X)`. Default DRF permission is `IsAuthenticated`.
- Frontend equivalent is route-level: `<AuthRoute allowedRoles={Role.ADMIN} />`, driven by the `roles` field on `currentUser` — not `usePermissionCheck`/`PermissionGate`.

**Before adding an authorization check, identify which layer the resource belongs to**: a tenant/org-scoped feature → the permission-registry pattern; a global, non-tenant capability (internal support-only view, global admin action) → `AccessPolicy`/`CommonGroups`.

Other auth extension points: new OAuth provider → `SOCIAL_AUTH_<PROVIDER>_KEY`/`SECRET` in `settings.py` + add to the frontend `OAuthProvider` enum (`modules/auth/auth.types.ts`) + wire a button via `useOAuthLogin(provider)`. New profile field → add to `UserProfile` model + migration, thread through `UserManager.create_user`, `UserSignupSerializer`, `CurrentUserType` (custom `graphene.String()` + `resolve_<field>`), and `UserProfileSerializer` if user-editable post-signup.

### Async / background jobs

Two systems depending on deploy target — **only relevant if you're on the AWS path**; Render/VPS have no Lambda equivalent, so background jobs there are Celery-only regardless of what an AWS-oriented guide says (consistent with the env-portability rule below).

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

- File I/O → always through Django's `default_storage` / the configured `STORAGE_BACKEND` (`local`, `s3`, `r2`, `b2`, `minio`), never a hardcoded local filesystem path assumed to persist.
- Email → always `django.core.mail` (`EMAIL_BACKEND` env-driven: SMTP, SES, SendGrid), never a direct provider SDK call.
- Secrets/config → read via Django settings (`env(...)`), never hardcode something that would need to differ between environments.
- Assume the container is stateless between deploys/restarts (matters more on AWS Fargate, but keeping it true everywhere avoids surprises when migrating from VPS to AWS later).
- If a feature genuinely needs environment-specific behavior, gate it behind a new env var following the `STORAGE_BACKEND`/`EMAIL_BACKEND` pattern rather than branching on a hardcoded assumption.

### Dev tools & operational extras

- **Mailcatcher**: switch `EMAIL_BACKEND` in `packages/backend/.env` — `console.EmailBackend` writes emails to `docker compose logs celery_default` (emails send async via Celery, so check _worker_ logs, not backend logs); `smtp.EmailBackend` + `EMAIL_HOST=mailcatcher`/`EMAIL_PORT=1025` shows them at `localhost:1080`. Restart (`pnpm saas down && pnpm saas up`) after changing. Production uses `django_ses.SESBackend`. Storybook email templates have a "Send Email" button that dispatches straight to Mailcatcher.
- **Sentry**: enable per-environment by setting `SENTRY_DSN` via `pnpm saas backend secrets` (after `pnpm saas aws set-env <stage>`) — AWS-specific activation path.
- **SSH into a deployed (AWS) container**: no bastion — uses AWS ECS Exec directly (`aws-vault exec <PROFILE> -- aws ecs execute-command --cluster <CLUSTER> --task <TASK_ID> --container <CONTAINER> --command "/bin/bash" --interactive`), requires the SSM Session Manager CLI plugin. Locally/VPS, just `pnpm saas backend shell`.
- **CLI telemetry**: the `saas` CLI collects anonymous usage telemetry; `SB_TELEMETRY_DEBUG=1 pnpm saas <cmd>` to inspect, `SB_TELEMETRY_DISABLED=1` to opt out.
- **Payments (one-time)**: reference implementation lives in `packages/backend/apps/finances/{serializers,schema}.py` + `packages/webapp-libs/webapp-finances/src/components/stripePayment.hooks.ts` — read those rather than re-deriving. `useStripePaymentIntent` (creates intent) + `useStripePayment` (confirms via `@stripe/react-stripe-js`).
- **Contentful sync**: `cd packages/contentful && node scripts/run_migrations.js` (needs `CONTENTFUL_SPACE_ID`/`CONTENTFUL_ACCESS_TOKEN`/`CONTENTFUL_ENVIRONMENT` in `packages/contentful/.env`). Manual/local only, not run in CI/CD.

## Further reading in this repo

`.cursor/rules/*.mdc` has deeper, example-heavy versions of the above (GraphQL mutation walkthroughs, full test patterns, styling/icon/i18n conventions, CI preflight decision trees) — check the relevant file there if you need copy-pasteable examples rather than the summary above.

The "Architecture" and "Dev tools" sections above already fold in the actionable parts of every page under <https://docs.demo.saas.apptoku.com/working-with-sb/> (46 pages, crawled and distilled). For anything not covered here — or if the upstream docs have since changed — fetch that page directly rather than assuming this file is exhaustive.
