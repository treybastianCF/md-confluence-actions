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

**Workflow** (`.github/workflows/sync-to-confluence.yml`) — detects changed and deleted `.md` files, then passes them to the script via `CHANGED_FILES` and `DELETED_FILES` env vars. Handles three cases in the "Determine files to sync" step:
- `workflow_dispatch` or first push (before SHA all zeros) → `git ls-files '*.md'` for full sync
- Normal push → `tj-actions/changed-files` outputs

**Script** (`scripts/sync_to_confluence.py`) — uses `atlassian-python-api` and the Confluence v1 REST API (`/wiki/rest/api/content`). Key flow:
1. `resolve_parent_chain()` walks directory segments of a file path, calling `get_or_create_page()` for each folder level. Results are cached in `_page_id_cache` (module-level dict) to avoid redundant API calls within a run.
2. `sync_page()` converts markdown to HTML via the `markdown` library (with `fenced_code`, `tables`, `toc` extensions), then creates or updates the Confluence page.
3. `delete_page()` looks up the page by title and calls `remove_page()`.

**Page title convention**: full relative path without extension — e.g. `docs/api/endpoints.md` → title `docs/api/endpoints`. Folder pages also use cumulative paths: `docs`, `docs/api`. This guarantees uniqueness within the Confluence space.

**Confluence API notes**: `update_page()` from `atlassian-python-api` handles version incrementing internally — do not pass `version_number`. Authentication uses email + API token with `cloud=True`.

## Required GitHub Secrets

`CONFLUENCE_URL`, `CONFLUENCE_EMAIL`, `CONFLUENCE_API_TOKEN`, `CONFLUENCE_SPACE_KEY`
