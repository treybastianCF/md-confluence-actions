# md-confluence-actions

A GitHub Actions pipeline that automatically syncs changed markdown files to Confluence on every push to `main`, mirroring the repository folder structure as a Confluence page hierarchy.

## How It Works

1. You push a commit that includes changes to `.md` files
2. GitHub Actions detects which markdown files changed (only those files, not all of them)
3. The sync script reads each file's frontmatter, converts the body from Markdown → HTML, and creates or updates the corresponding Confluence page
4. After creating or first finding a page, the script writes `confluence_id` back to the file's frontmatter in a follow-up commit — future syncs use this ID directly
5. Folder structure is mirrored: `docs/api/endpoints.md` becomes a page nested under folder pages `docs` → `docs/api` → `docs/api/endpoints`

## Repository Structure

```
.github/workflows/sync-to-confluence.yml   # The Actions workflow
scripts/sync_to_confluence.py              # Sync script
scripts/requirements.txt                   # Python dependencies
.confluenceignore                          # Patterns for files to exclude from sync
docs/                                      # Your markdown documents
```

## Setup

### 1. Get a Confluence API Token

1. Log in to [id.atlassian.com](https://id.atlassian.com)
2. Go to **Security → API tokens → Create API token**
3. Copy the token value

### 2. Find Your Confluence Space Key

Open any page in your target Confluence space. The space key appears in the URL:
`https://your-org.atlassian.net/wiki/spaces/SPACEKEY/...`

### 3. Configure GitHub Secrets

In your GitHub repository go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `CONFLUENCE_URL` | `https://your-org.atlassian.net` (no trailing slash) |
| `CONFLUENCE_EMAIL` | The email address of the Atlassian account that owns the API token |
| `CONFLUENCE_API_TOKEN` | The API token from step 1 |
| `CONFLUENCE_SPACE_KEY` | The short space key from step 2 |

### 4. Push to Main

Any push to `main` that includes `.md` file changes will trigger the sync. On the first push, all markdown files in the repo are treated as new and the full hierarchy is created in Confluence.

To force a full sync at any time, go to **Actions → Sync Markdown to Confluence → Run workflow**.

## Frontmatter

All frontmatter fields are optional. Add them to the top of any markdown file:

```yaml
---
title: "My Page Title"      # Overrides the default path-based title in Confluence
draft: true                  # Exclude this file from sync entirely
labels:                      # Confluence labels to apply to the page
  - api
  - reference
confluence_id: "4351721583"  # Auto-populated after first sync — do not set manually
---
```

**`confluence_id`** is written back automatically after the first sync. Once set, the script uses it for all future lookups so renaming `title` is always safe.

## Page Title Convention

By default, page titles use the full relative path without the `.md` extension:

- `docs/index.md` → **docs/index**
- `docs/api/endpoints.md` → **docs/api/endpoints**

This guarantees uniqueness within the Confluence space. Override with `title` in frontmatter for a human-readable title.

## Excluding Files

Add patterns to `.confluenceignore` at the repo root to prevent files from being synced:

```
# Repo meta files
README.md
CLAUDE.md

# Whole directory
internal/**
```

Patterns follow the same glob syntax as `.gitignore`. Files matching any pattern are skipped on both sync and delete.

## Folder Pages

Each directory in the path gets its own Confluence page (e.g., `docs`, `docs/api`) with an empty body, created automatically the first time a file in that directory is synced.

## Deleted Files

When a markdown file is deleted and pushed, the corresponding Confluence page is removed. The script reads the deleted file's frontmatter from the previous git commit to find its `confluence_id` for a reliable lookup.
