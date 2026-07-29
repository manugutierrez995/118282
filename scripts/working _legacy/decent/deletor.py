#!/usr/bin/env python3
"""Safely remove AnimePlex work metadata from local JSON catalogs."""
from __future__ import annotations

import argparse, copy, json, os, shutil, subprocess, sys, tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

@dataclass(frozen=True)
class Work:
    slug: str
    title: str
    source: str = "e"
    work_id: str | None = None
    manifest: str | None = None
    manifest_path: Path | None = None
    tags: tuple[str, ...] = ()
    canonical_paths: tuple[str, ...] = ()

@dataclass
class JsonFile:
    path: Path
    data: Any
    indent: int | None = 2

@dataclass
class Plan:
    works: list[Work]
    remaining: int
    json_updates: dict[Path, Any] = field(default_factory=dict)
    delete_files: list[Path] = field(default_factory=list)
    regenerated: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    backup_dir: Path | None = None


def repo_root() -> Path:
    try:
        return Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()).resolve()
    except Exception:
        return Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f: return json.load(f)


def parse_json_files(data_dir: Path) -> dict[Path, JsonFile]:
    out = {}
    for path in sorted(data_dir.rglob("*.json")):
        text = path.read_text(encoding="utf-8")
        indent = 4 if "\n    \"" in text else 2
        out[path] = JsonFile(path, json.loads(text), indent)
    return out


def catalog_works(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, dict) and isinstance(data.get("works"), list): return [x for x in data["works"] if isinstance(x, dict)]
    if isinstance(data, list): return [x for x in data if isinstance(x, dict)]
    return []


def display_from_slug(slug: str) -> str:
    return slug.replace("_", " ").replace("-", " ").strip() or slug


def discover_works(data_dir: Path) -> list[Work]:
    by_slug: dict[str, dict[str, Any]] = {}
    for name in ["fetch.json", "rotunda.json"]:
        p = data_dir / name
        if p.exists():
            for item in catalog_works(load_json(p)):
                slug = item.get("slug") or item.get("work") or item.get("work_slug")
                if isinstance(slug, str) and slug:
                    by_slug.setdefault(slug, {}).update(item)
    for p in sorted((data_dir / "works").glob("*.json")):
        item = load_json(p)
        if not isinstance(item, dict): continue
        slug = item.get("slug") if isinstance(item.get("slug"), str) else p.stem
        entry = by_slug.setdefault(slug, {})
        entry.update({k: v for k, v in item.items() if k not in entry or k in {"chapters", "tags"}})
        entry.setdefault("manifest", f"works/{p.name}")
    works = []
    for slug, item in sorted(by_slug.items(), key=lambda kv: (str(kv[1].get("display") or kv[0]).lower())):
        manifest = item.get("manifest") if isinstance(item.get("manifest"), str) else f"works/{slug}.json"
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        wid = item.get("id") if isinstance(item.get("id"), (str, int)) else item.get("work_id")
        paths = {slug, f"/reader?source={quote(str(item.get('source','e')), safe='')}&work={quote(slug, safe='')}", f"works/{slug}.json", manifest}
        works.append(Work(slug=slug, title=str(item.get("display") or item.get("title") or item.get("name") or display_from_slug(slug)), source=str(item.get("source") or "e"), work_id=str(wid) if wid is not None else None, manifest=manifest, manifest_path=(data_dir / manifest).resolve(), tags=tuple(map(str,tags)), canonical_paths=tuple(paths)))
    return works


def is_work_entry(obj: Any, selected: set[str]) -> bool:
    return isinstance(obj, dict) and (
        obj.get("slug") in selected or obj.get("work") in selected or obj.get("work_slug") in selected
    )


def mutate_catalog(data: Any, selected: set[str]) -> tuple[Any, bool]:
    new = copy.deepcopy(data)
    changed = False
    if isinstance(new, dict) and isinstance(new.get("works"), list):
        before = len(new["works"]); new["works"] = [x for x in new["works"] if not is_work_entry(x, selected)]; changed = len(new["works"]) != before
    elif isinstance(new, list):
        before = len(new); new = [x for x in new if not is_work_entry(x, selected)]; changed = len(new) != before
    return new, changed


def mutate_search(data: Any, selected: set[str]) -> tuple[Any, bool]:
    new = copy.deepcopy(data)
    if isinstance(new, dict) and isinstance(new.get("entries"), list):
        before = len(new["entries"]); new["entries"] = [x for x in new["entries"] if not is_work_entry(x, selected)]
        return new, len(new["entries"]) != before
    return new, False


