# md-confluence-actions

A GitHub Actions pipeline that automatically syncs changed markdown files to Confluence on every push to `main`, mirroring the repository folder structure as a Confluence page hierarchy.

## How It Works

1. You push a commit that includes changes to `.md` files
2. GitHub Actions detects which markdown files changed (only those files, not all of them)
3. The sync script converts each file from Markdown → HTML and creates or updates the corresponding Confluence page
4. Folder structure is mirrored: `docs/api/endpoints.md` becomes a page titled `docs/api/endpoints` nested under folder pages `docs` and `docs/api`

## Repository Structure

```
.github/workflows/sync-to-confluence.yml   # The Actions workflow
scripts/sync_to_confluence.py              # Sync script
scripts/requirements.txt                   # Python dependencies
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

## Page Title Convention

Page titles use the full relative path without the `.md` extension, e.g.:

- `docs/index.md` → **docs/index**
- `docs/api/endpoints.md` → **docs/api/endpoints**

This guarantees uniqueness within the Confluence space, even if two files in different folders share the same filename.

## Folder Pages

Each directory in the path gets its own Confluence page (e.g., `docs`, `docs/api`) with an empty body. These are created automatically the first time a file in that directory is synced.

## Deleted Files

Deleted markdown files are not removed from Confluence. This is intentional for the POC — deletion sync can be added later.
