"""RFC 4180 simple-partner CSV importer for Ad Runner workbooks."""
from __future__ import annotations

import argparse, csv, json, re, sys
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from placement_vocabulary import CANONICAL_PLACEMENTS

SOURCE = "simple-partner-csv"
FIELD_NAMES = {"Website / Domain", "Owner Name", "Enabled", "Traffic Share", "Ad Traffic Name", "Client Hints Meta Tag(s)"}
PLACEMENTS = {name.lower(): (anchor, fmt, device) for name, (anchor, _size, fmt, device) in CANONICAL_PLACEMENTS.items()}

def slugify(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not result: raise ValueError("must contain a letter or number")
    return result

@dataclass
class Ad:
    name: str; dimensions: str; code: str; row: int; skipped: bool = False
@dataclass
class Block:
    number: int; start_row: int; fields: dict[str, tuple[str,int]] = field(default_factory=dict)
    ads: list[Ad] = field(default_factory=list); errors: list[str] = field(default_factory=list)
    website: str = ""; owner: str = ""; enabled: bool = True; share: float = 0
    traffic_name: str = ""; head_markup: str = ""; partner_id: str = ""; block_key: str = ""
    @property
    def status(self): return "invalid" if self.errors else ("valid" if self.enabled else "disabled")

class _MetaParser(HTMLParser):
    def __init__(self): super().__init__(convert_charrefs=False); self.errors=[]; self.count=0
    def handle_starttag(self, tag, attrs):
        if tag.lower() != "meta": self.errors.append(f"only <meta> tags are allowed, found <{tag}>"); return
        self.count += 1
        allowed={"http-equiv","content","name","charset"}
        for k,v in attrs:
            if k.lower() not in allowed or v is None: self.errors.append(f"attribute {k!r} is not allowed on imported meta tags")
    def handle_startendtag(self, tag, attrs): self.handle_starttag(tag,attrs)
    def handle_endtag(self, tag):
        if tag.lower() != "meta": self.errors.append(f"closing </{tag}> is not allowed")
    def handle_data(self, data):
        if data.strip(): self.errors.append("text outside meta tags is not allowed")
    def handle_entityref(self, name): pass
    def handle_charref(self, name): pass
    def handle_comment(self, data): self.errors.append("comments are not allowed in Client Hints markup")
    def handle_decl(self, decl): self.errors.append("declarations are not allowed in Client Hints markup")
    def handle_pi(self, data): self.errors.append("processing instructions are not allowed in Client Hints markup")

def _placeholder(value: str) -> bool:
    text=value.strip().upper()
    return "PASTE_" in text or text.endswith("_OR_NONE")

def _error(block: Block, field_name: str, row: int, message: str):
    block.errors.append(f"Owner block {block.number}, website {block.website or '<missing>'}, {field_name}, CSV row {row}: {message}")

def parse_simple_csv(path: str | Path) -> list[Block]:
    blocks=[]; current=None; in_ads=False
    with Path(path).open("r", encoding="utf-8-sig", newline="") as fh:
        for rownum,row in enumerate(csv.reader(fh),1):
            row=(row+["", "", ""])[:3]; key=row[0].strip()
            if re.fullmatch(r"OWNER BLOCK\s+\d+", key, re.I):
                current=Block(len(blocks)+1,rownum); blocks.append(current); in_ads=False; continue
            if current is None or not any(row): continue
            if key.upper()=="AD NAME": in_ads=True; continue
            if not in_ads and key in FIELD_NAMES: current.fields[key]=(row[1],rownum); continue
            if in_ads and key: current.ads.append(Ad(row[0],row[1],row[2],rownum))
    if not blocks: raise ValueError("CSV contains no OWNER BLOCK sections")
    _validate(blocks)
    return blocks

def _validate(blocks: list[Block]):
    ids_by_site={}; ads_by_block=set()
    for b in blocks:
        def val(name): return b.fields.get(name,("",b.start_row))[0]
        def row(name): return b.fields.get(name,("",b.start_row))[1]
        b.website=val("Website / Domain").strip().lower(); b.owner=val("Owner Name").strip(); b.traffic_name=val("Ad Traffic Name").strip()
        enabled=val("Enabled").strip().lower()
        if enabled not in {"true","false"}: _error(b,"Enabled",row("Enabled"),"must be true or false")
        b.enabled=enabled=="true"
        share=val("Traffic Share").strip().removesuffix("%").strip()
        try: b.share=float(share)
        except ValueError: _error(b,"Traffic Share",row("Traffic Share"),"must be a number or percentage")
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]{0,251}[a-z0-9])?",b.website): _error(b,"Website / Domain",row("Website / Domain"),"is empty, unsafe, or unresolved")
        for name,value in [("Website / Domain",b.website),("Owner Name",b.owner),("Ad Traffic Name",b.traffic_name)]:
            if not value: _error(b,name,row(name),"is required")
            if _placeholder(value): _error(b,name,row(name),"contains an unresolved template value")
        try: b.partner_id=f"partner-{slugify(b.website)}-{slugify(b.owner)}-{slugify(b.traffic_name)}"
        except ValueError: b.partner_id="invalid"
        b.block_key=f"{b.website}|{slugify(b.owner) if b.owner else 'missing'}|{slugify(b.traffic_name) if b.traffic_name else 'missing'}"
        previous=ids_by_site.setdefault(b.website,{}).get(b.partner_id)
        if previous: _error(b,"Owner Name / Ad Traffic Name",b.start_row,f"generated partner ID duplicates owner block {previous}")
        ids_by_site[b.website][b.partner_id]=b.number
        head=val("Client Hints Meta Tag(s)")
        if _placeholder(head): _error(b,"Client Hints Meta Tag(s)",row("Client Hints Meta Tag(s)"),"contains an unresolved template value")
        elif head.strip().upper()=="NONE": b.head_markup=""
        else:
            parser=_MetaParser()
            try: parser.feed(head); parser.close()
            except Exception as e: parser.errors.append(str(e))
            if not parser.count: parser.errors.append("at least one complete <meta> tag is required, or NONE")
            for e in parser.errors: _error(b,"Client Hints Meta Tag(s)",row("Client Hints Meta Tag(s)"),e)
            b.head_markup=head
        for ad in b.ads:
            if ad.code.strip().upper()=="NONE": ad.skipped=True; continue
            if not ad.name.strip(): _error(b,"ad name",ad.row,"is required")
            key=(b.block_key,slugify(ad.name) if ad.name.strip() else "")
            if key in ads_by_block: _error(b,ad.name or "ad name",ad.row,"duplicates an advertisement in this owner block")
            ads_by_block.add(key)
            dim=ad.dimensions.strip().upper()
            if dim not in {"N/A","NONE"} and not re.fullmatch(r"[1-9]\d{0,4}\s*[xX]\s*[1-9]\d{0,4}",dim): _error(b,ad.name,ad.row,"dimensions must be WIDTHxHEIGHT, N/A, or NONE")
            if not ad.code: _error(b,ad.name,ad.row,"complete ad code is required")
            if _placeholder(ad.code): _error(b,ad.name,ad.row,"complete ad code contains an unresolved template value")
    for site,site_blocks in _group(blocks).items():
        enabled=[b for b in site_blocks if b.enabled]
        total=sum(b.share for b in enabled)
        if enabled and abs(total-100)>1e-9:
            for b in enabled: _error(b,"Traffic Share",b.fields.get("Traffic Share",("",b.start_row))[1],f"enabled shares for {site} total {total:g}%, not exactly 100%")

