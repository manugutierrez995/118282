#!/usr/bin/env python3
"""Incremental, dependency-free Tkinter navigator for R2 work folders.

Canonical local database: r2-audit-output/search.index.jsonl

Normal startup:
1. Read every complete JSONL line already present.
2. Ignore/truncate a malformed trailing fragment left by Ctrl+C.
3. Ask R2 only for direct folder names under the configured works prefix.
4. Inspect only newly discovered folders.
5. Append one complete JSON line per new or changed work.
6. Open the Tkinter navigator.

Existing work folders are not reinspected unless explicitly refreshed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

DEFAULT_REMOTE = "animeplex.lol:extended/works"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "r2-audit-output"
ARCHIVE_EXTS = {".zip", ".cbz"}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def natural_key(value: str) -> list[Any]:
    return [int(x) if x.isdigit() else x.casefold() for x in re.split(r"(\d+)", value)]


def quote(value: str) -> str:
    import shlex
    return shlex.quote(value)


def run_capture(cmd: list[str]) -> str:
    print("$ " + " ".join(quote(x) for x in cmd))
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    except FileNotFoundError:
        raise SystemExit("rclone was not found in PATH.")
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout.rstrip())
        if exc.stderr:
            print(exc.stderr.rstrip(), file=sys.stderr)
        raise SystemExit(exc.returncode) from None
    return result.stdout


def run(cmd: list[str]) -> None:
    print("$ " + " ".join(quote(x) for x in cmd))
    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError:
        raise SystemExit("rclone was not found in PATH.")


def remote_join(remote: str, relative: str) -> str:
    return f"{remote.rstrip('/')}/{relative.lstrip('/')}"


def index_path(output_dir: Path) -> Path:
    return output_dir / "search.index.jsonl"


def load_index(path: Path, repair_tail: bool = True) -> dict[str, dict[str, Any]]:
    """Load complete lines. Last record for a work wins.

    A malformed final line is treated as an interrupted append and removed.
    A malformed non-final line is skipped but preserved, with a warning.
    """
    records: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return records
    data = path.read_bytes()
    lines = data.splitlines(keepends=True)
    valid_end = 0
    malformed_tail = False
    for number, raw in enumerate(lines, start=1):
        complete = raw.endswith((b"\n", b"\r"))
        stripped = raw.strip()
        if not stripped:
            valid_end += len(raw)
            continue
        try:
            row = json.loads(stripped.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            is_last = number == len(lines)
            if is_last and not complete:
                malformed_tail = True
                print(f"Ignoring interrupted trailing JSONL fragment at line {number}: {exc}")
                break
            print(f"Warning: skipping malformed complete JSONL line {number}: {exc}", file=sys.stderr)
            valid_end += len(raw)
            continue
        valid_end += len(raw)
        if isinstance(row, dict) and row.get("name"):
            records[str(row["name"])] = row
    if malformed_tail and repair_tail:
        with path.open("r+b") as handle:
            handle.truncate(valid_end)
        print(f"Repaired interrupted tail in {path}")
    return records


def append_record(path: Path, row: dict[str, Any]) -> None:
    """Append exactly one fsynced line so Ctrl+C cannot damage earlier rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8", newline="") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def list_direct_work_names(remote: str) -> list[str]:
    raw = run_capture(["rclone", "lsf", remote, "--dirs-only", "--max-depth", "1"])
    names = []
    for line in raw.splitlines():
        name = line.strip().replace("\\", "/").strip("/")
        if name and "/" not in name:
            names.append(name)
    return sorted(set(names), key=natural_key)


def list_structural_files(remote: str, work_name: str) -> list[dict[str, Any]]:
    raw = run_capture([
        "rclone", "lsjson", remote_join(remote, work_name),
        "--recursive", "--files-only", "--no-mimetype",
        "--include", "**/item.json",
        "--include", "**/details.json",
        "--include", "**/tags.json",
        "--include", "**/thumb.webp",
        "--include", "**/*.zip",
        "--include", "**/*.cbz",
        "--exclude", "*",
    ])
    rows = json.loads(raw or "[]")
    return [row for row in rows if isinstance(row, dict)]


