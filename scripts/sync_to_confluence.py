#!/usr/bin/env python3
"""
Sync changed markdown files to Confluence, mirroring the folder structure
as a page hierarchy.

Frontmatter properties (all optional):
  title:        Override the Confluence page title (default: file path without extension)
  draft:        If true, skip this file entirely
  labels:       List of Confluence labels to apply to the page
  confluence_id: Pinned Confluence page ID — auto-populated after first sync

Lookup priority: confluence_id (if present) → title → path-based title

Required environment variables:
  CONFLUENCE_URL        e.g. https://your-org.atlassian.net
  CONFLUENCE_EMAIL      Atlassian account email
  CONFLUENCE_API_TOKEN  API token from id.atlassian.com
  CONFLUENCE_SPACE_KEY  Short space key (e.g. DOCS)
  CHANGED_FILES         Space-separated list of changed .md paths (from tj-actions)
  DELETED_FILES         Space-separated list of deleted .md paths (from tj-actions)
"""

import os
import subprocess
import sys
import logging
from pathlib import Path

import frontmatter
import markdown
from atlassian import Confluence

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

WRITTEN_BACK_FILE = "/tmp/written_back.txt"
CONFLUENCEIGNORE = Path(".confluenceignore")


def load_ignore_patterns() -> list[str]:
    """Load exclusion patterns from .confluenceignore if it exists."""
    if not CONFLUENCEIGNORE.exists():
        return []
    lines = CONFLUENCEIGNORE.read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.startswith("#")]


def is_ignored(file_path: Path, patterns: list[str]) -> bool:
    """Return True if file_path matches any pattern from .confluenceignore."""
    return any(file_path.match(pattern) for pattern in patterns)

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


def md_to_storage(content: str) -> str:
    """Convert a markdown string to Confluence storage format (HTML)."""
    return markdown.markdown(
        content,
        extensions=["fenced_code", "tables", "toc"],
    )


def write_confluence_id(file_path: Path, page_id: str) -> None:
    """Write the confluence_id into a file's frontmatter in-place."""
    post = frontmatter.load(file_path)
    post["confluence_id"] = page_id
    file_path.write_text(frontmatter.dumps(post), encoding="utf-8")
    log.info("Wrote confluence_id=%s to %s", page_id, file_path)
    with open(WRITTEN_BACK_FILE, "a") as f:
        f.write(str(file_path) + "\n")


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
    parts = list(file_path.parts[:-1])
    if not parts:
        return None

    parent_id = None
    cumulative: list[str] = []

    for segment in parts:
        cumulative.append(segment)
        cache_key = "/".join(cumulative)

        if cache_key in _page_id_cache:
            parent_id = _page_id_cache[cache_key]
            continue

        page_id = get_or_create_page(
            confluence=confluence,
            space_key=space_key,
            title=cache_key,
            parent_id=parent_id,
            body="",
        )
        _page_id_cache[cache_key] = page_id
        parent_id = page_id

    return parent_id


def is_archived_path(file_path: Path) -> bool:
    """Return True if any path segment is named 'archived'."""
    return "archived" in file_path.parts


def archive_page(confluence: Confluence, page_id: str, title: str) -> None:
    """Archive a Confluence page by setting its status to 'archived'. Idempotent."""
    page_info = confluence.get_page_by_id(page_id, expand="version,body.storage")
    if page_info.get("status") == "archived":
        log.info("Page '%s' (id=%s) is already archived — skipping", title, page_id)
        return
    current_version = page_info["version"]["number"]
    existing_body = page_info["body"]["storage"]["value"]
    confluence.put(
        f"rest/api/content/{page_id}",
        data={
            "id": page_id,
            "type": "page",
            "status": "archived",
            "title": title,
            "version": {"number": current_version + 1},
            "body": {
                "storage": {
                    "value": existing_body,
                    "representation": "storage",
                }
            },
        },
    )
    log.info("Archived page '%s' (id=%s)", title, page_id)


def apply_labels(confluence: Confluence, page_id: str, labels: list[str]) -> None:
    """Add labels to a Confluence page via the REST API."""
    if not labels:
        return
    url = f"rest/api/content/{page_id}/label"
    data = [{"prefix": "global", "name": label} for label in labels]
    confluence.post(url, data=data)
    log.info("Applied labels %s to page %s", labels, page_id)