def _group(blocks):
    result={}
    for b in blocks: result.setdefault(b.website,[]).append(b)
    return result

def import_plan(blocks: list[Block], workbook: dict | None=None) -> str:
    lines=[]
    for b in blocks:
        active=[a for a in b.ads if not a.skipped]; skipped=[a.name for a in b.ads if a.skipped]
        lines.append(f"[{b.status.upper()}] website={b.website or '<missing>'} owner={b.owner or '<missing>'} enabled={str(b.enabled).lower()} share={b.share:g}% lane={b.traffic_name or '<missing>'} ads={len(active)}")
        lines.extend(f"  - {a.name}: {a.dimensions}" for a in active)
        if skipped: lines.append("  skipped NONE: "+", ".join(skipped))
        lines.extend("  ERROR: "+e for e in b.errors)
    if workbook:
        incoming={b.block_key:{slugify(a.name) for a in b.ads if not a.skipped} for b in blocks}
        stale=[]
        for sheet in workbook.get("Sheets",{}).values():
            for row in sheet.get("rows",[]):
                meta=_source_meta(row.get("notes",""))
                if meta and meta.get("block_key") in incoming and meta.get("ad_key") not in incoming[meta["block_key"]]: stale.append(f"{meta.get('website')}: {meta.get('ad_key')}")
        if stale: lines.append("Generated ads to remove: "+", ".join(stale))
    return "\n".join(lines)