def copy_remote_to_path(remote: str, relative: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    run(["rclone", "copyto", remote_join(remote, relative), str(destination)])


def read_remote_json(remote: str, relative: str) -> Any:
    raw = run_capture(["rclone", "cat", remote_join(remote, relative)])
    return json.loads(raw)


def derive_manifest(data: Any, item_path: str) -> dict[str, Any]:
    result: dict[str, Any] = {"item_path": item_path, "valid": False}
    if not isinstance(data, dict):
        result["error"] = "item.json is not an object"
        return result
    base_url = str(data.get("base_url") or data.get("baseUrl") or "").rstrip("/")
    extension = str(data.get("extension") or data.get("ext") or "webp").lstrip(".")
    try:
        pages = int(data.get("pages") or data.get("page_count") or data.get("pageCount"))
        padding = int(data.get("padding", 3))
    except (TypeError, ValueError):
        result["error"] = "invalid pages or padding"
        return result
    if not base_url or pages < 1 or padding < 1:
        result["error"] = "missing base_url or invalid numeric values"
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
    })
    return result


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


def normalize_tags_file(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        data = {}
    return {
        "schema_version": 1,
        "public": normalize_tag_tree(data.get("public")),
        "private": normalize_tag_tree(data.get("private")),
    }


def scan_work(remote: str, work_name: str) -> dict[str, Any]:
    structural = list_structural_files(remote, work_name)
    paths = [str(row.get("Path") or row.get("Name") or "").replace("\\", "/").lstrip("/") for row in structural]
    paths = [f"{work_name}/{p}" for p in paths if p]
    item_paths = sorted([p for p in paths if PurePosixPath(p).name.casefold() == "item.json"], key=natural_key)
    details_paths = sorted([p for p in paths if PurePosixPath(p).name.casefold() == "details.json"], key=natural_key)
    tag_paths = sorted([p for p in paths if PurePosixPath(p).name.casefold() == "tags.json"], key=natural_key)
    thumb_paths = sorted([p for p in paths if PurePosixPath(p).name.casefold() == "thumb.webp"], key=natural_key)
    archives = sorted([p for p in paths if PurePosixPath(p).suffix.casefold() in ARCHIVE_EXTS], key=natural_key)

    manifests = []
    for item_path in item_paths:
        try:
            manifests.append(derive_manifest(read_remote_json(remote, item_path), item_path))
        except Exception as exc:
            manifests.append({"item_path": item_path, "valid": False, "error": str(exc)})

    tags = default_tags()
    if tag_paths:
        try:
            tags = normalize_tags_file(read_remote_json(remote, tag_paths[0]))
        except Exception as exc:
            tags["load_error"] = str(exc)

    status = "complete"
    if any(not m.get("valid") for m in manifests):
        status = "unresolved"
    elif not details_paths or not thumb_paths or not item_paths:
        status = "incomplete"

    row = {
        "schema_version": 3,
        "name": work_name,
        "remote_path": remote_join(remote, work_name),
        "status": status,
        "details_paths": details_paths,
        "item_json_paths": item_paths,
        "thumb_paths": thumb_paths,
        "archive_paths": archives,
        "tags_path": tag_paths[0] if tag_paths else f"{work_name}/tags.json",
        "has_details_json": bool(details_paths),
        "has_thumb_webp": bool(thumb_paths),
        "item_json_count": len(item_paths),
        "archive_count": len(archives),
        "zip_count": sum(p.casefold().endswith(".zip") for p in archives),
        "cbz_count": sum(p.casefold().endswith(".cbz") for p in archives),
        "manifests": manifests,
        "tags": tags,
        "scanned_at": utc_iso(),
    }
    row["search_text"] = build_search_text(row)
    return row


def flatten_tag_paths(tree: dict[str, Any], prefix: tuple[str, ...] = ()) -> list[str]:
    out: list[str] = []
    for key in sorted(tree, key=natural_key):
        path = prefix + (key,)
        out.append(" > ".join(path))
        out.extend(flatten_tag_paths(tree[key], path))
    return out


def build_search_text(row: dict[str, Any]) -> str:
    values: list[str] = [str(row.get("name") or ""), str(row.get("remote_path") or ""), str(row.get("status") or "")]
    for key in ("details_paths", "item_json_paths", "thumb_paths", "archive_paths"):
        values.extend(str(x) for x in row.get(key) or [])
    for manifest in row.get("manifests") or []:
        values.extend(str(manifest.get(key) or "") for key in ("item_path", "base_url", "url_template", "first_page_url", "last_page_url", "error"))
    tags = normalize_tags_file(row.get("tags"))
    values.extend(flatten_tag_paths(tags["public"]))
    values.extend(flatten_tag_paths(tags["private"]))
    return " ".join(values).casefold()


def incremental_sync(remote: str, path: Path, refresh_all: bool = False, refresh_names: list[str] | None = None) -> dict[str, dict[str, Any]]:
    records = load_index(path)
    remote_names = list_direct_work_names(remote)
    requested = set(refresh_names or [])
    if refresh_all:
        to_scan = remote_names
    elif requested:
        to_scan = [name for name in remote_names if name in requested]
    else:
        to_scan = [name for name in remote_names if name not in records]
    print(f"R2 reports {len(remote_names)} work folders; {len(to_scan)} need inspection.")
    for number, name in enumerate(to_scan, start=1):
        print(f"[{number}/{len(to_scan)}] {name}")
        row = scan_work(remote, name)
        append_record(path, row)
        records[name] = row
    return records


def add_tag_path(tree: dict[str, Any], path_text: str) -> None:
    parts = [part.strip() for part in re.split(r"\s*>\s*", path_text) if part.strip()]
    node = tree
    for part in parts:
        node = node.setdefault(part, {})


def delete_tag_path(tree: dict[str, Any], parts: list[str]) -> None:
    if not parts:
        return
    node = tree
    parents: list[tuple[dict[str, Any], str]] = []
    for part in parts:
        child = node.get(part)
        if not isinstance(child, dict):
            return
        parents.append((node, part))
        node = child
    parent, key = parents[-1]
    parent.pop(key, None)


def launch_gui(remote: str, path: Path, output_dir: Path) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox, simpledialog, ttk
    except ImportError as exc:
        raise SystemExit("Tkinter is unavailable. Install python3-tk.") from exc

    records_map = load_index(path)
    rows = list(records_map.values())
    cache_dir = output_dir / "thumb-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    root = tk.Tk()
    root.title("R2 Work Navigator")
    root.geometry("1480x820")
    root.minsize(980, 560)

    query_var = tk.StringVar()
    count_var = tk.StringVar()
    status_var = tk.StringVar(value=f"Index: {path}")

    toolbar = ttk.Frame(root, padding=10)
    toolbar.pack(fill="x")
    ttk.Label(toolbar, text="Search").pack(side="left")
    search = ttk.Entry(toolbar, textvariable=query_var)
    search.pack(side="left", fill="x", expand=True, padx=8)

    body = ttk.Panedwindow(root, orient="horizontal")
    body.pack(fill="both", expand=True, padx=10, pady=(0, 10))
    left = ttk.Frame(body)
    middle = ttk.Frame(body)
    right = ttk.Frame(body)
    body.add(left, weight=2)
    body.add(middle, weight=3)
    body.add(right, weight=2)

    ttk.Label(left, textvariable=count_var).pack(anchor="w", pady=(0, 5))
    works = ttk.Treeview(left, columns=("state",), show="tree headings", selectmode="browse")
    works.heading("#0", text="Work")
    works.heading("state", text="State")
    works.column("#0", width=300, stretch=True)
    works.column("state", width=90, stretch=False)
    sy = ttk.Scrollbar(left, orient="vertical", command=works.yview)
    works.configure(yscrollcommand=sy.set)
    works.pack(side="left", fill="both", expand=True)
    sy.pack(side="right", fill="y")

    details = tk.Text(middle, wrap="word", state="disabled", padx=10, pady=10)
    details.pack(fill="both", expand=True)

    tags_box = ttk.LabelFrame(middle, text="tags.json", padding=8)
    tags_box.pack(fill="both", expand=False, pady=(8, 0))
    tag_panes = ttk.Panedwindow(tags_box, orient="horizontal")
    tag_panes.pack(fill="both", expand=True)
    public_frame = ttk.LabelFrame(tag_panes, text="Public tags")
    private_frame = ttk.LabelFrame(tag_panes, text="Private tags")
    tag_panes.add(public_frame, weight=1)
    tag_panes.add(private_frame, weight=1)

    def make_tag_tree(parent: Any) -> Any:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, show="tree")
        sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return tree

    public_tree = make_tag_tree(public_frame)
    private_tree = make_tag_tree(private_frame)
    public_buttons = ttk.Frame(public_frame); public_buttons.pack(fill="x")
    private_buttons = ttk.Frame(private_frame); private_buttons.pack(fill="x")

    ttk.Label(right, text="Thumbnail cache").pack(anchor="w")
    thumb_label = ttk.Label(right, text="Select a work, then request its thumbnail.", anchor="center", justify="center")
    thumb_label.pack(fill="both", expand=True, pady=8)
    thumb_path_var = tk.StringVar()
    ttk.Label(right, textvariable=thumb_path_var, wraplength=320).pack(fill="x")

    footer = ttk.Label(root, textvariable=status_var, padding=(10, 0, 10, 8))
    footer.pack(fill="x")

    visible: list[dict[str, Any]] = []
    selected_row: dict[str, Any] | None = None
    current_image: Any = None

    def set_details(text: str) -> None:
        details.configure(state="normal")
        details.delete("1.0", "end")
        details.insert("1.0", text)
        details.configure(state="disabled")

    def fill_tag_tree(widget: Any, tree_data: dict[str, Any]) -> None:
        widget.delete(*widget.get_children())
        def visit(parent_id: str, node: dict[str, Any]) -> None:
            for key in sorted(node, key=natural_key):
                item = widget.insert(parent_id, "end", text=key, open=True)
                visit(item, node[key])
        visit("", tree_data)

    def tree_item_path(widget: Any, item: str) -> list[str]:
        parts: list[str] = []
        while item:
            parts.append(str(widget.item(item, "text")))
            item = widget.parent(item)
        return list(reversed(parts))

    def display_row(row: dict[str, Any]) -> None:
        nonlocal selected_row
        selected_row = row
        lines = [
            str(row.get("name") or ""),
            "=" * len(str(row.get("name") or "")),
            f"Status: {row.get('status', 'unknown')}",
            f"Remote: {row.get('remote_path', '')}",
            f"Last inspected: {row.get('scanned_at', 'unknown')}",
            "",
            f"details.json: {'yes' if row.get('has_details_json') else 'no'}",
            f"thumb.webp: {'yes' if row.get('has_thumb_webp') else 'no'}",
            f"item.json files: {row.get('item_json_count', 0)}",
            f"archives: {row.get('archive_count', 0)}",
        ]
        for manifest in row.get("manifests") or []:
            lines += ["", f"Manifest: {manifest.get('item_path', '')}"]
            if manifest.get("valid"):
                lines += [
                    f"Pages: {manifest.get('pages')}",
                    f"Template: {manifest.get('url_template')}",
                    f"First: {manifest.get('first_page_url')}",
                    f"Last: {manifest.get('last_page_url')}",
                ]
            else:
                lines.append(f"Error: {manifest.get('error', 'unresolved')}")
        set_details("\n".join(lines))
        tags = normalize_tags_file(row.get("tags"))
        row["tags"] = tags
        fill_tag_tree(public_tree, tags["public"])
        fill_tag_tree(private_tree, tags["private"])
        show_cached_thumb(row)

    def refresh_list(*_args: Any) -> None:
        terms = [x.casefold() for x in query_var.get().split() if x.strip()]
        visible[:] = [row for row in rows if all(term in build_search_text(row) for term in terms)]
        visible.sort(key=lambda x: natural_key(str(x.get("name") or "")))
        works.delete(*works.get_children())
        for row in visible:
            works.insert("", "end", text=row.get("name", ""), values=(row.get("status", ""),))
        count_var.set(f"{len(visible)} / {len(rows)} works")
        if visible:
            first = works.get_children()[0]
            works.selection_set(first); works.focus(first); works.see(first)
            display_row(visible[0])
        else:
            set_details("No matching works.")

    def on_select(_event: Any = None) -> None:
        sel = works.selection()
        if not sel:
            return
        idx = works.index(sel[0])
        if 0 <= idx < len(visible):
            display_row(visible[idx])

    def cache_paths(row: dict[str, Any]) -> tuple[Path, Path]:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(row.get("name") or "work"))
        return cache_dir / f"{safe}.webp", cache_dir / f"{safe}.png"

    def convert_webp(src: Path, dst: Path) -> bool:
        for cmd in (["magick", str(src), str(dst)], ["convert", str(src), str(dst)], ["ffmpeg", "-y", "-i", str(src), str(dst)]):
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
        if not source:
            current_image = None
            thumb_label.configure(image="", text="Thumbnail not loaded.")
            thumb_path_var.set("")
            return
        try:
            image = tk.PhotoImage(file=str(source))
        except tk.TclError:
            if source.suffix.casefold() == ".webp" and convert_webp(source, png):
                try:
                    image = tk.PhotoImage(file=str(png))
                    source = png
                except tk.TclError:
                    thumb_label.configure(image="", text=f"Cached at:\n{webp}\n\nInstall ImageMagick or ffmpeg to display WebP.")
                    thumb_path_var.set(str(webp))
                    return
            else:
                thumb_label.configure(image="", text=f"Cached at:\n{source}\n\nTk cannot display this WebP.")
                thumb_path_var.set(str(source))
                return
        max_w, max_h = 360, 620
        factor = max(1, (max(image.width() // max_w, image.height() // max_h)))
        if factor > 1:
            image = image.subsample(factor, factor)
        current_image = image
        thumb_label.configure(image=image, text="")
        thumb_path_var.set(str(source))

    def load_thumb(row: dict[str, Any]) -> None:
        if not row.get("thumb_paths"):
            messagebox.showinfo("No thumbnail", "This work has no discovered thumb.webp.")
            return
        webp, _png = cache_paths(row)
        if not webp.exists():
            copy_remote_to_path(remote, row["thumb_paths"][0], webp)
        show_cached_thumb(row)

    def load_selected_thumb() -> None:
        if selected_row:
            load_thumb(selected_row)

    def load_all_thumbs() -> None:
        missing = [row for row in rows if row.get("thumb_paths") and not cache_paths(row)[0].exists()]
        for number, row in enumerate(missing, start=1):
            status_var.set(f"Loading thumbnail {number}/{len(missing)}: {row.get('name')}")
            root.update_idletasks()
            try:
                copy_remote_to_path(remote, row["thumb_paths"][0], cache_paths(row)[0])
            except Exception as exc:
                print(f"Thumbnail failed for {row.get('name')}: {exc}", file=sys.stderr)
        status_var.set(f"Thumbnail cache complete: {len(missing)} downloaded.")
        if selected_row:
            show_cached_thumb(selected_row)

    ttk.Button(right, text="Load selected thumbnail", command=load_selected_thumb).pack(fill="x", pady=2)
    ttk.Button(right, text="Load all thumbnails", command=load_all_thumbs).pack(fill="x", pady=2)

    def save_tags(row: dict[str, Any]) -> None:
        tags = normalize_tags_file(row.get("tags"))
        relative = str(row.get("tags_path") or f"{row['name']}/tags.json")
        with tempfile.TemporaryDirectory(prefix="r2-tags-") as tmp:
            local = Path(tmp) / "tags.json"
            local.write_text(json.dumps(tags, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            run(["rclone", "copyto", str(local), remote_join(remote, relative)])
        row["tags"] = tags
        row["tags_path"] = relative
        row["search_text"] = build_search_text(row)
        row["tags_updated_at"] = utc_iso()
        append_record(path, row)
        status_var.set(f"Saved {relative}")

    def add_tag(group: str) -> None:
        if not selected_row:
            return
        value = simpledialog.askstring("Add nested tag", "Tag path, for example: this > that > deeper", parent=root)
        if not value:
            return
        tags = normalize_tags_file(selected_row.get("tags"))
        add_tag_path(tags[group], value)
        selected_row["tags"] = tags
        save_tags(selected_row)
        display_row(selected_row)

    def remove_tag(group: str, widget: Any) -> None:
        if not selected_row or not widget.selection():
            return
        parts = tree_item_path(widget, widget.selection()[0])
        tags = normalize_tags_file(selected_row.get("tags"))
        delete_tag_path(tags[group], parts)
        selected_row["tags"] = tags
        save_tags(selected_row)
        display_row(selected_row)

    ttk.Button(public_buttons, text="+ Add path", command=lambda: add_tag("public")).pack(side="left")
    ttk.Button(public_buttons, text="Remove", command=lambda: remove_tag("public", public_tree)).pack(side="left", padx=4)
    ttk.Button(private_buttons, text="+ Add path", command=lambda: add_tag("private")).pack(side="left")
    ttk.Button(private_buttons, text="Remove", command=lambda: remove_tag("private", private_tree)).pack(side="left", padx=4)

    def refresh_selected() -> None:
        nonlocal rows
        if not selected_row:
            return
        name = str(selected_row["name"])
        row = scan_work(remote, name)
        append_record(path, row)
        records_map[name] = row
        rows = list(records_map.values())
        status_var.set(f"Refreshed {name}")
        refresh_list()

    def check_new() -> None:
        nonlocal rows, records_map
        records_map = incremental_sync(remote, path)
        rows = list(records_map.values())
        status_var.set("Checked R2 for newly uploaded works.")
        refresh_list()

    ttk.Button(toolbar, text="Check for new works", command=check_new).pack(side="left", padx=4)
    ttk.Button(toolbar, text="Refresh selected", command=refresh_selected).pack(side="left", padx=4)

    query_var.trace_add("write", refresh_list)
    works.bind("<<TreeviewSelect>>", on_select)
    search.focus_set()
    refresh_list()
    root.mainloop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incremental R2 work navigator with Tkinter GUI.")
    parser.add_argument("--remote", default=DEFAULT_REMOTE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-gui", action="store_true")
    parser.add_argument("--refresh-all", action="store_true", help="Reinspect every existing work.")
    parser.add_argument("--refresh", action="append", default=[], metavar="WORK", help="Reinspect one named work; repeatable.")
    parser.add_argument("--no-sync", action="store_true", help="Open the existing index without checking R2.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.expanduser().resolve()
    path = index_path(output_dir)
    if args.no_sync:
        load_index(path)
    else:
        incremental_sync(args.remote, path, refresh_all=args.refresh_all, refresh_names=args.refresh)
    if not args.no_gui:
        launch_gui(args.remote, path, output_dir)
    else:
        print(path)


if __name__ == "__main__":
    main()
