# Future Reader Architecture

## Vision

Every work in the archive should eventually have its own permanent, human-readable URL.

For example:

```text
https://564578634.xyz/work/example-work/
```

Every page inside that work should also have a permanent address:

```text
https://564578634.xyz/work/example-work/#page-23
```

The work URL identifies the publication.

The page hash identifies the reader's current location inside that publication.

This gives every work a stable identity that can be bookmarked, linked, indexed, and referenced for years without depending on temporary application state.

---

# Long-Term Objective

The long-term goal is to move as far away from Cloudflare Workers as reasonably possible.

Workers are useful today, but they should not become responsible for ordinary reading.

A billion readers should not mean a billion Worker executions.

Instead, Workers should eventually be reduced to deployment, compatibility, or exceptional routing tasks—not everyday browsing.

The reader itself should function almost entirely as a static application.

---

# Static Work Identity

Each work should have a permanent slug.

For example:

```text
example-work
```

A generated catalog should contain all metadata necessary to open that work.

Example:

```json
{
  "slug": "example-work",
  "title": "Example Work",
  "chapter": "chapter_1",
  "page_count": 43,
  "thumbnail": "https://cdn.564578634.xyz/works/example-work/chapter_1/thumb.webp",
  "content_base": "https://cdn.564578634.xyz/works/example-work/chapter_1/"
}
```

When opening a work, the browser should already possess enough information to construct every image URL directly.

No Worker should need to resolve the work.

No Worker should need to enumerate R2.

No Worker should need to discover which pages exist.

Only the requested images should be downloaded.

---

# Reader Navigation

The current page should simply be represented by the URL hash.

Examples:

```text
#page-1
#page-2
#page-23
```

Changing pages should only update browser history.

For example:

```javascript
history.replaceState(null, "", `#page-${page}`);
```

or

```javascript
history.pushState(null, "", `#page-${page}`);
```

The browser should never contact the Worker merely because the reader advances to another page.

Opening

```text
https://564578634.xyz/work/example-work/#page-23
```

should immediately display page 23.

---

# Request Model

The desired request flow is:

```
Open Work URL
        │
        ▼
Load Static Reader
        │
        ▼
Read Work Slug
        │
        ▼
Read Page Hash
        │
        ▼
Resolve Work From Local Catalog
        │
        ▼
