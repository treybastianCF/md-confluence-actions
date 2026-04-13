---
confluence_id: '4351755327'
---

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Does

On every push to `main` that touches `.md` files, a GitHub Actions workflow syncs changed markdown files to Confluence, mirroring the folder structure as a Confluence page hierarchy. Deleted files remove their Confluence page. A manual `workflow_dispatch` trigger forces a full sync of all markdown files.

## Running the Sync Script Locally

```bash
pip install -r scripts/requirements.txt

CONFLUENCE_URL=https://your-org.atlassian.net \
CONFLUENCE_EMAIL=you@example.com \
CONFLUENCE_API_TOKEN=your-token \
CONFLUENCE_SPACE_KEY=DOCS \
CHANGED_FILES="docs/api/overview.md docs/index.md" \
python scripts/sync_to_confluence.py
```

Set `DELETED_FILES` the same way to test page deletion.

## Architecture

**Workflow** (`.github/workflows/sync-to-confluence.yml`) — detects changed and deleted `.md` files, passes them via `CHANGED_FILES` and `DELETED_FILES` env vars. The "Determine files to sync" step handles three cases:
- `workflow_dispatch` or first push (before SHA all zeros) → `git ls-files '*.md'` for full sync
- Normal push → `tj-actions/changed-files` outputs

After the sync script runs, a second step reads `/tmp/written_back.txt` and commits any files the script wrote `confluence_id` and `confluence_version` back to, using `[skip ci]` to prevent re-triggering.

**Script** (`scripts/sync_to_confluence.py`) — uses `atlassian-python-api` and the Confluence v1 REST API (`/wiki/rest/api/content`). Key flow:

1. Loads `.confluenceignore` patterns at startup; skips any matching file on both sync and delete.
2. **Sync path**: reads frontmatter (`python-frontmatter`), then:
   - `draft: true` → skip entirely
   - `confluence_id` present → `update_page()` directly by ID
   - Otherwise → look up by `title` (frontmatter) then fall back to path-based title, then create if still not found
   - Drift detection: if `confluence_id` and `confluence_version` are both set, fetches the current page version; logs a WARNING if Confluence version has advanced beyond the stored value (meaning someone edited the page directly) before overwriting
   - After every sync: writes `confluence_id` and `confluence_version` back to the file
   - `lock: true` → after syncing, applies a Confluence restriction that limits editing to the service account only
3. **Delete path**: reads deleted file content from `git show HEAD^:{path}` to retrieve `confluence_id` from frontmatter; falls back to path-based title lookup if not available.
4. `resolve_parent_chain()` walks directory segments, calling `get_or_create_page()` for each folder level. Results cached in `_page_id_cache` (module-level dict) to avoid redundant API calls within a run.

**Page title convention**: full relative path without extension — e.g. `docs/api/endpoints.md` → title `docs/api/endpoints`. Folder pages also use cumulative paths: `docs`, `docs/api`. Override per-file with `title` in frontmatter.

**`.confluenceignore`**: gitignore-style pattern file at the repo root. Loaded at runtime with `fnmatch`/`Path.match()`. `README.md`, `CLAUDE.md`, and `docs/drafts/**` excluded by default.

## Confluence API Notes

- `update_page()` from `atlassian-python-api` handles version incrementing internally — do not pass `version_number`; the return value includes `version.number` for the newly created version
- Labels use a direct `confluence.post("rest/api/content/{id}/label", data=[...])` call rather than `set_page_label()` to avoid silent failures
- Authentication uses email + API token with `cloud=True`
- **Archiving**: neither `PUT /rest/api/content/{id}` with `status: "archived"` (silently ignored by v1) nor `PUT /api/v2/pages/{id}` (`PageUpdateAllowedStatus` only allows `CURRENT`/`DRAFT`) work. The correct endpoint is `POST /rest/api/content/archive` with body `{"pages": [{"id": "..."}]}`, called via `confluence._session.post()` to bypass library error mangling
- **Page locking**: uses `PUT /rest/api/content/{id}/restriction` (array payload) with the service account's `accountId` (fetched via `GET /rest/api/user/current` at startup). Called via `confluence._session.put()` to bypass library error mangling. The `byOperation/update` sub-endpoint returns 405 on Confluence Cloud — use the base `/restriction` endpoint instead. `atlassian-python-api` does not have a helper method for restrictions.
- **Write-backs**: `confluence_version` is written back after every sync (not just on first sync), so every run produces a `[skip ci]` commit with updated version metadata in the frontmatter of synced files

## Required GitHub Secrets

`CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_SPACE_KEY`