def import_into_workbook(workbook: dict, blocks: list[Block]) -> dict:
    errors=[e for b in blocks for e in b.errors]
    if errors: raise ValueError("CSV validation failed:\n"+"\n".join(errors))
    names=workbook.setdefault("SheetNames",[]); sheets=workbook.setdefault("Sheets",{})
    summary={"added":0,"updated":0,"removed":0,"blocks":len(blocks),"ads":0}
    incoming={b.block_key:{slugify(a.name) for a in b.ads if not a.skipped} for b in blocks}
    for site,site_blocks in _group(blocks).items():
        if site not in sheets: sheets[site]={"header":[],"rows":[]}; names.append(site)
        sheet=sheets[site]; rows=sheet.setdefault("rows",[]); sheet["header"]=[]; sheet.pop("aoa",None)
        # Delete only stale rows owned by this source/block/ad.
        kept=[]
        for r in rows:
            meta=_source_meta(r.get("notes",""))
            if meta and meta.get("block_key") in incoming and meta.get("ad_key") and meta["ad_key"] not in incoming[meta["block_key"]]: summary["removed"]+=1
            else: kept.append(r)
        rows[:]=kept
        index={_source_identity(r):(i,r) for i,r in enumerate(rows) if _source_identity(r)}
        for b in site_blocks:
            for ad in b.ads:
                if ad.skipped: continue
                summary["ads"]+=1; adkey=slugify(ad.name); placement,fmt,device=PLACEMENTS.get(ad.name.strip().lower(),(adkey,"custom", "all"))
                network="exoclick" if re.search(r"ad-provider\.js|AdProvider|magsrv\.com|pemsrv\.com",ad.code,re.I) else "external-tag"
                account=f"account-{b.partner_id.removeprefix('partner-')}"; unit=f"unit-{b.partner_id}-{adkey}"
                width=height=""
                if ad.dimensions.strip().upper() not in {"N/A","NONE"}: width,height=re.split(r"[xX]",ad.dimensions.replace(" ",""))
                note=json.dumps({"source":SOURCE,"website":site,"block_key":b.block_key,"ad_key":adkey},separators=(",",":"),sort_keys=True)
                row={"site_id":site,"enabled":str(b.enabled).lower(),"slot_id":placement,"slot_anchor":placement,"partner_id":b.partner_id,"partner_name":b.owner,"partner_share":b.share,"account_id":account,"network_id":network,"network_label":b.traffic_name,"unit_id":unit,"format_name":fmt,"width":width,"height":height,"devices":device,"ad_code":ad.code,"head_markup":b.head_markup,"network_priority":100,"timeout_ms":5000,"guaranteed":"false","share_basis":"confirmed-fills","share_policy":"protected-share","notes":note}
                identity=(b.block_key,adkey)
                if identity in index:
                    i,old=index[identity]
                    if old.get("share_policy") in {"protected-share","open-yield"}: row["share_policy"]=old["share_policy"]
                    rows[i]=row; summary["updated"]+=1
                else: rows.append(row); index[identity]=(len(rows)-1,row); summary["added"]+=1
    return summary

def _source_meta(note):
    try:
        data=json.loads(note); return data if data.get("source")==SOURCE else None
    except (ValueError,TypeError,AttributeError): return None
def _source_identity(row):
    meta=_source_meta(row.get("notes","")); return (meta.get("block_key"),meta.get("ad_key")) if meta else None

def main(argv=None):
    p=argparse.ArgumentParser(); p.add_argument("csv"); p.add_argument("workbook"); p.add_argument("--dry-run",action="store_true"); args=p.parse_args(argv)
    try:
        from ad_runner_gui import load_workbook, save_workbook
        blocks=parse_simple_csv(args.csv); wb=load_workbook(args.workbook); print(import_plan(blocks,wb)); errors=[e for b in blocks for e in b.errors]
        if errors: return 1
        if args.dry_run: print("Dry run: workbook was not changed."); return 0
        summary=import_into_workbook(wb,blocks); backup=save_workbook(args.workbook,wb)
        print(f"Imported {summary['ads']} ads: {summary['added']} added, {summary['updated']} updated, {summary['removed']} removed."+(f" Backup: {backup}" if backup else "")); return 0
    except Exception as e: print(f"ERROR: {e}",file=sys.stderr); return 1
if __name__=="__main__": raise SystemExit(main())
