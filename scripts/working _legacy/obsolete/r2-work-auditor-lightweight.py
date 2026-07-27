#!/usr/bin/env python3
"""
R2 Work Auditor and Slice Generator

Features
--------
- Lightweight by default: lists direct work folders and only structural files.
- Deep full-object inventory is available with --deep.
- Groups objects by top-level work folder.
- Reports:
  * work names
  * object/file counts
  * total bytes
  * ZIP and CBZ presence
  * details.json presence
  * item.json count
  * thumb.webp presence
  * predicted page URL templates from item.json
  * image count in --deep mode
  * suspicious duplicate work names
  * duplicate archives
- Interactive terminal interface.
- Exports full inventories as JSON, JSONL, and CSV.
- Generates a "work slice":
  * collected JSON files
  * summary.json
  * 3-4 evenly distributed preview images
  * optional copied archive metadata
- Read-only by default. It does not delete or alter R2 objects.

Requirements
------------
- Python 3.10+
- rclone installed and configured
- Optional: Pillow for contact-sheet generation

Examples
--------
    python r2-work-auditor.py
    python r2-work-auditor.py --remote animeplex.lol:extended/works
    python r2-work-auditor.py --remote animeplex.lol:extended/works --export
    python r2-work-auditor.py --remote animeplex.lol:extended/works --slice My_Work
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}
ARCHIVE_EXTS = {".zip", ".cbz"}
JSON_NAMES = {"details.json", "item.json"}
DEFAULT_REMOTE = "animeplex.lol:extended/works"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "r2-audit-output"
MAX_JSON_BYTES = 8 * 1024 * 1024


@dataclass
class RemoteObject:
    path: str
    name: str
    size: int
    mod_time: str | None
    mime_type: str | None
    hash_md5: str | None = None
    hash_sha1: str | None = None


@dataclass
class WorkRecord:
    name: str
    remote_path: str
    file_count: int = 0
    total_bytes: int = 0
    image_count: int = 0
    json_count: int = 0
    item_json_count: int = 0
    archive_count: int = 0
    zip_count: int = 0
    cbz_count: int = 0
    non_image_count: int = 0
    has_details_json: bool = False
    has_thumb_webp: bool = False
    archive_paths: list[str] = field(default_factory=list)
    details_paths: list[str] = field(default_factory=list)
    item_json_paths: list[str] = field(default_factory=list)
    thumb_paths: list[str] = field(default_factory=list)
    image_paths: list[str] = field(default_factory=list)
    other_json_paths: list[str] = field(default_factory=list)
    all_paths: list[str] = field(default_factory=list)
    suspicious_duplicate_group: str | None = None
    duplicate_archive_names: list[str] = field(default_factory=list)
    item_manifests: list[dict[str, Any]] = field(default_factory=list)


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def human_bytes(value: int) -> str:
    units = ["B", "KiB", "MiB", "GiB", "TiB"]
    number = float(value)
    for unit in units:
        if abs(number) < 1024 or unit == units[-1]:
            return f"{number:.1f} {unit}"
        number /= 1024
    return f"{value} B"


def natural_key(value: str) -> list[Any]:
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def normalized_work_name(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"\b(copy|duplicate|dup|backup|old|new|final|fixed|v\d+)\b", "", value)
    value = re.sub(r"[\W_]+", "", value)
    return value


def run_capture(cmd: list[str]) -> str:
    print("$ " + " ".join(shlex_quote(part) for part in cmd))
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError:
        raise SystemExit("rclone was not found. Install it and ensure it is available in PATH.")
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout.rstrip())
        if exc.stderr:
            print(exc.stderr.rstrip(), file=sys.stderr)
        raise SystemExit(exc.returncode) from None
    return result.stdout


def run(cmd: list[str]) -> None:
    print("$ " + " ".join(shlex_quote(part) for part in cmd))
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        raise SystemExit("rclone was not found. Install it and ensure it is available in PATH.")
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from None


def shlex_quote(value: str) -> str:
    import shlex
    return shlex.quote(value)


def remote_join(remote: str, relative: str) -> str:
    return f"{remote.rstrip('/')}/{relative.lstrip('/')}"


def list_work_directories(remote: str) -> list[str]:
    """List only directories directly beneath the configured works prefix."""
    raw = run_capture([
        "rclone", "lsf", remote,
        "--dirs-only", "--max-depth", "1",
    ])
    names = []
    for line in raw.splitlines():
        name = line.strip().replace("\\", "/").strip("/")
        if name and "/" not in name:
            names.append(name)
    return sorted(set(names), key=natural_key)


def _rows_to_objects(raw: str) -> list[RemoteObject]:
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Could not parse rclone lsjson output: {exc}") from exc

    objects: list[RemoteObject] = []
    for row in rows:
        path = str(row.get("Path") or row.get("Name") or "").replace("\\", "/").lstrip("/")
        if not path:
            continue
        hashes = row.get("Hashes") if isinstance(row.get("Hashes"), dict) else {}
        objects.append(RemoteObject(
            path=path,
            name=PurePosixPath(path).name,
            size=int(row.get("Size") or 0),
            mod_time=row.get("ModTime"),
            mime_type=row.get("MimeType"),
            hash_md5=hashes.get("MD5"),
            hash_sha1=hashes.get("SHA-1"),
        ))
    return objects


def list_lightweight_objects(remote: str, work_names: list[str]) -> list[RemoteObject]:
    """List only structural metadata and archives, never page images."""
    objects: list[RemoteObject] = []
    includes = [
        "--include", "**/item.json",
        "--include", "**/details.json",
        "--include", "**/thumb.webp",
        "--include", "**/*.zip",
        "--include", "**/*.cbz",
        "--exclude", "*",
    ]
    for work_name in work_names:
        raw = run_capture([
            "rclone", "lsjson", remote_join(remote, work_name),
            "--recursive", "--files-only", "--no-mimetype",
            *includes,
        ])
        for obj in _rows_to_objects(raw):
            obj.path = f"{work_name}/{obj.path}".strip("/")
            obj.name = PurePosixPath(obj.path).name
            objects.append(obj)
    return objects


def list_remote_objects(remote: str) -> list[RemoteObject]:
    """Deep inventory mode: enumerate all files and request hashes."""
    raw = run_capture([
        "rclone", "lsjson", remote,
        "--recursive", "--files-only", "--hash", "--no-mimetype",
    ])
    return _rows_to_objects(raw)


def build_inventory(remote: str, objects: list[RemoteObject]) -> list[WorkRecord]:
    grouped: dict[str, list[RemoteObject]] = defaultdict(list)

    for obj in objects:
        parts = PurePosixPath(obj.path).parts
        if not parts:
            continue
        grouped[parts[0]].append(obj)

    records: list[WorkRecord] = []
    normalized_groups: dict[str, list[str]] = defaultdict(list)

    for work_name, work_objects in grouped.items():
        record = WorkRecord(name=work_name, remote_path=remote_join(remote, work_name))
        archive_name_counts: dict[str, int] = defaultdict(int)

        for obj in sorted(work_objects, key=lambda item: natural_key(item.path)):
            suffix = PurePosixPath(obj.path).suffix.casefold()
            name_lower = obj.name.casefold()

            record.file_count += 1
            record.total_bytes += obj.size
            record.all_paths.append(obj.path)

            if suffix in IMAGE_EXTS:
                record.image_count += 1
                record.image_paths.append(obj.path)
            else:
                record.non_image_count += 1

            if suffix == ".json":
                record.json_count += 1
                if name_lower == "details.json":
                    record.has_details_json = True
                    record.details_paths.append(obj.path)
                elif name_lower == "item.json":
                    record.item_json_count += 1
                    record.item_json_paths.append(obj.path)
                else:
                    record.other_json_paths.append(obj.path)

            if name_lower == "thumb.webp":
                record.has_thumb_webp = True
                record.thumb_paths.append(obj.path)

            if suffix in ARCHIVE_EXTS:
                record.archive_count += 1
                record.archive_paths.append(obj.path)
                archive_name_counts[obj.name.casefold()] += 1
                if suffix == ".zip":
                    record.zip_count += 1
                elif suffix == ".cbz":
                    record.cbz_count += 1

        record.duplicate_archive_names = sorted(
            name for name, count in archive_name_counts.items() if count > 1
        )
        normalized_groups[normalized_work_name(work_name)].append(work_name)
        records.append(record)

    duplicate_groups = {
        key: names for key, names in normalized_groups.items() if key and len(names) > 1
    }
    for record in records:
        key = normalized_work_name(record.name)
        if key in duplicate_groups:
            record.suspicious_duplicate_group = " | ".join(sorted(duplicate_groups[key], key=natural_key))

    return sorted(records, key=lambda record: natural_key(record.name))



def derive_page_manifest(data: Any, item_path: str) -> dict[str, Any]:
    result: dict[str, Any] = {"item_path": item_path, "valid": False}
    if not isinstance(data, dict):
        result["error"] = "item.json is not a JSON object"
        return result

    base_url = str(data.get("base_url") or data.get("baseUrl") or "").rstrip("/")
    pages_raw = data.get("pages") or data.get("page_count") or data.get("pageCount")
    padding_raw = data.get("padding", 3)
    extension = str(data.get("extension") or data.get("ext") or "webp").lstrip(".")

    try:
        pages = int(pages_raw)
        padding = int(padding_raw)
    except (TypeError, ValueError):
        result["error"] = "missing or invalid pages/padding"
        result.update({"base_url": base_url, "extension": extension})
        return result

    if not base_url or pages < 1 or padding < 1:
        result["error"] = "missing base_url or invalid numeric values"
        result.update({"base_url": base_url, "pages": pages, "padding": padding, "extension": extension})
        return result

    def page_url(number: int) -> str:
        return f"{base_url}/{number:0{padding}d}.{extension}"

    result.update({
        "valid": True,
        "base_url": base_url,
        "pages": pages,
        "padding": padding,
        "extension": extension,
        "url_template": f"{base_url}/{{page:0{padding}d}}.{extension}",
        "first_page_url": page_url(1),
        "last_page_url": page_url(pages),
    })
    return result


def load_item_manifests(remote: str, records: list[WorkRecord]) -> None:
    """Download only item.json files and derive page URL patterns."""
    with tempfile.TemporaryDirectory(prefix="r2-auditor-items-") as tmp:
        root = Path(tmp)
        for record in records:
            for index, item_path in enumerate(record.item_json_paths, start=1):
                local = root / safe_local_name(record.name) / f"item-{index}.json"
                try:
                    copy_remote_file(remote, item_path, local)
                    data = parse_json_safely(local)
                    record.item_manifests.append(derive_page_manifest(data, item_path))
                except (OSError, SystemExit) as exc:
                    record.item_manifests.append({
                        "item_path": item_path,
                        "valid": False,
                        "error": str(exc),
                    })

def record_to_dict(record: WorkRecord) -> dict[str, Any]:
    return asdict(record)


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


def export_inventory(records: list[WorkRecord], output_dir: Path, remote: str) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = utc_iso()

    json_path = output_dir / "r2-inventory.json"
    jsonl_path = output_dir / "r2-inventory.jsonl"
    csv_path = output_dir / "r2-inventory.csv"
    duplicate_path = output_dir / "r2-duplicates.csv"

    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "remote": remote,
        "work_count": len(records),
        "works": [record_to_dict(record) for record in records],
    }
    atomic_write_text(json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    atomic_write_text(
        jsonl_path,
        "".join(json.dumps(record_to_dict(record), ensure_ascii=False) + "\n" for record in records),
    )

    csv_fields = [
        "name",
        "remote_path",
        "file_count",
        "total_bytes",
        "image_count",
        "json_count",
        "item_json_count",
        "archive_count",
        "zip_count",
        "cbz_count",
        "non_image_count",
        "has_details_json",
        "has_thumb_webp",
        "suspicious_duplicate_group",
        "duplicate_archive_names",
        "archive_paths",
        "details_paths",
        "item_json_paths",
        "thumb_paths",
    ]
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", delete=False, dir=output_dir, prefix=".r2-inventory.", suffix=".tmp"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_fields)
        writer.writeheader()
        for record in records:
            row = record_to_dict(record)
            for field_name in [
                "duplicate_archive_names",
                "archive_paths",
                "details_paths",
                "item_json_paths",
                "thumb_paths",
            ]:
                row[field_name] = json.dumps(row[field_name], ensure_ascii=False)
            writer.writerow({key: row.get(key) for key in csv_fields})
        temp_csv = Path(handle.name)
    os.replace(temp_csv, csv_path)

    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", delete=False, dir=output_dir, prefix=".r2-duplicates.", suffix=".tmp"
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(["type", "work", "details"])
        for record in records:
            if record.suspicious_duplicate_group:
                writer.writerow(["similar_work_name", record.name, record.suspicious_duplicate_group])
            if record.duplicate_archive_names:
                writer.writerow(["duplicate_archive_name", record.name, " | ".join(record.duplicate_archive_names)])
            if record.archive_count > 1:
                writer.writerow(["multiple_archives", record.name, " | ".join(record.archive_paths)])
        temp_dup = Path(handle.name)
    os.replace(temp_dup, duplicate_path)

    return [json_path, jsonl_path, csv_path, duplicate_path]


def print_record(record: WorkRecord) -> None:
    print(f"\n{record.name}")
    print("=" * len(record.name))
    print(f"Remote:            {record.remote_path}")
    print(f"Files:             {record.file_count}")
    print(f"Total size:        {human_bytes(record.total_bytes)}")
    print(f"Images:            {record.image_count}")
    print(f"JSON files:        {record.json_count}")
    print(f"item.json files:   {record.item_json_count}")
    print(f"details.json:      {'yes' if record.has_details_json else 'no'}")
    print(f"thumb.webp:        {'yes' if record.has_thumb_webp else 'no'}")
    print(f"Archives:          {record.archive_count}")
    print(f"ZIP:               {record.zip_count}")
    print(f"CBZ:               {record.cbz_count}")
    print(f"Non-image files:   {record.non_image_count}")

    if record.archive_paths:
        print("\nArchives:")
        for path in record.archive_paths:
            print(f"  - {path}")

    if record.details_paths:
        print("\ndetails.json:")
        for path in record.details_paths:
            print(f"  - {path}")

    if record.item_json_paths:
        print("\nitem.json:")
        for path in record.item_json_paths:
            print(f"  - {path}")

    if record.item_manifests:
        print("\nPredicted page URLs:")
        for manifest in record.item_manifests:
            if manifest.get("valid"):
                print(f"  - {manifest['url_template']} ({manifest['pages']} pages)")
                print(f"    first: {manifest['first_page_url']}")
                print(f"    last:  {manifest['last_page_url']}")
            else:
                print(f"  - {manifest.get('item_path')}: unresolved ({manifest.get('error', 'unknown error')})")

    if record.suspicious_duplicate_group:
        print(f"\nPossible duplicate group:\n  {record.suspicious_duplicate_group}")

    if record.duplicate_archive_names:
        print("\nDuplicate archive filenames:")
        for name in record.duplicate_archive_names:
            print(f"  - {name}")


def choose_evenly_spaced(paths: list[str], count: int) -> list[str]:
    paths = sorted(paths, key=natural_key)
    if not paths or count <= 0:
        return []
    if len(paths) <= count:
        return paths
    if count == 1:
        return [paths[len(paths) // 2]]

    indexes = []
    for i in range(count):
        index = round(i * (len(paths) - 1) / (count - 1))
        if index not in indexes:
            indexes.append(index)
    return [paths[index] for index in indexes]


def safe_local_name(remote_path: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", remote_path.strip("/"))


def copy_remote_file(remote: str, relative_path: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(["rclone", "copyto", remote_join(remote, relative_path), str(destination)])


def copy_json_files(remote: str, record: WorkRecord, slice_dir: Path) -> list[Path]:
    json_paths = sorted(
        set(record.details_paths + record.item_json_paths + record.other_json_paths),
        key=natural_key,
    )
    copied: list[Path] = []

    for remote_path in json_paths:
        relative_inside_work = PurePosixPath(remote_path).relative_to(record.name)
        destination = slice_dir / "json" / Path(*relative_inside_work.parts)
        copy_remote_file(remote, remote_path, destination)
        copied.append(destination)

    return copied


def parse_json_safely(path: Path) -> Any:
    if path.stat().st_size > MAX_JSON_BYTES:
        return {
            "_error": "JSON file exceeds local safety limit",
            "_size_bytes": path.stat().st_size,
        }
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"_error": str(exc)}


def build_contact_sheet(image_paths: list[Path], output_path: Path) -> bool:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return False

    loaded = []
    try:
        for path in image_paths:
            image = Image.open(path)
            image.thumbnail((500, 700))
            loaded.append((path, image.copy()))
            image.close()

        if not loaded:
            return False

        margin = 24
        label_height = 42
        width = max(image.width for _, image in loaded) + margin * 2
        total_height = margin + sum(image.height + label_height + margin for _, image in loaded)

        sheet = Image.new("RGB", (width, total_height), "white")
        draw = ImageDraw.Draw(sheet)
        y = margin

        for path, image in loaded:
            x = (width - image.width) // 2
            sheet.paste(image.convert("RGB"), (x, y))
            y += image.height + 8
            draw.text((margin, y), path.name, fill="black")
            y += label_height + margin - 8

        sheet.save(output_path, "JPEG", quality=90)
        return True
    finally:
        for _, image in loaded:
            image.close()


def generate_slice(
    remote: str,
    record: WorkRecord,
    output_dir: Path,
    preview_count: int = 4,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    slice_dir = output_dir / "slices" / f"{safe_local_name(record.name)}-{timestamp}"
    slice_dir.mkdir(parents=True, exist_ok=False)

    preview_remote_paths = choose_evenly_spaced(
        [path for path in record.image_paths if PurePosixPath(path).name.casefold() not in {"thumb.webp", "thumbnail.webp", "cover.webp"}],
        preview_count,
    )

    preview_local_paths: list[Path] = []
    for index, remote_path in enumerate(preview_remote_paths, start=1):
        suffix = PurePosixPath(remote_path).suffix or ".img"
        destination = slice_dir / "previews" / f"{index:02d}-{safe_local_name(remote_path)}"
        if not destination.suffix:
            destination = destination.with_suffix(suffix)
        copy_remote_file(remote, remote_path, destination)
        preview_local_paths.append(destination)

    copied_json = copy_json_files(remote, record, slice_dir)
    parsed_json = {
        str(path.relative_to(slice_dir)): parse_json_safely(path)
        for path in copied_json
    }

    summary = {
        "schema_version": 1,
        "generated_at": utc_iso(),
        "remote": remote,
        "work": record_to_dict(record),
        "preview_images": [
            {
                "remote_path": remote_path,
                "local_path": str(local_path.relative_to(slice_dir)),
            }
            for remote_path, local_path in zip(preview_remote_paths, preview_local_paths)
        ],
        "json_files": [
            str(path.relative_to(slice_dir))
            for path in copied_json
        ],
        "parsed_json": parsed_json,
    }
    atomic_write_text(slice_dir / "summary.json", json.dumps(summary, ensure_ascii=False, indent=2) + "\n")

    if preview_local_paths:
        built = build_contact_sheet(preview_local_paths, slice_dir / "contact-sheet.jpg")
        if not built:
            atomic_write_text(
                slice_dir / "CONTACT-SHEET-NOT-CREATED.txt",
                "Install Pillow to generate contact-sheet.jpg:\npython -m pip install Pillow\n",
            )

    readme = f"""R2 WORK SLICE

