import { readFile, writeFile } from "node:fs/promises";
export interface Sheet { header?: string[]; rows?: Record<string, unknown>[]; aoa?: unknown[][]; }
export interface Workbook { SheetNames: string[]; Sheets: Record<string, Sheet>; }
export const utils={ book_new():Workbook{return{SheetNames:[],Sheets:{}}}, book_append_sheet(wb:Workbook,ws:Sheet,name:string){wb.SheetNames.push(name); wb.Sheets[name]=ws;}, json_to_sheet(rows:Record<string,unknown>[], opts?:{header?:string[]}):Sheet{return{header:opts?.header??Object.keys(rows[0]??{}),rows}}, aoa_to_sheet(aoa:unknown[][]):Sheet{return{aoa}}, sheet_to_json(ws:Sheet, opts?:{defval?:unknown}):Record<string,unknown>[] { const defval=opts?.defval??""; if(ws.rows) return ws.rows; if(ws.aoa){const [h,...rs]=ws.aoa; return rs.map(r=>Object.fromEntries((h as string[]).map((k,i)=>[k,r[i]??defval])))} return []; } };
export async function readWorkbookFile(path:string):Promise<Workbook>{return JSON.parse(await readFile(path,"utf8"));}
export async function writeWorkbookFile(path:string,wb:Workbook):Promise<void>{await writeFile(path,JSON.stringify(wb,null,2));}
