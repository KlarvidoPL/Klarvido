# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Klarvido is built on Apptension's **SaaS Boilerplate**: an Nx/pnpm monorepo with a React/TypeScript frontend, a Django/GraphQL backend, Celery + event-driven workers, and infra-as-code that can deploy to AWS, Render.com, or a plain VPS. Requirements: Docker, Node 20+, pnpm 9+ (Python 3.11 + `uv` only needed if running backend/workers outside Docker).

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
- **Permissions are a plugin-style registry, not a central file.** Each Django app registers its own permissions via `register_permission_category`, `register_app_permissions`, `register_system_role_permissions` (see `apps/backup/permissions.py` as the reference implementation). **Never edit `multitenancy.permissions`, `multitenancy.constants`, or `ROLE_TEMPLATE_PERMISSIONS` directly** to add a new module's permissions — register from the module instead. Permissions get seeded via the module's own migration (`RunPython` + `get_all_permissions()`), not multitenancy's.
- **No inline imports in Python.** All imports at module top (exceptions: circular-import workarounds via `apps.get_model()` in migrations, or `TYPE_CHECKING` blocks).
- **Tests use pytest fixtures, not `django.test.TestCase`** (`TestCase` can cause `InterfaceError: connection already closed`). Mark with `pytestmark = pytest.mark.django_db`, use factories (`user_factory`, `tenant_factory`, ...). Factories that must not duplicate a row need `django_get_or_create` in `class Meta`.
- Emails go through `common.emails.Email` subclasses (`.send()`), not raw SMTP calls. In-app notifications go through `apps.notifications.sender.send_notification`.

### Frontend patterns

- **Apollo hooks must be imported from `@apollo/client/react`**, not `@apollo/client` — the plain import compiles but fails at runtime. `gql` comes from `@sb/webapp-api-client/graphql`.
- **Multi-tenancy is pervasive**: most mutations/queries take a `tenantId`; use `useCurrentTenant()` / `useGenerateTenantPath()` from `@sb/webapp-tenants` rather than assuming a single-tenant context.
- **Permission-gated UI**: `PermissionGate` / `usePermissionCheck('<module>.<action>')` from `@sb/webapp-tenants/hooks` control rendering. Components under `PermissionGate` render nothing in tests unless it's mocked (see Testing below) — this is the single most common cause of "element not found" test failures in this repo.
- File/naming convention per feature folder: `name.component.tsx`, `name.hook.ts`, `name.graphql.ts`, `name.stories.tsx`, tests in `__tests__/name.component.spec.tsx`, and a barrel `index.ts` re-exporting the public API.
- All user-facing text goes through `react-intl` (`FormattedMessage` / `useIntl().formatMessage`), with message IDs formatted as `"Section / description"`. No emojis in translated strings or toasts — toast icons are automatic based on `variant` (`success`, `destructive`, `warning`, `info`).

### Adding a new full-stack feature ("global module" pattern)

Reference implementation: the `backup` module (`packages/backend/apps/backup` + `packages/webapp-libs/webapp-backup`). A self-contained feature owns its own permissions, notification types, and GraphQL schema on both sides; the main app/shared libs only wire it in (route registration, merging notification templates). Same permission code strings must be used in the backend `requires()` check, the frontend `usePermissionCheck()`, and route guards. Don't put a module's notification types inside `webapp-notifications` — define them locally and have the main webapp merge the maps.

### Testing gotchas (frontend)

- Mock `PermissionGate`/`usePermissionCheck` at the top of test files when testing anything behind a permission check (very common — see `.cursor/rules/testing.mdc` for the exact mock).
- Mocked GraphQL mutation response keys **must match the mutation name exactly** (`composeMockedQueryResult`), not the mutation's semantic action.
- Components that render `<tr>` (table rows) must be wrapped in `<Table><TableBody>...</TableBody></Table>` in tests, or React DOM validation fails.
- CI runs on Linux (case-sensitive filesystem); macOS import paths that differ only by case will pass locally and fail in CI.

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

## Further reading in this repo

`.cursor/rules/*.mdc` has deeper, example-heavy versions of the above (GraphQL mutation walkthroughs, full test patterns, styling/icon/i18n conventions, CI preflight decision trees) — check the relevant file there if you need copy-pasteable examples rather than the summary above.
