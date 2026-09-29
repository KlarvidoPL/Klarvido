# Klarvido Repository Instructions

## Product intent

Klarvido is a decision system for Polish SMEs. It turns financial evidence into a small number of explainable decisions, supports execution, and later measures outcomes. It is not an accounting package, ERP, invoicing tool, or generic dashboard.

Read these files before changing Klarvido product code:

1. `PRD.md` for product requirements and delivery phases.
2. `ARCHITECTURE.md` for boundaries, data flow, and terminology.
3. `CALCULATIONS.md` for the reference financial behavior.
4. `DESIGN_SYSTEM.md` for production UI rules.

The production UI lives in React. Product documents describe intended behavior, but canonical backend facts remain the source of business truth.

## Delivery order

- Build the synthetic vertical slice before external integrations.
- Demo data must enter through the same source adapter contract that KSeF, GUS, and NBP will use later.
- Put financial calculations, readiness rules, and decision rules in deterministic backend services.
- Keep React components unaware of the physical data source.
- Preserve existing authentication, tenant isolation, GraphQL conventions, and AWS CDK infrastructure.

## Non-negotiable domain rules

- One canonical source feeds KPI, charts, tables, signals, and decisions.
- Do not persist derived values such as share, change, rank, or status when they can be calculated from canonical facts.
- Never use floating-point arithmetic for money.
- Distinguish `pre_tax_result`, `net_result`, `gross_margin`, and `net_margin` in code and UI.
- Store percentages and percentage-point changes as different concepts.
- Every analytical result must identify its period, unit, source, calculation version, calculation time, quality, and kind: `fact`, `estimate`, or `simulation`.
- A diagnosis cannot be stronger than its Data Readiness status allows.
- An LLM may explain approved facts and decisions, but must not calculate KPI or create financial facts.
- Tenant-owned data must always be queried and mutated in tenant context.

## Repository conventions

- Follow the module boundaries in `ARCHITECTURE.md` and the patterns used by neighboring packages.
- Add the backend product domain under `packages/backend/apps/klarvido`.
- Add reusable frontend product code under `packages/webapp-libs/webapp-klarvido`; keep `packages/webapp` focused on route and provider wiring.
- Use Django, Graphene, Celery, PostgreSQL, React, TypeScript, Apollo, Tailwind, the shared shadcn-based UI, and AWS CDK already present in the repository.
- Use `react-intl` for user-facing application text.
- Keep source identifiers and code in English; use natural Polish for the initial product copy.
- Generate GraphQL TypeScript types through the existing schema workflow. Never edit generated schema or generated types manually.
- Do not replace or bypass the existing authentication and authorization flows.

## Verification

Run checks scoped to the packages changed. At minimum:

```sh
pnpm nx run webapp:type-check
pnpm nx run webapp:test --watchAll=false
pnpm nx run webapp:build
pnpm nx run backend:test
```

For backend GraphQL changes, run the schema download and type generation workflow while the backend is running:

```sh
pnpm nx run webapp-api-client:graphql:download-schema
pnpm nx run webapp-api-client:graphql:generate-types
```

## Definition of done

A feature is complete only when:

- it uses canonical or explicitly marked synthetic data through an adapter;
- loading, empty, limited, blocked, success, and error states are handled where applicable;
- calculations and tenant isolation have automated tests;
- important values expose source, period, unit, quality, and kind;
- keyboard use, semantic structure, contrast, and responsive layouts are verified;
- the implementation matches the relevant reference behavior without copying mockup-only hardcoded conclusions;
- documentation is updated when a public contract, formula, or architectural boundary changes.