def find_ambiguous_references(path: Path, data: Any, works: list[Work]) -> list[str]:
    # Only report text/title matches in non-authoritative files; do not mutate them.
    text = json.dumps(data, ensure_ascii=False)
    warnings=[]
    for w in works:
        if w.title and w.title in text and path.name not in {"fetch.json","rotunda.json","search.index.json",f"{w.slug}.json"}:
            warnings.append(f"Ambiguous title reference left untouched in {path}: {w.title}")
    return warnings


def build_plan(data_dir: Path, selected_slugs: list[str]) -> Plan:
    files = parse_json_files(data_dir)
    works_all = discover_works(data_dir)
    selected_set = set(selected_slugs)
    selected = [w for w in works_all if w.slug in selected_set]
    missing = selected_set - {w.slug for w in selected}
    if missing: raise SystemExit(f"Unknown slug(s): {', '.join(sorted(missing))}")
    plan = Plan(selected, len(works_all)-len(selected))
    for path, jf in files.items():
        rel = path.relative_to(data_dir).as_posix()
        changed = False; new = jf.data
        if rel in {"fetch.json", "rotunda.json"}:
            new, changed = mutate_catalog(jf.data, selected_set)
        elif rel == "tags.json":
            new = copy.deepcopy(jf.data)
            if isinstance(new, dict) and isinstance(new.get("works"), dict):
                before = set(new["works"])
                for slug in selected_set: new["works"].pop(slug, None)
                changed = set(new["works"]) != before
        elif rel == "search.index.json":
            new, changed = mutate_search(jf.data, selected_set)
        else:
            plan.warnings.extend(find_ambiguous_references(path, jf.data, selected))
        if changed: plan.json_updates[path] = new
    for w in selected:
        p = (data_dir / (w.manifest or f"works/{w.slug}.json")).resolve()
        if p.exists() and data_dir in p.parents: plan.delete_files.append(p)
    if data_dir / "search.index.json" in files: plan.regenerated.append(data_dir / "search.index.json")
    public = repo_root() / "public" / "data" / "search.index.json"
    if public.exists(): plan.regenerated.append(public)
    return plan


def print_plan(plan: Plan, root: Path) -> None:
    print("Deletion plan")
    print(f"Selected works: {len(plan.works)}; remaining works: {plan.remaining}")
    for w in plan.works:
        print(f"- {w.title} | slug={w.slug} | id={w.work_id or '-'} | manifest={w.manifest or '-'}")
    print("JSON files that will change:")
    for p in sorted(plan.json_updates): print(f"- {p.relative_to(root)}")
    print("Manifest files that will be deleted:")
    for p in sorted(plan.delete_files): print(f"- {p.relative_to(root)}")
    if plan.regenerated:
        print("Regenerated files:"); [print(f"- {p.relative_to(root)}") for p in plan.regenerated if p.exists() or p.parent.exists()]
    for w in plan.warnings: print(f"WARNING: {w}")


def backup_paths(root: Path, paths: list[Path]) -> Path:
    bdir = root / ".deletor-backups" / datetime.now().strftime("%Y-%m-%dT%H%M%S")
    for p in paths:
        if p.exists():
            dest = bdir / p.resolve().relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, dest)
    return bdir


def atomic_write(path: Path, data: Any, indent: int|None=4) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=indent); f.write("\n"); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True); raise


def restore(root: Path, backup: Path, paths: list[Path]) -> None:
    for p in paths:
        src = backup / p.resolve().relative_to(root)
        if src.exists():
            p.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, p)
        elif p.exists(): p.unlink()


def regenerate_search(root: Path, data_dir: Path) -> list[Path]:
    script = root / "scripts" / "generate_search.py"
    out = data_dir / "search.index.json"; public = root / "public" / "data" / "search.index.json"
    cmd = [sys.executable, str(script), "--fetch", str(data_dir/"fetch.json"), "--storage", str(data_dir/"storage.json"), "--out", str(out)]
    if public.exists(): cmd += ["--public-out", str(public)]
    subprocess.check_call(cmd, cwd=root)
    return [p for p in [out, public] if p.exists()]


