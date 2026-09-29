# Klarvido Frontend Instructions

These instructions extend the repository-level `AGENTS.md` for files under `packages/webapp`.

## Architecture

- Preserve the existing login, session, tenant, role, route-guard, Apollo, and translation infrastructure.
- Klarvido product routes must be implemented as native React views.
- Product components belong in `@sb/webapp-klarvido`; the main application only wires routes, providers, and product entry points.
- Fetch product data through typed GraphQL operations. Do not import fixture arrays into React components.
- Keep server data in Apollo. Keep only transient view state such as an open dialog or local filter in component state.

## Component stack

- Reuse shared shadcn-based primitives from `@sb/webapp-core/components/ui` before adding components.
- Add missing shadcn components with the pinned command documented in `CLAUDE.md`; never use an unpinned latest CLI.
- Use Lucide icons, Recharts for financial charts, and TanStack Table for feature-rich data tables.
- Use React Hook Form for forms and the repository's GraphQL error helpers for mutations.
- Do not add a second general-purpose component library.

## Product UI rules

- The default home is decision-first: urgent decisions precede exploratory KPI.
- Charts support evidence; exact values remain available through tooltips or tables.
- Never smooth, interpolate, or synthesize values that can be interpreted as real observations.
- Show `fact`, `estimate`, and `simulation` explicitly where confusing them could alter a decision.
- `READY`, `LIMITED`, and `BLOCKED` require text or icon labels; color alone is insufficient.
- A drill-down must preserve the active company, period, and relevant filters.
- Do not simplify a reference workflow merely to reduce component count.

## Visual implementation

- Use tokens from `DESIGN_SYSTEM.md`; avoid one-off colors and arbitrary spacing.
- Use stable chart, table, toolbar, and control dimensions so content changes do not shift the layout.
- Keep operational screens compact and scannable. Do not introduce marketing-page composition.
- Avoid nested cards and decorative containers without information hierarchy.
- Verify at 1440 px desktop, 1024 px compact desktop/tablet, and 390 px mobile widths.
- No clipped labels, overlapping controls, hidden actions, or horizontal page scrolling. Data tables may use an intentional internal horizontal scroll.

## Frontend acceptance

- Include component or interaction tests for filtering, sorting, navigation, and decision actions.
- Include loading, empty, partial-data, blocked, and error fixtures.
- Validate keyboard operation for menus, dialogs, tabs, filters, and tables.
- Compare implementations against the accepted product requirements and design system.
