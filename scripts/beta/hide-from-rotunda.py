#!/usr/bin/env python3
"""Hide or restore works in the public rotunda without deleting any work data."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Work:
    slug: str
    title: str


def repo_root() -> Path:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        return Path(value).resolve()
    except Exception:
        return Path(__file__).resolve().parent


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def catalog_works(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("works"), list):
        return [item for item in data["works"] if isinstance(item, dict)]
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    return []


def discover_works(data_dir: Path, rotunda: dict[str, Any]) -> list[Work]:
    by_slug: dict[str, str] = {}
    for item in catalog_works(rotunda):
        slug = item.get("slug")
        if isinstance(slug, str) and slug:
            by_slug[slug] = str(
                item.get("display") or item.get("title") or slug.replace("_", " ")
            )

    fetch_path = data_dir / "fetch.json"
    if fetch_path.exists():
        for item in catalog_works(load_json(fetch_path)):
            slug = item.get("slug")
            if isinstance(slug, str) and slug:
                by_slug.setdefault(
                    slug,
                    str(item.get("display") or item.get("title") or slug.replace("_", " ")),
                )

    return [
        Work(slug, title)
        for slug, title in sorted(by_slug.items(), key=lambda pair: pair[1].casefold())
    ]


def get_omit_works(rotunda: dict[str, Any]) -> list[str]:
    public = rotunda.get("public_rotunda")
    if not isinstance(public, dict):
        raise SystemExit("rotunda.json is missing the public_rotunda object.")
    omitted = public.get("omit_works")
    if not isinstance(omitted, list) or not all(isinstance(x, str) for x in omitted):
        raise SystemExit("public_rotunda.omit_works must be an array of work slugs.")
    return omitted


def choose_numbered(works: list[Work], hidden: set[str], action: str) -> list[str]:
    candidates = [
        work for work in works
        if (work.slug in hidden) == (action == "show")
    ]
    if not candidates:
        print(f"No works are available to {action}.")
        return []
    for index, work in enumerate(candidates, 1):
        state = "HIDDEN" if work.slug in hidden else "shown"
        print(f"{index}. [{state}] {work.title} ({work.slug})")
    raw = input(
        f"Enter numbers to {action}, separated by spaces, or blank to quit: "
    ).split()
    chosen: list[str] = []
    for value in raw:
        if value.isdigit() and 1 <= int(value) <= len(candidates):
            chosen.append(candidates[int(value) - 1].slug)
    return chosen


def choose_interactive(
    works: list[Work], hidden: set[str], action: str
) -> list[str]:
    try:
        import curses
    except ImportError:
        return choose_numbered(works, hidden, action)

    candidates = [
        work for work in works
        if (work.slug in hidden) == (action == "show")
    ]
    if not candidates:
        print(f"No works are available to {action}.")
        return []

    selected: set[str] = set()
    query = ""
    position = 0

    def run(screen):
        nonlocal query, position
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        screen.keypad(True)

        while True:
            needle = query.casefold()
            filtered = [
                work
                for work in candidates
                if needle in f"{work.title} {work.slug}".casefold()
            ]
            position = min(position, max(0, len(filtered) - 1))
            screen.erase()
            height, width = screen.getmaxyx()
            visible_rows = max(1, height - 3)
            top = max(0, min(position - visible_rows + 1, len(filtered) - visible_rows))

            header = (
                f"Rotunda {action} — ↑/↓ move, Space select, / search, "
                "Enter review, q quit"
            )
            screen.addnstr(0, 0, header, max(0, width - 1))
            screen.addnstr(
                1,
                0,
                f"Search: {query} | Selected: {len(selected)} | Matches: {len(filtered)}",
                max(0, width - 1),
            )
            for row, work in enumerate(filtered[top : top + visible_rows], 2):
                absolute = top + row - 2
                mark = "[x]" if work.slug in selected else "[ ]"
                attr = curses.A_REVERSE if absolute == position else 0
                screen.addnstr(
                    row, 0, f"{mark} {work.title} ({work.slug})",
                    max(0, width - 1), attr
                )
            screen.refresh()
            key = screen.getch()

            if key in (ord("q"), 27):
                return []
            if key in (curses.KEY_DOWN, ord("j")) and filtered:
                position = min(len(filtered) - 1, position + 1)
            elif key in (curses.KEY_UP, ord("k")) and filtered:
                position = max(0, position - 1)
            elif key == ord(" ") and filtered:
                selected.symmetric_difference_update([filtered[position].slug])
            elif key in (10, 13, curses.KEY_ENTER):
                return sorted(selected)
            elif key == ord("/"):
                curses.echo()
                try:
                    curses.curs_set(1)
                    screen.move(1, 0)
                    screen.clrtoeol()
                    screen.addstr(1, 0, "Search: ")
                    query = screen.getstr(
                        1, 8, max(1, min(200, width - 9))
                    ).decode("utf-8", errors="replace")
                finally:
                    curses.noecho()
                    try:
                        curses.curs_set(0)
                    except curses.error:
                        pass
                position = 0

    return curses.wrapper(run)


def atomic_write(path: Path, data: Any) -> None:
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", nargs="?", choices=("hide", "show", "list"), default="hide"
    )
    parser.add_argument("--slug", action="append", default=[])
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--data-dir", default="src/data")
    args = parser.parse_args(argv)

    root = repo_root()
    data_dir = (root / args.data_dir).resolve()
    rotunda_path = data_dir / "rotunda.json"
    if not rotunda_path.exists():
        raise SystemExit(f"Not found: {rotunda_path}")

    rotunda = load_json(rotunda_path)
    if not isinstance(rotunda, dict):
        raise SystemExit("rotunda.json must contain a JSON object.")
    omitted_list = get_omit_works(rotunda)
    hidden = set(omitted_list)
    works = discover_works(data_dir, rotunda)
    known = {work.slug for work in works}

    if args.action == "list":
        titles = {work.slug: work.title for work in works}
        if not hidden:
            print("No works are hidden from the public rotunda.")
        for slug in omitted_list:
            print(f"{slug}\t{titles.get(slug, '(not present in current catalogs)')}")
        return 0

    slugs = args.slug or choose_interactive(works, hidden, args.action)
    if not slugs:
        print("No works selected; nothing changed.")
        return 0

    unknown = sorted(set(slugs) - known)
    if unknown:
        raise SystemExit(f"Unknown slug(s): {', '.join(unknown)}")

    if args.action == "hide":
        changes = [slug for slug in slugs if slug not in hidden]
        result = omitted_list + changes
    else:
        changes = [slug for slug in slugs if slug in hidden]
        remove = set(changes)
        result = [slug for slug in omitted_list if slug not in remove]

    if not changes:
        print(f"Selected works are already in the requested {args.action} state.")
        return 0

    titles = {work.slug: work.title for work in works}
    print(f"Works to {args.action}:")
    for slug in changes:
        print(f"- {titles[slug]} ({slug})")
    print("Only src/data/rotunda.json → public_rotunda.omit_works will change.")

    if args.dry_run:
        print("Dry run only; nothing changed.")
        return 0
    if not (args.yes and args.slug):
        expected = f"{args.action.upper()} {len(changes)}"
        if input(f'Type exactly "{expected}" to continue: ') != expected:
            print("Confirmation failed; nothing changed.")
            return 1

    backup_dir = (
        root / ".rotunda-hide-backups" /
        datetime.now().strftime("%Y-%m-%dT%H%M%S-%f")
    )
    backup_dir.mkdir(parents=True, exist_ok=False)
    shutil.copy2(rotunda_path, backup_dir / "rotunda.json")

    rotunda["public_rotunda"]["omit_works"] = result
    atomic_write(rotunda_path, rotunda)

    verified = load_json(rotunda_path)
    if get_omit_works(verified) != result:
        shutil.copy2(backup_dir / "rotunda.json", rotunda_path)
        raise SystemExit("Validation failed; the original rotunda.json was restored.")

    print(f"Successfully updated {len(changes)} work(s).")
    print(f"Backup: {backup_dir.relative_to(root)}")
    print(
        'Suggested Git commands:\n'
        'git diff -- src/data/rotunda.json\n'
        'git add src/data/rotunda.json scripts/hide-from-rotunda.py\n'
        'git commit -m "Update public rotunda exclusions"\n'
        'git push origin main'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
