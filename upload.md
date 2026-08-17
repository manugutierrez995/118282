# `upload.py` Operator Guide

This guide explains how to prepare works for `upload.py`, where to place them, what formats are accepted, what the script generates, how R2 upload works, and how to handle the GitHub token.

## 1. Where the works go

The interactive wizard defaults to:

```text
~/works
```

That means:

```text
/home/emmadoku/works
```

You can use another location when the script asks for one, but `~/works` is the normal default.

Run the uploader from the repository:

```bash
cd /home/emmadoku/dev/118282
python3 upload.py
```

---

## 2. Supported input formats

`upload.py` accepts either:

- normal work folders
- `.zip` archives
- `.cbz` archives

Supported page-image formats are:

```text
.jpg
.jpeg
.png
.webp
.gif
```

The script ignores common junk/helper files such as:

```text
.DS_Store
Thumbs.db
desktop.ini
__MACOSX
thumb.webp
thumbnail.webp
cover.webp
```

ZIP and CBZ files are treated as archives and extracted automatically for ingestion.

---

## 3. Single-work mode

Choose:

```text
Ingest mode: 1 single work, 2 multiple work folders [1]: 1
```

Then give the path to one work.

### Recommended folder layout

```text
~/works/My Work/
├── chapter_1/
│   ├── 001.webp
│   ├── 002.webp
│   └── 003.webp
├── chapter_2/
│   ├── 001.webp
│   ├── 002.webp
│   └── 003.webp
└── chapter_3/
    ├── 001.webp
    └── 002.webp
```

The chapter folder names do not have to be exactly `chapter_1`, `chapter_2`, etc. A directory that directly contains page images can be detected as a chapter.

For example, this is also valid:

```text
~/works/My Work/
├── Chapter 01/
│   ├── page1.jpg
│   └── page2.jpg
└── Final Chapter/
    ├── page1.jpg
    └── page2.jpg
```

By default, the script renumbers pages in each detected chapter to:

```text
001.ext
002.ext
003.ext
...
```

You can answer `n` when asked if you do not want this.

---

## 4. A work can also contain only loose images

This is valid:

```text
~/works/My Work/
├── image1.webp
├── image2.webp
├── image3.webp
└── image4.webp
```

By default, `upload.py` automatically creates:

```text
chapter_1/
```

and moves the loose page images into it.

The result becomes approximately:

```text
~/works/My Work/
└── chapter_1/
    ├── 001.webp
    ├── 002.webp
    ├── 003.webp
    └── 004.webp
```

Avoid mixing loose page images at the work root with existing chapter folders unless you intentionally use the script's merge option. The normal interactive workflow expects one layout or the other.

---

## 5. A single work can be a ZIP or CBZ

You may point single-work mode directly at:

```text
~/works/My Work.cbz
```

or:

```text
~/works/My Work.zip
```

The archive should contain page images or chapter folders.

Examples:

```text
My Work.cbz
├── chapter_1/
│   ├── 001.webp
│   ├── 002.webp
│   └── 003.webp
└── chapter_2/
    ├── 001.webp
    └── 002.webp
```

or simply:

```text
My Work.cbz
├── 001.webp
├── 002.webp
├── 003.webp
└── 004.webp
```

The second form is automatically turned into `chapter_1` during preprocessing.

Temporary extraction directories are normally cleaned up after ingestion.

---

## 6. Multiple-work / batch mode

Choose:

```text
Ingest mode: 1 single work, 2 multiple work folders [1]: 2
```

Then point the script at the parent directory containing the works.

The normal layout is:

```text
~/works/
├── Work One/
│   └── chapter_1/
│       ├── 001.webp
│       └── 002.webp
├── Work Two/
│   ├── chapter_1/
│   │   ├── 001.webp
│   │   └── 002.webp
│   └── chapter_2/
│       ├── 001.webp
│       └── 002.webp
├── Work Three.cbz
└── Work Four.zip
```

Each immediate work folder, ZIP, or CBZ becomes a separate work.

In batch mode:

- the work name comes from the immediate folder/archive name
- the slug is generated automatically
- `parent_work_id` is generated/reused automatically
- tags can be applied to all works in the batch

A good rule is:

```text
~/works/
└── ONE immediate item per work
```

