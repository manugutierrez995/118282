#!/usr/bin/env python3
"""Delete works or hide/unhide them in the public AnimePlex rotunda."""
from __future__ import annotations

import argparse, copy, hashlib, json, os, re, shutil, subprocess, sys, tempfile, threading, time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

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
    thumb_url: str | None = None

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


# ---------------------------------------------------------------------------
# Durable lazy metadata cache
# ---------------------------------------------------------------------------
#
# This cache deliberately uses ordinary files plus an append-only JSONL journal.
# There is no database service, schema migration, daemon, or vendor dependency.
# The design is intentionally boring: JSON bodies are stored as JSON, thumbnails
# are stored as files, and cache state is reconstructed from a journal that can
# be inspected, copied, repaired, or processed with standard Unix tools.
#
# The journal is append-only because replacing a large index for every small
# update is wasteful and more vulnerable to interruption.  The newest valid
# record for a key wins.  Periodic compaction rewrites only the current state.
# This is the same longevity-oriented pattern used by logs and event journals.

CACHE_FORMAT_VERSION = 1
DEFAULT_REVALIDATE_SECONDS = 300

@dataclass
class CacheRecord:
    key: str
    url: str
    path: str | None = None
    exists: bool = True
    etag: str | None = None
    last_modified: str | None = None
    checked_at: int = 0
    content_type: str | None = None
    sha256: str | None = None

