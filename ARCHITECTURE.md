# Klarvido Architecture

## Status

This document records the implementation decisions for the synthetic vertical slice and the later replacement of synthetic sources with KSeF, GUS, and NBP adapters.

## Current platform decision

Klarvido extends the platform already present in this repository:

```text
React 19 + Vite + TypeScript + Apollo + Tailwind
                    |
                 GraphQL
                    |
Django 5 + Graphene + Celery + PostgreSQL
                    |
             AWS CDK infrastructure
```

Repository code and configuration are the source of truth for the platform stack. New Klarvido modules extend these existing components and conventions.

## Module boundaries

### Backend

Create one tenant-aware Django product app at `packages/backend/apps/klarvido` with internal modules for:

```text
canonical data
source adapters
calculations and aggregates
data quality and readiness
economic profile
decision contracts and decision engine
actions and outcomes
audit
GraphQL schema
```

This is a modular monolith. Internal modules may be separated by responsibility, but they share one deployment and one database transaction boundary. External integrations must not own domain calculations.

### Frontend

Create `packages/webapp-libs/webapp-klarvido` as the reusable product module. It owns Klarvido GraphQL operations, routes, domain presentation components, tables, charts, and interaction tests. `packages/webapp` owns only application wiring and the authenticated entry point.

### Product reference

The React application and product documents define the maintained product surface. Production code must derive conclusions from canonical backend data rather than static presentation values.

## Data flow

```text
MockDataAdapter now / KSeF, GUS, NBP later
  -> normalized source records
  -> canonical facts
  -> versioned aggregates and metrics
  -> signals
  -> Data Readiness and Safety Gates
  -> Decision Contract and ranked Decision Package
  -> GraphQL
  -> React views
  -> accepted action
  -> implementation evidence
  -> outcome evaluation
  -> audit trail
```

Replacing a source adapter must not require changes to calculations, decisions, GraphQL consumers, or React components.

## Source adapter contract

Every adapter returns normalized records plus source metadata. The minimum conceptual contract is:

```text
source system and external identifier
tenant and company context
record type and schema version
effective date and ingestion time
payload or normalized fields
freshness and validation result
```

`MockDataAdapter` is a real implementation of this contract, not a frontend fallback. Future adapters may add source-specific metadata, but canonical services must depend only on normalized records.

The concrete adapter contract lives in `packages/backend/apps/klarvido/adapters/contracts.py`. Adapters return an immutable `AdapterDataset`; only the ingestion service translates that dataset into Django models. The versioned mock fixture is backend-owned and must not be read from the reference HTML at runtime.

For local development, load or refresh the dataset for an existing tenant with:

```sh
python manage.py load_klarvido_demo --tenant-slug <tenant-slug>
```

The command is idempotent for a tenant and fixture version: repeated execution updates canonical records and source metadata without duplicating invoices.

## Canonical concepts

The initial data model covers the information required by the first product views:

- company and economic profile;
- counterparty with customer/supplier roles;
- sales and purchase invoices;
- invoice corrections and line items where available;
- categories and category assignments;
- source and ingestion metadata;
- calculation periods and versions.

Bank transactions, payroll, inventory, CRM activity, and operational capacity are outside the synthetic vertical slice.

## Financial terminology

Use these code names and Polish labels consistently:

| Code                      | Polish UI label       | Definition                                                       |
| ------------------------- | --------------------- | ---------------------------------------------------------------- |
| `revenue`                 | Przychód              | Sales value in the selected period                               |
| `costs`                   | Koszty                | Purchase or classified cost value in the selected period         |
| `pre_tax_result`          | Wynik przed podatkiem | Revenue minus costs                                              |
| `net_result`              | Wynik netto           | Revenue minus costs minus a verified or explicitly estimated tax |
| `gross_margin`            | Marża brutto          | Pre-tax result divided by revenue                                |
| `net_margin`              | Marża netto           | Net result divided by revenue                                    |
| `percentage_change`       | Zmiana procentowa     | Relative change from a comparison value                          |
| `percentage_point_change` | Zmiana w p.p.         | Arithmetic difference between two percentages                    |

Money uses decimal arithmetic and an explicit ISO currency. Never use binary floating point for persisted or calculated money.

## Analytical result envelope

Metrics, signals, simulations, and decision evidence expose at least:

```text
value and unit
period
source references
calculation version
calculated_at
quality/readiness
kind: fact | estimate | simulation
limitations when applicable
```

The exact GraphQL types will be introduced with the canonical model. This envelope is the compatibility requirement across implementation phases.

## Calculation engine

Deterministic calculations live in `packages/backend/apps/klarvido/calculations`. `PeriodResolver` selects tenant-scoped current and comparison periods from trusted canonical invoices. `CalculationEngine` produces financial KPI, customer and supplier portfolios, concentration, invoice counts, and cost structure without persisting derived values.

Every calculation reads canonical invoices in tenant context and excludes cancelled documents and source records that failed validation. Comparative money values use relative percentage change, while margin comparisons use percentage points. Net result and net margin require an explicit income-tax analytical value; invoice VAT is never substituted for income tax.

The current engine returns Python domain contracts. Task 7 will expose those contracts through GraphQL without moving formulas into resolvers or React components.

## Data quality and readiness

Runtime readiness evaluation lives in `packages/backend/apps/klarvido/readiness`. `ReadinessEngine` calculates source health, validation coverage, freshness, history, identification, line, category, quantity, unit-price, payment-field, and bank-data coverage from tenant-owned canonical records.

Versioned policies select the metrics required by each analysis and return `READY`, `LIMITED`, or `BLOCKED`. A ready result permits a confirmed diagnosis, a limited result permits only an indicative diagnosis, and a blocked result permits no diagnosis. Readiness is not persisted; it is recalculated for the requested tenant, period, and analysis and can be converted to the shared `DataQuality` envelope.

## Decision boundary

The deterministic backend owns facts, calculations, readiness, allowed diagnoses, candidate actions, ranking inputs, and safety constraints. An LLM may translate a completed Decision Package into natural language or answer within that package. It cannot become the source of financial values or bypass blocked readiness.

## Initial vertical slice

The first complete decision family is `WEAKENING_KEY_CUSTOMER`:

```text
synthetic invoices
  -> customer aggregates
  -> declining value/frequency signal
  -> readiness gate
  -> diagnosis with limitations
  -> contact/observe/concentration action candidates
  -> selected action
  -> task status
  -> later revenue observation
  -> outcome evaluation
```

The vertical slice is complete only when a user can navigate from the decision to its source invoices and back to the recorded outcome.

## Failure behavior

- Invalid source records are retained for audit but excluded from trusted aggregates.
- A partial import is visible and cannot silently replace the last complete dataset.
- Missing comparison data returns no change instead of zero change.
- Missing required coverage produces `BLOCKED`; insufficient but usable coverage produces `LIMITED` with limitations.
- External source failure retains the last successful canonical state and marks freshness accordingly.
