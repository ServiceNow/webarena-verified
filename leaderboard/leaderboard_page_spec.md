# Leaderboard Page Specification

## Status
Draft v1

Related diagrams:
- `leaderboard/leaderboard_flows.md`

## Goal
Define the separate leaderboard static site that displays results with:
- sorting,
- filtering,
- search,
- separate Full/Hard views.

## Framework Choice
Use **Astro + Tabulator** for the leaderboard site:
- Astro for static-site structure and deployment packaging
- Tabulator for the interactive data table

Reason:
- stronger built-in table interactions for future growth,
- good fit for static GitHub Pages deployment,
- keeps implementation maintainable with minimal custom code.

## Page Location
- Leaderboard runs as a separate static site (not an MkDocs content page).
- MkDocs contains a top-level nav link pointing to the leaderboard site URL.

## Starting Implementation Baseline
Initial implementation baseline is the working prototype at:
- `tmp/leaderboard_test_astro`

This prototype is the starting version for productionization and includes:
- single table with Full/Hard switch
- sorting/search/filter/pagination
- KPI cards
- column visibility menu
- CSV/JSON export
- expandable row details
- modernized table styling

## Data Source
The page reads generated JSON from CI.

Primary file:
- `leaderboard-site/public/data/leaderboard.json`

Top-level shape:
- `generated_at`: ISO timestamp
- `full`: list of full-table entries
- `hard`: list of hard-table entries

Entry fields:
- `rank`
- `submission_id`
- `team_name`
- `model_name`
- `overall_score`
- `success_count`
- `failure_count`
- `error_count`
- `missing_count`
- `webarena_verified_version`
- `checksum`

## UX Requirements
- Two table views on one page:
  - `Full`
  - `Hard`
- Default view: `Full`
- Features:
  - column sorting
  - text search (team/model/submission id)
  - version filter
  - pagination
  - clear filters action

## Ranking Display
- Display rank from generated data.
- Primary ranking metric is `overall_score`.
- Any ranking/tie logic is handled during CI generation, not in browser logic.

## Styling
- Match MkDocs Material visual language.
- Reuse Material-like typography, spacing, borders, and colors in page CSS.
- Keep table styling scoped to leaderboard page to avoid side effects.

## Delivery Model
- CI generates leaderboard JSON.
- Leaderboard site renders JSON client-side with Tabulator.
- No server-side runtime required beyond static docs hosting.

## Non-Goals (v1)
- Authenticated/private leaderboard views.
- Inline submission drill-down UI.
- Chart-heavy analytics.

## Prototype References
- Primary baseline: `tmp/leaderboard_test_astro/`
- Legacy plain Tabulator prototype: `tmp/leaderboard_test/`
- Alternative Grid.js prototype: `tmp/leaderboard_test_gridjs/` (comparison only)

## Productionization Checklist

### 1) Repository Structure
- [ ] Create permanent leaderboard site directory (for example `leaderboard-site/`) from `tmp/leaderboard_test_astro/`.
- [ ] Remove temporary/demo-only assets and sample text from production version.
- [ ] Define canonical output data path consumed by the site (for example `leaderboard-site/public/data/leaderboard.json`).

### 2) Data Contract Finalization
- [ ] Freeze `leaderboard.json` schema (required fields and types).
- [ ] Define schema version field for future compatibility (for example `schema_version`).
- [ ] Add validation step for generated JSON before deploy.
- [ ] Document fallback behavior for empty leaderboard (no accepted submissions yet).

### 3) CI Generation Pipeline
- [ ] Implement canonical leaderboard data generator script from accepted submission artifacts.
- [ ] Ensure ranking is deterministic and based on `overall_score`.
- [ ] Ensure hard/full table generation follows submission metadata rules (`leaderboard`, `submit_to_hard`).
- [ ] Generate/update leaderboard data as part of post-merge submission processing.

### 4) Leaderboard Site Build & Deploy
- [ ] Add workflow to build leaderboard site (Astro build).
- [ ] Add workflow to publish leaderboard output to GitHub Pages subpath (for example `/leaderboard/`).
- [ ] Ensure deploy does not overwrite MkDocs content in `gh-pages`.
- [ ] Add concurrency guard so leaderboard deploy jobs do not race.

### 5) Coexistence with MkDocs
- [ ] Add top-level MkDocs nav link to leaderboard site URL.
- [ ] Confirm docs deploy and leaderboard deploy can run independently without clobbering each other.
- [ ] Validate final URLs on Pages:
  - MkDocs root/versioned docs
  - leaderboard static site

### 6) UX Hardening
- [ ] Confirm responsive behavior on mobile/tablet/desktop.
- [ ] Add empty-state and error-state messaging (fetch failure, malformed data).
- [ ] Verify accessibility basics (keyboard navigation, contrast, focus states).
- [ ] Confirm link behavior for submission artifacts/details.

### 7) Security & Safety
- [ ] Keep leaderboard site fully static (no secrets in frontend).
- [ ] Ensure all displayed strings are treated as untrusted input and safely rendered.
- [ ] Pin dependency versions and enable dependency update policy.

### 8) Observability & Operations
- [ ] Add deploy summary output in CI (rows generated, full/hard counts, timestamp).
- [ ] Add smoke check after deploy (fetch leaderboard JSON, verify HTTP 200).
- [ ] Add rollback procedure (re-deploy last known good artifact/commit).

### 9) Documentation
- [ ] Add maintainer runbook for leaderboard generation/deploy.
- [ ] Add contributor-facing note explaining leaderboard update latency after PR merge.
- [ ] Link submission CI spec and leaderboard page spec from main docs index.
