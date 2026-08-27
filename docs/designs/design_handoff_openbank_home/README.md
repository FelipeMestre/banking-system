# Handoff: OpenBank — Home (post-login dashboard)

## The design system is binding — read it first
This design is built on the **Modernist** design system, and it is a constraint, not a
suggestion. Before writing any UI code, read both files in this bundle:

- \`_ds/modernist-.../readme.md\` — the rules (what to do, what never to do)
- \`_ds/modernist-.../styles.css\` — the token sheet: every color, font, space, radius, shadow

Then work by these rules:

1. **Never hard-code a value the tokens already carry.** No hex codes, no font names, no raw
   px where a \`--space-*\` exists. Every value comes from a \`var(--*)\`.
2. **Zero corner radius, anywhere.** \`--radius-md\` is \`0\` on purpose.
3. **2px rules do the organising.** Sections are separated by
   \`2px solid var(--color-divider)\`, not by whitespace and not by hairlines. Nothing floats;
   no shadows on this screen.
4. **Everything flush left** — headings, copy, and the labels inside wide buttons. Never
   center a button label.
5. **The accent (#ec3013) is used sparingly** — the primary action and small emphasis only.
   The screen is mostly ink on ground. For body-size text in the accent, use
   \`--color-accent-700\`, never the base accent (contrast).
6. **Archivo for everything**, 400/600/800. All figures use \`font-variant-numeric: tabular-nums\`.
7. **Lucide icons only** (\`stroke-width: 2\`, \`stroke-linecap: square\`).
8. **Use the system's component classes** (\`.btn\`, \`.btn-primary\`, \`.table\`, \`.card\`, \`.hr\`,
   \`.tag\`, \`.grayscale\`) rather than inventing parallel ones. Its hover, pressed and
   \`:focus-visible\` states are already themed — do not restyle them per page.

If you port the tokens into the target codebase's styling layer (Tailwind config, CSS modules,
theme object), port them **from \`styles.css\`** and keep the names recognisable. If a design
decision is not covered by the token sheet or this README, ask rather than invent.

## Overview
The post-login home screen for OpenBank, a retail/business banking web app. It gives the
customer, in one view: the balance of every deposit account they hold (multi-currency), the
latest cleared movements on the selected account, the remaining limit on their credit card,
and a small set of quick actions.

The design is built on the **Modernist** design system (flat, Archivo, zero corner radius,
2px rules, single red accent on a light ground) and on the domain vocabulary of the existing
`Banking System` codebase (accounts have `account_number`, `currency`, `balance` in
**integer cents**, `status`).

## About the Design Files
The files in this bundle are **design references created in HTML** — a prototype showing the
intended look and behavior. They are *not* production code to copy directly.

The task is to **recreate this design in the target codebase's environment**. That codebase is
the Next.js App Router + TypeScript frontend at `frontend/` (see "Target codebase notes"
below), using its established patterns: server components where there is no state, `lib/money.ts`
for all formatting, `lib/types.ts` for wire types. Do not import the HTML or its inline styles.

## Fidelity
**High-fidelity.** Colors, typography, spacing, and interaction states are final and are all
taken from the Modernist token sheet. Recreate the UI pixel-perfectly, but express the tokens
the way the codebase already expresses them (CSS custom properties in `app/globals.css`, or the
project's styling layer if one is introduced).

One exception: the **credit card** section is invented. The backend has no credit-card entity
(no table in `infra/postgres/init.sql`, no route in `openbankapi/controllers/`). Treat it as a
design proposal that needs an API before it can ship; until then it should be behind a flag.

---

## Screens / Views

### Home
- **Name:** Home (route `/`, replacing the current placeholder `app/page.tsx`)
- **Purpose:** Orient the customer immediately after login — "what do I have, what just moved,
  how much card headroom is left" — and route them to the next action.

#### Layout
Top-level: CSS grid, `grid-template-columns: 76px 1fr`, `min-height: 100vh`, background
`--color-bg`.

**Column 1 — sidebar** (76px, `border-right: 2px solid var(--color-divider)`, flex column,
centered):
- Brand block: 72px tall, full width, `border-bottom: 2px solid var(--color-divider)`,
  containing a 22×22px solid `--color-accent` square (the OpenBank mark).
- Nav stack: `padding: 14px 0`, flex column, `gap: 2px`. Five 52×52px icon buttons.
- Footer: `margin-top: auto`, `padding: 16px 0`, the text "v2.1" at
  `font: 600 9px/1`, `letter-spacing: .12em`, color `--color-neutral-500`,
  `writing-mode: vertical-rl`.

**Column 2 — content** (flex column):
- **Topbar**: 72px tall, `border-bottom: 2px solid var(--color-divider)`,
  `padding: 0 32px`, `justify-content: space-between`.
- **Main**: `padding: 28px 32px 40px`, flex column.
  - Accounts section header row (label left, timestamp right), `margin-bottom: 14px`.
  - Accounts strip: `grid-template-columns: repeat(3, minmax(0,1fr))`, `gap: 0`,
    `border: 2px solid var(--color-divider)` with `border-right-width: 0` — each cell
    supplies its own `border-right: 2px`, so the internal dividers and the outer frame are
    the same weight. **This is the key structural move: the cards are cells of one grid, not
    separate cards with gaps.**
  - Lower area: `grid-template-columns: minmax(0,1fr) 300px`, `gap: 32px`,
    `margin-top: 36px`, `align-items: start` — transactions left, aside right.

#### Components

**1. Sidebar icon button** (×5)
- Size 52×52px, `border: 0`, `border-radius: 0`, flex-centered, `cursor: pointer`.
- Icon: Lucide, 21×21px, `stroke-width: 2`, `stroke-linecap: square`, `fill: none`.
- Items in order, with their Lucide names: Home (`home`), Cards (`credit-card`),
  Payments (`arrow-left-right`), Support (`headphones`), Settings (`settings`).
- **Active** (Home): `background: var(--color-accent)` (#ec3013), icon
  `var(--color-bg)` (#f3f2f2). Hover: `var(--color-accent-600)` (#dd2b0f).
- **Inactive**: `background: transparent`, icon `var(--color-neutral-700)` (#605d5d).
  Hover: `background: var(--color-neutral-200)` (#eae7e7), icon `var(--color-text)`.
- Each carries a `title` attribute for the tooltip; add `aria-label` in the real build.
  The active item carries `aria-current="page"`.

**2. Topbar**
- Left group: `display: flex`, `align-items: baseline`, `gap: 14px`.
  - `<h1>` greeting — "Good afternoon, Helena" — Archivo 800, **20px**,
    `letter-spacing: -.01em`, `margin: 0`.
  - Meta — "Last sign-in 26 Aug 2026, 09:14 GMT" — 12px, `--color-neutral-600` (#7d7979),
    `white-space: nowrap`.
- Right group: `display: flex`, `align-items: center`, `gap: 24px`, containing:
  1. Security chip: Lucide `lock` 14×14 + "SECURED SESSION" at
     `font: 600 11px/1`, `letter-spacing: .1em`, `text-transform: uppercase`,
     `--color-neutral-700`, `gap: 8px`.
  2. Vertical rule: 2px × 28px, `var(--color-divider)`.
  3. **Logo, top right (as specified by the client):** 14×14px `--color-accent` square +
     wordmark "OpenBank" in Archivo 800, **19px**, `letter-spacing: -.02em`, `gap: 10px`.

**3. Account cell** (×3 — the selector for the transaction table)
- Rendered as a `<button>`: `text-align: left`, `border: 0`,
  `border-right: 2px solid var(--color-divider)`, transparent background, `padding: 0`.
  Hover: `background: var(--color-neutral-200)`.
- **Selection indicator**: a 4px-tall bar across the top of the cell —
  `var(--color-accent)` when selected, `transparent` otherwise. No other selected styling.
- Body: `padding: 18px 20px 20px`, flex column, `gap: 14px`.
  - Row 1 (space-between): account label, e.g. "CURRENT ACCOUNT" —
    `font: 600 11px/1`, `letter-spacing: .1em`, uppercase, `--color-neutral-700`;
    currency code "USD" — `font: 600 11px/1`, `letter-spacing: .08em`, `--color-neutral-600`.
  - Row 2 (baseline, `gap: 6px`): currency symbol Archivo 800 **16px** `--color-neutral-700`;
    amount Archivo 800 **34px**, `letter-spacing: -.03em`, `line-height: 1`,
    `font-variant-numeric: tabular-nums`.
  - Row 3 (space-between, 12px, `--color-neutral-600`): masked number "•••• 3333"
    (`letter-spacing: .04em`, tabular-nums) and status "Active".
- Data (all balances integer cents, matching the API):
  | Label | Currency | Symbol | Number | balance (cents) | Displayed |
  |---|---|---|---|---|---|
  | Current account | USD | $ | 4111 0000 2222 3333 | 4582136 | $45,821.36 |
  | Euro account | EUR | € | 6820 4417 9003 1188 | 1897420 | €18,974.20 |
  | Sterling account | GBP | £ | 3390 1174 5520 8841 | 2144099 | £21,440.99 |
- Default selected: **the first account** (index 0).

**4. Transactions table** (left column of the lower grid)
- Header row above it: `h6` "LATEST TRANSACTIONS — <selected account label>" (12px, uppercase,
  `letter-spacing: .08em`) on the left; link "All activity" (Archivo 600, 12px,
  `--color-accent`) on the right, baseline-aligned, `margin-bottom: 14px`.
- `<table>`: `width: 100%`, `border-collapse: collapse`, `font-variant-numeric: tabular-nums`.
- Columns: **Date** (left) · **Description** (left) · **Credit** (right) · **Debit** (right) ·
  **Balance** (right). Credit and debit are deliberately **separate columns** — no signed
  single column.
- `<th>`: `font: 600 10px/1`, `letter-spacing: .1em`, uppercase, `--color-neutral-700`,
  `padding: 0 12px 10px 0` (last cell `0 0 10px 12px`),
  `border-bottom: 2px solid var(--color-divider)`.
- `<td>`: `padding: 13px 12px 13px 0` (last cell `13px 0 13px 12px`),
  `border-bottom: 1px solid var(--color-neutral-300)`, `vertical-align: top`,
  `white-space: nowrap` on all but Description.
  - Date: 12px, `--color-neutral-700`.
  - Description: two lines — description 14px `font-weight: 600`; reference below at 11px,
    `--color-neutral-600`, `letter-spacing: .04em`, `margin-top: 2px`.
  - Credit: 14px, `font-weight: 600`, `--color-neutral-900` (#2d2b2b).
  - Debit: 14px, `font-weight: 600`, `--color-accent-700` (#ae1800) — the deep ramp step,
    because accent-500 does not clear 4.5:1 at 14px.
  - Empty credit/debit cells render an em dash "—", never a blank.
  - Balance: 13px, `--color-neutral-700`.
- Footer row under the table, `margin-top: 14px`, 11px, `--color-neutral-600`,
  space-between: "Showing N of M movements" · "Cleared balances only · Pending items excluded".
- **Running balance rule:** the Balance column is the account balance *after* that movement,
  computed by walking **backwards** from the account's current balance, newest row first:
  `balanceAtRow = running; running = running - credit + debit`. In production this must come
  from the read model, not be derived client-side — see "State Management".

**5. Credit card panel** (aside, top) — *invented; see Fidelity*
- `border: 2px solid var(--color-divider)`, `padding: 20px`, flex column, `gap: 18px`.
- Row 1: a 54×36px solid `--color-text` (#201e1d) tile holding a Lucide `credit-card` icon
  26×26 in `--color-bg`; on the right, "SIGNATURE" (`font: 600 11px/1`, `.1em`, uppercase,
  `--color-neutral-700`) over "•••• 8842" (12px, `--color-neutral-600`, tabular-nums,
  `letter-spacing: .06em`, `margin-top: 4px`), right-aligned.
- Row 2: label "AVAILABLE LIMIT" (`font: 600 10px/1`, `.1em`, uppercase,
  `--color-neutral-700`, `margin-bottom: 8px`) over "£" (Archivo 800, 15px,
  `--color-neutral-700`) + "6,420.00" (Archivo 800, **32px**, `letter-spacing: -.03em`,
  `line-height: 1`, tabular-nums), baseline-aligned, `gap: 5px`.
- Row 3: a 2px `--color-neutral-300` track with a 36%-wide 2px `--color-accent` fill —
  the utilisation bar. 2px, not a rounded meter: the system does not round corners.
- Row 4: "£3,580.00 used" / "of £10,000.00" — 11px, `--color-neutral-600`, tabular-nums,
  space-between.
- Per the brief, this section is **just a card icon plus the remaining limit**; the
  utilisation bar and used/total line are additions you can drop without harm.

**6. Quick actions** (aside, middle)
- `h6` "QUICK ACTIONS", then a flex column with `gap: 2px` of three full-width buttons:
  "Send a transfer" (`.btn .btn-primary .btn-block`), "Pay a bill" and "Download statement"
  (`.btn .btn-secondary .btn-block`).
- **Labels are flush left** (`justify-content: flex-start`) — a Modernist rule, not a
  preference. Never center them.
- "Send a transfer" should route to the existing `/transfer` page.

**7. Total position** (aside, bottom)
- `h6` "TOTAL POSITION", then `border-top: 2px solid var(--color-divider)`,
  `padding-top: 14px`, flex column, `gap: 10px`, 13px text, tabular-nums.
- Rows (label `--color-neutral-700` left / value `font-weight: 600` right):
  Deposits £68,412.55 · Card balance −£3,580.00 · **Net** £64,832.55 (the Net row has
  `border-top: 1px solid var(--color-neutral-300)`, `padding-top: 10px`, and its value is
  Archivo 800 16px).
- Caption: "Converted at ECB reference rates, 26 Aug 2026." — 10px, `--color-neutral-600`.
- **This whole section is a design proposal.** It needs an FX rate source and a card balance;
  cut it if neither exists.

---

## Interactions & Behavior
- **Account selection** is the only real interaction. Clicking an account cell sets
  `selected` and re-renders the transactions table (header label, rows, running balance) and
  the "Showing N of M" footer. Default `selected = 0`. Selection is expressed *only* by the
  4px accent bar on the cell.
- **Hover states**: sidebar buttons and account cells tint as documented above. Table rows do
  **not** have a hover state in this design; add one (`--color-neutral-100`) only if rows
  become clickable.
- **Focus**: do not override. Modernist supplies
  `:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 2px }` globally —
  every button here must be reachable by keyboard and show it. Account cells are real
  `<button>`s for exactly this reason; if you make them a radiogroup instead, keep the
  keyboard behaviour.
- **No animations or transitions.** The system is flat and static; a tint change is instant.
  Do not add fades to the selection change.
- **Loading state** (to build; not in the mock): account cells and table rows should render as
  skeletons keeping the same 2px frame and row heights, so nothing reflows when data lands.
  Balance figures are the last thing to appear — never show a zero balance as a placeholder.
- **Error state** (to build): if accounts fail to load, replace the accounts strip with a
  bordered cell carrying the message and a "Try again" `.btn-secondary`. If *transactions*
  fail but balances loaded, keep the balances and put the error in the table area only — a
  balance is the more important of the two and should not be hidden by a failure in the other.
- **Empty state** (to build): an account with no movements shows one full-width bordered row,
  "No movements in the last 90 days", 13px, `--color-neutral-600`.
- **Responsive**: the mock is desktop-only (designed at ~1440px, works down to ~1100px).
  Below ~1000px the intended behaviour is: aside drops under the transactions column
  (single-column lower grid); accounts strip becomes a single-column stack, each cell keeping
  its 2px rule as a `border-bottom`; sidebar collapses to a 56px icon rail. Not designed —
  confirm before building.
- **A11y note**: the Balance column carries an accessible-name-free "—" in credit/debit cells;
  give those cells `aria-label="none"` or use `<td><span aria-hidden>—</span></td>` so screen
  readers don't read a dash as a value.

## State Management
Client state in the mock is a single value:
- `selected: number` — index of the active account. Default `0`. Set by clicking an account cell.

Props exposed as design tweaks (keep or drop as you like):
- `showCreditCard: boolean` (default `true`) — hides the credit card panel. Useful as the
  real feature flag while the card API does not exist.
- `showRunningBalance: boolean` (default `true`) — blanks the Balance column.
- `transactionCount: number` (default `6`, range 4–8) — rows shown.

Data fetching required in the real build:
- **Accounts for the logged-in customer.** No such endpoint exists yet. The schema has
  `idx_accounts_customer_id` for exactly this read, and the frontend already documents the gap
  in `lib/placeholder-account.ts` ("it exists only so the home page has something to render
  while the v2 account-lookup endpoint does not exist yet"). You will need something like
  `GET /customers/{id}/accounts` before this screen is real.
- **Transactions for an account.** Also does not exist. Per the README, "Balances are Flink
  state, not a queryable store" and there is no `GET /accounts/{id}/balance`; movements live
  in the `account-events` topic. A read model — projected from `account-events`, the same way
  `accounts.balance` is projected by the `account-balances` consumer — is the correct source,
  and it should carry the **running balance per movement** so the UI never derives it.
- **Credit card summary.** No entity, no endpoint. Blocked.
- Amounts stay **integer cents on the wire and in state**, formatted only at render. The mock's
  formatter is the same integer-arithmetic approach as `lib/money.ts`
  (`formatCents` — split whole and fraction with integer division, never divide by 100) and
  masking follows `maskAccountNumber`. **Reuse those functions; do not write new ones.**
  The mock extends them only by prefixing a per-account currency symbol instead of a hard `$`
  — `formatCents` currently hard-codes the dollar sign, which a multi-currency home page
  makes wrong. Widening it to take a currency is the one change this design forces on
  `lib/money.ts`.

## Design Tokens
All from `_ds/modernist-.../styles.css` — take them from the stylesheet, not from this list;
the list is here so values can be checked at a glance.

**Colors**
| Token | Value | Used for |
|---|---|---|
| `--color-bg` | #f3f2f2 | page ground, icon on accent fill |
| `--color-text` | #201e1d | body text, card icon tile |
| `--color-accent` | #ec3013 | logo mark, active nav, selection bar, utilisation fill, primary button |
| `--color-accent-600` | #dd2b0f | accent hover |
| `--color-accent-700` | #ae1800 | debit amounts (body-size accent text) |
| `--color-divider` | `color-mix(in srgb, #201e1d 40%, transparent)` | every 2px rule |
| `--color-neutral-200` | #eae7e7 | hover tint |
| `--color-neutral-300` | #d7d3d3 | 1px table row rules, meter track |
| `--color-neutral-500` | #9b9797 | sidebar version text |
| `--color-neutral-600` | #7d7979 | meta and caption text |
| `--color-neutral-700` | #605d5d | labels, inactive icons |
| `--color-neutral-900` | #2d2b2b | credit amounts |

**Spacing** — `--space-1..8`: 4 / 8 / 12 / 16 / 24 / 32px. Layout paddings in this screen:
32px page gutter, 28px top, 20px inside cells, 32px lower-grid gap, 36px section gap.

**Typography** — Archivo (400 / 600 / 800) for both heading and body; `--font-heading` weight 800.
Sizes used: 34px and 32px (balances), 20px (h1), 19px (wordmark), 16px (net figure), 14px
(table amounts, buttons), 13px (balance column, aside rows), 12px (meta, dates), 11px (labels,
captions), 10px (table headers, caption), 9px (version). Uppercase labels carry
`letter-spacing: .08–.12em`; display figures carry `-.03em`. **All figures use
`font-variant-numeric: tabular-nums`** so columns align — this is not optional in a ledger UI.

**Radius** — `0` everywhere. `--radius-sm/md/lg` are all 0px on purpose. Do not round anything,
including the utilisation meter and the avatar-less logo mark.

**Shadows** — none used. The screen is organised entirely by 2px rules; nothing floats.

## Assets
- **Icons**: Lucide (https://lucide.dev), as the design system requires — `home`,
  `credit-card`, `arrow-left-right`, `headphones`, `settings`, `lock`. They are inlined as
  hand-written SVG paths in the mock at `stroke-width: 2`, `stroke-linecap: square` to match
  the system's squared geometry. In the real build, install `lucide-react` and set the same
  stroke props globally rather than copying the mock's paths.
- **Logo**: there is no OpenBank logo asset. The mark is a solid `--color-accent` square
  standing in for one, in two sizes (22px sidebar, 14px topbar). **Replace with the real
  asset**; the wordmark is set in Archivo 800.
- **Fonts**: Archivo from Google Fonts, imported by the design system's `styles.css`. Self-host
  it in production.
- **Images**: none. If photography is ever added, it goes through the system's `.grayscale`
  wrapper — the system does not permit tinted or colour imagery.

## Files
- `OpenBank Home.dc.html` — the design. A single self-contained HTML file: the markup is the
  layout, and a small script block at the end holds the mock account/transaction data and the
  selection logic. Open it in a browser to interact with it.
- `_ds/modernist-57303892-aaaf-40a5-a1ab-2474c615593f/styles.css` — the Modernist token sheet
  and component classes the design consumes. **Read this for exact values.**
- `_ds/modernist-57303892-aaaf-40a5-a1ab-2474c615593f/readme.md` — the design system's own
  guide: the do's and don'ts (no radius, flush-left labels, 2px rules, accent used sparingly)
  that this screen follows.

## Target codebase notes
Built against the `Banking System` repo. Relevant existing files:
- `frontend/app/page.tsx` — the current home page: a heading and a single `AccountCard` fed by
  a fixture. **This screen replaces it.**
- `frontend/app/layout.tsx` — root layout; the sidebar + topbar shell introduced here belongs
  in a layout, not in the page.
- `frontend/app/globals.css` — the current token set (`--bg`, `--surface`, `--accent: #2f6feb`,
  a dark-mode block, 12px radii, element-level styling of `button`/`input`/`a`). Modernist
  **replaces** this: different palette, zero radius, Archivo, and no dark mode is designed.
  Decide deliberately whether to drop the `prefers-color-scheme` block or design a dark
  Modernist ground — do not let the two token systems coexist.
- `frontend/components/AccountCard.tsx` — the presentational account card; the new account cell
  supersedes it and is the natural place to evolve it.
- `frontend/lib/money.ts` — `formatCents`, `maskAccountNumber`, `parseCentsInput`. Reuse;
  see the currency-symbol note above.
- `frontend/lib/types.ts` — `Account` (`account_number`, `currency`, `balance` cents,
  `status: active | blocked | closed`). The mock's data conforms to it. There is **no**
  transaction type yet — one needs adding.
- `frontend/lib/placeholder-account.ts` — the fixture, explicitly marked "FAKE DATA … do not
  wire this to a live source without replacing it entirely". Same applies to the mock's data.
- `frontend/app/transfer/page.tsx` — the existing transfer screen "Send a transfer" should
  link to. It is currently unstyled by this design; expect a follow-up to bring it onto
  Modernist and under the same shell.

## Open questions for the designer
1. The **credit card**, **total position**, and FX conversion have no backend. Which of these
   are real roadmap items and which should be cut from the screen?
2. Only the `status: "active"` case is designed. What should a **blocked** or **closed**
   account cell look like — and can a blocked account still be selected to view history?
3. The screen assumes exactly three accounts and a 3-column strip. What happens at **one
   account**, and at **six**? (Suggestion: cells keep a min-width and the strip wraps to a
   second row, dividers still 2px.)
4. Responsive/mobile is undesigned (see Interactions).
5. Transactions show cleared items only. Is there a **pending** state to design?
