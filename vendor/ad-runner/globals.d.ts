declare module 'node:crypto' { export function createHash(a:string): { update(v:string|Buffer): any; digest(enc:string): string }; export function randomUUID(): string; }
declare module 'node:fs' { export function createReadStream(p:string): any; export function mkdirSync(p:string,o?:any): any; }
declare module 'node:fs/promises' { export const mkdir:any; export const readFile:any; export const writeFile:any; export const rename:any; export const readdir:any; export const appendFile:any; export const cp:any; }
declare module 'node:path' { const path:any; export default path; export const join:any; export const dirname:any; }
declare module 'node:http' { const http:any; export default http; export interface ServerResponse { setHeader(...a:any[]):any; writeHead(...a:any[]):any; end(...a:any[]):any;} export interface IncomingMessage { [Symbol.asyncIterator](): AsyncIterableIterator<any>; headers:any; url?:string; method?:string;} }
declare module 'xlsx' { export const utils:any; export function readFile(path:string,opts?:any):any; export function writeFile(wb:any,path:string):void; }
declare const Buffer:any; declare const process:any;

declare module 'node:child_process' { export function execFileSync(cmd:string,args?:any[],opts?:any): string; export function spawnSync(cmd:string,args?:any[],opts?:any): {status:number|null}; }
