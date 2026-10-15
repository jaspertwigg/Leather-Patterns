# Leather Patterns

A free, personal, phone-only app for cataloguing your leathercraft
patterns. Your pattern files are stored only on your phone.

## What it does

- **Upload** a pattern file — `.lcc`, `.dxf`, `.svg`, `.pdf`, or a
  photo — plus an optional separate reference PDF.
- **Auto-fills the name** from the filename if you leave it blank.
- **Reads `.lcc` metadata on upload**: named layers, a rough shape
  count, and the overall canvas size.
- **Thumbnails** generated from the first page of whichever PDF is
  attached.
- **Search and filter** by name/notes, category, or tag.
- **Edit or delete** any pattern.
- **Save a file back out** to your phone's Files app at any time.
- Installable to your phone's home screen and works offline.
- **Backup and restore**, from Settings, to one file you keep
  somewhere of your own choosing (iCloud Drive, Google Drive, etc).

## Where your data lives

| What | Where |
| --- | --- |
| Pattern files, metadata, tags, notes | Only on your phone, in the app's private browser storage (IndexedDB) |
| The app's code | This GitHub repo, published by GitHub Pages so your phone can download and install it |

There is no server and no database in the cloud. GitHub Pages only
serves the empty app. Anyone who finds the address gets a blank copy
with no access to your patterns.

**Back up regularly.** If you delete the app, clear your browser data,
or lose your phone, the data is gone. Use *Settings → Export backup*.

## Set it up

1. **Turn on GitHub Pages.** In this repo, go to *Settings → Pages →
   Build and deployment → Source* and choose **GitHub Actions**. The
   included workflow builds and publishes the app on every push to
   `main`. The address appears on that page, like
   `https://jaspertwigg.github.io/Leather-Patterns/`.
2. **Install it on your phone.** Open that address in Safari (iPhone)
   or Chrome (Android), then choose *Share → Add to Home Screen*
   (iPhone) or *⋮ → Install app* (Android). Always open it from the
   home-screen icon — on iPhone, data saved by an installed app isn't
   cleared automatically the way plain Safari website data can be.

## How it's built

Plain HTML, CSS and JavaScript in `app/` — no build step, no
framework. Every push to `main` deploys `app/` to GitHub Pages via
`.github/workflows/deploy.yml`.

To try it locally: `cd app && python3 -m http.server` and open
<http://localhost:8000>.

| File | Purpose |
| --- | --- |
| `app/app.js` | Everything: IndexedDB storage, `.lcc` parsing, thumbnails (via pdf.js), backup/restore |
| `app/index.html` / `app/style.css` | Page shell and styling |
| `app/sw.js` | Caches the app so it opens without a connection |
| `.github/workflows/deploy.yml` | Builds and publishes to GitHub Pages |
