# Leather Patterns

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/jaspertwigg/Leather-Patterns)

A small self-hosted library for cataloguing your leathercraft patterns:
upload a pattern file, give it a name, category and tags, and find it
again later by searching or filtering instead of digging through a folder
of cryptically-named `.lcc`/`.dxf` files.

## What it does

- **Upload** a pattern file — `.lcc`, `.dxf`, `.svg`, `.pdf`, or a photo —
  plus an optional separate reference PDF (a print-ready cut sheet, if you
  keep one apart from the CAD file).
- **Auto-fills the name** from the filename if you don't give one
  (stripping the extension, an upload-hash prefix, underscores, and a
  trailing "- Copy") — the same trick used in the companion
  [leathercraft-pdf](https://github.com/jaspertwigg/Footy-Stats-Counter)
  converter.
- **Reads `.lcc` metadata on upload**: named layers, a rough shape count,
  and the overall canvas size, shown on the pattern's detail page. (This
  is a lightweight read for cataloguing, not the full geometry engine —
  the shape count won't notice that two shapes are mirror images of the
  same piece, for instance.)
- **Thumbnails** are generated from the first page of whichever PDF is
  attached (the reference PDF, or the pattern file itself if it's already
  a PDF). No PDF attached yet → a plain file-type badge instead.
- **Search and filter** the library by name/notes text, category, or tag.
- **Edit or delete** a pattern's metadata and files at any time.

It deliberately doesn't try to *generate* those PDFs — that's what
leathercraft-pdf is for. This app is just the shelf you put the finished
patterns on.

## Where your data lives

This repository is public, but your patterns aren't. Every uploaded file
and the SQLite database live under `data/`, which is git-ignored — nothing
you upload is ever committed or pushed. Only the application code is
public.

`data/` is created automatically on first run. Back it up yourself if you
care about the patterns in it (it's just a folder you can copy/zip).

**If you deployed with the "Deploy to Render" button above on Render's
free plan:** that plan doesn't include a persistent disk, so uploaded
patterns can be wiped whenever the app redeploys or Render moves it to a
new instance. Fine for trying the app out; if you want it to reliably
keep your patterns long-term, add a small persistent disk (Render's
paid tiers support this for a few dollars a month) or run it yourself
somewhere with real storage.

There's no login or access control — anyone who can reach the app's URL
can see and delete everything in it. Run it on `localhost`, on your own
LAN, or behind your own auth/reverse proxy; don't expose it to the open
internet as-is.

## Running it

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000>.

By default, data is stored in `./data`. Point it elsewhere with:

```bash
LEATHER_PATTERNS_DATA_DIR=/path/to/your/data uvicorn app.main:app
```

## Running the tests

```bash
pip install -r requirements.txt pytest httpx
pytest
```

## Stack

FastAPI + Jinja2 templates + a plain SQLite file (via the standard
library's `sqlite3` — no ORM). PyMuPDF renders PDF thumbnails if it's
installed; without it the app still works, just without thumbnail
images. No JavaScript build step, no frontend framework — just
server-rendered HTML and a stylesheet.
