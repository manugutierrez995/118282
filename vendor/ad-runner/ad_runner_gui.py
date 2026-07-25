#!/usr/bin/env python3
"""Tkinter control panel and workbook helpers for Ad Runner."""
from __future__ import annotations

import json, os, re, shutil, subprocess, tempfile, threading, webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from placement_vocabulary import CANONICAL_PLACEMENTS

COLUMNS = ["block_type","block_id","field","value","aesthetic","maximum_visibility","maximum_clicks","maximum_revenue","notes"]
DEFAULT_WORKBOOK = Path("data/workbooks/ad-runner.xlsx")
MODES = ["aesthetic","maximum-visibility","maximum-clicks","maximum-revenue"]
AD_NAMES = list(CANONICAL_PLACEMENTS)
SIZES = ["728x90","970x90","300x250","300x600","160x600","320x50","320x100","Custom width and height"]
MAPPINGS = {name: (values[0], values[1]) for name, values in CANONICAL_PLACEMENTS.items()}
RESERVED = {"_README", "_TEMPLATE", "_GLOBAL"}


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.strip().lower()).strip("-")
    if not slug:
        raise ValueError("Text must contain at least one letter or number")
    return slug


def parse_dimensions(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"\s*(\d{1,5})\s*x\s*(\d{1,5})\s*", value or "", re.I)
    if not match:
        raise ValueError("Size must be WIDTHxHEIGHT, for example 728x90")
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0 or width > 10000 or height > 10000:
        raise ValueError("Size dimensions must be between 1 and 10000 pixels")
    return width, height


def _blank_row(block_type: str, block_id: str, field: str, value: object) -> dict:
    row = {c: "" for c in COLUMNS}
    row.update({"block_type": block_type, "block_id": block_id, "field": field, "value": str(value)})
    for mode in ["aesthetic", "maximum_visibility", "maximum_clicks", "maximum_revenue"]:
        row[mode] = "on"
    return row


def load_workbook(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {"SheetNames": [], "Sheets": {}}
    with p.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict) or not isinstance(data.get("SheetNames"), list) or not isinstance(data.get("Sheets"), dict):
        raise ValueError("Workbook is not in the Ad Runner JSON workbook format")
    return data


def save_workbook(path: str | Path, workbook: dict) -> Path | None:
    if not isinstance(workbook.get("SheetNames"), list) or not isinstance(workbook.get("Sheets"), dict):
        raise ValueError("Refusing to save malformed workbook")
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if p.exists():
        backup = p.with_suffix(p.suffix + ".bak")
        shutil.copy2(p, backup)
    fd, tmp = tempfile.mkstemp(prefix=p.name + ".", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(workbook, fh, indent=2)
            fh.write("\n")
        os.replace(tmp, p)
    except Exception:
        try: os.unlink(tmp)
        except OSError: pass
        raise
    return backup


def _rows_for_sheet(sheet: dict) -> list[dict]:
    rows = sheet.setdefault("rows", [])
    sheet["header"] = COLUMNS
    sheet.pop("aoa", None)
    return rows


def list_sites(workbook: dict) -> list[str]:
    return [name for name in workbook.get("SheetNames", []) if name not in RESERVED]


def ensure_site_sheet(workbook: dict, site_id: str, mode: str = "maximum-revenue") -> list[dict]:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,253}", site_id or ""):
        raise ValueError("Website ID may only contain letters, numbers, dots, underscores, and hyphens")
    sheets = workbook.setdefault("Sheets", {})
    names = workbook.setdefault("SheetNames", [])
    if site_id not in sheets:
        sheets[site_id] = {"header": COLUMNS, "rows": []}
        names.append(site_id)
    rows = _rows_for_sheet(sheets[site_id])
    upsert_row(rows, "SITE", "site", "site_id", site_id)
    upsert_row(rows, "SITE", "site", "enabled", "true")
    upsert_row(rows, "SITE", "site", "default_mode", mode)
    return rows


def upsert_row(rows: list[dict], block_type: str, block_id: str, field: str, value: object) -> None:
    matches = [r for r in rows if r.get("block_type") == block_type and r.get("block_id") == block_id and r.get("field") == field]
    if matches:
        matches[0]["value"] = str(value)
        for duplicate in matches[1:]: rows.remove(duplicate)
    else:
        rows.append(_blank_row(block_type, block_id, field, value))


def add_or_update_exoclick_ad(workbook: dict, site_id: str, ad_name: str, size: str, anchor: str, markup: str, mode: str = "maximum-revenue") -> dict:
    if mode not in MODES: raise ValueError("Invalid optimization mode")
    if not markup.strip(): raise ValueError("ExoClick code is required")
    if not re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", anchor or ""): raise ValueError("Anchor contains invalid characters")
    width, height = parse_dimensions(size)
    placement_id = slugify(ad_name)
    unit_id = f"{placement_id}-exoclick"
    rows = ensure_site_sheet(workbook, site_id, mode)
    for f, v in {"adapter":"exoclick", "enabled":"true"}.items(): upsert_row(rows,"NETWORK","exoclick",f,v)
    unit = {"network":"exoclick","format":"banner","width":width,"height":height,"markup":markup,"assume_filled_on_mount":"true","mount_grace_ms":"750"}
    for f, v in unit.items(): upsert_row(rows,"UNIT",unit_id,f,v)
    placement = {"anchor":anchor,"candidates":unit_id,"priority":"100","timeout_ms":"5000","enabled":"true"}
    for f, v in placement.items(): upsert_row(rows,"PLACEMENT",placement_id,f,v)
    return {"site_id": site_id, "anchor": anchor, "placement_id": placement_id, "unit_id": unit_id, "width": width, "height": height}


