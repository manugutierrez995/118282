#!/usr/bin/env python3
"""Generate and preserve public 7-digit work IDs.

Reads src/data/fetch.json and writes src/data/ID.json.

Rules:
- Existing non-empty IDs are preserved exactly.
- Blank/missing IDs receive the next available 7-digit ID.
- Default allocation starts at 1199999 and decrements by 23.
- Existing IDs are never reused for another work.
- Title/slug/work_url are refreshed from fetch.json each run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

DEFAULT_START_ID = 1_199_999
DEFAULT_STEP = 23
MIN_PUBLIC_ID = 1_000_000
MAX_PUBLIC_ID = 9_999_999

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "src" / "data" / "fetch.json"
DEFAULT_OUTPUT = ROOT / "src" / "data" / "ID.json"


def read_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def public_id(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def validate_public_id(value: str, *, context: str) -> None:
    if not value:
        return
    if len(value) != 7 or not value.isdigit():
        raise ValueError(f"{context}: ID must be exactly 7 digits, got {value!r}")
    number = int(value)
    if not MIN_PUBLIC_ID <= number <= MAX_PUBLIC_ID:
        raise ValueError(
            f"{context}: ID must be between {MIN_PUBLIC_ID} and {MAX_PUBLIC_ID}"
        )


def work_url(slug: str) -> str:
    return "/" + quote(slug, safe="-._~")


def next_id(candidate: int, step: int, used: set[str]) -> tuple[str, int]:
    while candidate >= MIN_PUBLIC_ID:
        text = f"{candidate:07d}"
        if text not in used:
            return text, candidate - step
        candidate -= step
    raise RuntimeError(
        "Ran out of 7-digit IDs. Change settings.start_id/step or manually assign IDs."
    )


def build_mapping(catalog: dict, existing: dict) -> dict:
    works = catalog.get("works") or []
    if not isinstance(works, list):
        raise ValueError("fetch.json: 'works' must be a list")

    settings = dict(existing.get("settings") or {})
    start_id = int(settings.get("start_id", DEFAULT_START_ID))
    step = int(settings.get("step", DEFAULT_STEP))

    if not MIN_PUBLIC_ID <= start_id <= MAX_PUBLIC_ID:
        raise ValueError("settings.start_id must be a 7-digit integer")
    if step <= 0:
        raise ValueError("settings.step must be greater than zero")

    existing_works = existing.get("works") or []
    if not isinstance(existing_works, list):
        raise ValueError("ID.json: 'works' must be a list")

    by_slug: dict[str, dict] = {}
    used: set[str] = set()
    owner_by_id: dict[str, str] = {}

    for item in existing_works:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        if slug in by_slug:
            raise ValueError(f"ID.json: duplicate slug {slug!r}")
        by_slug[slug] = item

        pid = public_id(item.get("id"))
        validate_public_id(pid, context=f"ID.json work {slug!r}")
        if pid:
            previous = owner_by_id.get(pid)
            if previous and previous != slug:
                raise ValueError(
                    f"ID.json: duplicate ID {pid} used by {previous!r} and {slug!r}"
                )
            owner_by_id[pid] = slug
            used.add(pid)

    seen_catalog_slugs: set[str] = set()
    result_works: list[dict] = []
    candidate = start_id
    created = 0
    preserved = 0

    for index, work in enumerate(works):
        if not isinstance(work, dict):
            raise ValueError(f"fetch.json works[{index}] must be an object")

        slug = str(work.get("slug") or "").strip()
        if not slug:
            raise ValueError(f"fetch.json works[{index}] has no slug")
        if slug in seen_catalog_slugs:
            raise ValueError(f"fetch.json: duplicate slug {slug!r}")
        seen_catalog_slugs.add(slug)

        old = dict(by_slug.get(slug) or {})
        pid = public_id(old.get("id"))
        if pid:
            preserved += 1
        else:
            pid, candidate = next_id(candidate, step, used)
            used.add(pid)
            owner_by_id[pid] = slug
            created += 1

        entry = old
        entry.pop("active", None)
        entry.update(
            {
                "id": pid,
                "title": str(work.get("display") or slug),
                "slug": slug,
                "work_url": work_url(slug),
            }
        )
        result_works.append(entry)

    # Keep mappings for works that disappeared from the current catalog so their
    # public IDs are not silently recycled. They naturally fail catalog lookup
    # until the work returns.
    for slug, old in by_slug.items():
        if slug in seen_catalog_slugs:
            continue
        retired = dict(old)
        retired["active"] = False
        result_works.append(retired)

    output = {
        "version": int(existing.get("version", 1)),
        "settings": {
            **settings,
            "start_id": start_id,
            "step": step,
        },
        "works": result_works,
    }

    print(
        f"works={len(works)} preserved={preserved} assigned={created} "
        f"retired={len(result_works) - len(works)}",
        file=sys.stderr,
    )
    return output


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"

    fd, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate stable 7-digit public IDs for every catalog work."
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated JSON instead of writing ID.json.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog = read_json(args.catalog, None)
    if catalog is None:
        raise FileNotFoundError(f"Catalog not found: {args.catalog}")

    existing = read_json(
        args.output,
        {
            "version": 1,
            "settings": {
                "start_id": DEFAULT_START_ID,
                "step": DEFAULT_STEP,
            },
            "works": [],
        },
    )

    generated = build_mapping(catalog, existing)

    if args.dry_run:
        json.dump(generated, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        atomic_write_json(args.output, generated)
        print(f"Wrote {args.output}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
