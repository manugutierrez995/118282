#!/usr/bin/env python3
"""AnimePlex work ingestion wizard, single-work runner, and batch ingester.

Single mode: behaves like the original wizard.
Batch mode: point it at a parent folder containing many work folders. Each immediate
subfolder becomes one work. Slug/display/parent_work_id are inferred automatically.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import hashlib
import re
import shlex
import shutil
import stat
import tempfile
import zipfile
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
DEFAULT_CDN = "https://cdn.564578634.xyz/works"
DEFAULT_UPLOAD_REMOTE = "animeplex.lol:extended/works"
DEFAULT_TOKEN_ENV = "GITHUB_TOKEN"
DEFAULT_THUMB_LOCATION = "first-chapter"
DEFAULT_DETAILS_FILENAME = "details.json"
HASH_CHUNK_SIZE = 4 * 1024 * 1024

HARDCODED_GITHUB_TOKEN = ""
HARDCODED_R2_REMOTE_NAME = "animeplex.lol"
HARDCODED_R2_ACCOUNT_ID = "40439992e793a00d8f33b19f898fa0c2"
HARDCODED_R2_ACCESS_KEY_ID = ""
HARDCODED_R2_SECRET_ACCESS_KEY = ""
HARDCODED_R2_BUCKET = "extended"
HARDCODED_R2_PREFIX = "works"
HARDCODED_R2_ENDPOINT = ""
HARDCODED_TOKEN_VALUE = ""

@dataclass
class Chapter:
    rel: str
    path: Path
    images: list[Path]
    pages: int
    padding: int
    extension: str


@dataclass
class WorkSpec:
    root: Path
    slug: str
    display: str
    parent_work_id: int | None
    original_input: Path | None = None
    extraction_dir: Path | None = None
    temporary_extraction: bool = False



ARCHIVE_EXTS = {".zip"}
JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
HELPER_IMAGE_NAMES = {"thumb.webp", "thumbnail.webp", "cover.webp"}


def utc_iso(timestamp: float | None = None) -> str:
    dt = datetime.fromtimestamp(timestamp, timezone.utc) if timestamp is not None else datetime.now(timezone.utc)
    return dt.isoformat(timespec="seconds").replace("+00:00", "Z")


def hash_cache_path() -> Path:
    base = Path(os.getenv("XDG_CACHE_HOME", Path.home() / ".cache")).expanduser()
    return base / "animeplex-ingest" / "archive-hashes.json"


def load_hash_cache() -> dict[str, Any]:
    data = load_json(hash_cache_path(), {})
    return data if isinstance(data, dict) else {}


def save_hash_cache(data: dict[str, Any]) -> None:
    path = hash_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def sha256_file(path: Path, force: bool = False) -> tuple[str, bool]:
    """Return a ZIP SHA-256, reusing a safe local stat-keyed cache when possible."""
    resolved = path.resolve()
    st = resolved.stat()
    cache_key = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()
    signature = {
        "size_bytes": st.st_size,
        "mtime_ns": st.st_mtime_ns,
        "ctime_ns": st.st_ctime_ns,
        "device": st.st_dev,
        "inode": st.st_ino,
    }
    cache = load_hash_cache()
    cached = cache.get(cache_key)
    if not force and isinstance(cached, dict) and all(cached.get(k) == v for k, v in signature.items()):
        digest = cached.get("sha256")
        if isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest):
            return digest, True

    digest = hashlib.sha256()
    with resolved.open("rb") as f:
        while chunk := f.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    value = digest.hexdigest()
    cache[cache_key] = {**signature, "sha256": value, "cached_at": utc_iso()}
    save_hash_cache(cache)
    return value, False


def archive_member_key(name: str) -> list[Any]:
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", name.replace("\\", "/"))]


def is_archive_page_name(name: str) -> bool:
    path = Path(name.replace("\\", "/"))
    return path.suffix.lower() in IMAGE_EXTS and path.name.lower() not in HELPER_IMAGE_NAMES and not is_junk_path(path)


def build_archive_metadata(archive: Path, force_rehash: bool = False) -> dict[str, Any]:
    st = archive.stat()
    sha256, reused = sha256_file(archive, force=force_rehash)
    with zipfile.ZipFile(archive) as zf:
        infos = [info for info in zf.infolist() if not info.is_dir()]
        records = [
            {
                "name": info.filename.replace("\\", "/"),
                "crc32": f"{info.CRC:08x}",
                "size": info.file_size,
                "compressed_size": info.compress_size,
                "compression": info.compress_type,
            }
            for info in infos
        ]
        records.sort(key=lambda item: archive_member_key(item["name"]))
        listing_bytes = json.dumps(records, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        image_names = sorted(
            [item["name"] for item in records if is_archive_page_name(item["name"])],
            key=archive_member_key,
        )
        compressed = sum(item["compressed_size"] for item in records)
        uncompressed = sum(item["size"] for item in records)
        comment_sha256 = hashlib.sha256(zf.comment).hexdigest() if zf.comment else None

    return {
        "filename": archive.name,
        "mime_type": "application/zip",
        "size_bytes": st.st_size,
        "modified_utc": utc_iso(st.st_mtime),
        "sha256": sha256,
        "sha256_reused_from_local_cache": reused,
        "zip_file_entries": len(records),
        "zip_image_entries": len(image_names),
        "zip_compressed_bytes": compressed,
        "zip_uncompressed_bytes": uncompressed,
        "zip_compression_ratio": round(compressed / uncompressed, 6) if uncompressed else None,
        "zip_member_listing_sha256": hashlib.sha256(listing_bytes).hexdigest(),
        "zip_comment_sha256": comment_sha256,
        "first_image_member": image_names[0] if image_names else None,
        "last_image_member": image_names[-1] if image_names else None,
        "first_image_members": image_names[:5],
        "last_image_members": image_names[-5:] if image_names else [],
    }


def repo_root() -> Path:
    try:
        out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=Path(__file__).resolve().parent, text=True, stderr=subprocess.DEVNULL).strip()
        if out:
            return Path(out).resolve()
    except Exception:
        pass
    return Path(__file__).resolve().parents[1]


def resolve_repo_path(value: str | Path) -> Path:
    p = Path(value).expanduser()
    return p.resolve() if p.is_absolute() else (repo_root() / p).resolve()


def is_supported_archive(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in ARCHIVE_EXTS


def is_junk_path(path: Path) -> bool:
    parts = path.parts
    return any(part.startswith(".") or part == "__MACOSX" or part in JUNK_NAMES or part.startswith("._") for part in parts)


def is_candidate_page_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in IMAGE_EXTS and path.name.lower() not in HELPER_IMAGE_NAMES and not is_junk_path(path)


def valid_chapter_dirs(root: Path) -> list[Path]:
    return [p for p in sorted(root.iterdir(), key=natural_key) if p.is_dir() and not is_junk_path(p) and any(is_candidate_page_image(c) for c in p.iterdir())]


def root_page_images(root: Path) -> list[Path]:
    return sorted([p for p in root.iterdir() if is_candidate_page_image(p)], key=natural_key)


def safe_extract_zip(archive: Path, dest: Path, dry: bool = False) -> None:
    if dry:
        print(f"DRY extract {archive} -> {dest}")
        return
    dest.mkdir(parents=True, exist_ok=True)
    root = dest.resolve()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            name = info.filename.replace('\\', '/')
            pp = Path(name)
            if pp.is_absolute() or re.match(r"^[A-Za-z]:", name) or ".." in pp.parts:
                raise SystemExit(f"Unsafe ZIP member path rejected: {info.filename}")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise SystemExit(f"Unsafe ZIP symlink member rejected: {info.filename}")
            target = (root / pp).resolve()
            if root != target and root not in target.parents:
                raise SystemExit(f"Unsafe ZIP member escapes extraction root: {info.filename}")
        zf.extractall(root)
    for child in root.rglob("*"):
        if child.is_symlink():
            resolved = child.resolve()
            if root != resolved and root not in resolved.parents:
                raise SystemExit(f"Unsafe ZIP symlink escape rejected: {child.relative_to(root)}")


def meaningful_children(root: Path) -> list[Path]:
    return [p for p in sorted(root.iterdir(), key=natural_key) if not is_junk_path(p)]


def descend_wrapper_folders(root: Path) -> Path:
    current = root
    while True:
        children = meaningful_children(current)
        dirs = [p for p in children if p.is_dir()]
        files = [p for p in children if p.is_file() and not is_junk_path(p)]
        if len(dirs) == 1 and not any(is_candidate_page_image(f) for f in files) and not valid_chapter_dirs(current):
            current = dirs[0]
            continue
        return current


def resolve_work_root(path: Path) -> Path:
    root = descend_wrapper_folders(path)
    children = meaningful_children(root)
    dirs = [p for p in children if p.is_dir()]
    files = [p for p in children if p.is_file()]
    chapter_dirs = valid_chapter_dirs(root)
    if not chapter_dirs and not root_page_images(root) and len(dirs) == 1:
        return descend_wrapper_folders(dirs[0])
    return root


def create_chapter_one_for_loose_images(root: Path, images: list[Path], dry: bool) -> Path:
    chapter = root / "chapter_1"
    if dry:
        print(f"DRY create {chapter} and move {len(images)} root images into it")
        return chapter
    chapter.mkdir(exist_ok=True)
    for img in images:
        img.rename(chapter / img.name)
    return chapter


def prepare_work_root(path: Path, args: argparse.Namespace, slug_source: str | None = None) -> tuple[Path, Path | None, bool]:
    original = path
    extraction_dir = None
    temporary = False
    if is_supported_archive(path):
        base = slug_source or path.stem
        if args.extract_dir:
            extraction_dir = Path(args.extract_dir).expanduser().resolve()
            if extraction_dir.exists() and any(extraction_dir.iterdir()) and not args.overwrite_extracted:
                raise SystemExit(f"Extraction destination is not empty: {extraction_dir}; use --overwrite-extracted")
            if not args.dry_run:
                if args.overwrite_extracted and extraction_dir.exists():
                    shutil.rmtree(extraction_dir)
                extraction_dir.mkdir(parents=True, exist_ok=True)
        else:
            extraction_dir = Path(tempfile.mkdtemp(prefix=f"animeplex_{slugify_name(base)}_"))
            temporary = True
        safe_extract_zip(path, extraction_dir, args.dry_run)
        path = extraction_dir if not args.dry_run else extraction_dir
    root = resolve_work_root(path) if path.exists() else path
    chapters = valid_chapter_dirs(root) if root.exists() else []
    images = root_page_images(root) if root.exists() else []
    if images and chapters and not args.merge_root_images_into_chapter_one:
        raise SystemExit(f"Ambiguous work root {root}: contains both chapter folders and root page images; use --merge-root-images-into-chapter-one")
    if images and not args.no_auto_chapter:
        target = root / "chapter_1"
        if chapters and args.merge_root_images_into_chapter_one:
            if dry := args.dry_run:
                print(f"DRY move {len(images)} root images into {target}")
            else:
                target.mkdir(exist_ok=True)
                for img in images:
                    img.rename(target / img.name)
        elif not chapters:
            create_chapter_one_for_loose_images(root, images, args.dry_run)
    elif images and args.no_auto_chapter:
        raise SystemExit(f"Loose root images found in {root}, but --no-auto-chapter is set")
    print(f"preprocess: {original} -> root={root} archive={'yes' if is_supported_archive(original) else 'no'} loose_images={len(images)} chapters={len(chapters)}")
    return root, extraction_dir, temporary


def cleanup_extractions(specs: list[WorkSpec], args: argparse.Namespace) -> None:
    if args.keep_extracted:
        return
    for spec in specs:
        if spec.extraction_dir and (spec.temporary_extraction or args.cleanup_extracted):
            if spec.extraction_dir.exists():
                shutil.rmtree(spec.extraction_dir)
                print(f"cleanup: removed {spec.extraction_dir}")


def discover_batch_inputs(parent: Path) -> list[Path]:
    out: list[Path] = []
    for p in sorted(parent.iterdir(), key=natural_key):
        if is_junk_path(p):
            continue
        if p.is_dir():
            if root_page_images(p) or detect_chapters(p) or valid_chapter_dirs(resolve_work_root(p)):
                out.append(p)
        elif is_supported_archive(p):
            out.append(p)
    return out


def clean_input(value: str) -> str:
    value = (value or "").strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default not in (None, "") else ""
    value = clean_input(input(f"{prompt}{suffix}: "))
    return value or (default or "")


def ask_secret(prompt: str, default: str | None = None) -> str:
    suffix = " [hidden default]" if default else ""
    value = clean_input(getpass.getpass(f"{prompt}{suffix}: "))
    return value or (default or "")


def ask_bool(prompt: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    return ask(f"{prompt} ({d})", "y" if default else "n").lower() in {"y", "yes", "true", "1"}


def expand_path(value: str) -> Path:
    return Path(clean_input(value)).expanduser().resolve()


def slugify_name(name: str) -> str:
    name = clean_input(name)
    name = re.sub(r"[’']", "", name)
    name = re.sub(r"[^A-Za-z0-9.-]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "Untitled_Work"


def display_from_slug(slug: str) -> str:
    text = slug.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def display_from_folder_name(name: str) -> str:
    text = clean_input(name)
    text = text.replace(" _ ", " ")
    text = text.replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or display_from_slug(slugify_name(name))


def load_json(path: Path, fallback: Any = None) -> Any:
    if not path.exists():
        return fallback
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any, dry: bool = False) -> None:
    if dry:
        print(f"DRY write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def natural_key(path: Path) -> list[Any]:
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", path.name)]


def is_page_image(path: Path) -> bool:
    """Return True only for reader pages, excluding generated helper images."""
    if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
        return False
    return path.name.lower() not in {"thumb.webp", "thumbnail.webp", "cover.webp"}


def detect_chapters(root: Path) -> list[Chapter]:
    """Recursively detect any folder that directly contains page images as a chapter."""
    chapters: list[Chapter] = []
    for d in sorted([p for p in root.rglob("*") if p.is_dir()], key=lambda x: natural_key(x)):
        imgs = sorted([p for p in d.iterdir() if is_page_image(p)], key=natural_key)
        if not imgs:
            continue
        rel = d.relative_to(root).as_posix()
        nums = [re.match(r"^(\d+)", p.stem) for p in imgs]
        padding = max((len(m.group(1)) for m in nums if m), default=3)
        ext = imgs[0].suffix.lower().lstrip(".")
        chapters.append(Chapter(rel, d, imgs, len(imgs), padding, ext))
    return chapters


def immediate_work_folders(parent: Path) -> list[Path]:
    candidates = [p for p in sorted(parent.iterdir(), key=natural_key) if p.is_dir()]
    return [p for p in candidates if detect_chapters(p)]


def require_pillow() -> Any:
    try:
        from PIL import Image
        return Image
    except ImportError as e:
        raise SystemExit("Image resize/thumb generation requires Pillow. Install with: python -m pip install Pillow") from e


def normalize_images(chapters: list[Chapter], width: int | None, quality: int, convert: str | None, delete_originals: bool, dry: bool) -> None:
    if not width and not convert:
        return
    Image = require_pillow()
    for ch in chapters:
        new: list[Path] = []
        for img in ch.images:
            out = img.with_suffix(f".{convert}") if convert else img
            if dry:
                new.append(out)
                continue
            with Image.open(img) as im:
                if width and im.width > width:
                    h = round(im.height * (width / im.width))
                    im = im.resize((width, h))
                save_kwargs = {"quality": quality} if out.suffix.lower() in {".jpg", ".jpeg", ".webp"} else {}
                if out.suffix.lower() == ".webp" and im.mode not in {"RGB", "RGBA"}:
                    im = im.convert("RGB")
                im.save(out, **save_kwargs)
            if convert and delete_originals and out != img:
                img.unlink()
            new.append(out)
        ch.images = sorted(new, key=natural_key)
        ch.extension = ch.images[0].suffix.lower().lstrip(".")


def renumber_pages(chapters: list[Chapter], dry: bool, default_padding: int = 3) -> None:
    """Rename pages in every chapter to 001.ext, 002.ext, ... in detected order.

    Numeric filenames are naturally sorted. Non-numeric filenames are sorted by their
    existing natural filename order and then renamed. A two-phase temporary rename avoids
    collisions when targets such as 001.webp already exist.
    """
    for ch in chapters:
        if not ch.images:
            continue

        extensions = {p.suffix.lower() for p in ch.images}
        if len(extensions) != 1:
            raise SystemExit(
                f"Mixed image extensions in {ch.path}. Convert them first with --convert webp "
                "or make the chapter use one extension."
            )

        ext = ch.images[0].suffix.lower()
        padding = max(default_padding, len(str(len(ch.images))))
        targets = [ch.path / f"{i:0{padding}d}{ext}" for i in range(1, len(ch.images) + 1)]

        if [p.resolve() for p in ch.images] == [p.resolve() for p in targets]:
            ch.padding = padding
            ch.extension = ext.lstrip(".")
            continue

        print(f"renumber: {ch.rel} -> {targets[0].name} .. {targets[-1].name}")
        if dry:
            ch.images = targets
            ch.padding = padding
            ch.extension = ext.lstrip(".")
            continue

        temp_paths: list[Path] = []
        for index, source in enumerate(ch.images):
            temporary = ch.path / f".__ingest_tmp_{index:06d}{source.suffix.lower()}"
            if temporary.exists():
                temporary.unlink()
            source.rename(temporary)
            temp_paths.append(temporary)

        for temporary, target in zip(temp_paths, targets):
            if target.exists():
                target.unlink()
            temporary.rename(target)

        ch.images = targets
        ch.pages = len(targets)
        ch.padding = padding
        ch.extension = ext.lstrip(".")


def thumb_rel(chapters: list[Chapter], thumb_location: str) -> str:
    if thumb_location == "first-chapter":
        return f"{chapters[0].rel}/thumb.webp"
    return "thumb.webp"


def thumb_url(cdn: str, slug: str, chapters: list[Chapter], thumb_location: str) -> str:
    return f"{cdn.rstrip('/')}/{slug}/{thumb_rel(chapters, thumb_location)}"


def companion_dir_rel(chapters: list[Chapter], thumb_location: str) -> str:
    parent = Path(thumb_rel(chapters, thumb_location)).parent.as_posix()
    return "" if parent == "." else parent.strip("/")


def companion_rel(name: str, chapters: list[Chapter], thumb_location: str) -> str:
    directory = companion_dir_rel(chapters, thumb_location)
    return f"{directory}/{name}" if directory else name


def companion_path(work_root: Path, name: str, chapters: list[Chapter], thumb_location: str) -> Path:
    return work_root / companion_rel(name, chapters, thumb_location)


def build_details(
    spec: WorkSpec,
    manifest: dict[str, Any],
    chapters: list[Chapter],
    args: argparse.Namespace,
) -> dict[str, Any]:
    archive_path = spec.original_input if spec.original_input and is_supported_archive(spec.original_input) else None
    archive = None
    if archive_path and archive_path.exists() and not args.dry_run:
        print(f"archive metadata: hashing/indexing {archive_path.name}")
        archive = build_archive_metadata(archive_path, force_rehash=args.rehash_zip)
        cache_note = "cache hit" if archive["sha256_reused_from_local_cache"] else "computed"
        print(f"archive sha256: {archive['sha256']} ({cache_note})")

    chapter_details: list[dict[str, Any]] = []
    page_tree_records: list[dict[str, Any]] = []
    total_page_bytes = 0
    for chapter in chapters:
        page_sizes: list[int] = []
        for page in chapter.images:
            size = page.stat().st_size if page.exists() and page.is_file() else 0
            page_sizes.append(size)
            total_page_bytes += size
            page_tree_records.append({
                "chapter": chapter.rel,
                "name": page.name,
                "size_bytes": size,
            })
        chapter_details.append({
            "rel": chapter.rel,
            "pages": chapter.pages,
            "padding": chapter.padding,
            "extension": chapter.extension,
            "page_bytes": sum(page_sizes),
            "first_page": chapter.images[0].name if chapter.images else None,
            "last_page": chapter.images[-1].name if chapter.images else None,
        })

    page_tree_bytes = json.dumps(page_tree_records, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    identity_payload = {
        "slug": spec.slug,
        "display": spec.display,
        "parent_work_id": spec.parent_work_id,
        "tags": normalize_tags(manifest.get("tags")),
        "public": manifest.get("public") is not False,
        "chapters": chapter_details,
        "page_tree_sha256": hashlib.sha256(page_tree_bytes).hexdigest(),
        "archive_sha256": archive.get("sha256") if archive else None,
        "archive_member_listing_sha256": archive.get("zip_member_listing_sha256") if archive else None,
    }
    identity_bytes = json.dumps(identity_payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    archive_name = archive_path.name if archive_path and args.upload_zip else None
    return {
        "schema_version": 1,
        "generated_at": utc_iso(),
        "generator": "ingest-work.py",
        "work": {
            "slug": spec.slug,
            "display": spec.display,
            "parent_work_id": spec.parent_work_id,
            "source": args.source,
            "tags": normalize_tags(manifest.get("tags")),
            "public": manifest.get("public") is not False,
            "thumb": thumb_rel(chapters, args.thumb_location),
            "details": companion_rel(DEFAULT_DETAILS_FILENAME, chapters, args.thumb_location),
            "archive": companion_rel(archive_name, chapters, args.thumb_location) if archive_name else None,
        },
        "content": {
            "chapter_count": len(chapters),
            "page_count": sum(chapter.pages for chapter in chapters),
            "page_bytes": total_page_bytes,
            "page_tree_sha256": hashlib.sha256(page_tree_bytes).hexdigest(),
            "chapters": chapter_details,
        },
        "archive": archive,
        "fingerprints": {
            "work_identity_sha256": hashlib.sha256(identity_bytes).hexdigest(),
            "archive_sha256": archive.get("sha256") if archive else None,
            "archive_structure_sha256": archive.get("zip_member_listing_sha256") if archive else None,
            "page_tree_sha256": hashlib.sha256(page_tree_bytes).hexdigest(),
        },
    }


def generate_thumb(work_root: Path, chapters: list[Chapter], quality: int, dry: bool, thumb_location: str) -> Path:
    if not chapters:
        raise SystemExit("No chapters detected; cannot generate thumbnail.")
    thumb = chapters[0].path / "thumb.webp" if thumb_location == "first-chapter" else work_root / "thumb.webp"
    first_page = chapters[0].images[0]
    if dry:
        print(f"DRY thumb {first_page} -> {thumb}")
        return thumb
    Image = require_pillow()
    with Image.open(first_page) as im:
        if im.mode not in {"RGB", "RGBA"}:
            im = im.convert("RGB")
        im.thumbnail((600, 900))
        im.save(thumb, "WEBP", quality=quality)
    return thumb


def pointer(slug: str, display: str, source: str, cdn: str, chapters: list[Chapter], thumb_location: str) -> dict[str, Any]:
    return {"slug": slug, "display": display, "source": source, "manifest": f"works/{slug}.json", "thumb": thumb_url(cdn, slug, chapters, thumb_location)}


def upsert_pointer(path: Path, entry: dict[str, Any], dry: bool) -> None:
    upsert_pointer_merge(path, entry, dry, add=True)



def normalize_tag(value: Any) -> str:
    return re.sub(r"\s+", "-", str(value or "").strip().lower())


def normalize_tags(values: Any) -> list[str]:
    raw = values if isinstance(values, list) else []
    out: list[str] = []
    seen: set[str] = set()
    for value in raw:
        tag = normalize_tag(value)
        if not tag or tag in seen:
            continue
        seen.add(tag)
        out.append(tag)
    return out


def parse_tags_arg(value: str | None) -> list[str] | None:
    if value is None or value == "":
        return None
    return normalize_tags(value.split(","))


def apply_metadata_options(manifest: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    next_manifest = dict(manifest)
    current_tags = normalize_tags(next_manifest.get("tags"))
    parsed_tags = parse_tags_arg(getattr(args, "tags", None))
    if getattr(args, "clear_tags", False):
        next_manifest["tags"] = []
    elif parsed_tags is not None:
        next_manifest["tags"] = parsed_tags
    elif "tags" in next_manifest:
        next_manifest["tags"] = current_tags

    if getattr(args, "private", False):
        next_manifest["public"] = False
    elif getattr(args, "public", False):
        next_manifest["public"] = True
    elif "public" in next_manifest:
        next_manifest["public"] = next_manifest.get("public") is not False
    return next_manifest


def derived_metadata(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "slug": manifest.get("slug"),
        "display": manifest.get("display"),
        "source": manifest.get("source"),
        "manifest": f"works/{manifest.get('slug')}.json",
        "thumb": manifest.get("thumb"),
        "tags": normalize_tags(manifest.get("tags")),
        "public": manifest.get("public") is not False,
    }


def upsert_pointer_merge(path: Path, entry: dict[str, Any], dry: bool, add: bool = True) -> bool:
    data = load_json(path, {"version": 2, "default": {}, "works": []})
    works = data.setdefault("works", [])
    for i, w in enumerate(works):
        if isinstance(w, dict) and w.get("slug") == entry.get("slug"):
            works[i] = {**w, **{k: v for k, v in entry.items() if v is not None}}
            write_json(path, data, dry)
            return True
    if not add:
        return False
    works.append({k: v for k, v in entry.items() if v is not None})
    write_json(path, data, dry)
    return True


def metadata_only_update(args: argparse.Namespace) -> list[Path]:
    if not args.slug:
        raise SystemExit("--metadata-only requires --slug")
    data = resolve_repo_path(args.repo_data)
    manifest_path = data / "works" / f"{args.slug}.json"
    manifest = load_json(manifest_path, None)
    if not isinstance(manifest, dict):
        raise SystemExit(f"Work manifest not found: {manifest_path}")
    manifest = apply_metadata_options(manifest, args)
    write_json(manifest_path, manifest, args.dry_run)
    entry = derived_metadata(manifest)
    written = [manifest_path]
    if upsert_pointer_merge(data / "fetch.json", entry, args.dry_run, add=False):
        written.append(data / "fetch.json")
    if args.update_rotunda or any(isinstance(w, dict) and w.get("slug") == args.slug for w in load_json(data / "rotunda.json", {}).get("works", [])):
        if upsert_pointer_merge(data / "rotunda.json", entry, args.dry_run, add=args.update_rotunda):
            written.append(data / "rotunda.json")
    print("Metadata-only update complete.")
    print(f"- Slug: {manifest.get('slug')}")
    print(f"- Tags: {normalize_tags(manifest.get('tags'))}")
    print(f"- Public rotunda eligible: {manifest.get('public') is not False}")
    print("No chapter images, upload remotes, or search generation were touched.")
    return written

def safe_cmd(cmd: list[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def run(cmd: list[str], dry: bool, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess[str] | None:
    print("$ " + safe_cmd(cmd))
    if dry:
        return None
    return subprocess.run(cmd, check=check, env=env, text=True)


def verify_rclone_archive(
    archive: Path,
    remote_dir: str,
    env: dict[str, str] | None,
    strong: bool,
    dry: bool,
) -> bool:
    """Verify one uploaded file. Strong mode reads remote bytes back before deletion."""
    if "\n" in archive.name or "\r" in archive.name:
        raise SystemExit(f"Cannot safely verify archive with a newline in its filename: {archive}")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", prefix="animeplex-rclone-files-", delete=True) as listing:
        listing.write(archive.name + "\n")
        listing.flush()
        cmd = [
            "rclone", "check", str(archive.parent), remote_dir,
            "--files-from-raw", listing.name,
            "--one-way",
        ]
        if strong:
            cmd.append("--download")
        print("$ " + safe_cmd(cmd))
        if dry:
            return False
        result = subprocess.run(cmd, env=env, text=True, capture_output=True)
    if result.stdout.strip():
        print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    return result.returncode == 0


def verify_rsync_archive(archive: Path, remote_file: str, dry: bool) -> bool:
    cmd = ["rsync", "--dry-run", "--checksum", "--itemize-changes", str(archive), remote_file]
    print("$ " + safe_cmd(cmd))
    if dry:
        return False
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    changes = result.stdout.strip()
    if changes:
        print(changes)
    return result.returncode == 0 and not changes


def upload_source_archive(
    spec: WorkSpec,
    chapters: list[Chapter],
    work_destination: str,
    args: argparse.Namespace,
    upload_env: dict[str, str] | None,
) -> tuple[bool, bool]:
    archive = spec.original_input
    if not archive or not is_supported_archive(archive):
        return False, False
    if not archive.exists():
        raise SystemExit(f"Source ZIP disappeared before upload: {archive}")

    directory = companion_dir_rel(chapters, args.thumb_location)
    remote_dir = f"{work_destination.rstrip('/')}/{directory}" if directory else work_destination.rstrip("/")
    remote_file = f"{remote_dir}/{archive.name}"
    if args.upload == "rclone":
        run(["rclone", "copyto", str(archive), remote_file, "--progress"], args.dry_run, env=upload_env)
        verified = verify_rclone_archive(
            archive,
            remote_dir,
            upload_env,
            strong=args.delete_local_zip_after_upload,
            dry=args.dry_run,
        )
    else:
        run(["rsync", "-av", "--progress", str(archive), remote_file], args.dry_run)
        verified = verify_rsync_archive(archive, remote_file, args.dry_run)

    if args.dry_run:
        print(f"DRY verify source ZIP at {remote_file}")
        return True, False
    if not verified:
        raise SystemExit(f"ZIP verification failed; local archive was preserved: {archive}")

    verification_kind = "full remote-byte comparison" if args.delete_local_zip_after_upload or args.upload == "rsync" else "remote size/hash comparison"
    print(f"ZIP verified ({verification_kind}): {remote_file}")
    deleted = False
    if args.delete_local_zip_after_upload:
        archive.unlink()
        deleted = True
        print(f"ZIP cleanup: deleted verified local source {archive}")
    return True, deleted


def parse_github_token_answer(answer: str) -> tuple[str, str | None]:
    answer = clean_input(answer)
    if not answer:
        return DEFAULT_TOKEN_ENV, None
    m = re.match(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$", answer)
    if m:
        return m.group(1), clean_input(m.group(2))
    if answer.startswith(("github_pat_", "ghp_", "gho_", "ghu_", "ghs_", "ghr_")):
        return DEFAULT_TOKEN_ENV, answer
    return answer, None


def git_push_with_optional_token(token: str | None, dry: bool) -> None:
    def handle_push(cmd: list[str]) -> None:
        try:
            run(cmd, dry)
        except subprocess.CalledProcessError as e:
            print("Git push failed; local commit remains intact.")
            print("Resolve remote changes, then run:")
            print("git pull --rebase --autostash origin main")
            print("git push origin main")
            raise SystemExit(e.returncode) from None
    if not token:
        handle_push(["git", "push"])
        return
    remote_url = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True).strip()
    if remote_url.startswith("https://github.com/"):
        authed_url = remote_url.replace("https://github.com/", f"https://x-access-token:{quote(token, safe='')}@github.com/", 1)
        print("$ git push origin HEAD  # token hidden")
        if not dry:
            try:
                subprocess.run(["git", "push", authed_url, "HEAD"], check=True)
            except subprocess.CalledProcessError as e:
                print("Git push failed; local commit remains intact.")
                print("Resolve remote changes, then run:")
                print("git pull --rebase --autostash origin main")
                print("git push origin main")
                raise SystemExit(e.returncode) from None
    else:
        handle_push(["git", "push"])


def has_staged_changes() -> bool:
    return subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode != 0


def r2_endpoint(account_id: str, endpoint: str) -> str:
    endpoint = clean_input(endpoint)
    if endpoint:
        return endpoint.rstrip("/")
    account_id = clean_input(account_id)
    return f"https://{account_id}.r2.cloudflarestorage.com" if account_id else ""


def rclone_remote_env(remote_name: str, account_id: str, endpoint: str, access_key_id: str, secret_access_key: str) -> dict[str, str]:
    remote_key = re.sub(r"[^A-Za-z0-9]", "_", remote_name).upper()
    endpoint_value = r2_endpoint(account_id, endpoint)
    if not endpoint_value:
        raise SystemExit("R2 endpoint/account id is required for built-in R2 credentials.")
    if not access_key_id or not secret_access_key:
        raise SystemExit("R2 access key id and secret access key are required for built-in R2 credentials.")
    env = os.environ.copy()
    env[f"RCLONE_CONFIG_{remote_key}_TYPE"] = "s3"
    env[f"RCLONE_CONFIG_{remote_key}_PROVIDER"] = "Cloudflare"
    env[f"RCLONE_CONFIG_{remote_key}_ACCESS_KEY_ID"] = access_key_id
    env[f"RCLONE_CONFIG_{remote_key}_SECRET_ACCESS_KEY"] = secret_access_key
    env[f"RCLONE_CONFIG_{remote_key}_ENDPOINT"] = endpoint_value
    env[f"RCLONE_CONFIG_{remote_key}_ACL"] = "private"
    return env


def deterministic_parent_work_id(slug: str) -> int:
    digest = hashlib.sha256(slug.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big")
    return 1_000_000_000 + (value % 8_999_999_999)


def existing_parent_work_id(data_dir: Path, slug: str) -> int | None:
    manifest = load_json(data_dir / "works" / f"{slug}.json", None)
    if isinstance(manifest, dict) and isinstance(manifest.get("parent_work_id"), int):
        return manifest["parent_work_id"]
    return None


def make_work_spec(root: Path, data_dir: Path, slug: str | None = None, display: str | None = None, parent_work_id: int | None = None, auto_id: bool = False) -> WorkSpec:
    real_slug = slug or slugify_name(root.name)
    real_display = display or display_from_folder_name(root.name)
    real_parent = parent_work_id
    if auto_id and real_parent is None:
        real_parent = existing_parent_work_id(data_dir, real_slug) or deterministic_parent_work_id(real_slug)
    return WorkSpec(root=root, slug=real_slug, display=real_display, parent_work_id=real_parent)


def ingest_one_work(spec: WorkSpec, args: argparse.Namespace) -> tuple[dict[str, Any], list[Path], list[Chapter], dict[str, Any] | None]:
    data = Path(args.repo_data)
    chapters = detect_chapters(spec.root)
    if not chapters and args.dry_run and not args.no_auto_chapter:
        loose = root_page_images(spec.root)
        if loose:
            virtual = spec.root / "chapter_1"
            chapters = [Chapter("chapter_1", virtual, [virtual / p.name for p in loose], len(loose), 3, loose[0].suffix.lower().lstrip("."))]
    if not chapters:
        raise SystemExit(f"No image chapter folders found under {spec.root}")

    normalize_images(chapters, args.resize_width, args.quality, args.convert, args.delete_originals, args.dry_run)

    if args.normalize_page_numbers and not args.no_normalize_page_numbers:
        renumber_pages(chapters, args.dry_run)

    if args.generate_thumb:
        thumb_path = generate_thumb(spec.root, chapters, args.quality, args.dry_run, args.thumb_location)
        print(f"thumb: {thumb_path}")

    written: list[Path] = []
    for ch in chapters:
        ch.pages = len(ch.images)
        ch.padding = max([len(m.group(1)) for p in ch.images if (m := re.match(r"^(\d+)", p.stem))] or [ch.padding])
        ch.extension = ch.images[0].suffix.lower().lstrip(".")
        item = {
            "version": 1,
            "id": f"{spec.slug}-{ch.rel.replace('/', '-')}",
            "parent_work_slug": spec.slug,
            "slug": Path(ch.rel).name,
            "type": "chapter",
            "title": spec.display,
            "subtitle": Path(ch.rel).name.replace("_", " ").title(),
            "base_url": f"{args.cdn_base.rstrip('/')}/{spec.slug}/{ch.rel}",
            "pages": ch.pages,
            "padding": ch.padding,
            "extension": ch.extension,
        }
        if spec.parent_work_id is not None:
            item["parent_work_id"] = spec.parent_work_id
        write_json(ch.path / "item.json", item, args.dry_run)

    existing_manifest = load_json(data / "works" / f"{spec.slug}.json", {})
    manifest = {
        **(existing_manifest if isinstance(existing_manifest, dict) else {}),
        "version": 1,
        "slug": spec.slug,
        "display": spec.display,
        "source": args.source,
        "thumb": thumb_url(args.cdn_base, spec.slug, chapters, args.thumb_location),
        "chapters": [c.rel for c in chapters],
    }
    if args.generate_details:
        manifest["details"] = f"{args.cdn_base.rstrip('/')}/{spec.slug}/{companion_rel(DEFAULT_DETAILS_FILENAME, chapters, args.thumb_location)}"
    if spec.original_input and is_supported_archive(spec.original_input) and args.upload_zip:
        manifest["archive"] = f"{args.cdn_base.rstrip('/')}/{spec.slug}/{companion_rel(spec.original_input.name, chapters, args.thumb_location)}"
    manifest = apply_metadata_options(manifest, args)
    if spec.parent_work_id is not None:
        manifest["parent_work_id"] = spec.parent_work_id
    manifest_path = data / "works" / f"{spec.slug}.json"
    write_json(manifest_path, manifest, args.dry_run)
    written.append(manifest_path)

    ent = derived_metadata(manifest)
    if args.update_fetch and not args.no_fetch_update:
        upsert_pointer(data / "fetch.json", ent, args.dry_run)
        written.append(data / "fetch.json")
    if args.update_rotunda and not args.no_rotunda:
        upsert_pointer(data / "rotunda.json", ent, args.dry_run)
        written.append(data / "rotunda.json")

    details = None
    if args.generate_details:
        details = build_details(spec, manifest, chapters, args)
        details_path = companion_path(spec.root, DEFAULT_DETAILS_FILENAME, chapters, args.thumb_location)
        write_json(details_path, details, args.dry_run)
        print(f"details: {details_path}")

    return manifest, written, chapters, details


def print_work_summary(spec: WorkSpec, chapters: list[Chapter], args: argparse.Namespace) -> None:
    print(
        f"\nDetected work:\n"
        f"- Work: {spec.display}\n"
        f"- Slug: {spec.slug}\n"
        f"- Parent work id: {spec.parent_work_id if spec.parent_work_id is not None else 'none'}\n"
        f"- Chapters: {len(chapters)}\n"
        f"- Pages: {sum(c.pages for c in chapters)}\n"
        f"- Extension: {chapters[0].extension}\n"
        f"- Thumb: {thumb_rel(chapters, args.thumb_location) if args.generate_thumb else 'skipped'}\n"
        f"- Details: {companion_rel(DEFAULT_DETAILS_FILENAME, chapters, args.thumb_location) if args.generate_details else 'skipped'}\n"
        f"- Source ZIP upload: {'yes' if args.upload_zip and spec.original_input and is_supported_archive(spec.original_input) else 'no'}\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest AnimePlex work folders.")
    ap.add_argument("folder", nargs="?", help="Single work folder, or parent folder in --multi mode.")
    ap.add_argument("--multi", action="store_true", help="Treat folder as a parent containing many work folders.")
    ap.add_argument("--slug")
    ap.add_argument("--display")
    ap.add_argument("--source", default="e")
    ap.add_argument("--parent-work-id", type=int)
    ap.add_argument("--auto-parent-work-id", action="store_true", help="Generate/reuse parent_work_id automatically. Deterministic IDs use SHA-256 of the normalized slug; capitalization and slug spelling affect the ID.")
    ap.add_argument("--cdn-base", default=DEFAULT_CDN)
    ap.add_argument("--repo-data", default="src/data")
    ap.add_argument("--resize-width", type=int)
    ap.add_argument("--quality", type=int, default=85)
    ap.add_argument("--convert", choices=["webp"])
    ap.add_argument("--normalize-page-numbers", action="store_true", help="Rename every chapter to 001.ext onward.")
    ap.add_argument("--no-normalize-page-numbers", action="store_true", help="Keep original page filenames.")
    ap.add_argument("--generate-thumb", action="store_true")
    ap.add_argument("--thumb-location", choices=["first-chapter", "work-root"], default=DEFAULT_THUMB_LOCATION)
    ap.add_argument("--delete-originals", action="store_true")
    ap.add_argument("--update-fetch", action="store_true")
    ap.add_argument("--update-rotunda", action="store_true")
    tag_group = ap.add_mutually_exclusive_group()
    tag_group.add_argument("--tags", help="Comma-separated normalized visibility tags. Empty string preserves existing tags.")
    tag_group.add_argument("--clear-tags", action="store_true", help="Explicitly clear all visibility tags.")
    public_group = ap.add_mutually_exclusive_group()
    public_group.add_argument("--public", action="store_true", help="Mark eligible for public rotunda presentation; not access control.")
    public_group.add_argument("--private", action="store_true", help="Hide from rotunda presentation only; search and reader URLs remain valid.")
    ap.add_argument("--metadata-only", action="store_true", help="Update manifest/pointer metadata without inspecting images, upload, or search generation.")
    ap.add_argument("--generate-search", action="store_true")
    ap.add_argument("--upload", choices=["rclone", "rsync"])
    ap.add_argument("--remote")
    zip_upload_group = ap.add_mutually_exclusive_group()
    zip_upload_group.add_argument("--upload-zip", dest="upload_zip", action="store_true", help="Upload each original source ZIP beside thumb.webp (default when uploading).")
    zip_upload_group.add_argument("--no-upload-zip", dest="upload_zip", action="store_false", help="Do not upload original source ZIPs.")
    ap.set_defaults(upload_zip=None)
    ap.add_argument("--delete-local-zip-after-upload", action="store_true", help="Delete a local source ZIP only after strong remote verification. Off by default.")
    details_group = ap.add_mutually_exclusive_group()
    details_group.add_argument("--details-json", dest="generate_details", action="store_true", help="Generate details.json beside thumb.webp (default).")
    details_group.add_argument("--no-details-json", dest="generate_details", action="store_false", help="Skip details.json generation.")
    ap.set_defaults(generate_details=True)
    ap.add_argument("--rehash-zip", action="store_true", help="Ignore the local stat-keyed SHA-256 cache and hash source ZIPs again.")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--no-search", action="store_true")
    ap.add_argument("--no-rotunda", action="store_true")
    ap.add_argument("--no-fetch-update", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--commit-push", action="store_true")
    ap.add_argument("--github-repo")
    ap.add_argument("--github-token-env", default=DEFAULT_TOKEN_ENV)
    ap.add_argument("--github-token", default=HARDCODED_GITHUB_TOKEN or None)
    ap.add_argument("--use-r2-values", action="store_true")
    ap.add_argument("--r2-remote-name", default=HARDCODED_R2_REMOTE_NAME)
    ap.add_argument("--r2-account-id", default=HARDCODED_R2_ACCOUNT_ID)
    ap.add_argument("--r2-endpoint", default=HARDCODED_R2_ENDPOINT)
    ap.add_argument("--r2-access-key-id", default=HARDCODED_R2_ACCESS_KEY_ID)
    ap.add_argument("--r2-secret-access-key", default=HARDCODED_R2_SECRET_ACCESS_KEY)
    ap.add_argument("--r2-bucket", default=HARDCODED_R2_BUCKET)
    ap.add_argument("--r2-prefix", default=HARDCODED_R2_PREFIX)
    ap.add_argument("--keep-extracted", action="store_true", help="Preserve ZIP extraction directories after ingestion.")
    ap.add_argument("--extract-dir", help="User-owned destination for ZIP extraction.")
    ap.add_argument("--overwrite-extracted", action="store_true", help="Allow deleting/replacing a non-empty extraction destination.")
    ap.add_argument("--merge-root-images-into-chapter-one", action="store_true", help="Move root images into chapter_1 when chapter folders also exist.")
    ap.add_argument("--no-auto-chapter", action="store_true", help="Disable automatic chapter_1 creation for loose-image work roots.")
    ap.add_argument("--cleanup-extracted", action="store_true", help="Allow cleanup of user-specified extraction directory after completion.")
    args = ap.parse_args()

    if args.metadata_only:
        metadata_only_update(args)
        return

    guided = not args.folder
    token_value: str | None = args.github_token
    upload_env: dict[str, str] | None = None

    if guided:
        mode = ask("Ingest mode: 1 single work, 2 multiple work folders", "1")
        args.multi = mode.strip() == "2"
        folder_prompt = "Where is the parent folder containing work folders?" if args.multi else "Where is the curated work folder?"
        args.folder = ask(folder_prompt, "~/works")

        data_dir = Path(args.repo_data)
        if not args.multi:
            folder_name = expand_path(args.folder).name
            suggested_slug = slugify_name(folder_name)
            args.slug = ask("Work slug?", suggested_slug)
            suggested_display = display_from_folder_name(folder_name)
            args.display = ask("Display title?", suggested_display)
            p = ask("Parent work id?", "")
            args.parent_work_id = int(p) if p else None
            existing = load_json(data_dir / "works" / f"{args.slug}.json", {})
            current_public = (existing.get("public") is not False) if isinstance(existing, dict) else True
            print(f"Current public rotunda eligibility: {current_public}")
            public_choice = ask("Visibility: keep, public, or private?", "keep").lower()
            if public_choice == "public": args.public = True
            elif public_choice == "private": args.private = True
        else:
            print("Batch mode uses each immediate subfolder name as the display-name source and auto-generates/reuses parent_work_id.")
            args.auto_parent_work_id = True

        existing_tags = normalize_tags(existing.get("tags")) if not args.multi and isinstance(existing, dict) else []
        if not args.multi:
            print(f"Current tags: {existing_tags}")
        tag_prompt = "Tag all works with tags?" if args.multi else "Tag this work with tags?"
        if ask_bool(tag_prompt, False):
            entered_tags = normalize_tags(ask("Tags separated by commas", ",".join(existing_tags)).split(","))
            if entered_tags:
                args.tags = ",".join(entered_tags)
                print(f"Tags to apply: {entered_tags}")
            else:
                print("No valid tags entered; existing tags will be preserved.")

        args.source = ask("Source letter?", args.source or "e")
        args.cdn_base = ask("CDN base URL?", DEFAULT_CDN)
        args.repo_data = ask("Repo data folder?", "src/data")

        if ask_bool("Resize images?", False):
            args.resize_width = int(ask("Width?", "600"))
            args.quality = int(ask("Quality?", "85"))
            args.convert = "webp" if ask_bool("Convert to webp?", False) else None
            args.delete_originals = ask_bool("Delete originals after conversion?", False)

        args.normalize_page_numbers = ask_bool("Normalize/renumber every chapter to 001.ext onward?", True)
        args.generate_thumb = ask_bool("Generate thumb.webp?", True)
        args.thumb_location = DEFAULT_THUMB_LOCATION
        args.update_fetch = ask_bool("Update fetch.json?", True)
        args.update_rotunda = ask_bool("Update rotunda.json?", False)
        args.generate_search = ask_bool("Regenerate search.index.json?", True)

        if ask_bool("Upload to R2/CDN?", False):
            args.upload = ask("Upload method?", "rclone")
            if args.upload == "rclone" and ask_bool("Use pasted/built-in R2 credentials instead of existing rclone config?", False):
                args.use_r2_values = True
                args.r2_remote_name = ask("Temporary rclone remote name", args.r2_remote_name)
                args.r2_account_id = ask("Cloudflare account id", args.r2_account_id)
                args.r2_endpoint = ask("R2 endpoint URL", args.r2_endpoint or r2_endpoint(args.r2_account_id, ""))
                args.r2_bucket = ask("R2 bucket", args.r2_bucket)
                args.r2_prefix = ask("R2 prefix before work slug", args.r2_prefix)
                args.r2_access_key_id = ask("R2 access key id", args.r2_access_key_id)
                args.r2_secret_access_key = ask_secret("R2 secret access key", args.r2_secret_access_key)
                args.remote = f"{args.r2_remote_name}:{args.r2_bucket}/{args.r2_prefix.strip('/')}"
            else:
                args.remote = ask("Upload remote/destination before work slug?", DEFAULT_UPLOAD_REMOTE)

            guided_root = expand_path(args.folder)
            has_zip_inputs = is_supported_archive(guided_root)
            if args.multi and guided_root.is_dir():
                has_zip_inputs = any(is_supported_archive(path) for path in guided_root.iterdir())
            if has_zip_inputs:
                args.upload_zip = ask_bool("Upload each original ZIP beside thumb.webp?", True)
                if args.upload_zip:
                    args.delete_local_zip_after_upload = ask_bool(
                        "Delete each local ZIP after strong remote verification? This may read the uploaded ZIP back",
                        False,
                    )
            else:
                args.upload_zip = False
                print("ZIP upload: skipped because no source ZIP inputs were detected.")

        args.commit_push = ask_bool("Commit/push to GitHub?", False)
        if args.commit_push:
            args.github_repo = ask("GitHub repo? optional; current git origin is used", "")
            token_answer = ask("GitHub token env var OR raw token OR export command", DEFAULT_TOKEN_ENV)
            args.github_token_env, parsed_token = parse_github_token_answer(token_answer)
            token_value = parsed_token or token_value

    if not guided and not args.no_normalize_page_numbers:
        args.normalize_page_numbers = True

    if args.upload_zip is None:
        args.upload_zip = bool(args.upload and not args.no_upload)
    if args.upload_zip and (not args.upload or args.no_upload):
        raise SystemExit("--upload-zip requires --upload rclone|rsync and an enabled upload.")
    if args.delete_local_zip_after_upload and (not args.upload_zip or not args.upload or args.no_upload):
        raise SystemExit("--delete-local-zip-after-upload requires an enabled upload and source ZIP upload.")

    root = expand_path(args.folder)
    data = resolve_repo_path(args.repo_data)
    args.repo_data = str(data)
    prepared_specs: list[WorkSpec] = []
    try:
        if args.multi:
            if root_page_images(root):
                paths = [root]
            else:
                paths = discover_batch_inputs(root)
            if not paths:
                raise SystemExit(f"No work folders or ZIP archives found under {root}")
            for p in paths:
                slug_src = p.stem if is_supported_archive(p) else p.name
                prepared, exdir, temp = prepare_work_root(p, args, slug_src)
                prepared_specs.append(make_work_spec(prepared, data, slugify_name(slug_src), display_from_folder_name(slug_src), auto_id=True))
                prepared_specs[-1].original_input = p
                prepared_specs[-1].extraction_dir = exdir
                prepared_specs[-1].temporary_extraction = temp
            specs = prepared_specs
        else:
            slug_src = args.slug or (root.stem if is_supported_archive(root) else root.name)
            prepared, exdir, temp = prepare_work_root(root, args, slug_src)
            specs = [make_work_spec(prepared, data, args.slug or slugify_name(slug_src), args.display or display_from_folder_name(slug_src), args.parent_work_id, args.auto_parent_work_id)]
            specs[0].original_input = root
            specs[0].extraction_dir = exdir
            specs[0].temporary_extraction = temp
    except BaseException:
        cleanup_extractions(prepared_specs, args)
        raise

    print("\nWorks to ingest:")
    for spec in specs:
        print(f"- {spec.display} -> {spec.slug}")

    all_written: list[Path] = []
    all_summaries: list[tuple[WorkSpec, list[Chapter]]] = []
    for spec in specs:
        print(f"\n=== Ingesting {spec.display} ===")
        _manifest, written, chapters, _details = ingest_one_work(spec, args)
        all_written.extend(written)
        all_summaries.append((spec, chapters))
        print_work_summary(spec, chapters, args)

    if args.generate_search and not args.no_search:
        source_index = data / "search.index.json"
        public_index = repo_root() / "public" / "data" / "search.index.json"
        run([
            sys.executable,
            str(repo_root() / "scripts" / "generate_search.py"),
            "--fetch", str(data / "fetch.json"),
            "--storage", str(data / "storage.json"),
            "--out", str(source_index),
            "--public-out", str(public_index),
            "--source", args.source,
        ], args.dry_run)
        all_written.extend([source_index, public_index])

    uploaded = False
    uploaded_zips = 0
    deleted_local_zips = 0
    if args.upload and not args.no_upload:
        if args.use_r2_values:
            upload_env = rclone_remote_env(args.r2_remote_name, args.r2_account_id, args.r2_endpoint, args.r2_access_key_id, args.r2_secret_access_key)
            if not args.remote:
                args.remote = f"{args.r2_remote_name}:{args.r2_bucket}/{args.r2_prefix.strip('/')}"
        if not args.remote:
            raise SystemExit("--remote is required for upload")
        chapters_by_slug = {spec.slug: chapters for spec, chapters in all_summaries}
        for spec in specs:
            dest = f"{args.remote.rstrip('/')}/{spec.slug}"
            cmd = ["rclone", "copy", str(spec.root), dest, "--progress"] if args.upload == "rclone" else ["rsync", "-av", "--progress", str(spec.root) + "/", dest + "/"]
            run(cmd, args.dry_run, env=upload_env)
            if args.upload_zip:
                zip_uploaded, zip_deleted = upload_source_archive(
                    spec,
                    chapters_by_slug[spec.slug],
                    dest,
                    args,
                    upload_env,
                )
                uploaded_zips += int(zip_uploaded)
                deleted_local_zips += int(zip_deleted)
        uploaded = True

    if args.commit_push:
        token = token_value or os.getenv(args.github_token_env or DEFAULT_TOKEN_ENV) or HARDCODED_GITHUB_TOKEN or None
        if not token:
            raise SystemExit(f"GitHub token not found. Set {args.github_token_env}=... or paste the raw token when prompted.")
        paths = sorted({str(p) for p in all_written})
        run(["git", "add", *paths], args.dry_run)
        if args.dry_run or has_staged_changes():
            msg = f"Add AnimePlex works batch ({len(specs)})" if len(specs) > 1 else f"Add AnimePlex work {specs[0].display}"
            run(["git", "commit", "-m", msg], args.dry_run)
            git_push_with_optional_token(token, args.dry_run)
        else:
            print("GitHub: no staged data changes to commit; skipping commit/push.")

    cleanup_extractions(specs, args)

    print("\nAnimePlex ingest complete.")
    print(f"Works: {len(specs)}")
    print(f"Uploaded: {'yes' if uploaded else 'skipped'}")
    print(f"Source ZIPs uploaded: {uploaded_zips}")
    print(f"Verified local ZIPs deleted: {deleted_local_zips}")
    if args.generate_search and not args.no_search:
        print("Search indexes updated:")
        print(f"- {data / 'search.index.json'}")
        print(f"- {repo_root() / 'public' / 'data' / 'search.index.json'}")
    for spec, chapters in all_summaries:
        manifest = load_json(data / "works" / f"{spec.slug}.json", {})
        print(f"- {spec.display}: {len(chapters)} chapters, {sum(c.pages for c in chapters)} pages, slug={spec.slug}, public={manifest.get('public') is not False}")


if __name__ == "__main__":
    main()
