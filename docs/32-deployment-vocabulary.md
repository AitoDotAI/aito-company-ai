# Deployment vocabulary

*How another company runs this on its own data.*

## The problem this solves

`schema.py` is this repository's own business written down. Its customers are
segmented into `accounting / erp / ecommerce / analytics / consultancy`, its
deals stall on `consultant_lock`, its posts go to `linkedin / hackernews`.

Rule 3 (`docs/00`) turns every one of those into a hard gate: an unknown value
raises with the offending row rather than being coerced or skipped. That is
right for a pipeline and fatal for a newcomer — before this existed, another
company's **first CSV row raised**, and no amount of documentation made the
product usable on their data.

The gate is not the problem. The vocabulary being ours is.

## Using it

Point `COMPANY_AI_VOCABULARY` at a JSON file naming the sets to replace:

```json
{
  "SEGMENTS":      ["public-sector", "retail", "industry", "finance", "other"],
  "TIERS":         ["strategic", "growth", "long-tail"],
  "DEAL_BLOCKERS": ["none", "procurement", "framework-agreement", "budget-cycle"],
  "PLATFORMS":     ["linkedin", "blog"]
}
```

A set you do not name keeps its default, so you can start by replacing only
`SEGMENTS` and grow into the rest. Validation stays exactly as strict: a row
whose segment is not in *your* list still raises with the row attached.

## What may be replaced, and what may not

**Overridable** — descriptive vocabulary, nothing in the code reads their
values:

| | |
|---|---|
| who you sell to | `SEGMENTS` `TIERS` `SOURCES` `LIFECYCLES` `TECHNICAL_ROLES` |
| how you reach them, why deals stall | `TOUCH_CHANNELS` `DEAL_BLOCKERS` |
| what you publish, and where | `MATERIAL_TYPES` `PLATFORMS` `TONES` `POST_FORMATS` `POST_TOPICS` |
| the rest | `DECISION_TYPES` `EVENT_TYPES` `WEB_SOURCES` `DEVICES` `LANDING_PAGES` |

**Structural, and refused** — code branches on these values, so replacing them
would not configure the product, it would break it:

- `DEAL_STAGES` — a deal is `won` *because* its stage is `closed_won`.
- `WINDOWS` — the brief picks a call window from the clock (`brief.py`), and
  `schedule.py` has rules keyed to specific windows.
- `TODO_AREAS` — the dashboard's views are keyed on them.
- every `*_STATUS`, `USER_ROLES`, `LINKED_TYPES` — lifecycle and permission
  logic.

Naming one of those raises and lists what *is* available, rather than being
ignored and leaving you to wonder why your vocabulary did not take. Same for a
set that does not exist at all.

Widening this list is a real piece of work, not a config change: it means
removing the code's dependency on the values first. `WINDOWS` is the clearest
candidate and the clearest warning — five modules read `"0800"` directly.

## Defaults derive from your vocabulary

Anything that previously assumed a value now derives it. A surface that scores
"the usual platform" calls `schema.default_platform()`, which is `linkedin`
when you publish there and your first platform otherwise — so a deployment
that has never heard of LinkedIn is not quietly broken.

## What this does not fix

Your data still has to match the shapes in `docs/02-schema.md` — the columns,
not the values. Bringing a rolodex means producing `rolodex.csv` with the
documented columns; the vocabulary file is what lets the *values* in those
columns be yours.

## Checking your data before you load it

```sh
./do validate path/to/your/export       # no Aito instance needed
```

Rule 3 still holds — nothing loads if anything fails — but the refusal is now
useful on a first export. Every CSV in the directory is parsed, **every**
failed check is collected (not just the first on each row), and identical
failures are grouped:

```
rolodex.csv          61 rows  62 problem(s)
    unknown segment 'public-sector'  (21 rows: line 2, 4, 8, 9, …)
      → allowed: accounting, analytics, … — or add it to SEGMENTS in your
        vocabulary file (COMPANY_AI_VOCABULARY, docs/32)
    created is not an ISO date: '12.03.2026'  (1 row: line 14)
    duplicate contact_id 'sc004' (first on line 5)  (1 row: line 62)
```

Three hundred bad rows are usually three or four fixes, and most are answered
by the vocabulary file. Where a value belongs to a structural set, the hint
says so instead of suggesting an override that would be refused.

`load_all` (and so `./do seed`) runs the same check first and raises
`DataProblems` — an `AssertionError`, so existing handling still catches it —
with the full report.

## The knowledge graph follows your data

The graph's example questions used to name this repository's home turf outright
— "an accounting account", "Which CFOs…", "where we know a CTO" — so on another
company's data the showcase cards came back empty. Each parameter is now
resolved from what is loaded, by an Aito query:

- the industry is the one with **the most deals** (not the best win rate, which
  picks a thin segment whose rate is noise);
- the person is the **commonest non-technical role** at accounts in that
  industry — who you would usually be talking to there;
- the technical contact is whatever `TECHNICAL_ROLES` says. One role or several:
  several become an `$or` of whole `$exists` clauses, because the engine
  rejects an `$or` inside one.

On the shipped seed these resolve to exactly the values the cards always used,
so the demo is unchanged. On an empty instance they fall back to *your*
configured vocabulary rather than to ours.
