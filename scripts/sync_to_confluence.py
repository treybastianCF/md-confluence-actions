#!/usr/bin/env python3
"""
Sync changed markdown files to Confluence, mirroring the folder structure
as a page hierarchy. Page titles use the full relative path without extension
(e.g., docs/api/endpoints) to guarantee uniqueness within the space.

Required environment variables:
  CONFLUENCE_URL        e.g. https://your-org.atlassian.net
  CONFLUENCE_EMAIL      Atlassian account email
  CONFLUENCE_API_TOKEN  API token from id.atlassian.com
  CONFLUENCE_SPACE_KEY  Short space key (e.g. DOCS)
  CHANGED_FILES         Space-separated list of changed .md paths (from tj-actions)
"""

import os
import sys
import logging
from pathlib import Path

import markdown
from atlassian import Confluence

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# Module-level cache: maps cumulative path string → Confluence page ID
# e.g. "docs" → "123456", "docs/api" → "789012"
_page_id_cache: dict[str, str] = {}


def load_config() -> dict:
    required = ["CONFLUENCE_URL", "CONFLUENCE_EMAIL", "CONFLUENCE_API_TOKEN", "CONFLUENCE_SPACE_KEY"]
    config = {}
    missing = []
    for key in required:
        val = os.environ.get(key, "").strip()
        if not val:
            missing.append(key)
        else:
            config[key.lower()] = val
    if missing:
        log.error("Missing required environment variables: %s", ", ".join(missing))
        sys.exit(1)
    return config


def md_to_storage(md_path: Path) -> str:
    """Convert a markdown file to Confluence storage format (HTML)."""
    raw = md_path.read_text(encoding="utf-8")
    return markdown.markdown(
        raw,
        extensions=["fenced_code", "tables", "toc"],
    )


def get_or_create_page(
    confluence: Confluence,
    space_key: str,
    title: str,
    parent_id: str | None,
    body: str = "",
) -> str:
    """Find a Confluence page by title in the space, or create it. Returns page ID."""
    existing_id = confluence.get_page_id(space=space_key, title=title)
    if existing_id:
        log.info("Found existing page '%s' (id=%s)", title, existing_id)
        return str(existing_id)

    log.info("Creating page '%s' under parent_id=%s", title, parent_id)
    result = confluence.create_page(
        space=space_key,
        title=title,
        body=body,
        parent_id=parent_id,
        representation="storage",
    )
    new_id = str(result["id"])
    log.info("Created page '%s' → id=%s", title, new_id)
    return new_id


def resolve_parent_chain(
    confluence: Confluence,
    space_key: str,
    file_path: Path,
) -> str | None:
    """
    Walk the directory segments of file_path (excluding filename) and ensure
    each segment exists as a Confluence page nested under the previous one.
    Returns the page ID of the immediate parent for the file, or None if the
    file is at repo root.

    Folder page titles use the cumulative path: "docs", "docs/api", etc.
    Uses _page_id_cache to avoid redundant API calls within a run.
    """
    parts = list(file_path.parts[:-1])  # drop the filename
    if not parts:
        return None  # file at repo root → attach to space root

    parent_id = None
    cumulative: list[str] = []

    for segment in parts:
        cumulative.append(segment)
        cache_key = "/".join(cumulative)

        if cache_key in _page_id_cache:
            parent_id = _page_id_cache[cache_key]
            continue

        folder_title = cache_key  # full path as title, e.g. "docs/api"
        page_id = get_or_create_page(
            confluence=confluence,
            space_key=space_key,
            title=folder_title,
            parent_id=parent_id,
            body="",
        )
        _page_id_cache[cache_key] = page_id
        parent_id = page_id

    return parent_id


def sync_page(confluence: Confluence, space_key: str, file_path: Path) -> None:
    """Full sync lifecycle for a single markdown file."""
    # Title = full path without extension, e.g. "docs/api/endpoints"
    title = str(file_path.with_suffix(""))
    body = md_to_storage(file_path)
    parent_id = resolve_parent_chain(confluence, space_key, file_path)

    existing_id = confluence.get_page_id(space=space_key, title=title)

    if existing_id:
        log.info("Updating page '%s' (id=%s)", title, existing_id)
        confluence.update_page(
            page_id=existing_id,
            title=title,
            body=body,
            representation="storage",
        )
    else:
        log.info("Creating content page '%s'", title)
        confluence.create_page(
            space=space_key,
            title=title,
            body=body,
            parent_id=parent_id,
            representation="storage",
        )


def delete_page(confluence: Confluence, space_key: str, file_path: Path) -> None:
    """Remove the Confluence page corresponding to a deleted markdown file."""
    title = str(file_path.with_suffix(""))
    page_id = confluence.get_page_id(space=space_key, title=title)
    if not page_id:
        log.warning("No Confluence page found for deleted file '%s' — skipping", title)
        return
    log.info("Removing page '%s' (id=%s)", title, page_id)
    confluence.remove_page(page_id)


def main() -> None:
    config = load_config()

    confluence = Confluence(
        url=config["confluence_url"],
        username=config["confluence_email"],
        password=config["confluence_api_token"],
        cloud=True,
    )

    errors = []

    # Handle deletions
    deleted_files = [
        Path(f) for f in os.environ.get("DELETED_FILES", "").split()
        if f.endswith(".md")
    ]
    if deleted_files:
        log.info("Deleting %d page(s): %s", len(deleted_files), [str(f) for f in deleted_files])
    for file_path in deleted_files:
        try:
            delete_page(confluence=confluence, space_key=config["confluence_space_key"], file_path=file_path)
        except Exception as exc:
            log.error("Failed to delete page for %s: %s", file_path, exc)
            errors.append((file_path, exc))

    # Handle creates/updates
    changed_files = [
        Path(f) for f in os.environ.get("CHANGED_FILES", "").split()
        if f.endswith(".md")
    ]
    if not changed_files and not deleted_files:
        log.info("No changes detected. Exiting.")
        return

    log.info("Processing %d changed file(s): %s", len(changed_files), [str(f) for f in changed_files])

    for file_path in changed_files:
        if not file_path.exists():
            log.warning("File %s not found — skipping", file_path)
            continue
        try:
            sync_page(confluence=confluence, space_key=config["confluence_space_key"], file_path=file_path)
        except Exception as exc:
            log.error("Failed to sync %s: %s", file_path, exc)
            errors.append((file_path, exc))

    if errors:
        log.error("%d file(s) failed to sync.", len(errors))
        sys.exit(1)
    else:
        log.info("All files synced successfully.")


if __name__ == "__main__":
    main()
