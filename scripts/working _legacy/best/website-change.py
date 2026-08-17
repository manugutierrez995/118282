#!/usr/bin/env python3
"""
website-change.py

One-shot CDN/domain migration helper for the 118282 website repo.

Run this script from anywhere after placing it in the repository root:

    python website-change.py

It will:
  1. Update the old CDN URL in root-level Python scripts such as upload.py
     and curator.py / curator(1).py when present.
  2. Update existing JSON website/catalog data under src/data and public/data.
  3. Make a timestamped backup of every file it actually changes.
  4. Leave everything else alone.

Preview without changing anything:

    python website-change.py --dry-run

Override the old/new CDN values if needed:

    python website-change.py \
        --old https://cdn.564578634.xyz \
        --new https://cdn.118282.xyz
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path


DEFAULT_OLD = "https://cdn.564578634.xyz"
DEFAULT_NEW = "https://cdn.118282.xyz"

ROOT_SCRIPT_NAMES = (
    "upload.py",
    "curator.py",
    "curator(1).py",
)

DATA_DIRS = (
    Path("src/data"),
    Path("public/data"),
)

TEXT_EXTENSIONS = {
    ".json",
    ".py",
}


def candidate_files(root: Path) -> list[Path]:
    """Return only the files this migration is intended to touch."""
    found: set[Path] = set()

    # Root-level helper scripts.
    for name in ROOT_SCRIPT_NAMES:
        path = root / name
        if path.is_file():
            found.add(path)

    # Existing website/catalog JSON data.
    for rel_dir in DATA_DIRS:
        directory = root / rel_dir
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
                found.add(path)

    return sorted(found)


def relative_or_name(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return Path(path.name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migrate the website CDN URL in root scripts and existing catalog data."
    )
    parser.add_argument(
        "--old",
        default=DEFAULT_OLD,
        help=f"Old CDN origin/base to replace (default: {DEFAULT_OLD})",
    )
    parser.add_argument(
        "--new",
        default=DEFAULT_NEW,
        help=f"New CDN origin/base to use (default: {DEFAULT_NEW})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing anything.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    old = args.old.rstrip("/")
    new = args.new.rstrip("/")

    if not old or not new:
        print("ERROR: --old and --new must not be empty.", file=sys.stderr)
        return 2

    if old == new:
        print("Nothing to do: old and new CDN values are identical.")
        return 0

    files = candidate_files(root)
    if not files:
        print("No target files were found.")
        print(f"Expected the script to live in the repository root: {root}")
        return 1

    changes: list[tuple[Path, str, str, int]] = []

    for path in files:
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        count = original.count(old)
        if count == 0:
            continue

        updated = original.replace(old, new)
        changes.append((path, original, updated, count))

    if not changes:
        print(f'No occurrences of "{old}" were found.')
        print("Your repo may already be migrated.")
        return 0

    print(f"CDN migration: {old}  ->  {new}")
    print()

    for path, _, _, count in changes:
        rel = relative_or_name(path, root)
        print(f"{'[DRY] ' if args.dry_run else ''}{rel}  ({count} replacement{'s' if count != 1 else ''})")

    if args.dry_run:
        print()
        print(f"Dry run complete. {len(changes)} file(s) would change.")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = root / ".website-change-backup" / stamp

    # Back up first, then write.
    for path, original, _, _ in changes:
        rel = relative_or_name(path, root)
        backup = backup_root / rel
        backup.parent.mkdir(parents=True, exist_ok=True)

        # copy2 preserves timestamps/metadata better than writing the backup manually.
        shutil.copy2(path, backup)

    try:
        for path, _, updated, _ in changes:
            path.write_text(updated, encoding="utf-8")
    except Exception:
        print("\nERROR while writing. Restoring files from backup...", file=sys.stderr)
        for path, _, _, _ in changes:
            rel = relative_or_name(path, root)
            backup = backup_root / rel
            if backup.exists():
                shutil.copy2(backup, path)
        raise

    print()
    print(f"Done. Changed {len(changes)} file(s).")
    print(f"Backup: {backup_root}")
    print()
    print("New URLs keep all existing paths after the domain, for example:")
    print("  https://cdn.118282.xyz/works/<work>/chapter_1/thumb.webp")
    print()
    print("Recommended next check:")
    print(f'  grep -R --line-number --fixed-strings "{old}" upload.py curator.py "curator(1).py" src/data public/data 2>/dev/null || true')

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