def tags_catalog_has_slug(data: Any, slug: str) -> bool:
    return isinstance(data, dict) and isinstance(data.get("works"), dict) and slug in data["works"]


def validate(data_dir: Path, selected: list[Work]) -> None:
    files = parse_json_files(data_dir)
    fetch = files.get(data_dir/"fetch.json")
    if fetch:
        for item in catalog_works(fetch.data):
            m = item.get("manifest")
            if isinstance(m, str) and not (data_dir/m).exists(): raise ValueError(f"fetch manifest missing: {m}")
    for slug in {w.slug for w in selected}:
        for rel in ["fetch.json", "rotunda.json", "search.index.json"]:
            jf = files.get(data_dir/rel)
            if jf and any(is_work_entry(x, {slug}) for x in (jf.data.get("entries", []) if rel.startswith("search") and isinstance(jf.data, dict) else catalog_works(jf.data))):
                raise ValueError(f"Deleted slug remains in {rel}: {slug}")
        tags = files.get(data_dir/"tags.json")
        if tags and tags_catalog_has_slug(tags.data, slug):
            raise ValueError(f"Deleted slug remains in tags.json: {slug}")


def apply_plan(root: Path, data_dir: Path, plan: Plan) -> None:
    all_paths = sorted(set(plan.json_updates) | set(plan.delete_files) | set(plan.regenerated))
    backup = backup_paths(root, all_paths); plan.backup_dir = backup
    try:
        # Validate all affected JSON before mutation.
        for p in set(plan.json_updates) | {x for x in plan.regenerated if x.exists()}: load_json(p)
        original_files = parse_json_files(data_dir)
        for p, data in plan.json_updates.items(): atomic_write(p, data, original_files[p].indent)
        for p in plan.delete_files: p.unlink(missing_ok=True)
        plan.regenerated = regenerate_search(root, data_dir)
        validate(data_dir, plan.works)
    except BaseException:
        restore(root, backup, all_paths)
        raise


def choose_interactive(works: list[Work]) -> list[str]:
    try:
        import curses
    except Exception:
        return choose_numbered(works)

    selected: set[str] = set()
    query = ""
    pos = 0

    def run(stdscr):
        nonlocal query, pos, selected

        try:
            curses.curs_set(0)
        except curses.error:
            pass

        stdscr.keypad(True)

        try:
            curses.mousemask(curses.ALL_MOUSE_EVENTS)
        except curses.error:
            pass

        def draw(row: int, col: int, value: str, width: int, attr=0):
            if row < 0 or width <= 0:
                return
            try:
                stdscr.addnstr(row, col, value, width, attr)
            except curses.error:
                pass

        while True:
            needle = query.casefold()
            filtered = [
                work for work in works
                if needle in " ".join([
                    work.slug,
                    work.title,
                    work.work_id or "",
                    *work.tags,
                ]).casefold()
            ]

            if filtered:
                pos = max(0, min(pos, len(filtered) - 1))
            else:
                pos = 0

            stdscr.erase()
            height, width = stdscr.getmaxyx()

            header_rows = 3
            visible_rows = max(1, height - header_rows)

            # Keep the highlighted item inside the visible viewport.
            top = max(0, pos - visible_rows + 1)
            top = min(top, max(0, len(filtered) - visible_rows))
            visible = filtered[top:top + visible_rows]

            draw(
                0, 0,
                "AnimePlex deletor — ↑/↓ move, Space toggle, PgUp/PgDn, "
                "Home/End, / search, a all, n none, Enter review, q quit",
                max(0, width - 1),
            )

            if filtered:
                status = (
                    f"Search: {query} | Selected: {len(selected)} | "
                    f"Item {pos + 1}/{len(filtered)} | "
                    f"Showing {top + 1}-{top + len(visible)}"
                )
            else:
                status = (
                    f"Search: {query} | Selected: {len(selected)} | "
                    "No matching works"
                )

            draw(1, 0, status, max(0, width - 1))

            for row, item in enumerate(visible):
                absolute_index = top + row
                mark = "[x] DELETE" if item.slug in selected else "[ ] Keep  "
                line = f"{mark} {item.title} ({item.slug})"
                attr = curses.A_REVERSE if absolute_index == pos else 0
                draw(row + 2, 0, line, max(0, width - 1), attr)

            stdscr.refresh()
            ch = stdscr.getch()

            if ch in (ord("q"), 27):
                return []

            if ch in (curses.KEY_DOWN, ord("j")):
                if filtered:
                    pos = min(len(filtered) - 1, pos + 1)

            elif ch in (curses.KEY_UP, ord("k")):
                if filtered:
                    pos = max(0, pos - 1)

            elif ch == curses.KEY_NPAGE:
                if filtered:
                    pos = min(len(filtered) - 1, pos + visible_rows)

            elif ch == curses.KEY_PPAGE:
                if filtered:
                    pos = max(0, pos - visible_rows)

            elif ch == curses.KEY_HOME:
                pos = 0

            elif ch == curses.KEY_END:
                if filtered:
                    pos = len(filtered) - 1

            elif ch == curses.KEY_MOUSE:
                try:
                    _, _, _, _, button_state = curses.getmouse()

                    if button_state & getattr(curses, "BUTTON4_PRESSED", 0):
                        pos = max(0, pos - 3)

                    if button_state & getattr(curses, "BUTTON5_PRESSED", 0):
                        if filtered:
                            pos = min(len(filtered) - 1, pos + 3)
                except curses.error:
                    pass

            elif ch == ord(" ") and filtered:
                selected.symmetric_difference_update([filtered[pos].slug])

            elif ch == ord("a"):
                selected.update(work.slug for work in filtered)

            elif ch == ord("n"):
                selected.clear()

            elif ch in (10, 13, curses.KEY_ENTER):
                return list(selected)

            elif ch == ord("/"):
                curses.echo()
                try:
                    curses.curs_set(1)
                except curses.error:
                    pass

                prompt = "Search: "
                draw(1, 0, " " * max(0, width - 1), max(0, width - 1))
                draw(1, 0, prompt, max(0, width - 1))
                stdscr.refresh()

                maximum = max(1, min(200, width - len(prompt) - 1))

                try:
                    query = stdscr.getstr(
                        1, len(prompt), maximum
                    ).decode("utf-8", errors="replace")
                except curses.error:
                    query = ""

                curses.noecho()

                try:
                    curses.curs_set(0)
                except curses.error:
                    pass

                pos = 0

    return curses.wrapper(run)


