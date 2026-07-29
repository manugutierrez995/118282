# Future Reader Architecture

> **Note:** This document describes the long-term architectural vision for the reader, catalog, and annotation system. It intentionally separates permanent design goals from current implementation details.

## Vision

Every work in the archive should eventually have its own permanent, human-readable URL.

```text
https://564578634.xyz/work/example-work/
```

Every page inside that work should also have a permanent address.

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

# Guiding Principle

The archive should distinguish between **content** and **knowledge**.

The content is immutable.

The knowledge surrounding it grows indefinitely.

Works, pages, annotations, summaries, relationships, and future discoveries should all exist as metadata layered upon the archive rather than modifications of it.

---

# Addendum: Persistent Annotation Architecture

## Addressable Knowledge

Today a work has an identity.

Eventually every page will have an identity.

One day, every meaningful region inside a page may possess its own permanent identity.

The goal is not simply to annotate images.

The goal is to make knowledge itself addressable.

---

## Normalized Coordinates

Annotations should never be stored using screen pixels.

Instead, they should use normalized coordinates relative to the original image.

```json
{
  "type": "bounding-box",
  "x": 0.18,
  "y": 0.27,
  "width": 0.34,
  "height": 0.21
}
```

Rather than storing pixel coordinates, the annotation records percentages relative to the original page.

This makes annotations independent of:

- browser zoom
- screen resolution
- monitor size
- mobile versus desktop layouts
- future reader implementations

The browser reconstructs the overlay from the current image dimensions.

---

## Non-Destructive Design

Annotations should never modify the archive itself.

Conceptually:

```text
Original Page
      +
Annotation Metadata
      =
Annotated Reader View
```

The original page remains untouched forever.

Only metadata evolves.

---

## Beyond Bounding Boxes

Rectangles are only the first primitive.

Future annotation types may include:

- rectangles
- polygons
- freehand paths
- arrows
- highlighted text
- speech bubbles
- panel outlines
- masks
- points of interest

Every annotation stores semantic information rather than rendered pixels.

---

## Rich Semantic Objects

An annotation is more than geometry.

Every region may eventually contain:

- public tags
- private tags
- summaries
- editorial notes
- OCR corrections
- translation notes
- character names
- publication status
- moderation history
- arbitrary future metadata

The annotation records not merely *where* something is, but *what it means*.

---

## Interactive Reading

Imagine hovering over a shaded polygon.

The region softly illuminates.

A subtle connector line appears.

A panel fades into view displaying:

- title
- summary
- tags
- notes
- related annotations
- references elsewhere in the archive

The reader ceases to be merely an image viewer.

It becomes an interactive knowledge layer built upon the archive.

---

## Multiple Annotation Layers

Different overlays may be independently enabled.

Examples include:

- Editorial
- Public
- Private
- Translation
- Character
- Research
- Moderation
- Favorites

The same page can therefore be viewed from entirely different perspectives without changing the underlying image.

---

## Annotation Relationships

Annotations may eventually reference one another.

A panel on page 23 may point directly to another on page 117.

Characters may be linked across an entire work.

Scenes may reference callbacks dozens of chapters later.

The archive gradually becomes a connected graph of ideas rather than isolated pages.

---

## Persistent Annotation Identity

Annotations themselves should possess permanent identifiers.

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

These identifiers make annotations searchable, editable, referenceable, and shareable.

---

## Deep Linking

Eventually a URL may reference not merely a work or page, but a specific annotation.

```text
/work/example-work/#page-23&annotation=ann_9b4f1a2
```

Opening such a URL could:

1. Open the work.
2. Navigate to page 23.
3. Restore the annotation.
4. Highlight the selected region.
5. Display its associated metadata.

---

## Looking Even Further Ahead

Perhaps the most exciting possibility is moving beyond simple highlighting.

Imagine outlining an irregular panel with a polygon.

Different regions might have different visual "temperatures" or emphasis levels.

Some could be softly shaded.

Others could glow gently to indicate importance.

Hovering over one region could reveal:

- a concise summary
- public tags
- private editorial tags
- related works
- references
- historical notes

Connector lines could visually relate distant regions on the page.

Entire conversations could emerge between annotations.

The page itself would become an interactive map of accumulated understanding.

---

## An Evolving Archive

The archive is immutable.

The knowledge surrounding it is not.

Every note, relationship, summary, tag, annotation, and future insight becomes another layer laid gently atop the original work, preserving its integrity while allowing understanding to deepen indefinitely.

The archive becomes more valuable over time—not because the images change, but because humanity's understanding of them does.
