# Klarvido Design System

## Product character

Klarvido is a quiet operational tool for business owners. It should feel trustworthy, precise, and calm. Information hierarchy comes from spacing, typography, alignment, and restrained semantic color rather than decoration.

The production UI follows the reference mockup's information architecture while using reusable React components and accessible interaction patterns.

## Foundations

### Typography

- Preferred family: Satoshi when a self-hosted licensed asset is available.
- Current production fallback: Inter, then the system sans-serif stack.
- Body: 14 px with comfortable line height.
- Supporting text: 12 px; never reduce essential content below 11 px.
- Page title: 30 px maximum.
- Compact panel title: 15-20 px according to hierarchy.
- Do not scale font size with viewport width and do not use negative letter spacing.

### Core colors

| Token | Value | Purpose |
| --- | --- | --- |
| `primary` | `#0B2545` | Main text, navigation, primary structure |
| `primary-strong` | `#143A66` | Hover and secondary navy |
| `accent` | `#F59E0B` | Calls to action and attention |
| `accent-soft` | `#FFF4DB` | Attention background |
| `background` | `#F7F9FC` | Application background |
| `surface` | `#FFFFFF` | Panels, dialogs, table surfaces |
| `surface-subtle` | `#F8FAFD` | Secondary surface |
| `border` | `#E4EAF1` | Dividers and controls |
| `muted` | `#6B7C93` | Secondary text |
| `success` | `#13A66A` | Positive or confirmed state |
| `success-soft` | `#EAF8F2` | Positive state background |
| `danger` | `#E34D59` | Negative or destructive state |
| `danger-soft` | `#FFF0F1` | Negative state background |
| `info` | `#2A6FDB` | Informational state and links |
| `info-soft` | `#EEF5FF` | Informational background |

Semantic green and red do not change with the selected visual theme. Never communicate status through color alone.

### Shape and elevation

- Cards and panels: 8 px radius.
- Inputs and buttons: 8 px radius.
- Pills and status badges may be fully rounded.
- Use borders as the default separation; shadows remain subtle and are reserved for overlays or clear elevation.
- Do not nest decorative cards. Use sections, dividers, or layout groups inside a card.

### Spacing

Use a 4 px base scale. Common gaps are 8, 12, 16, 24, and 32 px. Dense tables and toolbars use the lower part of the scale; page sections use 24-32 px.

## Components

### Buttons

- Primary commands use the accent color when attention is required and navy for persistent application actions.
- Secondary commands use a neutral surface and border.
- Destructive actions require a semantic danger treatment and confirmation where irreversible.
- Use Lucide icons for familiar icon-only commands and provide tooltips or accessible labels.
- Do not use text in a rounded rectangle when a universally understood icon is clearer.

### Cards and status panels

- Use cards only for individual bounded objects, repeated items, dialogs, or genuinely framed tools.
- KPI cards show label, exact value, comparison context, and optional evidence trend.
- A decision card prioritizes situation, impact, confidence/readiness, limitation, and next action.
- Status text must remain understandable without its icon or color.

### Tables

- Tables are the exact-value companion to charts.
- Headers remain readable and sorting state is announced visually and semantically.
- Filters show their active values and can be cleared individually or together.
- Numeric columns align right; entity and descriptive columns align left.
- Use internal horizontal scrolling on small screens instead of shrinking data into unreadable text.

### Charts

- Recharts is the production charting engine.
- Use fixed or constrained chart heights so loading and interaction do not shift layouts.
- Tooltips include series name, exact value, unit, and period.
- Axes and visible ranges must be clear when they affect interpretation.
- Smoothing is presentation-only and must pass through real observations; never generate intermediate values for analysis.
- Every decision-critical chart has an equivalent exact-value table or drill-down.

### Forms and filters

- Use labels for all fields; placeholders are examples, not labels.
- Use segmented controls for short mode switches, selects for option sets, switches for binary settings, and numeric inputs/sliders for simulations.
- Validation appears next to the affected field and is announced to assistive technology.

### Dialogs and drawers

- Dialogs handle focused confirmation or editing.
- The assistant uses a drawer and never covers an unrecoverable workflow state.
- Focus is trapped while open and returns to the invoking control on close.

## Domain presentation

- `fact`: normal presentation with source access.
- `estimate`: visible `Estymacja` label and assumptions.
- `simulation`: visible `Symulacja` label; never word the output as a forecast.
- `READY`: analysis available.
- `LIMITED`: result available with explicit limitations.
- `BLOCKED`: no diagnosis; show the missing requirement and next possible action.
- Percentage changes use `%`; margin differences use `p.p.`.
- Use `Wynik przed podatkiem` and `Wynik netto`, never the ambiguous standalone `Dochód` in analytical UI.

## Responsive acceptance

Validate every migrated route at:

| Viewport | Expected behavior |
| --- | --- |
| 1440 px | Full navigation, comparison layouts, complete tables |
| 1024 px | Compact navigation and reflowed grids without hidden actions |
| 390 px | Single-column workflow, mobile navigation, internally scrollable tables |

Text and controls must not overlap, clip, or resize their parent unexpectedly. The first viewport should expose the primary decision or task, not a decorative introduction.
