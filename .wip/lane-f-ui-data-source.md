# Lane F - UI Data Source and Caching

## Goal

Use build-time manifest URL only and keep caching behavior safe.

## Tasks

- [ ] F01 Lock manifest URL to build-time env (`deps: none`)
  - Use `PUBLIC_LEADERBOARD_MANIFEST_URL`
  - No runtime UI override

- [ ] F02 Keep local fallback (`deps: F01`)
  - Fallback to local manifest path for dev

- [ ] F03 Configure production manifest source (`deps: E06`)
  - Point to branch-hosted `leaderboard_manifest.json`

- [ ] F04 Apply caching strategy (`deps: E06`)
  - Manifest: aggressive revalidate/no-store
  - Generation files: aggressive cache (immutable names)

- [ ] F05 Verify user-facing error states (`deps: F01`)
  - Missing manifest
  - Malformed table payloads

## Outputs

- Stable UI data source policy
- Caching behavior aligned with atomic manifest updates