def website_code(site_id: str, anchor: str, base="http://localhost:4178") -> str:
    return f'<script\n  src="{base}/v1/ad-runner.min.js"\n  data-ad-runner-site="{site_id}"\n  data-ad-runner-base="{base}"\n  defer>\n</script>\n\n<div data-ad-runner-slot="{anchor}"></div>'

class App:
    def __init__(self, root):
        self.root=root; self.server=None; root.title("Ad Runner v0.3 ExoClick Control Panel")
        self.workbook=tk.StringVar(value=str(DEFAULT_WORKBOOK)); self.site=tk.StringVar(); self.mode=tk.StringVar(value="maximum-revenue"); self.network=tk.StringVar(value="ExoClick"); self.ad=tk.StringVar(value="Top Banner"); self.size=tk.StringVar(value="728x90"); self.anchor=tk.StringVar(value="top-banner"); self.code=tk.StringVar()
        self.build()
        self.refresh_sites()
    def build(self):
        frm=ttk.Frame(self.root,padding=8); frm.grid(sticky="nsew"); self.root.columnconfigure(0,weight=1); self.root.rowconfigure(0,weight=1)
        labels=[("Workbook",self.workbook), ("Website",self.site), ("Optimization",self.mode), ("Network",self.network), ("Ad name",self.ad), ("Size",self.size), ("Page anchor",self.anchor)]
        for i,(lab,var) in enumerate(labels):
            ttk.Label(frm,text=lab).grid(row=i,column=0,sticky="w")
            if lab=="Workbook": ttk.Entry(frm,textvariable=var,width=55).grid(row=i,column=1,sticky="ew"); ttk.Button(frm,text="Browse",command=self.browse).grid(row=i,column=2)
            elif lab=="Website": self.sitebox=ttk.Combobox(frm,textvariable=var); self.sitebox.grid(row=i,column=1,columnspan=2,sticky="ew")
            elif lab=="Optimization": ttk.Combobox(frm,textvariable=var,values=MODES,state="readonly").grid(row=i,column=1,columnspan=2,sticky="ew")
            elif lab=="Network": ttk.Combobox(frm,textvariable=var,values=["ExoClick"],state="readonly").grid(row=i,column=1,columnspan=2,sticky="ew")
            elif lab=="Ad name": cb=ttk.Combobox(frm,textvariable=var,values=AD_NAMES); cb.grid(row=i,column=1,columnspan=2,sticky="ew"); cb.bind("<<ComboboxSelected>>",self.suggest)
            elif lab=="Size": ttk.Combobox(frm,textvariable=var,values=SIZES).grid(row=i,column=1,columnspan=2,sticky="ew")
            else: ttk.Entry(frm,textvariable=var).grid(row=i,column=1,columnspan=2,sticky="ew")
        ttk.Label(frm,text="ExoClick code").grid(row=7,column=0,sticky="nw"); self.markup=ScrolledText(frm,height=8); self.markup.grid(row=7,column=1,columnspan=2,sticky="nsew")
        btns=[("Initialize Workbook",self.init_wb),("Import Simple Partner CSV",self.import_simple_csv),("Save / Update Ad",self.save_ad),("Validate",lambda:self.cmd(["validate",self.workbook.get()])),("Publish",lambda:self.cmd(["publish",self.workbook.get()])),("Status",lambda:self.cmd(["status"])),("Build Ad Runner",lambda:self.cmd_shell("npm install && npm run build")),("Start Server",self.start_server),("Stop Server",self.stop_server),("Open Admin",lambda:webbrowser.open("http://localhost:4178/admin")),("Open Demo",lambda:webbrowser.open("http://localhost:4178/demo")),("Copy Website Code",self.copy_code)]
        bar=ttk.Frame(frm); bar.grid(row=8,column=0,columnspan=3,sticky="ew")
        for i,(t,c) in enumerate(btns): ttk.Button(bar,text=t,command=c).grid(row=i//4,column=i%4,sticky="ew")
        ttk.Label(frm,text="Website code / activity log").grid(row=9,column=0,sticky="nw"); self.log=ScrolledText(frm,height=12); self.log.grid(row=9,column=1,columnspan=2,sticky="nsew")
        frm.columnconfigure(1,weight=1); frm.rowconfigure(7,weight=1); frm.rowconfigure(9,weight=1)
    def suggest(self,_=None):
        a,s=MAPPINGS.get(self.ad.get(),("custom","300x250")); self.anchor.set(a); self.size.set(s)
    def browse(self):
        p=filedialog.askopenfilename(filetypes=[("Ad Runner workbook","*.xlsx *.json"),("All files","*")]);
        if p: self.workbook.set(p); self.refresh_sites()
    def refresh_sites(self):
        try:
            sites=list_sites(load_workbook(self.workbook.get())); self.sitebox["values"]=sites
            if sites and not self.site.get(): self.site.set(sites[0])
        except Exception as e: self.write(f"Could not load sites: {e}\n")
    def write(self,t): self.log.insert("end",t); self.log.see("end")
    def init_wb(self): self.cmd(["init"])
    def import_simple_csv(self):
        csv_path=filedialog.askopenfilename(title="Select Simple Partner CSV",initialdir="data/imports",filetypes=[("CSV files","*.csv"),("All files","*")])
        if not csv_path: return
        try:
            from simple_partner_csv import parse_simple_csv, import_plan, import_into_workbook
            blocks=parse_simple_csv(csv_path); plan=import_plan(blocks,load_workbook(self.workbook.get()))
        except Exception as e:
            messagebox.showerror("CSV import failed",str(e)); self.write(f"ERROR: {e}\n"); return
        win=tk.Toplevel(self.root); win.title("Simple Partner CSV Import Preview"); win.geometry("850x600")
        ttk.Label(win,text="Review every owner block before importing:").pack(anchor="w",padx=8,pady=6)
        preview=ScrolledText(win,wrap="word"); preview.pack(fill="both",expand=True,padx=8); preview.insert("1.0",plan); preview.configure(state="disabled")
        bar=ttk.Frame(win); bar.pack(fill="x",padx=8,pady=8)
        invalid=any(b.errors for b in blocks)
        def commit_import():
            active=sum(1 for b in blocks if b.enabled); ads=sum(1 for b in blocks for a in b.ads if not a.skipped)
            if not messagebox.askyesno("Confirm Simple Partner CSV Import",f"Import/update {ads} advertisements in {active} enabled partner blocks across {len(set(b.website for b in blocks))} websites? Stale generated ads listed in the preview may be removed. Unrelated manual rows will be preserved.",parent=win): return
            try:
                wb=load_workbook(self.workbook.get()); summary=import_into_workbook(wb,blocks); backup=save_workbook(self.workbook.get(),wb)
                self.write(f"Simple Partner CSV import: {summary['added']} added, {summary['updated']} updated, {summary['removed']} removed; backup={backup or 'not needed'}\n")
                self.refresh_sites(); win.destroy()
            except Exception as e: messagebox.showerror("Import failed",str(e),parent=win); self.write(f"ERROR: {e}\n")
        ttk.Button(bar,text="Import",command=commit_import,state="disabled" if invalid else "normal").pack(side="right",padx=4)
        ttk.Button(bar,text="Cancel",command=win.destroy).pack(side="right")
    def save_ad(self):
        try:
            wb=load_workbook(self.workbook.get()); info=add_or_update_exoclick_ad(wb,self.site.get().strip(),self.ad.get(),self.size.get(),self.anchor.get().strip(),self.markup.get("1.0","end-1c"),self.mode.get()); backup=save_workbook(self.workbook.get(),wb); code=website_code(info["site_id"],info["anchor"]); self.write((f"Saved {info['unit_id']} to {self.workbook.get()}"+(f" (backup {backup})" if backup else ""))+"\n"+code+"\n"); self.refresh_sites()
        except Exception as e: messagebox.showerror("Save failed",str(e)); self.write(f"ERROR: {e}\n")
    def cli(self): return ["node","dist/cli/ad-runner.js"] if Path("dist/cli/ad-runner.js").exists() else None
    def cmd(self,args):
        base=self.cli()
        if not base: self.write("dist/cli/ad-runner.js is missing. Click Build Ad Runner first (runs npm install && npm run build).\n"); return
        self.run(base+args)
    def cmd_shell(self,cmd): self.run(cmd,shell=True)
    def run(self,cmd,shell=False):
        self.write(f"$ {cmd if isinstance(cmd,str) else ' '.join(cmd)}\n")
        def worker():
            p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,shell=shell)
            if not shell and cmd[-1]=="serve": self.server=p
            for line in p.stdout: self.root.after(0,self.write,line)
            rc=p.wait(); self.root.after(0,self.write,f"[exit {rc}]\n")
        threading.Thread(target=worker,daemon=True).start()
    def start_server(self):
        if self.server and self.server.poll() is None: self.write("Server already running from this app.\n"); return
        self.cmd(["serve"])
    def stop_server(self):
        if self.server and self.server.poll() is None: self.server.terminate(); self.write("Stopped server launched by this app.\n")
        else: self.write("No server launched by this app is running.\n")
    def copy_code(self):
        code=website_code(self.site.get().strip(),self.anchor.get().strip()); self.root.clipboard_clear(); self.root.clipboard_append(code); self.write(code+"\nCopied website code.\n")

if __name__ == "__main__":
    root=tk.Tk(); App(root); root.mainloop()
