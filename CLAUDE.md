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

After the sync script runs, a second step reads `/tmp/written_back.txt` and commits any files the script wrote `confluence_id` back to, using `[skip ci]` to prevent re-triggering.

**Script** (`scripts/sync_to_confluence.py`) — uses `atlassian-python-api` and the Confluence v1 REST API (`/wiki/rest/api/content`). Key flow:

1. Loads `.confluenceignore` patterns at startup; skips any matching file on both sync and delete.
2. **Sync path**: reads frontmatter (`python-frontmatter`), then:
   - `draft: true` → skip entirely
   - `confluence_id` present → `update_page()` directly by ID
   - Otherwise → look up by `title` (frontmatter) then fall back to path-based title, then create if still not found
   - After first find/create: writes `confluence_id` back to the file
3. **Delete path**: reads deleted file content from `git show HEAD^:{path}` to retrieve `confluence_id` from frontmatter; falls back to path-based title lookup if not available.
4. `resolve_parent_chain()` walks directory segments, calling `get_or_create_page()` for each folder level. Results cached in `_page_id_cache` (module-level dict) to avoid redundant API calls within a run.

**Page title convention**: full relative path without extension — e.g. `docs/api/endpoints.md` → title `docs/api/endpoints`. Folder pages also use cumulative paths: `docs`, `docs/api`. Override per-file with `title` in frontmatter.

**`.confluenceignore`**: gitignore-style pattern file at the repo root. Loaded at runtime with `fnmatch`/`Path.match()`. `README.md`, `CLAUDE.md`, and `docs/drafts/**` excluded by default.

## Confluence API Notes

- `update_page()` from `atlassian-python-api` handles version incrementing internally — do not pass `version_number`
- Labels use a direct `confluence.post("rest/api/content/{id}/label", data=[...])` call rather than `set_page_label()` to avoid silent failures
- Authentication uses email + API token with `cloud=True`

## Required GitHub Secrets

`CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_SPACE_KEY`
