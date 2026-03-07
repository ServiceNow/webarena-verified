# Lane F - UI Data Source and Caching

## Goal

Use build-time manifest URL only and keep caching behavior safe.

## Status after Lane E merge

- Completed: F01, F02, F03, F04, F05
- Remaining: none

## Tasks

- [x] F01 Lock manifest URL to build-time env (`deps: none`)
  - Use `PUBLIC_LEADERBOARD_MANIFEST_URL`
  - No runtime UI override

- [x] F02 Keep local fallback (`deps: F01`)
  - Fallback to local manifest path for dev

- [x] F03 Configure production manifest source (`deps: E06`)
  - Point to branch-hosted `leaderboard_manifest.json`
  - Wire env at site deploy/build time

- [x] F04 Apply caching strategy (`deps: E06`)
  - Manifest: aggressive revalidate/no-store
  - Generation files: aggressive cache (immutable names)
  - Enforce via request options and/or hosting headers

- [x] F05 Verify user-facing error states (`deps: F01`)
  - Missing manifest
  - Malformed table payloads

## Replanned execution

1. Run site build workflow and confirm resolved `PUBLIC_LEADERBOARD_MANIFEST_URL` in summary.
2. Keep runtime checks in site tests for manifest no-store and generation force-cache behavior.
3. Perform manual browser smoke check against the branch-hosted manifest URL.

## Outputs

- Stable UI data source policy
- Caching behavior aligned with atomic manifest updates
