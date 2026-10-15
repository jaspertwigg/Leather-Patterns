# Leather Patterns

A phone-only catalog for your leathercraft patterns — no sign-ups, no
database, no hosting account. Open one link, add a pattern, find it
again later.

## The actual app

**Your link:** https://claude.ai/artifact/BhBt7MEhPSNnDwG5Qn6vrM

Open that on your phone and tap Safari's "Add to Home Screen" (or
"Install app") to get an icon like any other app. That link *is* the
app — nothing to deploy, nothing to sign up for. It only opens for you,
since it's private to your Claude account.

`index.html` in this repo is the source code behind that link, kept here
so it's not just living in one place. It doesn't do anything on its own
if you open it as a plain file — the storage only works through the
Claude artifact link above.

## How it stores things, with no database

Everything — pattern metadata (name, tags, notes, layer info) and the
files themselves (your `.lcc`/`.dxf`/`.svg`/`.pdf`/photos) — lives
inside the Claude artifact itself, using two built-in capabilities of
the claude.ai platform:

- **A small database** that belongs to the page, for the metadata.
- **Asset storage** that belongs to the page, for the actual files.

Neither needs an account, a connection string, or any setup from you.
It's tied to your Claude account rather than to a server you run, which
also means: if you ever delete this artifact, everything in it goes
with it.

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
- **Save a file back out** to your phone, via the "Save original" /
  "Save PDF" buttons on a pattern's page.

### One quirk worth knowing: saving `.lcc` and `.dxf` files

The save mechanism this runs on only allows a fixed list of file
extensions, and `.lcc`/`.dxf` aren't on it — even though they're just
plain text underneath. So saving one of those gives you back the exact
same file content, but named e.g. `Trifold.lcc.json` instead of
`Trifold.lcc`. If you need it back in its original form (say, to reopen
it in LeathercraftCAD), rename it in your Files app, dropping the
`.json`/`.txt` and keeping `.lcc`/`.dxf`. PDFs, SVGs, and photos save
with their real extension, no renaming needed.
