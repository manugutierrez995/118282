# Repository-specific Astro target architecture

## Target

```text
canonical JSON/JSONL --typed build adapters--> /releases/<id>/...
                                             Astro static output
/work/<slug>/ HTML -> one reader TypeScript entry -> versioned manifest -> direct immutable media
```

**RECOMMENDATION:** `output: "static"`; no server adapter and no UI framework. Generate one page per public work at current scale, plus landing and compatibility reader. The page embeds only route identity/release URL, not private metadata. The reader reads initial hash, loads one immutable work projection, and maintains page/history without navigation.

| Proposed file | Wraps current behavior | Static/client/build | Risk |
|---|---|---|---|
| `astro/src/layouts/SiteLayout.astro` | `index.html` head/root/startup/error shell | static; loads hashed client entry as needed | medium: exact DOM/CSS assumptions |
| `astro/src/pages/index.astro` | `Landing.start` markup | static shell + landing client entry | high: Rotunda/ticker/blocks parity |
| `astro/src/pages/work/[slug]/index.astro` | query route + reader root | `getStaticPaths` reads public route adapter; reader script only | medium: scale/hidden filtering |
| `astro/src/pages/reader.astro` | legacy `/reader?...` compatibility | static redirect/compat shell | medium: GitHub/static redirect limits |
| `astro/src/components/{Header,ReaderRoot,BlockMounts,Footer}.astro` | stable presentational markup | static, no independent hydration | low–medium |
| `astro/src/data/{canonical,public-release,routes}.ts` | existing JSON imports and validation | build only | high: privacy/contract correctness |
| `astro/src/client/reader/index.ts` | `reader.js`, storage/resolver/work loader | one coordinated client system | high; convert minimally |
| `astro/src/client/{landing,search,rotunda,blocks,ghost}.ts` | corresponding JS modules | client modules, not islands | medium |
| `astro/src/client/annotations/svg-layer.ts` | future only | lazy client SVG overlay | low now; do not implement semantics |
| `astro/src/styles/*` | existing CSS | retained imports -> hashed CSS | high if selector/DOM changes |
| `public/releases/<id>/*`, `public/current.json` | new generated projections | immutable static data / short pointer | high publish atomicity |

## Routes and data

`/`, `/work/<encoded canonical slug>/`, optional `/catalog/`, `/404.html`; compatibility `/reader?source=&work=&chapter=` canonicalizes client-side or via static-platform redirects. Each generated work HTML references a release ID selected at build/deploy so it cannot mix pointer versions mid-session. Public manifest carries ordered chapters, page pattern **or explicit filenames**, page counts/dimensions/revision, thumbnails, and annotation snapshot URL.

## Preservation boundaries

Retain `landing.css`/`rotunda.css`/`discussion.css` initially. Keep reader scroll/session/image lifecycle together. Astro components create stable mount DOM only. Keep Supabase discussion dynamic and separate. Future SVG sits per page, shares normalized coordinates and persistent IDs, and never changes media. Astro consumes versioned Rotunda output but does not select editorial content.
