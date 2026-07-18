# Vercel deployment

This repository can run the PlayCover → GBox conversion every day through Vercel Cron while keeping `output/catalog.json` in the same GitHub repository.

## Routes

- `GET /gbox/catalog.json` — stable public GBox catalog URL.
- `GET /api/health` — deployment and environment status.
- `GET /api/preview` — protected conversion preview without a commit.
- `GET /api/cron/sync` — protected synchronization endpoint used by Vercel Cron.

## Required Vercel environment variables

Copy the names from `.env.example` and configure at least:

- `CRON_SECRET`: a random secret. Vercel Cron sends it as `Authorization: Bearer <CRON_SECRET>`.
- `GITHUB_TOKEN`: a fine-grained GitHub token restricted to this repository with **Contents: Read and write**.
- `GITHUB_OWNER=defffis`
- `GITHUB_REPO=Open-ipa-Library`
- `GITHUB_BRANCH=main`

The token is needed because a Vercel Function filesystem is ephemeral. The function therefore writes the generated JSON through GitHub's Contents API. A resulting commit triggers the repository's normal Vercel Git deployment and the public catalog URL remains unchanged.

## Source configuration

The Vercel converter reads `config/sources.json` from GitHub and processes enabled entries where either `adapter` or `type` equals `playcover_json` and `catalogUrl` is a valid HTTPS URL.

Example:

```json
{
  "id": "my-playcover-feed",
  "name": "My PlayCover Feed",
  "type": "playcover_json",
  "adapter": "playcover_json",
  "catalogUrl": "https://example.com/library.json",
  "enabled": true,
  "priority": 10,
  "category": "Apps"
}
```

Lower `priority` values win when duplicate bundle identifiers are found. For equal priorities, the newer version wins.

## Schedule

`vercel.json` runs `/api/cron/sync` daily at `03:15 UTC`.

## Safety behavior

The sync is rejected when:

- all enabled PlayCover sources fail;
- the generated catalog contains fewer apps than `MIN_APPLICATIONS`;
- the generated catalog would remove more than `MAX_REMOVAL_PERCENT` of the current catalog;
- the GitHub write token is missing.

No commit is created when only timestamps would change.