Do not put unrelated non-work folders in the batch directory if you can avoid it.

---

## 7. Slugs and display names

In single mode the wizard asks:

```text
Work slug? [...]
Display title? [...]
```

The suggested slug comes from the work folder/archive name.

Spaces and many special characters are normalized for the slug.

For example:

```text
Dekiai Koubi Blind Love Mating
```

may become a slug similar to:

```text
Dekiai_Koubi_Blind_Love_Mating
```

The display title remains the human-facing title.

In batch mode this is inferred automatically from each immediate work name.

---

## 8. Dolphin/Linux tags

The default is:

```text
Import Dolphin/Linux tags from each input file or work folder? [Y/n]: y
```

If you have assigned KDE/Dolphin tags to a source work folder or archive, the script can import those tags from the Linux `user.xdg.tags` extended attribute.

You can answer `n` to ignore filesystem tags.

The wizard also separately asks whether you want to manually tag the work or all works.

---

## 9. Current important defaults

Pressing Enter accepts these defaults:

```text
Import Dolphin/Linux tags?                  YES
Resize images?                              NO
Normalize/renumber pages?                   YES
Generate thumb.webp?                        YES
Update fetch.json?                          YES
Update rotunda.json?                        YES
Regenerate search.index.json?               YES
Upload to R2/CDN?                           YES
Upload method?                              rclone
Commit/push to GitHub?                      YES
```

They are still questions. You can type `n` whenever you want to disable a Yes-defaulted action for that run.

---

## 10. Thumbnail and generated metadata

By default the script generates `thumb.webp`.

The configured thumbnail location is the first detected chapter, so a work may end up looking like:

```text
My Work/
└── chapter_1/
    ├── 001.webp
    ├── 002.webp
    ├── thumb.webp
    ├── details.json
    └── item.json
```

Each detected chapter gets an `item.json`.

The work also gets repository metadata under:

```text
src/data/works/<slug>.json
```

Depending on the selected options, the script also updates:

```text
src/data/fetch.json
src/data/rotunda.json
src/data/tags.json
src/data/search.index.json
public/data/search.index.json
```

---

## 11. R2 / CDN upload

The current defaults are:

```text
Upload to R2/CDN? [Y/n]: y
Upload method? [rclone]: rclone
Upload remote/destination before work slug? [animeplex.lol:extended/works]:
```

With the default remote, a work with slug:

```text
My_Work
```

is uploaded under:

```text
animeplex.lol:extended/works/My_Work
```

The public CDN base used in generated metadata defaults to:

```text
https://cdn.118282.xyz/works
```

so generated URLs for that work begin with:

```text
https://cdn.118282.xyz/works/My_Work/
```

### rclone requirement

If you use the existing rclone configuration, make sure the remote is available:

```bash
rclone listremotes
```

You should have:

```text
animeplex.lol:
```

The wizard also supports entering R2 credentials directly, but the default is to use the existing rclone configuration.

---

## 12. Original ZIP/CBZ upload

If the input itself is a `.zip` or `.cbz`, the wizard can ask:

```text
Upload each original ZIP/CBZ beside thumb.webp? [Y/n]:
```

Default:

```text
YES
```

If the source input was only a normal folder, there is no original archive to upload, so the script reports that archive upload was skipped.

The script can also ask:

```text
Delete each local ZIP/CBZ after strong remote verification? ... [y/N]:
```

Default:

```text
NO
```

Leaving this as `n` preserves the original local archive.

If you intentionally answer `y`, the script verifies the remote copy before deleting the local source archive.

---

## 13. GitHub setup

The script's commit/push question currently defaults to:

```text
Commit/push to GitHub? [Y/n]: y
```

The repository itself may use SSH for its Git remote.

Check with:

```bash
cd /home/emmadoku/dev/118282
git remote -v
```

For the `manugutierrez995` SSH setup, it should look similar to:

```text
origin  git@github-manu:manugutierrez995/118282.git (fetch)
origin  git@github-manu:manugutierrez995/118282.git (push)
```

Test SSH authentication with:

```bash
ssh -T git@github-manu
```

---

## 14. The GitHub token

### Important

The current `upload.py` still requires a GitHub token whenever:

