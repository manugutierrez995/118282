#!/usr/bin/env python3

from __future__ import annotations

import json
import re
import shutil

try:
    import readline
except ImportError:
    readline = None
from datetime import datetime
from pathlib import Path


URL_RE = re.compile(r'https?://[^\s"\'<>]+')

STORAGE_LOCATIONS = (
    "src/data/storage.json",
    "public/data/storage.json",
    "storage.json",
)

SKIP_DIRS = {
    ".git",
    "node_modules",
    ".website-change-backup",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
}

TEXT_EXTENSIONS = {
    ".json", ".py", ".js", ".mjs", ".cjs",
    ".ts", ".tsx", ".jsx",
    ".html", ".css", ".md", ".txt",
    ".toml", ".yaml", ".yml", ".env",
    ".sh", ".bash", ".zsh",
}


def find_storage(root: Path) -> Path | None:
    for rel in STORAGE_LOCATIONS:
        path = root / rel
        if path.is_file():
            return path

    matches = [
        p for p in root.rglob("storage.json")
        if p.is_file()
        and not any(part in SKIP_DIRS for part in p.relative_to(root).parts)
    ]

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    print("\nMultiple storage.json files found:\n")

    for i, path in enumerate(matches, 1):
        print(f"  {i}. {path.relative_to(root)}")

    while True:
        choice = input("\nChoose one: ").strip()

        if choice.isdigit() and 1 <= int(choice) <= len(matches):
            return matches[int(choice) - 1]

        print("Enter one of the numbers shown.")


def urls_in_line(line: str) -> list[str]:
    found = []

    for match in URL_RE.finditer(line):
        url = match.group(0).rstrip(".,);]}")

        if url not in found:
            found.append(url)

    return found


def ask_yes_no(question: str) -> bool:
    return input(f"{question} [y/N]: ").strip().lower() in {"y", "yes"}


def backup(root: Path, source: Path, backup_root: Path) -> None:
    destination = backup_root / source.relative_to(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> int:
    root = Path(__file__).resolve().parent

    print()
    print("Website URL Changer")
    print("===================")
    print(f"Repository: {root}")

    storage = find_storage(root)

    if storage is None:
        print("\nERROR: Could not find storage.json")
        return 1

    print(f"Storage: {storage.relative_to(root)}")

    raw = storage.read_text(encoding="utf-8")

    try:
        json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"\nERROR: storage.json is not valid JSON: {exc}")
        return 1

    lines = raw.splitlines()

    choices = {}
    choice_number = 1

    print()
    print("storage.json")
    print("=" * 100)

    for real_line_number, line in enumerate(lines, 1):
        urls = urls_in_line(line)

        if urls:
            choices[choice_number] = {
                "line_number": real_line_number,
                "line": line,
                "urls": urls,
            }

            marker = f"[{choice_number}]"
            choice_number += 1
        else:
            marker = ""

        print(f"{marker:>6} {line}")

    print("=" * 100)

    if not choices:
        print("\nNo URLs were found in storage.json.")
        return 0

    while True:
        selected = input(
            "\nEnter the number beside the URL line you want to change: "
        ).strip()

        if selected.isdigit() and int(selected) in choices:
            selected = int(selected)
            break

        print("Enter one of the numbers shown above.")

    item = choices[selected]

    print()
    print(f"Selected storage.json line {item['line_number']}:")
    print(item["line"])

    print()
    print("Type the exact URL from that line.")
    print("This prevents accidentally changing the wrong address.")

    for url in item["urls"]:
        print(f"  {url}")

    while True:
        old_url = input("\nExact URL: ").strip()

        if old_url in item["urls"]:
            break

        print()
        print("That does NOT exactly match a URL on the selected line.")
        print("Please type one of these exactly:")

        for url in item["urls"]:
            print(f"  {url}")

    print()
    print(f"Confirmed:")
    print(f"  {old_url}")

    new_url = input("\nNew URL: ").strip().rstrip("/")

    if not new_url:
        print("No new URL entered. Nothing changed.")
        return 0

    if not new_url.startswith(("http://", "https://")):
        new_url = "https://" + new_url

    if new_url == old_url.rstrip("/"):
        print("Old and new URLs are the same. Nothing changed.")
        return 0

    print()
    print("Change")
    print("------")
    print(f"OLD: {old_url}")
    print(f"NEW: {new_url}")

    if not ask_yes_no("\nChange this in storage.json?"):
        print("Cancelled.")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = root / ".website-change-backup" / timestamp

    backup(root, storage, backup_root)

    storage_count = raw.count(old_url)
    updated_storage = raw.replace(old_url, new_url)

    storage.write_text(updated_storage, encoding="utf-8")

    print()
    print(f"storage.json updated.")
    print(f"Replacements: {storage_count}")

    print()

    if not ask_yes_no(
        "Would you like to change this same URL everywhere else in the repository?"
    ):
        print()
        print("Done. Only storage.json was changed.")
        print(f"Backup: {backup_root}")
        return 0

    matches = []

    for path in root.rglob("*"):
        if not path.is_file() or path == storage:
            continue

        rel = path.relative_to(root)

        if any(part in SKIP_DIRS for part in rel.parts):
            continue

        if path.suffix.lower() not in TEXT_EXTENSIONS:
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        count = text.count(old_url)

        if count:
            matches.append((path, text, count))

    if not matches:
        print("\nNo other occurrences were found.")
        print(f"Backup: {backup_root}")
        return 0

    print()
    print("Found elsewhere")
    print("===============")

    total = 0

    for path, _, count in matches:
        print(f"{path.relative_to(root)}  ({count})")
        total += count

    print()
    print(f"{len(matches)} files")
    print(f"{total} replacements")

    if not ask_yes_no("\nChange all of these too?"):
        print()
        print("Done. Only storage.json was changed.")
        print(f"Backup: {backup_root}")
        return 0

    for path, text, count in matches:
        backup(root, path, backup_root)
        path.write_text(text.replace(old_url, new_url), encoding="utf-8")

    print()
    print("Done")
    print("====")
    print(f"Changed storage.json plus {len(matches)} other files.")
    print(f"Backup: {backup_root}")
    print()
    print("Review with:")
    print("  git status")
    print("  git diff")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