Load Requested Image
```

The only network activity after opening the reader should be fetching the required media assets.

---

# Catalog Editor

Eventually,

```
scripts/deletor.py
```

should evolve into a complete catalog management application.

The ideal layout would resemble:

```
┌──────────────────────────────┬──────────────────────────────┐
│ Catalog                      │ Reader                       │
├──────────────────────────────┼──────────────────────────────┤
│ Search                       │ Current Work                │
│ Thumbnail                    │ Current Page                │
│ Metadata                     │ Previous / Next             │
│ Work Tags                    │ Zoom                        │
│                              │                             │
│ Hide                         │                             │
│ Unhide                       │                             │
│ Delete                       │                             │
│ Edit Tags                    │                             │
└──────────────────────────────┴──────────────────────────────┘
```

Selecting a work in the catalog should immediately open its permanent URL inside the reader.

The operator can then decide whether to:

* hide it
* unhide it
* delete it
* edit tags
* inspect pages
* copy its URL

without leaving the management interface.

---

# Split-Screen Workflow

Eventually the catalog editor should automatically arrange itself beside the browser.

```
┌──────────────┬───────────────────────────────┐
│ deletor.py   │ Browser                       │
│              │                               │
│ Search       │ Current Work                  │
│ Tags         │ Page 23                       │
│ Hide         │                               │
│ Delete       │                               │
└──────────────┴───────────────────────────────┘
```

The browser is responsible for displaying the work.

The catalog editor is responsible for modifying repository metadata.

The two remain separate while working together.

---

# Page-Level Metadata

Once every page possesses a permanent URL, pages themselves become first-class objects.

This opens the door to attaching information directly to individual pages.

Examples include:

* notes
* tags
* editorial reminders
* quality control
* thumbnail candidates
* translation notes
* publication status

A page might store metadata such as:

```json
{
  "page": 23,
  "notes": [
    "Excellent composition.",
    "Possible homepage thumbnail."
  ],
  "public": {
    "featured": {}
  },
  "private": {
    "review-later": {}
  }
}
```

The work remains unchanged.

Only metadata is added.

---

# Stable Page Identity

Internally, every page should possess a stable identifier.

For example:

```text
example-work:chapter_1:23
```

The browser URL may remain simple:

```text
/work/example-work/#page-23
```

while the application internally resolves:

* work
* chapter
* page

This leaves room for future multi-chapter works without changing the public URL structure.

---

# Bounding-Box Annotations

One of the most exciting future capabilities is page annotation.

Rather than attaching notes only to an entire page, the user should eventually be able to draw a rectangle around any portion of the image.

Examples include:

* speech bubbles
* individual panels
* characters
* objects
* artwork
* visual defects
* translation regions
* thumbnail candidates

Annotations should use normalized coordinates instead of pixels.

Example:

```json
{
  "type": "bounding-box",
  "x": 0.18,
  "y": 0.27,
  "width": 0.34,
  "height": 0.21,
  "note": "Possible thumbnail crop.",
  "tags": [
    "favorite",
    "thumbnail-candidate"
  ]
}
```

Coordinates remain correct regardless of screen size or zoom level.

The original page is never modified.

The annotation simply overlays it.

---

# Reader Annotation Tools

Eventually the reader may support tools such as:

* Show annotations
* Hide annotations
* Add note
* Add tag
* Draw bounding box
* Edit annotation
* Delete annotation
* Copy annotated page URL

Annotations should be optional overlays, never destructive edits.

---

# Metadata Storage

Metadata should remain separate from the original archive.

For example:

```
src/data/
├── works/
├── tags/
└── annotations/
```

A possible annotation structure:

```json
{
  "schema_version": 1,
  "work": "example-work",
  "chapters": {
    "chapter_1": {
      "pages": {
        "23": {
          "notes": [],
          "public": {},
          "private": {},
          "annotations": []
        }
      }
    }
  }
}
```

This allows metadata to evolve indefinitely without ever touching the source images.

---

# Guiding Philosophy

Every work should have a permanent identity.

Every page should have a permanent identity.

Eventually, every meaningful region inside a page may also possess a permanent identity.

The reader displays the archive.

The catalog manages the archive.

Metadata enriches the archive.

The original works remain immutable.

By separating content from metadata, the archive becomes increasingly searchable, annotatable, and maintainable without ever modifying the original source material.

The URL is therefore not merely a way to reach a work.

It becomes the foundation upon which every future capability is built.



------------------


## Addendum: The Future of Annotations

Permanent page URLs are only the beginning.

Once every page possesses a stable identity, it becomes possible to attach meaning not merely to an entire page, but to any region within it.

Today, one might draw a simple bounding box.

Tomorrow, one might outline an irregular panel using a polygon.

The annotation itself becomes an object rather than merely a drawing.

For example:

```json
{
  "id": "ann_9b4f1a2",
  "type": "polygon",
  "points": [
    [0.18, 0.27],
    [0.31, 0.24],
    [0.44, 0.36],
    [0.39, 0.48],
    [0.21, 0.43]
  ]
}
```

Because the coordinates are normalized relative to the original image, the annotation remains perfectly aligned regardless of:

* browser zoom;
* screen resolution;
* monitor size;
* mobile or desktop viewing;
* future reader implementations.

The annotation is therefore not tied to pixels.

It is tied to the work itself.

---

### Rich Semantic Objects

An annotation should be far more than geometry.

Every region may eventually carry its own metadata.

For example:

* public tags;
* private tags;
* editorial notes;
* summaries;
* translation notes;
* quality-control reminders;
* publication status;
* character names;
* scene descriptions;
* OCR corrections;
* moderation decisions.

A single highlighted region could therefore describe not only *where* something is, but *what* it means.

---

### Interactive Reading

Annotations should not merely exist.

They should become interactive.

Imagine moving the cursor over a highlighted panel.

The shaded region softly brightens.

A connecting line appears.

A small information panel fades into view containing:

* its title;
* its tags;
* a short summary;
* editorial notes;
* related annotations;
* links to other pages;
* references elsewhere in the archive.

The reader ceases to be merely an image viewer.

It becomes an interactive knowledge layer built upon the archive.

---

### Multiple Layers

Not every annotation should be visible all the time.

Different layers may be toggled independently.

Examples include:

* Editorial
* Public
* Private
* Translation
* Character
* Research
* Moderation
* Favorites

A researcher might enable every annotation.

A casual reader might disable them entirely.

The original work remains untouched.

Only the knowledge layered upon it changes.

---

### Annotation Relationships

Annotations themselves may eventually reference one another.

A panel on page 23 could point directly to another panel on page 117.

A recurring character could be linked throughout an entire work.

An object introduced in one chapter could reference every later appearance.

Rather than isolated notes, the archive gradually becomes a network of interconnected ideas.

---

### Beyond Rectangles

Bounding boxes are merely the first primitive.

Future annotation types might include:

* rectangles;
* polygons;
* freehand regions;
* arrows;
* highlighted text;
* curved paths;
* points of interest;
* speech bubble regions;
* panel outlines;
* image masks.

The system should remain flexible enough that new annotation types can be introduced without changing the underlying philosophy.

---

### Stable Annotation Identity

Just as works possess permanent URLs, annotations should eventually possess permanent identities.

For example:

```text
/work/example-work/#page-23&annotation=ann_9b4f1a2
```

Opening such a URL could:

1. open the work;
2. navigate directly to page 23;
3. restore the annotation;
4. gently highlight the selected region;
5. display its associated information.

A conversation about the archive no longer requires saying,

> "Look at the third panel on page twenty-three."

Instead, one may simply share the annotation itself.

---

### An Evolving Archive

The archive should distinguish between content and understanding.

The content remains immutable.

The understanding grows.

Over the years, thousands of annotations, summaries, relationships, tags, and observations may accumulate without ever modifying a single source image.

The archive therefore becomes more valuable with time.

Not because the images change—

but because humanity's knowledge of them does.
