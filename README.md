# Leather Patterns

A small library for cataloguing your leathercraft patterns: upload a
pattern file, give it a name, category and tags, and find it again later
by searching or filtering instead of digging through a folder of
cryptically-named `.lcc`/`.dxf` files.

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
- Installable to a phone's home screen like a regular app (it's a website
  under the hood, so no app store needed) — the same as the other apps
  built for this account.

It deliberately doesn't try to *generate* those PDFs — that's what
leathercraft-pdf is for. This app is just the shelf you put the finished
patterns on.

## Putting it online (so you can use it from your phone too), for free

This needs two free accounts: one for a permanent little database (so
your patterns don't disappear), and one to actually run the app and give
it a web address. Both have free tiers with no card required.

1. **Database — [neon.com](https://neon.com)**: sign up free, create a
   project, and copy the "connection string" it gives you (starts with
   `postgresql://`).
2. **Hosting — [render.com](https://render.com)**: sign up free, click
   **New +** → **Blueprint**, connect this GitHub repo, and pick this
   branch. Render will read `render.yaml` in this repo and set itself up
   automatically. When it asks for an environment variable, add:
   - `DATABASE_URL` — the connection string from Neon
3. Click deploy and wait a few minutes. Render gives you a URL like
   `https://leather-patterns.onrender.com` — that's your app, reachable
   from any device.
4. On your phone, open that URL in the browser, then use the browser's
   "Add to Home Screen" (or "Install app") option to get an app icon on
   your home screen.

Everything — your patterns' metadata and the files themselves — lives in
the Neon database, not on Render's own disk, so your data is safe even
though the free Render plan's disk isn't persistent. The free Render plan
does put the app to sleep after a while with no visits, so the first open
after a quiet spell takes 30-60 seconds to wake up.

## Where your data lives

This repository is public, but your patterns aren't. Nothing you upload
is ever committed or pushed to GitHub — it all lives in whichever Postgres
database `DATABASE_URL` points at (Neon, if you followed the steps
above), separate from this code entirely.

There's no login or access control — anyone who has the app's URL can
see and delete everything in it. That URL is only as guessable as Render
makes it, but if you want real privacy, put it behind your own
auth/reverse proxy rather than relying on the URL being obscure.

## Running it on your own computer instead

Requires Python 3.11+ and a Postgres database (a free
[neon.com](https://neon.com) one works fine here too, or a local Postgres
install).

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://user:password@host/dbname
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000>.

## Running the tests

The tests need their own Postgres database (so they never touch your real
patterns) — point `TEST_DATABASE_URL` at one, or they'll default to
`postgresql://root:devpass@127.0.0.1:5432/leather_patterns_test`.

```bash
pip install -r requirements.txt pytest httpx
pytest
```

## Stack

FastAPI + Jinja2 templates + Postgres (via `psycopg`, no ORM) — pattern
files and thumbnails are stored as bytes directly in the database, so
there's no separate file storage to configure or lose. PyMuPDF renders
PDF thumbnails if it's installed; without it the app still works, just
without thumbnail images. No JavaScript build step, no frontend
framework — just server-rendered HTML and a stylesheet.
