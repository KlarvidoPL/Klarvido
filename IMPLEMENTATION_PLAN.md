# Klarvido Implementation Plan

## Status legend

- `[ ]` not started
- `[-]` in progress
- `[x]` complete

## Delivery tasks

- [x] **1. Rules and architecture** - repository instructions, frontend guidance, design system, phased PRD, architecture boundaries, terminology, and definition of done.
- [ ] **2. Canonical Data Model** - tenant-scoped company, counterparty, invoice, line, category, source, and period models with migrations.
- [ ] **3. Synthetic data adapter** - backend fixtures and `MockDataAdapter` implementing the future source contract.
- [ ] **4. Calculation Engine** - versioned KPI, periods, customer/supplier aggregates, concentration, and cost structure.
- [ ] **5. Data Quality and Readiness** - calculated completeness, freshness, history, and `READY/LIMITED/BLOCKED` gates.
- [ ] **6. React and shared UI shell** - Klarvido tokens, shadcn primitives, responsive layout, and authenticated navigation without changing auth.
- [ ] **7. Production data views** - overview, invoices, customers, suppliers, and costs through GraphQL, Recharts, and TanStack Table.
- [ ] **8. First decision vertical slice** - `DecisionContract`, `DecisionPackage`, weakening key customer detection, ranking, and workspace.
- [ ] **9. Actions, outcome, and audit** - persistent tasks, status history, first outcome recipe, and traceable evidence.
- [ ] **10. Pilot readiness** - simulations, constrained assistant, product telemetry, accessibility, isolation, and end-to-end verification.

## Current delivery boundary

The implementation target before external integrations is the synthetic vertical slice. It uses the same production contracts and services as future KSeF/GUS/NBP data, but only `MockDataAdapter` is active.

Task 1 is complete when the documentation agrees on stack, module boundaries, data scope, financial terminology, delivery phases, UI rules, and acceptance criteria. Completing documentation does not imply that tasks 2-10 are implemented.