Work: {record.name}
Remote: {record.remote_path}
Generated: {summary['generated_at']}

Contents:
- summary.json
- json/          copied details.json, item.json, and other JSON files
- previews/      {len(preview_local_paths)} images spaced across the work
- contact-sheet.jpg, when Pillow is installed

Archive status:
- ZIP files: {record.zip_count}
- CBZ files: {record.cbz_count}
- Archive paths:
{os.linesep.join(f'  - {path}' for path in record.archive_paths) if record.archive_paths else '  none'}
"""
    atomic_write_text(slice_dir / "README.txt", readme)
    return slice_dir


def find_record(records: list[WorkRecord], query: str) -> WorkRecord | None:
    exact = [record for record in records if record.name.casefold() == query.casefold()]
    if exact:
        return exact[0]

    matches = [record for record in records if query.casefold() in record.name.casefold()]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print("\nMultiple matches:")
        for index, record in enumerate(matches, start=1):
            print(f"{index:4d}. {record.name}")
        answer = input("Choose number: ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(matches):
            return matches[int(answer) - 1]
    return None


def print_work_table(records: list[WorkRecord]) -> None:
    print()
    print(f"{'#':>4}  {'WORK':<48} {'FILES':>8} {'IMAGES':>8} {'ZIP':>4} {'CBZ':>4} {'DETAILS':>7} {'ITEMS':>6}")
    print("-" * 102)
    for index, record in enumerate(records, start=1):
        name = record.name[:48]
        duplicate_marker = "*" if record.suspicious_duplicate_group else " "
        print(
            f"{index:4d}{duplicate_marker} "
            f"{name:<48} "
            f"{record.file_count:8d} "
            f"{record.image_count:8d} "
            f"{record.zip_count:4d} "
            f"{record.cbz_count:4d} "
            f"{('yes' if record.has_details_json else 'no'):>7} "
            f"{record.item_json_count:6d}"
        )
    print("\n* possible duplicate-name group")


def print_duplicates(records: list[WorkRecord]) -> None:
    found = False
    print("\nPossible duplicates")
    print("===================")
    for record in records:
        issues = []
        if record.suspicious_duplicate_group:
            issues.append(f"name group: {record.suspicious_duplicate_group}")
        if record.archive_count > 1:
            issues.append(f"{record.archive_count} archives")
        if record.duplicate_archive_names:
            issues.append(f"duplicate archive filenames: {', '.join(record.duplicate_archive_names)}")
        if issues:
            found = True
            print(f"- {record.name}: {'; '.join(issues)}")
    if not found:
        print("No obvious duplicates were detected.")


def interactive_menu(remote: str, records: list[WorkRecord], output_dir: Path) -> None:
    while True:
        print(
            "\nR2 Work Auditor\n"
            "===============\n"
            "1. List all works\n"
            "2. Inspect a work\n"
            "3. Show possible duplicates\n"
            "4. Generate a work slice\n"
            "5. Export JSON, JSONL, and CSV\n"
            "6. Search work names\n"
            "7. Quit\n"
        )
        answer = input("Choose: ").strip()

        if answer == "1":
            print_work_table(records)

        elif answer == "2":
            query = input("Work name or part of name: ").strip()
            record = find_record(records, query)
            if record:
                print_record(record)
            else:
                print("No unique matching work found.")

        elif answer == "3":
            print_duplicates(records)

        elif answer == "4":
            query = input("Work name or part of name: ").strip()
            record = find_record(records, query)
            if not record:
                print("No unique matching work found.")
                continue
            count_answer = input("Preview images [4]: ").strip()
            count = int(count_answer) if count_answer.isdigit() else 4
            count = max(1, min(count, 12))
            slice_dir = generate_slice(remote, record, output_dir, count)
            print(f"\nSlice created:\n{slice_dir}")

        elif answer == "5":
            paths = export_inventory(records, output_dir, remote)
            print("\nExported:")
            for path in paths:
                print(f"- {path}")

        elif answer == "6":
            query = input("Search: ").strip().casefold()
            matches = [record for record in records if query in record.name.casefold()]
            print_work_table(matches)

        elif answer == "7":
            return

        else:
            print("Unknown choice.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit R2 work folders and generate work slices.")
    parser.add_argument("--remote", default=DEFAULT_REMOTE, help="rclone remote containing top-level work folders.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--export", action="store_true", help="Export inventory and exit unless --interactive is also given.")
    parser.add_argument("--slice", metavar="WORK", help="Generate a slice for one work.")
    parser.add_argument("--preview-count", type=int, default=4)
    parser.add_argument("--list", action="store_true", help="List works and exit.")
    parser.add_argument("--duplicates", action="store_true", help="Show possible duplicates and exit.")
    parser.add_argument("--interactive", action="store_true", help="Open the interactive interface after requested actions.")
    parser.add_argument("--deep", action="store_true", help="Enumerate every object and hash it. Slow; intended for intensive audits.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir = args.output_dir.expanduser().resolve()

    if args.deep:
        print(f"Deep-scanning every R2 object: {args.remote}")
        objects = list_remote_objects(args.remote)
        records = build_inventory(args.remote, objects)
        print(f"Found {len(objects)} objects across {len(records)} work folders.")
    else:
        print(f"Lightweight scan of direct work directories: {args.remote}")
        work_names = list_work_directories(args.remote)
        objects = list_lightweight_objects(args.remote, work_names)
        records = build_inventory(args.remote, objects)
        existing = {record.name for record in records}
        for work_name in work_names:
            if work_name not in existing:
                records.append(WorkRecord(name=work_name, remote_path=remote_join(args.remote, work_name)))
        records.sort(key=lambda record: natural_key(record.name))
        load_item_manifests(args.remote, records)
        print(f"Found {len(work_names)} direct work folders and {len(objects)} structural files.")

    performed_action = False

    if args.list:
        print_work_table(records)
        performed_action = True

    if args.duplicates:
        print_duplicates(records)
        performed_action = True

    if args.export:
        paths = export_inventory(records, args.output_dir, args.remote)
        print("\nExported:")
        for path in paths:
            print(f"- {path}")
        performed_action = True

    if args.slice:
        record = find_record(records, args.slice)
        if not record:
            raise SystemExit(f"No unique work matched: {args.slice}")
        slice_dir = generate_slice(
            args.remote,
            record,
            args.output_dir,
            max(1, min(args.preview_count, 12)),
        )
        print(f"\nSlice created:\n{slice_dir}")
        performed_action = True

    if args.interactive or not performed_action:
        interactive_menu(args.remote, records, args.output_dir)


if __name__ == "__main__":
    main()