```text
Commit/push to GitHub? [Y/n]
```

is answered `y`.

This is true even when the actual Git remote uses SSH.

The token is therefore required by the script's current logic before it reaches its commit/push step.

### Recommended way: export it before running

In the terminal, before starting `upload.py`, run:

```bash
export GITHUB_TOKEN='YOUR_GITHUB_TOKEN_HERE'
```

Then run:

```bash
cd /home/emmadoku/dev/118282
python3 upload.py
```

Near the end the wizard asks:

```text
GitHub token env var OR raw token OR export command [GITHUB_TOKEN]:
```

If you already exported `GITHUB_TOKEN`, simply press:

```text
Enter
```

The script then reads the value from the environment.

### One-command alternative

You can make the token available only to that invocation:

```bash
GITHUB_TOKEN='YOUR_GITHUB_TOKEN_HERE' python3 upload.py
```

At the token prompt, press Enter.

### You can also paste the raw token

When asked:

```text
GitHub token env var OR raw token OR export command [GITHUB_TOKEN]:
```

you may paste a GitHub token directly.

However, exporting it first is generally cleaner because you do not need to paste it into the wizard every run.

### Do not put the token in the repository

Do not save the real token inside:

```text
upload.py
upload.md
.env files that are tracked by Git
src/data/
```

and do not commit a token to GitHub.

The script supports the environment variable specifically so the secret can remain outside the repository.

---

## 15. What the GitHub portion does

When GitHub commit/push is enabled, the script:

1. collects the repository data files it changed
2. stages those generated/updated files with Git
3. creates a commit if staged changes exist
4. pushes the commit

For one work, the generated commit message is similar to:

```text
Add Doku-Doujin work <display name>
```

For a batch:

```text
Add Doku-Doujin works batch (<count>)
```

If there are no staged data changes, the script skips the commit/push step.

---

## 16. Recommended normal workflow

### Before the first run in a terminal session

```bash
cd /home/emmadoku/dev/118282
export GITHUB_TOKEN='YOUR_GITHUB_TOKEN_HERE'
```

Then:

```bash
python3 upload.py
```

### Single work

Put the work somewhere like:

```text
/home/emmadoku/works/My Work/
```

Then choose:

```text
1
```

and enter:

```text
~/works/My Work
```

### Many works

Arrange them like:

```text
/home/emmadoku/works/
├── Work One/
├── Work Two/
├── Work Three.cbz
└── Work Four.zip
```

Then choose:

```text
2
```

and use:

```text
~/works
```

With the current defaults, repeatedly pressing Enter will normally:

- import Linux/Dolphin tags
- keep the inferred names/settings
- renumber pages
- generate thumbnails
- update `fetch.json`
- update `rotunda.json`
- regenerate the search index
- upload to R2 using rclone
- commit and push repository metadata to GitHub

Read each prompt before pressing Enter, especially any prompt involving deleting a local archive.

---

## 17. Example: easiest folder to prepare

For a one-chapter work, this is enough:

```text
~/works/Example Work/
├── 001.webp
├── 002.webp
├── 003.webp
└── 004.webp
```

Run:

```bash
cd /home/emmadoku/dev/118282
export GITHUB_TOKEN='YOUR_GITHUB_TOKEN_HERE'
python3 upload.py
```

Choose single mode and enter:

```text
~/works/Example Work
```

The script automatically creates `chapter_1`, renumbers the pages if necessary, generates the metadata/thumbnail files, updates the site indexes, uploads to R2, and—when enabled—commits and pushes the repository changes.

---

## 18. Quick checklist

Before ingestion:

- [ ] Work is under `~/works` or another known path
- [ ] Pages are JPG, JPEG, PNG, WEBP, or GIF
- [ ] Work is a folder, ZIP, or CBZ
- [ ] Multiple works are separated into immediate items under the batch parent
- [ ] `rclone` can see `animeplex.lol:`
- [ ] Git SSH remote is correct
- [ ] `GITHUB_TOKEN` is exported if commit/push will remain enabled
- [ ] You are prepared for page renumbering because it defaults to Yes
- [ ] You have checked the local-archive deletion prompt before answering

Then run:

```bash
cd /home/emmadoku/dev/118282
python3 upload.py
```