def sync_page(confluence: Confluence, space_key: str, file_path: Path) -> None:
    """Full sync lifecycle for a single markdown file, reading frontmatter for metadata."""
    post = frontmatter.load(file_path)
    meta = post.metadata

    if meta.get("draft"):
        log.info("Skipping draft file: %s", file_path)
        return

    title = meta.get("title") or str(file_path.with_suffix(""))
    body = md_to_storage(post.content)
    labels = meta.get("labels", [])
    pinned_id = meta.get("confluence_id")

    if meta.get("archived") or is_archived_path(file_path):
        log.info("Archiving page for %s", file_path)
        page_id = pinned_id
        if not page_id:
            path_title = str(file_path.with_suffix(""))
            page_id = confluence.get_page_id(space=space_key, title=title)
            if not page_id and title != path_title:
                page_id = confluence.get_page_id(space=space_key, title=path_title)
        if page_id:
            archive_page(confluence, page_id, title)
        else:
            log.warning("No Confluence page found to archive for '%s' — skipping", file_path)
        return

    if pinned_id:
        # Update by pinned ID — title lookup not needed
        log.info("Updating page by pinned confluence_id=%s ('%s')", pinned_id, title)
        confluence.update_page(
            page_id=pinned_id,
            title=title,
            body=body,
            representation="storage",
        )
        if labels:
            apply_labels(confluence, pinned_id, labels)
    else:
        existing_id = confluence.get_page_id(space=space_key, title=title)

        # If a custom title was set but not found, also try the path-based title.
        # This handles the case where a file already exists in Confluence under its
        # path-based title and the author is adding a title to frontmatter for the
        # first time — without this fallback a duplicate page would be created.
        path_title = str(file_path.with_suffix(""))
        if not existing_id and title != path_title:
            log.info("Title '%s' not found, checking path-based title '%s'", title, path_title)
            existing_id = confluence.get_page_id(space=space_key, title=path_title)

        if existing_id:
            log.info("Updating page '%s' (id=%s)", title, existing_id)
            confluence.update_page(
                page_id=existing_id,
                title=title,
                body=body,
                representation="storage",
            )
            if labels:
                apply_labels(confluence, existing_id, labels)
            write_confluence_id(file_path, existing_id)
        else:
            parent_id = resolve_parent_chain(confluence, space_key, file_path)
            log.info("Creating content page '%s'", title)
            result = confluence.create_page(
                space=space_key,
                title=title,
                body=body,
                parent_id=parent_id,
                representation="storage",
            )
            new_id = str(result["id"])
            log.info("Created page '%s' → id=%s", title, new_id)
            if labels:
                apply_labels(confluence, new_id, labels)
            write_confluence_id(file_path, new_id)


def delete_page(confluence: Confluence, space_key: str, file_path: Path) -> None:
    """Remove the Confluence page corresponding to a deleted markdown file."""
    # Read the deleted file from the previous commit to get its confluence_id
    pinned_id = None
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD^:{file_path}"],
            capture_output=True, text=True, check=True,
        )
        post = frontmatter.loads(result.stdout)
        pinned_id = post.metadata.get("confluence_id")
    except subprocess.CalledProcessError:
        log.warning("Could not read %s from previous commit — falling back to title lookup", file_path)

    page_id = pinned_id
    if not page_id:
        title = str(file_path.with_suffix(""))
        page_id = confluence.get_page_id(space=space_key, title=title)
        if not page_id:
            log.warning("No Confluence page found for deleted file '%s' — skipping", title)
            return

    page_info = confluence.get_page_by_id(page_id, expand="version")
    if page_info.get("status") == "archived":
        log.info("Page (id=%s) is already archived — skipping hard delete", page_id)
        return

    log.info("Removing page (id=%s) for deleted file %s", page_id, file_path)
    confluence.remove_page(page_id)


def main() -> None:
    config = load_config()

    confluence = Confluence(
        url=config["confluence_url"],
        username=config["confluence_email"],
        password=config["confluence_api_token"],
        cloud=True,
    )

    # Clear write-back tracking file
    Path(WRITTEN_BACK_FILE).unlink(missing_ok=True)

    ignore_patterns = load_ignore_patterns()

    errors = []

    # Handle deletions
    deleted_files = [
        Path(f) for f in os.environ.get("DELETED_FILES", "").split()
        if f.endswith(".md")
    ]
    if deleted_files:
        log.info("Deleting %d page(s): %s", len(deleted_files), [str(f) for f in deleted_files])
    for file_path in deleted_files:
        if is_ignored(file_path, ignore_patterns):
            log.info("Ignoring deleted file (matches .confluenceignore): %s", file_path)
            continue
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
        if is_ignored(file_path, ignore_patterns):
            log.info("Ignoring file (matches .confluenceignore): %s", file_path)
            continue
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
