# Verified current runtime flow

## Request diagrams

```text
Browser -> Cloudflare static assets: HTML + Vite hashed JS/CSS + public JSON/HTML
Browser -> cdn.564578634.xyz: item.json + thumb.webp + computed page WebP
Browser -> Supabase: optional discussion (not R2, not page routing)
```

```text
Static host -> dist object lookup -> SPA fallback index.html for unknown path
(no repository application Worker fetch handler)
```

```text
Browser -> CDN edge -> [cache status unknown] -> R2/custom-domain origin on miss
```

**VERIFIED IN CODE:** `Page.start()` parses only query parameters. With both `work` and `chapter`, it opens the reader; otherwise it opens landing. Pathname and hash are ignored.

## Seventeen flows

1. **Homepage:** HTML/module assets load; `boot()` starts ghost text, awaits `Page`, then Footer.
2. **Search startup:** mount is synchronous; index fetch is deferred until focus/input and stored in one module promise. Current fetch uses `cache: "no-store"`.
3. **Rotunda:** bundled Rotunda/tags/pointers seed candidates; a bounded virtual window resolves metadata concurrently (limit 4) and thumbnails.
4. **Sides/ticker:** landing starts search, Rotunda, blocks, and `/header-ticker.json` concurrently. Four embedded block documents each fetch `/data/side_column_images_cycle.json` with `no-store`.
5. **Selection:** search/Rotunda dispatch `open-reader`; no URL navigation occurs.
6. **Open:** handler chooses source/work/chapter and renders inside `#blocks-reader`/`#blocks-root`.
7. **Chapter metadata:** each render fetches CDN `<work>/<chapter>/item.json`; no chapter promise cache.
8. **Page URL:** `base_url + '/' + padStart(index+1,padding) + '.' + extension`; no bucket list.
9. **Scroll:** IntersectionObserver (50% root margin) selects active page; fallback uses scroll+rAF.
10. **Unload/reload:** 10 before + active + 10 after; leaving window removes `src` and image node. Revisiting assigns the same URL, relying only on HTTP cache; failed pages require explicit retry.
11. **Direct query:** `/?source=e&work=<slug>&chapter=<path>` works (also SPA `/reader?...` if fallback serves shell).
12. **Direct pathname:** unknown paths receive SPA shell in Cloudflare configuration, but app ignores pathname and shows landing.
13. **Hash:** ignored; page changes do not update history.
14. **Hidden work:** Rotunda filters omission policy; direct reader lookup/URL does not consistently enforce public/hidden policy.
15. **Thumbnails:** direct CDN URLs; Rotunda has bounded URL/metadata caches and aborts stale images. Search results do not display full images.
16. **Failure:** image `onerror` unloads and shows retry; manifest errors show chapter failure; no automatic exponential retry.
17. **Refresh:** browser reloads shell and query reader; unchanged chapter `item.json` behavior depends on external headers. Visibility policy `refresh()` re-runs provider but bundled default requires no network.

## Exact browser request classes

| Request | Frequency/caching | Origin distinction |
|---|---|---|
| HTML, hashed JS/CSS | navigation/build chunks | static host; Vite filenames hashed |
| text-behind, ticker, fetched block HTML | once per relevant startup | same-origin static |
| search index | shared promise/page, explicit no-store | same-origin static; possible edge/origin depends deployment |
| side image-cycle JSON | up to four documents, explicit no-store | duplicate browser requests |
| Rotunda work manifests | visible/bounded, promise/map behavior | same-origin Vite assets or configured URL |
| thumbs/pages/item.json | direct CDN URL | CDN request; R2 origin read only on cache miss |
| discussion | when parent ID present | Supabase, unrelated to R2 |

**VERIFIED IN CODE:** there is no reader Worker request and no R2 list operation. **EXTERNAL CONFIGURATION UNKNOWN:** actual cache hits, `CF-Cache-Status`, `Age`, collapse/tier behavior, and whether a dashboard Worker intercepts hostnames.
