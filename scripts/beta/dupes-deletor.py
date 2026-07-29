#!/usr/bin/env python3
"""Delete AnimePlex catalog metadata identified by ZIPs in a duplicates folder.

Place this file beside scripts/deletor.py, then pass the duplicate directory.
Matching ignores case, punctuation, spaces/underscores, and trailing copy suffixes
such as ``(2)``. Unique matches are applied immediately; ambiguous and unmatched
names are reported and left untouched.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


def load_core():
    """Load deletor.py from beside this file or from the current repo's scripts/."""
    candidates = [
        Path(__file__).resolve().with_name("deletor.py"),
        Path.cwd() / "scripts" / "deletor.py",
    ]
    for candidate in candidates:
        if candidate.is_file():
            spec = importlib.util.spec_from_file_location("animeplex_deletor", candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return module
    raise SystemExit(
        "Cannot find deletor.py. Run this command from the beep-boop repository "
        "or place dupes-deletor.py beside scripts/deletor.py."
    )


core = load_core()


ARCHIVE_SUFFIXES = {".zip", ".cbz", ".rar", ".7z"}
COPY_SUFFIX = re.compile(r"(?:\s*\(\d+\)|\s*-?\s*copy(?:\s*\d+)?)$", re.I)


def archive_name(path: Path) -> str:
    """Return an archive's likely original work name."""
    name = path.name
    # Account for names produced by `mv --backup=numbered`.
    name = re.sub(r"\.~\d+~$", "", name)
    suffix = Path(name).suffix.lower()
    if suffix in ARCHIVE_SUFFIXES:
        name = name[: -len(suffix)]
    return COPY_SUFFIX.sub("", name).strip()


def key(value: str) -> str:
    """Normalize a filename/title/slug for exact, punctuation-insensitive matching."""
    return re.sub(r"[^a-z0-9]+", "", value.casefold())


def aliases(work: core.Work) -> set[str]:
    values = {work.slug, work.title}
    if work.manifest:
        values.add(Path(work.manifest).stem)
    return {key(value) for value in values if value and key(value)}


def match_archives(dupes_dir: Path, works: list[core.Work]):
    index: dict[str, list[core.Work]] = defaultdict(list)
    for work in works:
        for alias in aliases(work):
            if work not in index[alias]:
                index[alias].append(work)

    matched: dict[str, list[Path]] = defaultdict(list)
    unmatched: list[Path] = []
    ambiguous: list[tuple[Path, list[core.Work]]] = []

    archives = sorted(
        path for path in dupes_dir.rglob("*")
        if path.is_file()
        and (
            path.suffix.lower() in ARCHIVE_SUFFIXES
            or re.search(r"\.(?:zip|cbz|rar|7z)\.~\d+~$", path.name, re.I)
        )
    )
    for path in archives:
        candidates = index.get(key(archive_name(path)), [])
        if len(candidates) == 1:
            matched[candidates[0].slug].append(path)
        elif candidates:
            ambiguous.append((path, candidates))
        else:
            unmatched.append(path)
    return archives, matched, unmatched, ambiguous


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dupes_dir", type=Path, help="folder containing duplicate archives")
    parser.add_argument("--data-dir", default="src/data", help="catalog directory relative to repo root")
    parser.add_argument("--dry-run", action="store_true", help="show matches without changing anything")
    parser.add_argument(
        "--delete-r2",
        action="store_true",
        help="also permanently purge each matched work directory from R2 using rclone",
    )
    parser.add_argument(
        "--remote",
        default="animeplex.lol:extended/works",
        help="rclone works root (default: animeplex.lol:extended/works)",
    )
    args = parser.parse_args(argv)

    dupes_dir = args.dupes_dir.expanduser().resolve()
    if not dupes_dir.is_dir():
        parser.error(f"not a directory: {dupes_dir}")

    root = core.repo_root()
    data_dir = (root / args.data_dir).resolve()
    if not (data_dir / "fetch.json").is_file():
        parser.error(f"fetch.json not found beneath: {data_dir}")

    works = core.discover_works(data_dir)
    archives, matched, unmatched, ambiguous = match_archives(dupes_dir, works)

    print(f"Archives examined: {len(archives)}")
    print(f"Uniquely matched works: {len(matched)}")
    for slug, paths in sorted(matched.items()):
        print(f"  DELETE {slug}  <-  {', '.join(path.name for path in paths)}")

    if unmatched:
        print(f"Unmatched archives (left untouched): {len(unmatched)}")
        for path in unmatched:
            print(f"  {path.name}")
    if ambiguous:
        print(f"Ambiguous archives (left untouched): {len(ambiguous)}")
        for path, candidates in ambiguous:
            print(f"  {path.name}: {', '.join(work.slug for work in candidates)}")

    if not matched:
        print("No catalog entries matched; nothing changed.")
        return 0

    plan = core.build_plan(data_dir, sorted(matched))
    core.print_plan(plan, root)
    if args.dry_run:
        if args.delete_r2:
            print("R2 directories that would be purged:")
            for slug in sorted(matched):
                print(f"  {args.remote.rstrip('/')}/{slug}")
        print("Dry run only; nothing changed.")
        return 0

    core.apply_plan(root, data_dir, plan)
    print(f"Deleted {len(plan.works)} works from AnimePlex metadata.")
    print(f"Backup: {plan.backup_dir.relative_to(root) if plan.backup_dir else '-'}")

    r2_failures = []
    if args.delete_r2:
        for slug in sorted(matched):
            target = f"{args.remote.rstrip('/')}/{slug}"
            print(f"Purging R2 directory: {target}")
            result = subprocess.run(["rclone", "purge", target], cwd=root)
            if result.returncode:
                r2_failures.append(target)
        if r2_failures:
            print("ERROR: metadata was deleted, but these R2 purges failed:", file=sys.stderr)
            for target in r2_failures:
                print(f"  {target}", file=sys.stderr)
            print("The local metadata backup can be used for recovery.", file=sys.stderr)
    else:
        print("R2 was not changed (use --delete-r2 to purge matching work directories).")

    print("The duplicate archive files themselves were not deleted.")
    return 1 if r2_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
