# Klarvido Implementation Plan

## Status legend

- `[ ]` not started
- `[-]` in progress
- `[x]` complete

## Delivery tasks

- [x] **1. Rules and architecture** - repository instructions, frontend guidance, design system, phased PRD, architecture boundaries, terminology, and definition of done.
- [x] **2. Canonical Data Model** - tenant-scoped company, counterparty, invoice, line, category, source, and period models with migrations.
- [x] **3. Synthetic data adapter** - backend fixtures and `MockDataAdapter` implementing the future source contract.
- [x] **4. Calculation Engine** - versioned KPI, periods, customer/supplier aggregates, concentration, and cost structure.
- [x] **5. Data Quality and Readiness** - calculated completeness, freshness, history, and `READY/LIMITED/BLOCKED` gates.
- [ ] **6. React and shared UI shell** - Klarvido tokens, shadcn primitives, responsive layout, and authenticated navigation without changing auth.
- [ ] **7. Production data views** - overview, invoices, customers, suppliers, and costs through GraphQL, Recharts, and TanStack Table.
- [ ] **8. First decision vertical slice** - `DecisionContract`, `DecisionPackage`, weakening key customer detection, ranking, and workspace.
- [ ] **9. Actions, outcome, and audit** - persistent tasks, status history, first outcome recipe, and traceable evidence.
- [ ] **10. Pilot readiness** - simulations, constrained assistant, product telemetry, accessibility, isolation, and end-to-end verification.

## Current delivery boundary

The implementation target before external integrations is the synthetic vertical slice. It uses the same production contracts and services as future KSeF/GUS/NBP data, but only `MockDataAdapter` is active.

Task 1 is complete when the documentation agrees on stack, module boundaries, data scope, financial terminology, delivery phases, UI rules, and acceptance criteria. Completing documentation does not imply that tasks 2-10 are implemented.

Task 2 is complete with tenant-owned canonical source models, PostgreSQL constraints and indexes, source validation metadata, an immutable analytical value contract, and model isolation tests. Derived KPI values remain runtime results and are not persisted in the canonical tables.

Task 3 is complete with a versioned backend fixture, a typed adapter contract, `MockDataAdapter`, transactional idempotent ingestion, a tenant-scoped management command, and tests that reconcile the fixture with the reference monthly invoice totals.

Task 4 is complete with tenant-scoped period resolution and a deterministic calculation engine for financial KPI, period comparisons, customer and supplier portfolios, concentration, counts, and cost structure. Results are runtime analytical envelopes with source documents and formula versions; net metrics require an explicit income-tax fact or estimate.

Task 5 is complete with tenant-scoped, versioned readiness policies calculated from canonical records. The engine measures completeness, history, freshness, source health, and analysis-specific coverage, and enforces the maximum diagnosis strength allowed by `READY`, `LIMITED`, or `BLOCKED`.
