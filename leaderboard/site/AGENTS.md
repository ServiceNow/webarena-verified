# Leaderboard Site

Astro static site. Package manager: **npm**.

```bash
npm ci | npm run dev | npm run build | npm test | npm run lint
```

## Local Data

The site resolves its data source via `PUBLIC_LEADERBOARD_MANIFEST_URL` (see `src/scripts/data.js`). When unset, falls back to `public/data/leaderboard_manifest.json`.

Place dummy data files in `public/data/` to run locally without a remote source.