def choose_numbered(works: list[Work]) -> list[str]:
    for i,w in enumerate(works,1): print(f"{i}. [ ] Keep {w.title} ({w.slug})")
    raw=input("Enter numbers to delete separated by spaces, or blank to quit: ").split()
    return [works[int(x)-1].slug for x in raw if x.isdigit() and 1<=int(x)<=len(works)]


def main(argv=None) -> int:
    root=repo_root(); ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--yes", action="store_true")
    ap.add_argument("--data-dir", default="src/data"); ap.add_argument("--slug", action="append", default=[]); ap.add_argument("--list", action="store_true")
    args=ap.parse_args(argv); data_dir=(root/args.data_dir).resolve()
    works=discover_works(data_dir)
    if args.list:
        [print(f"{w.slug}\t{w.title}\t{w.manifest or ''}") for w in works]; return 0
    slugs=args.slug or choose_interactive(works)
    if not slugs: print("No works selected; nothing changed."); return 0
    plan=build_plan(data_dir, slugs); print_plan(plan, root)
    if args.dry_run: print("Dry run only; nothing changed."); return 0
    if not (args.yes and args.slug):
        if input(f'Type exactly "DELETE {len(plan.works)}" to continue: ') != f"DELETE {len(plan.works)}":
            print("Confirmation failed; nothing changed."); return 1
    apply_plan(root, data_dir, plan)
    print("Deleted works:"); [print(f"- {w.title} ({w.slug})") for w in plan.works]
    print("Modified files:"); [print(f"- {p.relative_to(root)}") for p in sorted(plan.json_updates)]
    print("Deleted manifest files:"); [print(f"- {p.relative_to(root)}") for p in sorted(plan.delete_files)]
    print("Regenerated files:"); [print(f"- {p.relative_to(root)}") for p in sorted(plan.regenerated)]
    print(f"Backup location: {plan.backup_dir.relative_to(root) if plan.backup_dir else '-'}")
    for w in plan.warnings: print(f"WARNING: {w}")
    print("Suggested Git commands:\ngit diff -- src/data scripts/deletor.py\ngit status\ngit add scripts/deletor.py src/data\ngit commit -m \"Delete selected works from catalog\"\ngit push origin main")
    return 0

if __name__ == "__main__": raise SystemExit(main())
