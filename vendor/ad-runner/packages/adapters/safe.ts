export function escapeHtml(v:string){return v.replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]!));}
export function sanitizeHtml(v:string){return v.replace(/<\/?(script|iframe|object|embed)[^>]*>/gi,"").replace(/ on\w+="[^"]*"/gi,"").replace(/javascript:/gi,"");}
export function safeUrl(v?:string){ if(!v) return undefined; const u=new URL(v, window.location.href); if(!["http:","https:","data:"].includes(u.protocol)) throw new Error(`Unsupported URL scheme ${u.protocol}`); return u.href; }
