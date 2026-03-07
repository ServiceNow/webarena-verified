# Leaderboard Site

Astro static site. Package manager: **pnpm**.

```bash
pnpm install | pnpm dev | pnpm build | pnpm test | pnpm lint
```

## Local Data

The site resolves its data source via `PUBLIC_LEADERBOARD_MANIFEST_URL` (see `src/scripts/data.js`). When unset, falls back to `public/data/leaderboard_manifest.json`.

Place dummy data files in `public/data/` to run locally without a remote source.