class JsonlCache:
    """Small, transparent cache index backed by an append-only JSONL log.

    The payload itself is not embedded in the index.  Large or frequently read
    objects live in deterministic files addressed by the SHA-256 of their URL.
    This gives filesystem-safe names, avoids slug/Unicode collisions, and makes
    cache lookup independent of catalog naming conventions.
    """

    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.objects = self.root / "objects"
        self.journal = self.root / "index.jsonl"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.state: dict[str, CacheRecord] = {}
        self._load()

    @staticmethod
    def key_for(url: str) -> str:
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _load(self) -> None:
        if not self.journal.exists():
            return
        with self.journal.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    row = json.loads(line)
                    if row.get("version") != CACHE_FORMAT_VERSION:
                        continue
                    rec = CacheRecord(**row["record"])
                    self.state[rec.key] = rec
                except (json.JSONDecodeError, KeyError, TypeError):
                    # A truncated final line after a power loss is harmless.
                    # Earlier complete records remain valid and recoverable.
                    continue

    def _append(self, rec: CacheRecord) -> None:
        self.state[rec.key] = rec
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a", encoding="utf-8") as f:
            json.dump({"version": CACHE_FORMAT_VERSION, "record": rec.__dict__}, f, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

    def object_path(self, url: str, suffix: str = ".bin") -> Path:
        return self.objects / f"{self.key_for(url)}{suffix}"

    def get(self, url: str) -> CacheRecord | None:
        return self.state.get(self.key_for(url))

    def fresh(self, url: str, max_age: int) -> bool:
        rec = self.get(url)
        return bool(rec and int(time.time()) - rec.checked_at < max_age)

    def store_response(self, url: str, body: bytes, headers: Any, suffix: str) -> CacheRecord:
        path = self.object_path(url, suffix)
        fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(body); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True); raise
        rec = CacheRecord(
            key=self.key_for(url), url=url, path=str(path), exists=True,
            etag=headers.get("ETag"), last_modified=headers.get("Last-Modified"),
            checked_at=int(time.time()), content_type=headers.get("Content-Type"),
            sha256=hashlib.sha256(body).hexdigest(),
        )
        self._append(rec)
        return rec

    def mark_checked(self, url: str, exists: bool, prior: CacheRecord | None = None) -> CacheRecord:
        rec = CacheRecord(
            key=self.key_for(url), url=url, path=prior.path if prior else None,
            exists=exists, etag=prior.etag if prior else None,
            last_modified=prior.last_modified if prior else None,
            checked_at=int(time.time()), content_type=prior.content_type if prior else None,
            sha256=prior.sha256 if prior else None,
        )
        self._append(rec)
        return rec

    def compact(self) -> None:
        """Rewrite the journal to one record per URL after atomic backup."""
        payload = [{"version": CACHE_FORMAT_VERSION, "record": r.__dict__} for r in self.state.values()]
        fd, tmp = tempfile.mkstemp(prefix=".index.", suffix=".jsonl.tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for row in sorted(payload, key=lambda x: x["record"]["url"]):
                    json.dump(row, f, ensure_ascii=False); f.write("\n")
                f.flush(); os.fsync(f.fileno())
            os.replace(tmp, self.journal)
        except BaseException:
            Path(tmp).unlink(missing_ok=True); raise

def derived_urls(thumb_url: str) -> dict[str, str]:
    """Derive related objects from the authoritative thumbnail location.

    Keeping one canonical URL in fetch.json prevents duplicated path logic and
    guarantees that metadata follows the same work/chapter prefix as the image.
    """
    base = thumb_url.rsplit("/", 1)[0] + "/"
    return {name: urljoin(base, name) for name in ("revision.json", "details.json", "item.json", "tags.json")}

def conditional_fetch(cache: JsonlCache, url: str, *, suffix: str = ".json", max_age: int = DEFAULT_REVALIDATE_SECONDS, force: bool = False) -> CacheRecord:
    """Fetch an object only when absent, stale, or changed on the CDN.

    ETag is preferred because it is a content validator. Last-Modified is used
    as a portable fallback. A 304 response updates only checked_at; the cached
    body is reused without paying the bandwidth or parsing cost again. A 404 is
    cached as an explicit absence, which is especially useful for tags.json.
    """
    prior = cache.get(url)
    if prior and not force and cache.fresh(url, max_age):
        return prior
    headers = {"User-Agent": "AnimePlex-Catalog/2.0", "Accept": "application/json,*/*"}
    if prior and prior.etag:
        headers["If-None-Match"] = prior.etag
    elif prior and prior.last_modified:
        headers["If-Modified-Since"] = prior.last_modified
    try:
        with urlopen(Request(url, headers=headers), timeout=15) as resp:
            return cache.store_response(url, resp.read(), resp.headers, suffix)
    except HTTPError as e:
        if e.code == 304 and prior:
            return cache.mark_checked(url, prior.exists, prior)
        if e.code == 404:
            return cache.mark_checked(url, False, prior)
        raise

def load_cached_json(rec: CacheRecord) -> Any | None:
    if not rec.exists or not rec.path:
        return None
    with Path(rec.path).open("r", encoding="utf-8") as f:
        return json.load(f)

def lazy_work_metadata(cache: JsonlCache, work: Work, *, max_age: int = DEFAULT_REVALIDATE_SECONDS, force: bool = False) -> dict[str, Any]:
    """Load metadata only after a work is inspected.

    The first touch downloads metadata. Later touches revalidate one tiny
    revision object where available. If revision.json is absent, each metadata
    object is conditionally checked. This preserves compatibility while allowing
    a future uploader to provide a single elegant directory-level change switch.
    """
    if not work.thumb_url:
        return {"details": None, "item": None, "tags": None, "error": "No thumbnail URL"}
    urls = derived_urls(work.thumb_url)
    previous_revision = cache.get(urls["revision.json"])
    rev = conditional_fetch(cache, urls["revision.json"], max_age=max_age, force=force)
    revision_changed = bool(
        force
        or previous_revision is None
        or previous_revision.exists != rev.exists
        or previous_revision.etag != rev.etag
        or previous_revision.last_modified != rev.last_modified
        or previous_revision.sha256 != rev.sha256
    )
    names = ("details.json", "item.json", "tags.json")
    result: dict[str, Any] = {}
    # A present revision object is the one-request change switch. If it changed,
    # refresh the metadata conditionally; unchanged files can still answer 304.
    # If revision.json does not exist, fall back to checking each object itself.
    for name in names:
        rec = cache.get(urls[name])
        should_check = force or rec is None or not rev.exists or revision_changed
        if should_check:
            rec = conditional_fetch(cache, urls[name], max_age=max_age, force=force or revision_changed)
        result[name.removesuffix(".json")] = load_cached_json(rec) if rec else None
    result["revision"] = load_cached_json(rev)
    return result


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
        works.append(Work(slug=slug, title=str(item.get("display") or item.get("title") or item.get("name") or display_from_slug(slug)), source=str(item.get("source") or "e"), work_id=str(wid) if wid is not None else None, manifest=manifest, manifest_path=(data_dir / manifest).resolve(), tags=tuple(map(str,tags)), canonical_paths=tuple(paths), thumb_url=item.get("thumb") if isinstance(item.get("thumb"), str) else None))
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



# ---------------------------------------------------------------------------
# Likely duplicate detection
# ---------------------------------------------------------------------------

# Conservative copy suffixes generated by browsers/file managers or repeated
# ingest attempts. Unseparated title numbers such as "Rocky2" are preserved.
_NUMBERED_COPY_SUFFIX = re.compile(
    r"""
    (?:
        \s*\(\s*(?P<paren>\d+)\s*\) |
        [\s_.-]+(?P<number>\d+) |
        [\s_.-]+copy(?:[\s_.-]*(?P<copy_number>\d+))? |
        [\s_.-]+duplicate(?:[\s_.-]*(?P<duplicate_number>\d+))?
    )$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def dedupe_identity(value: str) -> tuple[str, bool, str]:
    """Return normalized base key, suffix status, and readable base name."""
    original = str(value or "").strip()
    match = _NUMBERED_COPY_SUFFIX.search(original)
    had_copy_suffix = match is not None
    base = original[:match.start()] if match else original
    base = base.rstrip(" _.-")
    key = re.sub(r"[^a-z0-9]+", "", base.casefold())
    return key, had_copy_suffix, base


def duplicate_group_map(works: list[Work]) -> dict[str, tuple[int, str, bool]]:
    """Return slug -> (group number, base name, is numbered copy).

    A group appears only when at least two distinct works normalize to the same
    name and at least one member has a clear numbered/copy suffix. Detection
    never selects or deletes anything automatically.
    """
    buckets: dict[str, list[tuple[Work, bool, str]]] = {}

    for work in works:
        slug_key, slug_suffix, slug_base = dedupe_identity(work.slug)
        title_key, title_suffix, title_base = dedupe_identity(work.title)

        # Prefer whichever field exposes an explicit copy suffix. Otherwise use
        # the slug because it is the catalog's stable identity.
        if title_suffix and not slug_suffix:
            key, suffixed, base = title_key, True, title_base
        else:
            key, suffixed, base = slug_key, slug_suffix, slug_base

        if key:
            buckets.setdefault(key, []).append((work, suffixed, base))

    duplicate_buckets: list[list[tuple[Work, bool, str]]] = []
    for members in buckets.values():
        distinct_slugs = {work.slug for work, _, _ in members}
        if len(distinct_slugs) >= 2 and any(suffixed for _, suffixed, _ in members):
            duplicate_buckets.append(members)

    duplicate_buckets.sort(
        key=lambda members: min(
            (work.title.casefold() for work, _, _ in members),
            default="",
        )
    )

    result: dict[str, tuple[int, str, bool]] = {}
    for group_number, members in enumerate(duplicate_buckets, 1):
        base_name = min(
            (base for _, _, base in members if base),
            key=lambda value: (len(value), value.casefold()),
            default="duplicate",
        )
        for work, suffixed, _ in members:
            result[work.slug] = (group_number, base_name, suffixed)

    return result


# ---------------------------------------------------------------------------
# Public rotunda visibility
# ---------------------------------------------------------------------------

def set_rotunda_omissions(
    root: Path,
    data_dir: Path,
    slugs: list[str],
    *,
    hidden: bool,
    dry_run: bool = False,
) -> tuple[Path, Path | None, list[str]]:
    """Hide or unhide works through public_rotunda.omit_works.

    This intentionally does not alter each work's broader ``public`` value.
    It only controls appearance in the public rotunda. The JSON is replaced
    atomically and a timestamped backup is made before a real write.
    """
    rotunda_path = data_dir / "rotunda.json"
    if not rotunda_path.is_file():
        raise FileNotFoundError(f"rotunda.json not found: {rotunda_path}")

    with rotunda_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    public_rotunda = payload.setdefault("public_rotunda", {})
    current = public_rotunda.setdefault("omit_works", [])
    if not isinstance(current, list):
        raise ValueError("public_rotunda.omit_works must be a JSON array")

    requested = {str(slug) for slug in slugs}
    before = {str(slug) for slug in current}

    if hidden:
        after = before | requested
    else:
        after = before - requested

    ordered = sorted(after, key=str.casefold)
    changed = sorted(before ^ after, key=str.casefold)

    if not changed or dry_run:
        return rotunda_path, None, changed

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = root / ".deletor-backups" / f"rotunda-{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / "rotunda.json"
    shutil.copy2(rotunda_path, backup_path)

    public_rotunda["omit_works"] = ordered

    fd, temporary_name = tempfile.mkstemp(
        prefix=".rotunda.",
        suffix=".json.tmp",
        dir=rotunda_path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=4)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, rotunda_path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise

    return rotunda_path, backup_path, changed

def work_tag_path(data_dir: Path, slug: str) -> Path:
    """Resolve the repository tag file for one work.

    Existing files beneath src/data/tags are respected. When no file exists,
    the user's preferred fallback is created directly beneath src/data:
    src/data/<work-slug>.json.
    """
    nested = data_dir / "tags" / f"{slug}.json"
    direct = data_dir / f"{slug}.json"
    return nested if nested.is_file() else direct


def load_work_tags(data_dir: Path, slug: str) -> tuple[Path, dict[str, Any]]:
    path = work_tag_path(data_dir, slug)
    if path.is_file():
        value = load_json(path)
        if not isinstance(value, dict):
            raise ValueError(f"Tag file must contain a JSON object: {path}")
    else:
        value = {
            "schema_version": 1,
            "name": slug,
            "public": {},
            "private": {},
        }

    value.setdefault("schema_version", 1)
    value.setdefault("name", slug)
    if not isinstance(value.get("public"), dict):
        value["public"] = {}
    if not isinstance(value.get("private"), dict):
        value["private"] = {}
    return path, value


def add_work_tags(
    root: Path,
    data_dir: Path,
    slug: str,
    block: str,
    values: list[str],
) -> tuple[Path, Path | None, list[str]]:
    """Add flat tag names beneath a top-level tag block, preserving all JSON."""
    path, payload = load_work_tags(data_dir, slug)
    clean = [value.strip() for value in values if value.strip()]
    if not clean:
        return path, None, []

    node = payload.setdefault(block, {})
    if not isinstance(node, dict):
        raise ValueError(f"Tag block {block!r} is not a JSON object in {path}")

    added: list[str] = []
    for value in clean:
        if value not in node:
            node[value] = {}
            added.append(value)

    if not added:
        return path, None, []

    backup_path: Path | None = None
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_dir = root / ".deletor-backups" / f"tags-{stamp}" / path.relative_to(root).parent
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / path.name
        shutil.copy2(path, backup_path)

    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, payload, 4)
    return path, backup_path, added


def thumbnail_url_for(work: Work) -> str:
    if work.thumb_url:
        return work.thumb_url
    escaped = quote(work.slug, safe="._-~")
    return f"https://cdn.564578634.xyz/works/{escaped}/chapter_1/thumb.webp"


def cached_thumbnail_path(cache_dir: Path, work: Work) -> Path:
    url = thumbnail_url_for(work)
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_dir / "thumbs" / f"{digest}.webp"


def fetch_thumbnail(cache_dir: Path, work: Work, *, refresh: bool = False) -> Path:
    path = cached_thumbnail_path(cache_dir, work)
    if path.is_file() and not refresh:
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(
        thumbnail_url_for(work),
        headers={"User-Agent": "AnimePlex-Catalog/2.0", "Accept": "image/webp,image/*"},
    )
    with urlopen(request, timeout=20) as response:
        body = response.read()

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return path


def choose_interactive(
    works: list[Work],
    root: Path,
    data_dir: Path,
    cache_dir: Path,
) -> tuple[str, list[str]]:
    """Tkinter catalog selector with thumbnail preview and per-work tag editing."""
    try:
        import tkinter as tk
        from tkinter import messagebox, simpledialog, ttk
        from PIL import Image, ImageTk
    except Exception:
        return ("delete", choose_numbered(works))

    result: dict[str, Any] = {"action": "quit", "slugs": []}
    window = tk.Tk()
    window.title("AnimePlex Catalog Editor")
    window.geometry("1380x820")
    window.minsize(980, 620)

    query_var = tk.StringVar()
    status_var = tk.StringVar(value="Select a work. Thumbnails are cached after first load.")
    visible: list[Work] = []
    image_ref: dict[str, Any] = {"image": None}
    image_generation = {"value": 0}

    top = ttk.Frame(window, padding=10)
    top.pack(fill="x")
    ttk.Label(top, text="Search").pack(side="left")
    search = ttk.Entry(top, textvariable=query_var)
    search.pack(side="left", fill="x", expand=True, padx=(8, 10))

    body = ttk.Panedwindow(window, orient="horizontal")
    body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    left = ttk.Frame(body)
    right = ttk.Frame(body, padding=(12, 0, 0, 0))
    body.add(left, weight=3)
    body.add(right, weight=2)

    tree = ttk.Treeview(
        left,
        columns=("slug",),
        show="tree headings",
        selectmode="extended",
    )
    tree.heading("#0", text="Work")
    tree.heading("slug", text="Slug")
    tree.column("#0", width=430)
    tree.column("slug", width=430)
    scroll = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    title_var = tk.StringVar(value="No work selected")
    slug_var = tk.StringVar()
    tag_path_var = tk.StringVar()
    thumb_url_var = tk.StringVar()

    ttk.Label(right, textvariable=title_var, font=("TkDefaultFont", 12, "bold"), wraplength=470).pack(anchor="w")
    ttk.Label(right, textvariable=slug_var, wraplength=470).pack(anchor="w", pady=(3, 8))

    image_label = ttk.Label(
        right,
        text="Select a work to load thumb.webp",
        anchor="center",
        justify="center",
    )
    image_label.pack(fill="both", expand=True)

    ttk.Label(right, textvariable=thumb_url_var, wraplength=470).pack(fill="x", pady=(8, 4))
    ttk.Label(right, textvariable=tag_path_var, wraplength=470).pack(fill="x", pady=(0, 8))

    tag_buttons = ttk.Frame(right)
    tag_buttons.pack(fill="x", pady=(4, 8))

    selected_work: dict[str, Work | None] = {"work": None}

    def current_tree_works() -> list[Work]:
        chosen: list[Work] = []
        by_slug = {work.slug: work for work in visible}
        for item in tree.selection():
            slug = str(tree.set(item, "slug"))
            if slug in by_slug:
                chosen.append(by_slug[slug])
        return chosen

    def update_tag_path(work: Work) -> None:
        path = work_tag_path(data_dir, work.slug)
        state = "existing" if path.exists() else "will be created"
        tag_path_var.set(f"Tags: {path.relative_to(root)} ({state})")

    def render_image(path: Path, generation: int) -> None:
        try:
            image = Image.open(path)
            image.thumbnail((460, 590))
            photo = ImageTk.PhotoImage(image)
        except Exception as exc:
            if generation == image_generation["value"]:
                image_ref["image"] = None
                image_label.configure(image="", text=f"Unable to display thumbnail:\n{exc}")
            return

        if generation != image_generation["value"]:
            return
        image_ref["image"] = photo
        image_label.configure(image=photo, text="")
        status_var.set(f"Cached thumbnail: {path}")

    def load_selected_thumbnail(*, refresh: bool = False) -> None:
        work = selected_work["work"]
        if work is None:
            return

        image_generation["value"] += 1
        generation = image_generation["value"]
        image_ref["image"] = None
        image_label.configure(image="", text="Loading thumbnail…")
        status_var.set(f"Loading thumbnail for {work.title}")

        def worker() -> None:
            try:
                path = fetch_thumbnail(cache_dir, work, refresh=refresh)
            except Exception as exc:
                def fail() -> None:
                    if generation == image_generation["value"]:
                        image_label.configure(image="", text=f"Thumbnail unavailable:\n{exc}")
                        status_var.set(f"Thumbnail failed: {work.slug}")
                window.after(0, fail)
                return
            window.after(0, lambda: render_image(path, generation))

        threading.Thread(target=worker, daemon=True).start()

    def on_select(_event: Any = None) -> None:
        selection = tree.selection()
        if not selection:
            return
        slug = str(tree.set(selection[0], "slug"))
        work = next((candidate for candidate in visible if candidate.slug == slug), None)
        if work is None:
            return
        selected_work["work"] = work
        title_var.set(work.title)
        slug_var.set(work.slug)
        thumb_url_var.set(thumbnail_url_for(work))
        update_tag_path(work)
        load_selected_thumbnail()

    tree.bind("<<TreeviewSelect>>", on_select)

    def add_tags(block: str) -> None:
        work = selected_work["work"]
        if work is None:
            messagebox.showinfo("Select a work", "Select a work first.")
            return
        raw = simpledialog.askstring(
            f"Add {block} tags",
            f"Comma-separated tags for {work.title}:",
            parent=window,
        )
        if not raw:
            return
        values = [part.strip() for part in raw.split(",") if part.strip()]
        try:
            path, backup, added = add_work_tags(root, data_dir, work.slug, block, values)
        except Exception as exc:
            messagebox.showerror("Tags", str(exc))
            return
        update_tag_path(work)
        if added:
            detail = f"Added {len(added)} tag(s) to {path.relative_to(root)}"
            if backup:
                detail += f"\nBackup: {backup.relative_to(root)}"
            messagebox.showinfo("Tags saved", detail)
            status_var.set(detail.replace("\n", " | "))
        else:
            status_var.set("Those tags were already present.")

    ttk.Button(tag_buttons, text="Add public tags", command=lambda: add_tags("public")).pack(side="left", padx=(0, 6))
    ttk.Button(tag_buttons, text="Add private tags", command=lambda: add_tags("private")).pack(side="left", padx=(0, 6))
    ttk.Button(tag_buttons, text="Refresh image", command=lambda: load_selected_thumbnail(refresh=True)).pack(side="left")

    actions = ttk.Frame(window, padding=(10, 0, 10, 8))
    actions.pack(fill="x")

    def finish(action: str) -> None:
        chosen = current_tree_works()
        if not chosen and selected_work["work"] is not None:
            chosen = [selected_work["work"]]
        if not chosen:
            messagebox.showinfo("Select works", "Select one or more works first.")
            return
        result["action"] = action
        result["slugs"] = [work.slug for work in chosen]
        window.destroy()

    ttk.Button(actions, text="DELETE selected", command=lambda: finish("delete")).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Hide from rotunda", command=lambda: finish("hide")).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Unhide from rotunda", command=lambda: finish("unhide")).pack(side="left", padx=(0, 6))
    ttk.Button(actions, text="Close", command=window.destroy).pack(side="right")
    ttk.Label(window, textvariable=status_var, padding=(10, 0, 10, 10)).pack(fill="x")

    def refresh_list(*_args: Any) -> None:
        needle = query_var.get().casefold().strip()
        visible[:] = [
            work for work in works
            if needle in f"{work.title} {work.slug} {' '.join(work.tags)}".casefold()
        ]
        tree.delete(*tree.get_children())
        for work in visible:
            tree.insert("", "end", text=work.title, values=(work.slug,))
        if visible:
            first = tree.get_children()[0]
            tree.selection_set(first)
            tree.focus(first)
            tree.see(first)
            on_select()

    query_var.trace_add("write", refresh_list)
    refresh_list()
    search.focus_set()
    window.mainloop()
    return str(result["action"]), list(result["slugs"])

def choose_numbered(works: list[Work]) -> list[str]:
    for i,w in enumerate(works,1): print(f"{i}. [ ] Keep {w.title} ({w.slug})")
    raw=input("Enter numbers to delete separated by spaces, or blank to quit: ").split()
    return [works[int(x)-1].slug for x in raw if x.isdigit() and 1<=int(x)<=len(works)]


def main(argv=None) -> int:
    root=repo_root(); ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true"); ap.add_argument("--yes", action="store_true")
    ap.add_argument("--data-dir", default="src/data"); ap.add_argument("--slug", action="append", default=[]); ap.add_argument("--list", action="store_true")
    ap.add_argument("--inspect", metavar="SLUG", help="Lazily fetch and print cached remote metadata for one work")
    ap.add_argument("--cache-dir", default="~/.cache/animeplex-catalog")
    ap.add_argument("--cache-max-age", type=int, default=DEFAULT_REVALIDATE_SECONDS)
    ap.add_argument("--refresh", action="store_true", help="Force conditional revalidation")
    ap.add_argument("--compact-cache", action="store_true")
    args=ap.parse_args(argv); data_dir=(root/args.data_dir).resolve()
    works=discover_works(data_dir)
    cache = JsonlCache(Path(args.cache_dir))
    if args.compact_cache:
        cache.compact(); print(f"Compacted cache: {cache.journal}")
    if args.inspect:
        match = next((w for w in works if w.slug == args.inspect), None)
        if not match: raise SystemExit(f"Unknown slug: {args.inspect}")
        print(f"Loading metadata for {match.title}...")
        try:
            metadata = lazy_work_metadata(cache, match, max_age=args.cache_max_age, force=args.refresh)
        except (HTTPError, URLError, TimeoutError) as e:
            raise SystemExit(f"Metadata request failed: {e}")
        print(json.dumps(metadata, ensure_ascii=False, indent=2)); return 0
    if args.list:
        [print(f"{w.slug}\t{w.title}\t{w.manifest or ''}") for w in works]; return 0
    if args.slug:
        action, slugs = "delete", args.slug
    else:
        action, slugs = choose_interactive(works, root, data_dir, Path(args.cache_dir).expanduser().resolve())

    if not slugs:
        print("No works selected; nothing changed.")
        return 0

    if action in {"hide", "unhide"}:
        verb = "HIDE" if action == "hide" else "UNHIDE"
        known = {work.slug: work for work in works}
        selected_works = [known[slug] for slug in slugs if slug in known]

        print(f"{verb} from public rotunda:")
        for work in selected_works:
            print(f"- {work.title} ({work.slug})")

        if args.dry_run:
            _, _, changed = set_rotunda_omissions(
                root,
                data_dir,
                slugs,
                hidden=(action == "hide"),
                dry_run=True,
            )
            print(f"Dry run: {len(changed)} rotunda omission(s) would change.")
            return 0

        expected = f"{verb} {len(selected_works)}"
        if input(f'Type exactly "{expected}" to continue: ') != expected:
            print("Confirmation failed; nothing changed.")
            return 1

        rotunda_path, backup_path, changed = set_rotunda_omissions(
            root,
            data_dir,
            slugs,
            hidden=(action == "hide"),
        )
        state = "Hidden from" if action == "hide" else "Restored to"
        print(f"{state} public rotunda: {len(changed)} work(s)")
        print(f"Modified: {rotunda_path.relative_to(root)}")
        if backup_path:
            print(f"Backup: {backup_path.relative_to(root)}")
        print(
            "Suggested Git commands:\n"
            "git diff -- src/data/rotunda.json scripts/deletor.py\n"
            "git status\n"
            "git add scripts/deletor.py src/data/rotunda.json\n"
            f'git commit -m "{verb.title()} selected works in public rotunda"\n'
            "git push origin main"
        )
        return 0

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
