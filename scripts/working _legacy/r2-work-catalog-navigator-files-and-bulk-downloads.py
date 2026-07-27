#!/usr/bin/env python3
"""Incremental R2 work catalog and Tkinter navigator.

Two durable JSONL files are maintained:

1. manifest.index.jsonl
   Canonical, append-only work records. Existing schema-2 and schema-3
   search-index rows can be imported. The newest complete row for a work wins.

2. search.index.jsonl
   Compact, atomically rebuilt name-search index used by the GUI. It is
   backwards compatible with the original schema-2 search rows: the familiar
   fields remain present, while newer fields are additive.

Normal startup is lightweight:
- salvage complete JSONL lines after interruption;
- list only direct work directories in R2;
- append placeholder records only for newly discovered work names;
- open the GUI;
- rebuild the compact search index in small GUI-safe batches.

Structural metadata, thumbnails, details.json, tags.json, and item.json are
retrieved only when requested through GUI buttons, except --scan-new which may
inspect newly discovered works before opening the GUI.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import webbrowser
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable

DEFAULT_REMOTE = "animeplex.lol:extended/works"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "r2-audit-output"
MANIFEST_FILENAME = "manifest.index.jsonl"
SEARCH_FILENAME = "search.index.jsonl"
ARCHIVE_EXTS = {".zip", ".cbz"}
STRUCTURAL_NAMES = {"details.json", "tags.json", "item.json", "thumb.webp"}
MAX_JSON_BYTES = 8 * 1024 * 1024


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def natural_key(value: str) -> list[Any]:
    return [int(x) if x.isdigit() else x.casefold() for x in re.split(r"(\d+)", value)]


def shell_quote(value: str) -> str:
    import shlex
    return shlex.quote(value)


def run_capture(cmd: list[str]) -> str:
    print("$ " + " ".join(shell_quote(x) for x in cmd))
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError:
        raise RuntimeError("rclone was not found in PATH.")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(detail or f"Command failed with exit code {exc.returncode}") from exc
    return result.stdout


def run(cmd: list[str]) -> None:
    print("$ " + " ".join(shell_quote(x) for x in cmd))
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        raise RuntimeError("rclone was not found in PATH.")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"Command failed with exit code {exc.returncode}") from exc


def remote_join(remote: str, relative: str) -> str:
    return f"{remote.rstrip('/')}/{relative.lstrip('/')}"


def cli_file_entry(remote: str, relative: str) -> dict[str, str]:
    """Describe a remote file with directly usable rclone CLI locations."""
    uri = remote_join(remote, relative)
    return {
        "path": relative,
        "rclone_uri": uri,
        "cat_command": f"rclone cat {shell_quote(uri)}",
        "copy_command": f"rclone copyto {shell_quote(uri)} <LOCAL_DESTINATION>",
        "link_command": f"rclone link {shell_quote(uri)}",
    }


def build_file_catalog(remote: str, paths: Iterable[str]) -> list[dict[str, str]]:
    return [cli_file_entry(remote, path) for path in sorted(set(paths), key=natural_key)]


def rclone_link(remote: str, relative: str) -> str:
    """Request a visitable link from the configured rclone backend."""
    return run_capture(["rclone", "link", remote_join(remote, relative)]).strip()




def normalize_search_value(value: str) -> str:
    """Aggressively normalize a title for forgiving filename search."""
    value = value.casefold()
    value = re.sub(r"[_\-.]+", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def compact_search_value(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def title_search_profile(name: str) -> dict[str, Any]:
    """Create deterministic search keys for a work/file name.

    The profile supports exact, prefix, token-prefix, acronym, compact,
    subsequence, and typo-tolerant matching without external dependencies.
    """
    normalized = normalize_search_value(name)
    tokens = normalized.split()
    stop = {"a", "an", "and", "of", "the", "to", "x"}
    meaningful = [token for token in tokens if token not in stop]
    initials_all = "".join(token[0] for token in tokens if token)
    initials_meaningful = "".join(token[0] for token in meaningful if token)

    aliases = {
        normalized,
        compact_search_value(name),
        initials_all,
        initials_meaningful,
    }
    # Joined adjacent token forms help DBZ-like and punctuation-heavy names.
    for start in range(len(tokens)):
        for end in range(start + 1, min(len(tokens), start + 4) + 1):
            aliases.add("".join(tokens[start:end]))
    aliases.discard("")
    return {
        "normalized_name": normalized,
        "compact_name": compact_search_value(name),
        "tokens": tokens,
        "token_prefixes": sorted({token[:n] for token in tokens for n in range(1, len(token) + 1)}),
        "acronyms": sorted({x for x in (initials_all, initials_meaningful) if x}),
        "aliases": sorted(aliases),
    }


def is_subsequence(needle: str, haystack: str) -> bool:
    iterator = iter(haystack)
    return all(any(char == candidate for candidate in iterator) for char in needle)


def rank_name_query(query: str, row: dict[str, Any]) -> float | None:
    """Return a lower-is-better relevance score, or None when unmatched."""
    q_norm = normalize_search_value(query)
    q_compact = compact_search_value(query)
    if not q_compact:
        return 0.0

    profile = row.get("search_profile")
    if not isinstance(profile, dict):
        profile = title_search_profile(str(row.get("name") or ""))
    normalized = str(profile.get("normalized_name") or "")
    compact = str(profile.get("compact_name") or "")
    tokens = [str(x) for x in profile.get("tokens") or []]
    acronyms = [str(x) for x in profile.get("acronyms") or []]
    aliases = [str(x) for x in profile.get("aliases") or []]

    if q_norm == normalized or q_compact == compact:
        return 0.0
    if q_compact in acronyms:
        return 1.0 + max(0, len(compact) - len(q_compact)) / 1000
    if compact.startswith(q_compact):
        return 2.0 + (len(compact) - len(q_compact)) / 1000
    if any(token.startswith(q_norm) or token.startswith(q_compact) for token in tokens):
        return 3.0 + min((len(token) - len(q_compact) for token in tokens if token.startswith(q_compact)), default=0) / 1000
    if any(alias.startswith(q_compact) for alias in aliases):
        return 4.0
    if q_compact in compact:
        return 5.0 + compact.index(q_compact) / 1000
    if is_subsequence(q_compact, compact) and len(q_compact) >= 2:
        return 6.0 + (len(compact) - len(q_compact)) / 1000

    # Typo tolerance scales with query length and avoids noisy one-letter matches.
    if len(q_compact) >= 3:
        candidates = [compact, *tokens, *acronyms, *aliases]
        best = max((difflib.SequenceMatcher(None, q_compact, candidate).ratio() for candidate in candidates if candidate), default=0.0)
        threshold = 0.72 if len(q_compact) <= 5 else 0.64
        if best >= threshold:
            return 10.0 - best
    return None

def default_tags() -> dict[str, Any]:
    return {"schema_version": 1, "public": {}, "private": {}}


def normalize_tag_tree(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    out: dict[str, Any] = {}
    for key, child in value.items():
        name = str(key).strip()
        if name:
            out[name] = normalize_tag_tree(child)
    return out


def normalize_tags_file(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    return {
        "schema_version": 1,
        "public": normalize_tag_tree(value.get("public")),
        "private": normalize_tag_tree(value.get("private")),
    }


def flatten_tag_paths(tree: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[str]:
    out: list[str] = []
    for key in sorted(tree, key=natural_key):
        path = prefix + (key,)
        out.append(" > ".join(path))
        out.extend(flatten_tag_paths(tree[key], path))
    return out


def add_tag_path(tree: dict[str, Any], text: str) -> None:
    parts = [part.strip() for part in text.split(">") if part.strip()]
    node = tree
    for part in parts:
        child = node.setdefault(part, {})
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child


def delete_tag_path(tree: dict[str, Any], parts: list[str]) -> None:
    if not parts:
        return
    stack: list[tuple[dict[str, Any], str]] = []
    node = tree
    for part in parts:
        child = node.get(part)
        if not isinstance(child, dict):
            return
        stack.append((node, part))
        node = child
    parent, key = stack[-1]
    parent.pop(key, None)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    """Append one complete fsynced JSONL record.

    Earlier complete rows survive Ctrl+C or power loss. At worst, the final
    line is partial and is truncated on the next launch.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def salvage_jsonl(path: Path, repair_tail: bool = True) -> list[dict[str, Any]]:
    """Read all valid rows and salvage an interrupted trailing fragment.

    Malformed complete interior lines are skipped with a warning. A malformed
    incomplete final line is truncated, preserving all earlier bytes.
    """
    if not path.exists():
        return []
    data = path.read_bytes()
    rows: list[dict[str, Any]] = []
    lines = data.splitlines(keepends=True)
    valid_end = 0
    for number, raw in enumerate(lines, 1):
        complete = raw.endswith((b"\n", b"\r"))
        stripped = raw.strip()
        if not stripped:
            valid_end += len(raw)
            continue
        try:
            value = json.loads(stripped.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            if number == len(lines) and not complete:
                print(f"Salvaging {path.name}: truncating interrupted line {number}: {exc}")
                if repair_tail:
                    with path.open("r+b") as handle:
                        handle.truncate(valid_end)
                break
            print(f"Warning: skipping malformed complete line {path}:{number}: {exc}", file=sys.stderr)
            valid_end += len(raw)
            continue
        valid_end += len(raw)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def row_name(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("slug") or "").strip()


def merge_latest(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for source in rows:
        name = row_name(source)
        if not name:
            continue
        row = migrate_row(source)
        previous = latest.get(name)
        latest[name] = merge_rows(previous, row) if previous else row
    return latest


def merge_rows(old: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    if old is None:
        return dict(new)
    merged = dict(old)
    for key, value in new.items():
        # Do not erase useful prior lists/dicts with empty placeholder values.
        if value in (None, "", [], {}) and merged.get(key) not in (None, "", [], {}):
            continue
        merged[key] = value
    return merged


def migrate_row(source: dict[str, Any]) -> dict[str, Any]:
    """Normalize original schema-2 and incremental schema-3 rows.

    All original search-index keys are retained. New keys are additive.
    """
    row = dict(source)
    name = row_name(row)
    row["schema_version"] = max(4, int(row.get("schema_version") or 0))
    row["name"] = name
    row.setdefault("remote_path", "")
    row.setdefault("status", "unscanned")
    for key in (
        "archive_paths", "details_paths", "item_json_paths", "thumb_paths",
        "image_paths", "other_json_paths", "all_paths", "manifests",
        "duplicate_archive_names",
    ):
        if not isinstance(row.get(key), list):
            row[key] = []
    for key in (
        "file_count", "total_bytes", "image_count", "json_count",
        "item_json_count", "archive_count", "zip_count", "cbz_count",
        "non_image_count",
    ):
        try:
            row[key] = int(row.get(key) or 0)
        except (TypeError, ValueError):
            row[key] = 0
    row["has_details_json"] = bool(row.get("has_details_json") or row["details_paths"])
    row["has_thumb_webp"] = bool(row.get("has_thumb_webp") or row["thumb_paths"])
    row.setdefault("possible_duplicate", row.get("suspicious_duplicate_group"))
    row["tags"] = normalize_tags_file(row.get("tags"))
    row.setdefault("tags_path", f"{name}/tags.json" if name else "")
    row.setdefault("resources", {})
    row.setdefault("file_catalog", [])
    if not isinstance(row["resources"], dict):
        row["resources"] = {}
    row["search_profile"] = title_search_profile(name)
    row["search_text"] = build_search_text(row)
    return row


def build_search_text(row: dict[str, Any]) -> str:
    values: list[str] = [
        str(row.get("name") or ""), str(row.get("remote_path") or ""),
        str(row.get("status") or ""), str(row.get("possible_duplicate") or ""),
    ]
    for key in (
        "archive_paths", "details_paths", "item_json_paths", "thumb_paths",
        "image_paths", "other_json_paths", "all_paths",
    ):
        values.extend(map(str, row.get(key) or []))
    for manifest in row.get("manifests") or []:
        if isinstance(manifest, dict):
            values.extend(str(manifest.get(key) or "") for key in (
                "item_path", "base_url", "url_template", "first_page_url",
                "last_page_url", "error", "title", "subtitle",
            ))
    tags = normalize_tags_file(row.get("tags"))
    values.extend(flatten_tag_paths(tags["public"]))
    values.extend(flatten_tag_paths(tags["private"]))
    return " ".join(values).casefold()


def compact_search_row(row: dict[str, Any]) -> dict[str, Any]:
    """Produce a rich superset of the original schema-2 search format."""
    source = migrate_row(row)
    return {
        "schema_version": 4,
        "name": source["name"],
        "remote_path": source.get("remote_path", ""),
        "status": source.get("status", "unscanned"),
        "has_details_json": source.get("has_details_json", False),
        "has_thumb_webp": source.get("has_thumb_webp", False),
        "item_json_count": source.get("item_json_count", 0),
        "archive_count": source.get("archive_count", 0),
        "zip_count": source.get("zip_count", 0),
        "cbz_count": source.get("cbz_count", 0),
        "archive_paths": source.get("archive_paths", []),
        "details_paths": source.get("details_paths", []),
        "item_json_paths": source.get("item_json_paths", []),
        "thumb_paths": source.get("thumb_paths", []),
        "manifests": source.get("manifests", []),
        "possible_duplicate": source.get("possible_duplicate"),
        # Additive fields understood by this navigator.
        "tags_path": source.get("tags_path"),
        "tags": source.get("tags", default_tags()),
        "resources": source.get("resources", {}),
        "file_catalog": source.get("file_catalog", []),
        "scanned_at": source.get("scanned_at"),
        "search_profile": title_search_profile(source["name"]),
        "search_text": build_search_text(source),
    }


def list_direct_work_names(remote: str) -> list[str]:
    raw = run_capture(["rclone", "lsf", remote, "--dirs-only", "--max-depth", "1"])
    names: list[str] = []
    for line in raw.splitlines():
        name = line.strip().replace("\\", "/").strip("/")
        if name and "/" not in name:
            names.append(name)
    return sorted(set(names), key=natural_key)


def placeholder_row(remote: str, name: str) -> dict[str, Any]:
    return migrate_row({
        "schema_version": 4,
        "name": name,
        "remote_path": remote_join(remote, name),
        "status": "unscanned",
        "tags_path": f"{name}/tags.json",
        "discovered_at": utc_iso(),
    })


def list_structural_files(remote: str, name: str) -> list[dict[str, Any]]:
    raw = run_capture([
        "rclone", "lsjson", remote_join(remote, name),
        "--recursive", "--files-only", "--no-mimetype",
        "--include", "**/item.json",
        "--include", "**/details.json",
        "--include", "**/tags.json",
        "--include", "**/thumb.webp",
        "--include", "**/*.zip",
        "--include", "**/*.cbz",
        "--exclude", "*",
    ])
    value = json.loads(raw or "[]")
    return [x for x in value if isinstance(x, dict)]


def structural_scan(remote: str, name: str, old: dict[str, Any] | None = None) -> dict[str, Any]:
    files = list_structural_files(remote, name)
    paths: list[str] = []
    total_bytes = 0
    for item in files:
        path = str(item.get("Path") or item.get("Name") or "").replace("\\", "/").lstrip("/")
        if path:
            paths.append(f"{name}/{path}")
            total_bytes += int(item.get("Size") or 0)
    details = sorted([p for p in paths if PurePosixPath(p).name.casefold() == "details.json"], key=natural_key)
    items = sorted([p for p in paths if PurePosixPath(p).name.casefold() == "item.json"], key=natural_key)
    tags = sorted([p for p in paths if PurePosixPath(p).name.casefold() == "tags.json"], key=natural_key)
    thumbs = sorted([p for p in paths if PurePosixPath(p).name.casefold() == "thumb.webp"], key=natural_key)
    archives = sorted([p for p in paths if PurePosixPath(p).suffix.casefold() in ARCHIVE_EXTS], key=natural_key)
    row = migrate_row({
        **(old or {}),
        "schema_version": 4,
        "name": name,
        "remote_path": remote_join(remote, name),
        "status": "indexed" if items else "incomplete",
        "file_count": len(paths),
        "total_bytes": total_bytes,
        "json_count": len(details) + len(items) + len(tags),
        "item_json_count": len(items),
        "archive_count": len(archives),
        "zip_count": sum(p.casefold().endswith(".zip") for p in archives),
        "cbz_count": sum(p.casefold().endswith(".cbz") for p in archives),
        "non_image_count": len(paths) - len(thumbs),
        "has_details_json": bool(details),
        "has_thumb_webp": bool(thumbs),
        "archive_paths": archives,
        "details_paths": details,
        "item_json_paths": items,
        "thumb_paths": thumbs,
        "all_paths": paths,
        "file_catalog": build_file_catalog(remote, paths),
        "tags_path": tags[0] if tags else f"{name}/tags.json",
        "scanned_at": utc_iso(),
    })
    return row


def read_remote_json(remote: str, relative: str) -> Any:
    raw = run_capture(["rclone", "cat", remote_join(remote, relative)])
    if len(raw.encode("utf-8")) > MAX_JSON_BYTES:
        raise RuntimeError(f"JSON exceeds {MAX_JSON_BYTES} byte safety limit")
    return json.loads(raw)


def derive_manifest(data: Any, item_path: str) -> dict[str, Any]:
    result: dict[str, Any] = {"item_path": item_path, "valid": False}
    if not isinstance(data, dict):
        result["error"] = "item.json is not a JSON object"
        return result
    base_url = str(data.get("base_url") or data.get("baseUrl") or "").rstrip("/")
    extension = str(data.get("extension") or data.get("ext") or "webp").lstrip(".")
    try:
        pages = int(data.get("pages") or data.get("page_count") or data.get("pageCount"))
        padding = int(data.get("padding", 3))
    except (TypeError, ValueError):
        result.update({"error": "missing or invalid pages/padding", "base_url": base_url, "extension": extension})
        return result
    if not base_url or pages < 1 or padding < 1:
        result.update({"error": "missing base_url or invalid values", "base_url": base_url, "pages": pages, "padding": padding})
        return result
    result.update({
        "valid": True,
        "base_url": base_url,
        "pages": pages,
        "padding": padding,
        "extension": extension,
        "url_template": f"{base_url}/{{page:0{padding}d}}.{extension}",
        "first_page_url": f"{base_url}/{1:0{padding}d}.{extension}",
        "last_page_url": f"{base_url}/{pages:0{padding}d}.{extension}",
        "predicted_page_urls": {
            "template": f"{base_url}/{{page:0{padding}d}}.{extension}",
            "first": f"{base_url}/{1:0{padding}d}.{extension}",
            "last": f"{base_url}/{pages:0{padding}d}.{extension}",
            "count": pages,
        },
    })
    for key in ("id", "title", "subtitle", "slug", "parent_work_slug", "parent_work_id"):
        if key in data:
            result[key] = data[key]
    return result


def update_status(row: dict[str, Any]) -> None:
    manifests = row.get("manifests") or []
    if manifests and any(not m.get("valid") for m in manifests if isinstance(m, dict)):
        row["status"] = "unresolved"
    elif row.get("item_json_count") and row.get("has_details_json") and row.get("has_thumb_webp"):
        row["status"] = "complete"
    elif row.get("scanned_at"):
        row["status"] = "incomplete"
    else:
        row["status"] = "unscanned"
    row["search_text"] = build_search_text(row)


def call_items(remote: str, row: dict[str, Any]) -> dict[str, Any]:
    if not row.get("scanned_at"):
        row = structural_scan(remote, row["name"], row)
    manifests: list[dict[str, Any]] = []
    raw_items: dict[str, Any] = {}
    for path in row.get("item_json_paths") or []:
        try:
            data = read_remote_json(remote, path)
            raw_items[path] = data
            manifests.append(derive_manifest(data, path))
        except Exception as exc:
            manifests.append({"item_path": path, "valid": False, "error": str(exc)})
    row["manifests"] = manifests
    row.setdefault("resources", {})["item_json"] = raw_items
    row["items_called_at"] = utc_iso()
    update_status(row)
    return row


def call_details(remote: str, row: dict[str, Any]) -> dict[str, Any]:
    if not row.get("scanned_at"):
        row = structural_scan(remote, row["name"], row)
    values: dict[str, Any] = {}
    for path in row.get("details_paths") or []:
        try:
            values[path] = read_remote_json(remote, path)
        except Exception as exc:
            values[path] = {"_error": str(exc)}
    row.setdefault("resources", {})["details_json"] = values
    row["details_called_at"] = utc_iso()
    row["search_text"] = build_search_text(row)
    return row


def call_tags(remote: str, row: dict[str, Any]) -> dict[str, Any]:
    if not row.get("scanned_at"):
        row = structural_scan(remote, row["name"], row)
    try:
        data = read_remote_json(remote, row.get("tags_path") or f"{row['name']}/tags.json")
        row["tags"] = normalize_tags_file(data)
    except Exception as exc:
        # A missing tag file is a valid empty state.
        row["tags"] = default_tags()
        row.setdefault("resources", {})["tags_error"] = str(exc)
    row["tags_called_at"] = utc_iso()
    row["search_text"] = build_search_text(row)
    return row


def save_tags(remote: str, row: dict[str, Any]) -> dict[str, Any]:
    relative = str(row.get("tags_path") or f"{row['name']}/tags.json")
    tags = normalize_tags_file(row.get("tags"))
    with tempfile.TemporaryDirectory(prefix="r2-tags-") as tmp:
        local = Path(tmp) / "tags.json"
        local.write_text(json.dumps(tags, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        run(["rclone", "copyto", str(local), remote_join(remote, relative)])
    row["tags_path"] = relative
    row["tags"] = tags
    row["tags_updated_at"] = utc_iso()
    row["search_text"] = build_search_text(row)
    return row


def copy_remote_file(remote: str, relative: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(["rclone", "copyto", remote_join(remote, relative), str(destination)])


def load_catalog(output_dir: Path, import_paths: list[Path]) -> dict[str, dict[str, Any]]:
    manifest_path = output_dir / MANIFEST_FILENAME
    rows: list[dict[str, Any]] = []
    rows.extend(salvage_jsonl(manifest_path))
    for path in import_paths:
        if path.exists() and path.resolve() != manifest_path.resolve():
            rows.extend(salvage_jsonl(path, repair_tail=False))
    # Also import the old/default search index automatically when present.
    old_search = output_dir / SEARCH_FILENAME
    if old_search.exists() and old_search not in import_paths:
        rows.extend(salvage_jsonl(old_search, repair_tail=False))
    return merge_latest(rows)


def discover_new(remote: str, catalog: dict[str, dict[str, Any]], manifest_path: Path) -> list[str]:
    names = list_direct_work_names(remote)
    new_names = [name for name in names if name not in catalog]
    for name in new_names:
        row = placeholder_row(remote, name)
        append_jsonl(manifest_path, row)
        catalog[name] = row
        print(f"Discovered: {name}")
    return new_names


def write_search_index(catalog: dict[str, dict[str, Any]], path: Path) -> None:
    rows = [compact_search_row(catalog[name]) for name in sorted(catalog, key=natural_key)]
    text = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    atomic_write_text(path, text)


def launch_gui(remote: str, output_dir: Path, catalog: dict[str, dict[str, Any]]) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox, simpledialog, ttk
    except ImportError as exc:
        raise SystemExit("Tkinter is unavailable. Install python3-tk.") from exc

    manifest_path = output_dir / MANIFEST_FILENAME
    search_path = output_dir / SEARCH_FILENAME
    cache_dir = output_dir / "thumb-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.title("R2 Work Catalog Navigator")
    root.geometry("1480x860")
    root.minsize(980, 620)

    query_var = tk.StringVar()
    count_var = tk.StringVar()
    status_var = tk.StringVar(value="Manifest catalog loaded. Building fast name index…")
    search_ready = {"value": False}
    rows: list[dict[str, Any]] = [catalog[name] for name in sorted(catalog, key=natural_key)]
    visible: list[dict[str, Any]] = []
    selected_row: dict[str, Any] | None = None
    current_image: Any = None

    toolbar = ttk.Frame(root, padding=10)
    toolbar.pack(fill="x")
    ttk.Label(toolbar, text="Search work names").grid(row=0, column=0, sticky="w")
    search = ttk.Entry(toolbar, textvariable=query_var, state="disabled")
    search.grid(row=1, column=0, sticky="ew", padx=(0, 8))
    ttk.Label(toolbar, textvariable=count_var).grid(row=1, column=1, sticky="e")
    toolbar.columnconfigure(0, weight=1)

    actionbar = ttk.Frame(root, padding=(10, 0, 10, 8))
    actionbar.pack(fill="x")

    panes = ttk.Panedwindow(root, orient="horizontal")
    panes.pack(fill="both", expand=True, padx=10, pady=(0, 8))
    left = ttk.Frame(panes)
    middle = ttk.Frame(panes)
    right = ttk.Frame(panes)
    panes.add(left, weight=2)
    panes.add(middle, weight=4)
    panes.add(right, weight=2)

    works = ttk.Treeview(left, columns=("state", "items", "thumb"), show="tree headings", selectmode="extended")
    works.heading("#0", text="Work")
    works.heading("state", text="State")
    works.heading("items", text="Items")
    works.heading("thumb", text="Thumb")
    works.column("#0", width=300)
    works.column("state", width=85, anchor="center", stretch=False)
    works.column("items", width=50, anchor="center", stretch=False)
    works.column("thumb", width=52, anchor="center", stretch=False)
    works_sb = ttk.Scrollbar(left, orient="vertical", command=works.yview)
    works.configure(yscrollcommand=works_sb.set)
    works.pack(side="left", fill="both", expand=True)
    works_sb.pack(side="right", fill="y")

    notebook = ttk.Notebook(middle)
    notebook.pack(fill="both", expand=True)
    summary_tab = ttk.Frame(notebook)
    details_tab = ttk.Frame(notebook)
    items_tab = ttk.Frame(notebook)
    tags_tab = ttk.Frame(notebook)
    files_tab = ttk.Frame(notebook)
    raw_tab = ttk.Frame(notebook)
    notebook.add(summary_tab, text="Summary")
    notebook.add(details_tab, text="details.json")
    notebook.add(items_tab, text="item.json")
    notebook.add(tags_tab, text="Tags")
    notebook.add(files_tab, text="Remote files / CLI")
    notebook.add(raw_tab, text="Raw manifest row")

    def text_widget(parent: Any) -> Any:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        widget = tk.Text(frame, wrap="word", state="disabled", padx=10, pady=10)
        sb = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=sb.set)
        widget.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return widget

    summary_text = text_widget(summary_tab)
    details_text = text_widget(details_tab)
    items_text = text_widget(items_tab)
    raw_text = text_widget(raw_tab)

    files_frame = ttk.Frame(files_tab, padding=6)
    files_frame.pack(fill="both", expand=True)
    files_tree = ttk.Treeview(files_frame, columns=("type", "uri"), show="tree headings", selectmode="extended")
    files_tree.heading("#0", text="Remote path")
    files_tree.heading("type", text="Type")
    files_tree.heading("uri", text="rclone URI")
    files_tree.column("#0", width=430, stretch=True)
    files_tree.column("type", width=100, stretch=False)
    files_tree.column("uri", width=520, stretch=True)
    files_scroll = ttk.Scrollbar(files_frame, orient="vertical", command=files_tree.yview)
    files_tree.configure(yscrollcommand=files_scroll.set)
    files_tree.pack(side="left", fill="both", expand=True)
    files_scroll.pack(side="right", fill="y")
    files_actions = ttk.Frame(files_tab, padding=(6, 0, 6, 6))
    files_actions.pack(fill="x")

    tag_panes = ttk.Panedwindow(tags_tab, orient="horizontal")
    tag_panes.pack(fill="both", expand=True)
    public_frame = ttk.LabelFrame(tag_panes, text="Public tags", padding=6)
    private_frame = ttk.LabelFrame(tag_panes, text="Private tags", padding=6)
    tag_panes.add(public_frame, weight=1)
    tag_panes.add(private_frame, weight=1)

    def make_tag_tree(parent: Any) -> Any:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, show="tree", selectmode="browse")
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return tree

    public_tree = make_tag_tree(public_frame)
    private_tree = make_tag_tree(private_frame)
    public_buttons = ttk.Frame(public_frame); public_buttons.pack(fill="x", pady=(5, 0))
    private_buttons = ttk.Frame(private_frame); private_buttons.pack(fill="x", pady=(5, 0))

    ttk.Label(right, text="Thumbnail", font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
    thumb_label = ttk.Label(right, text="Select a work and call its thumbnail.", anchor="center", justify="center")
    thumb_label.pack(fill="both", expand=True, pady=8)
    thumb_path_var = tk.StringVar()
    ttk.Label(right, textvariable=thumb_path_var, wraplength=330).pack(fill="x")

    ttk.Label(root, textvariable=status_var, padding=(10, 0, 10, 8)).pack(fill="x")

    def set_text(widget: Any, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")

    def fill_tag_tree(widget: Any, data: dict[str, Any]) -> None:
        widget.delete(*widget.get_children())
        def visit(parent: str, node: dict[str, Any]) -> None:
            for key in sorted(node, key=natural_key):
                item = widget.insert(parent, "end", text=key, open=True)
                visit(item, node[key])
        visit("", data)

    def tree_path(widget: Any, item: str) -> list[str]:
        parts: list[str] = []
        while item:
            parts.append(str(widget.item(item, "text")))
            item = widget.parent(item)
        return list(reversed(parts))

    def cache_paths(row: dict[str, Any]) -> tuple[Path, Path]:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", row["name"])
        return cache_dir / f"{safe}.webp", cache_dir / f"{safe}.png"

    def convert_webp(src: Path, dst: Path) -> bool:
        commands = (["magick", str(src), str(dst)], ["convert", str(src), str(dst)], ["ffmpeg", "-y", "-i", str(src), str(dst)])
        for cmd in commands:
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    return dst.exists()
                except subprocess.CalledProcessError:
                    pass
        return False

    def show_cached_thumb(row: dict[str, Any]) -> None:
        nonlocal current_image
        webp, png = cache_paths(row)
        source = png if png.exists() else webp if webp.exists() else None
        if source is None:
            current_image = None
            thumb_label.configure(image="", text="Thumbnail not cached.")
            thumb_path_var.set("")
            return
        try:
            image = tk.PhotoImage(file=str(source))
        except tk.TclError:
            if source.suffix.casefold() == ".webp" and convert_webp(source, png):
                try:
                    image = tk.PhotoImage(file=str(png)); source = png
                except tk.TclError:
                    thumb_label.configure(image="", text=f"Cached at:\n{webp}\n\nUnable to display WebP.")
                    thumb_path_var.set(str(webp)); return
            else:
                thumb_label.configure(image="", text=f"Cached at:\n{source}\n\nInstall ImageMagick or ffmpeg for WebP display.")
                thumb_path_var.set(str(source)); return
        factor = max(1, image.width() // 350, image.height() // 650)
        if factor > 1:
            image = image.subsample(factor, factor)
        current_image = image
        thumb_label.configure(image=image, text="")
        thumb_path_var.set(str(source))

    def persist(row: dict[str, Any], message: str = "Updated") -> None:
        row = migrate_row(row)
        catalog[row["name"]] = row
        append_jsonl(manifest_path, row)
        status_var.set(f"{message}: {row['name']}")
        display_row(row)
        refresh_list()
        schedule_search_rebuild()

    def display_row(row: dict[str, Any]) -> None:
        nonlocal selected_row
        selected_row = row
        resources = row.get("resources") or {}
        lines = [
            row["name"], "=" * len(row["name"]),
            f"State: {row.get('status', 'unknown')}",
            f"Remote: {row.get('remote_path', '')}",
            f"Last structural scan: {row.get('scanned_at', 'not called')}",
            "",
            f"details.json: {'yes' if row.get('has_details_json') else 'unknown/no'}",
            f"thumb.webp: {'yes' if row.get('has_thumb_webp') else 'unknown/no'}",
            f"item.json files: {row.get('item_json_count', 0)}",
            f"archives: {row.get('archive_count', 0)}",
        ]
        for label, key in (("details", "details_paths"), ("items", "item_json_paths"), ("thumbs", "thumb_paths"), ("archives", "archive_paths")):
            values = row.get(key) or []
            if values:
                lines.extend(["", label + ":", *[f"  {x}" for x in values]])
        set_text(summary_text, "\n".join(lines))
        set_text(details_text, json.dumps(resources.get("details_json", {"message": "Press Call details.json"}), ensure_ascii=False, indent=2))
        item_display = {"derived_manifests": row.get("manifests", []), "raw_item_json": resources.get("item_json", {})}
        set_text(items_text, json.dumps(item_display, ensure_ascii=False, indent=2))
        set_text(raw_text, json.dumps(row, ensure_ascii=False, indent=2))
        tags = normalize_tags_file(row.get("tags")); row["tags"] = tags
        fill_tag_tree(public_tree, tags["public"])
        fill_tag_tree(private_tree, tags["private"])
        files_tree.delete(*files_tree.get_children())
        catalog_entries = row.get("file_catalog") or build_file_catalog(remote, row.get("all_paths") or [])
        for entry in catalog_entries:
            path = str(entry.get("path") or "")
            suffix = PurePosixPath(path).suffix.casefold().lstrip(".") or "file"
            files_tree.insert("", "end", text=path, values=(suffix, entry.get("rclone_uri", remote_join(remote, path))))
        show_cached_thumb(row)

    def refresh_list(*_args: Any) -> None:
        prior = selected_row["name"] if selected_row else None
        query = query_var.get().strip() if search_ready["value"] else ""
        ranked: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            score = rank_name_query(query, row)
            if score is not None:
                ranked.append((score, row))
        ranked.sort(key=lambda pair: (pair[0], natural_key(pair[1]["name"])))
        visible[:] = [row for _score, row in ranked]
        works.delete(*works.get_children())
        select_id = None
        for row in visible:
            webp, _ = cache_paths(row)
            item = works.insert("", "end", text=row["name"], values=(row.get("status", ""), row.get("item_json_count", 0), "yes" if webp.exists() else ""))
            if row["name"] == prior:
                select_id = item
        count_var.set(f"{len(visible)} / {len(rows)} works")
        if visible:
            select_id = select_id or works.get_children()[0]
            works.selection_set(select_id); works.focus(select_id); works.see(select_id)
            display_row(visible[works.index(select_id)])

    def on_select(_event: Any = None) -> None:
        selection = works.selection()
        if selection:
            index = works.index(selection[0])
            if 0 <= index < len(visible):
                display_row(visible[index])

    works.bind("<<TreeviewSelect>>", on_select)
    query_var.trace_add("write", refresh_list)

    def selected_required() -> dict[str, Any] | None:
        if not selected_row:
            messagebox.showinfo("Select a work", "Select a work first.")
            return None
        return selected_row

    def selected_rows() -> list[dict[str, Any]]:
        chosen: list[dict[str, Any]] = []
        for item in works.selection():
            index = works.index(item)
            if 0 <= index < len(visible):
                chosen.append(visible[index])
        return chosen

    def do_one(label: str, function: Callable[[str, dict[str, Any]], dict[str, Any]]) -> None:
        row = selected_required()
        if row is None:
            return
        status_var.set(f"{label}: {row['name']}"); root.update_idletasks()
        try:
            persist(function(remote, row), label)
        except Exception as exc:
            messagebox.showerror(label, str(exc)); status_var.set(f"{label} failed")

    def ensure_structural(row: dict[str, Any]) -> dict[str, Any]:
        return structural_scan(remote, row["name"], row)

    def do_all(label: str, function: Callable[[str, dict[str, Any]], dict[str, Any]]) -> None:
        failures = 0
        for number, row in enumerate(list(rows), 1):
            status_var.set(f"{label} {number}/{len(rows)}: {row['name']}"); root.update_idletasks()
            try:
                updated = function(remote, row)
                catalog[row["name"]] = updated
                append_jsonl(manifest_path, updated)
                rows[number - 1] = updated
            except Exception as exc:
                failures += 1; print(f"{label} failed for {row['name']}: {exc}", file=sys.stderr)
        status_var.set(f"{label} finished. Failures: {failures}")
        refresh_list(); schedule_search_rebuild()

    def call_thumb(row: dict[str, Any]) -> dict[str, Any]:
        if not row.get("scanned_at"):
            row = structural_scan(remote, row["name"], row)
        if not row.get("thumb_paths"):
            raise RuntimeError("No thumb.webp was discovered for this work.")
        webp, _ = cache_paths(row)
        if not webp.exists():
            copy_remote_file(remote, row["thumb_paths"][0], webp)
        row.setdefault("resources", {})["thumbnail_cache"] = str(webp)
        row["thumb_called_at"] = utc_iso()
        return row

    def call_all_resources(_remote: str, row: dict[str, Any]) -> dict[str, Any]:
        row = structural_scan(remote, row["name"], row)
        row = call_items(remote, row)
        row = call_details(remote, row)
        row = call_tags(remote, row)
        try:
            row = call_thumb(row)
        except Exception:
            pass
        return row

    def json_paths_for_type(row: dict[str, Any], kind: str) -> list[str]:
        mapping = {
            "details": "details_paths",
            "tags": "tags_path",
            "items": "item_json_paths",
            "all-json": None,
        }
        if kind == "tags":
            path = str(row.get("tags_path") or "")
            return [path] if path and path in (row.get("all_paths") or []) else []
        if kind == "all-json":
            return [p for p in row.get("all_paths") or [] if PurePosixPath(p).suffix.casefold() == ".json"]
        return list(row.get(mapping[kind]) or [])

    def download_json_for_rows(kind: str, target_rows: list[dict[str, Any]], label: str) -> None:
        if not target_rows:
            messagebox.showinfo("Select works", "Select one or more works first.")
            return
        download_root = output_dir / "downloads" / kind
        failures = 0
        copied = 0
        for number, row in enumerate(target_rows, 1):
            status_var.set(f"{label} {number}/{len(target_rows)}: {row['name']}")
            root.update_idletasks()
            try:
                if not row.get("scanned_at"):
                    updated = structural_scan(remote, row["name"], row)
                    catalog[row["name"]] = updated
                    append_jsonl(manifest_path, updated)
                    row = updated
                for relative in json_paths_for_type(row, kind):
                    inside = PurePosixPath(relative).relative_to(row["name"])
                    destination = download_root / re.sub(r"[^A-Za-z0-9._-]+", "_", row["name"]) / Path(*inside.parts)
                    copy_remote_file(remote, relative, destination)
                    copied += 1
            except Exception as exc:
                failures += 1
                print(f"{label} failed for {row['name']}: {exc}", file=sys.stderr)
        status_var.set(f"{label}: downloaded {copied} file(s); failures: {failures}. Destination: {download_root}")
        refresh_list(); schedule_search_rebuild()

    def selected_file_path() -> str | None:
        selection = files_tree.selection()
        if not selection:
            messagebox.showinfo("Select a file", "Select a remote file in the Remote files / CLI tab.")
            return None
        return str(files_tree.item(selection[0], "text"))

    def open_selected_remote_file() -> None:
        path = selected_file_path()
        if not path:
            return
        try:
            url = rclone_link(remote, path)
            if not url:
                raise RuntimeError("rclone did not return a link for this file.")
            webbrowser.open(url)
            status_var.set(f"Opened link for {path}")
        except Exception as exc:
            messagebox.showerror("Open remote file", str(exc))

    def pull_selected_remote_files() -> None:
        row = selected_required()
        if row is None:
            return
        selection = files_tree.selection()
        if not selection:
            messagebox.showinfo("Select files", "Select one or more files in the Remote files / CLI tab.")
            return
        root_dir = output_dir / "downloads" / "selected-files" / re.sub(r"[^A-Za-z0-9._-]+", "_", row["name"])
        copied = 0
        for item in selection:
            relative = str(files_tree.item(item, "text"))
            inside = PurePosixPath(relative).relative_to(row["name"])
            copy_remote_file(remote, relative, root_dir / Path(*inside.parts))
            copied += 1
        status_var.set(f"Pulled {copied} file(s) to {root_dir}")

    ttk.Button(files_actions, text="Visit selected", command=open_selected_remote_file).pack(side="left", padx=(0, 5))
    ttk.Button(files_actions, text="Pull selected", command=pull_selected_remote_files).pack(side="left", padx=(0, 5))

    buttons = [
        ("Refresh structure", lambda: do_one("Refresh structure", lambda _r, x: ensure_structural(x))),
        ("Call thumbnail", lambda: do_one("Call thumbnail", lambda _r, x: call_thumb(x))),
        ("Call details.json", lambda: do_one("Call details.json", call_details)),
        ("Call tags.json", lambda: do_one("Call tags.json", call_tags)),
        ("Call item.json", lambda: do_one("Call item.json", call_items)),
        ("Call everything", lambda: do_one("Call everything", call_all_resources)),
    ]
    for text, command in buttons:
        ttk.Button(actionbar, text=text, command=command).pack(side="left", padx=(0, 5))

    all_menu = ttk.Menubutton(actionbar, text="Call all…")
    menu = tk.Menu(all_menu, tearoff=False)
    menu.add_command(label="All thumbnails", command=lambda: do_all("Call all thumbnails", lambda _r, x: call_thumb(x)))
    menu.add_command(label="All details.json", command=lambda: do_all("Call all details.json", call_details))
    menu.add_command(label="All tags.json", command=lambda: do_all("Call all tags.json", call_tags))
    menu.add_command(label="All item.json", command=lambda: do_all("Call all item.json", call_items))
    menu.add_separator()
    menu.add_command(label="Download selected details.json", command=lambda: download_json_for_rows("details", selected_rows(), "Download selected details.json"))
    menu.add_command(label="Download selected tags.json", command=lambda: download_json_for_rows("tags", selected_rows(), "Download selected tags.json"))
    menu.add_command(label="Download selected item.json", command=lambda: download_json_for_rows("items", selected_rows(), "Download selected item.json"))
    menu.add_command(label="Download selected all JSON", command=lambda: download_json_for_rows("all-json", selected_rows(), "Download selected JSON"))
    menu.add_separator()
    menu.add_command(label="Download ALL details.json", command=lambda: download_json_for_rows("details", list(rows), "Download all details.json"))
    menu.add_command(label="Download ALL tags.json", command=lambda: download_json_for_rows("tags", list(rows), "Download all tags.json"))
    menu.add_command(label="Download ALL item.json", command=lambda: download_json_for_rows("items", list(rows), "Download all item.json"))
    menu.add_command(label="Download ALL JSON", command=lambda: download_json_for_rows("all-json", list(rows), "Download all JSON"))
    menu.add_separator()
    menu.add_command(label="All resources", command=lambda: do_all("Call all resources", call_all_resources))
    all_menu["menu"] = menu
    all_menu.pack(side="left")

    def add_tag(group: str) -> None:
        row = selected_required()
        if row is None:
            return
        value = simpledialog.askstring("Add nested tag", "Path, for example: this > that > deeper", parent=root)
        if not value:
            return
        tags = normalize_tags_file(row.get("tags")); add_tag_path(tags[group], value); row["tags"] = tags
        try:
            persist(save_tags(remote, row), "Saved tags")
        except Exception as exc:
            messagebox.showerror("Save tags", str(exc))

    def remove_tag(group: str, widget: Any) -> None:
        row = selected_required()
        selection = widget.selection()
        if row is None or not selection:
            return
        tags = normalize_tags_file(row.get("tags")); delete_tag_path(tags[group], tree_path(widget, selection[0])); row["tags"] = tags
        try:
            persist(save_tags(remote, row), "Saved tags")
        except Exception as exc:
            messagebox.showerror("Save tags", str(exc))

    ttk.Button(public_buttons, text="+", width=4, command=lambda: add_tag("public")).pack(side="left")
    ttk.Button(public_buttons, text="Remove", command=lambda: remove_tag("public", public_tree)).pack(side="left", padx=4)
    ttk.Button(private_buttons, text="+", width=4, command=lambda: add_tag("private")).pack(side="left")
    ttk.Button(private_buttons, text="Remove", command=lambda: remove_tag("private", private_tree)).pack(side="left", padx=4)

    rebuild_job: str | None = None
    def rebuild_search_now() -> None:
        nonlocal rows
        write_search_index(catalog, search_path)
        rows = [catalog[name] for name in sorted(catalog, key=natural_key)]
        search_ready["value"] = True
        search.configure(state="normal")
        status_var.set(f"Fast search ready: {len(rows)} works. Index: {search_path}")
        refresh_list(); search.focus_set()

    def schedule_search_rebuild() -> None:
        nonlocal rebuild_job
        search_ready["value"] = False
        search.configure(state="disabled")
        status_var.set("Updating fast search index…")
        if rebuild_job is not None:
            try: root.after_cancel(rebuild_job)
            except Exception: pass
        rebuild_job = root.after(100, rebuild_search_now)

    refresh_list()
    schedule_search_rebuild()
    root.mainloop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incremental R2 work catalog and GUI navigator.")
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--import-index", type=Path, action="append", default=[], help="Import an older schema-2/3 JSONL index. May be repeated.")
    parser.add_argument("--offline", action="store_true", help="Open existing catalog without contacting R2.")
    parser.add_argument("--scan-new", action="store_true", help="Structurally inspect only newly discovered works before opening the GUI.")
    parser.add_argument("--no-gui", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / MANIFEST_FILENAME
    search_path = output_dir / SEARCH_FILENAME
    imports = [path.expanduser().resolve() for path in args.import_index]
    catalog = load_catalog(output_dir, imports)
    print(f"Loaded {len(catalog)} known works from salvageable JSONL records.")

    new_names: list[str] = []
    if not args.offline:
        try:
            new_names = discover_new(args.remote, catalog, manifest_path)
            print(f"R2 directory comparison complete: {len(new_names)} new work(s).")
        except Exception as exc:
            print(f"Warning: R2 discovery failed; opening cached catalog: {exc}", file=sys.stderr)

    if args.scan_new:
        for number, name in enumerate(new_names, 1):
            print(f"Scanning new work {number}/{len(new_names)}: {name}")
            try:
                row = structural_scan(args.remote, name, catalog[name])
                append_jsonl(manifest_path, row)
                catalog[name] = row
            except KeyboardInterrupt:
                print("\nInterrupted. Completed JSONL lines are preserved; run again to continue.")
                break
            except Exception as exc:
                print(f"Failed to scan {name}: {exc}", file=sys.stderr)

    # Ensure imported rows become durable in the new canonical manifest without
    # rewriting it. Only absent names need one migration append.
    canonical_names = {row_name(x) for x in salvage_jsonl(manifest_path)}
    for name in sorted(catalog, key=natural_key):
        if name not in canonical_names:
            append_jsonl(manifest_path, catalog[name])

    if args.no_gui:
        write_search_index(catalog, search_path)
        print(f"Manifest index: {manifest_path}")
        print(f"Search index:   {search_path}")
        return

    launch_gui(args.remote, output_dir, catalog)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted safely. Complete JSONL lines remain usable.")
        raise SystemExit(130)
