import type { SpreadsheetRow } from "../packages/compiler/parser.js"; import { compileRows } from "../packages/compiler/compiler.js";
export async function compileChangedSheet(rows: SpreadsheetRow[], siteVersion: string) { return compileRows(rows, "maximum-revenue", siteVersion); }
