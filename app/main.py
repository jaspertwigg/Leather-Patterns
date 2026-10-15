from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import storage
from .database import get_connection, init_db
from .lcc_parser import parse_lcc_summary
from .naming import clean_title

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LEATHER_PATTERNS_DATA_DIR", BASE_DIR.parent / "data"))
DB_PATH = DATA_DIR / "patterns.db"

ALLOWED_PATTERN_EXTS = {".lcc", ".dxf", ".svg", ".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_PDF_EXTS = {".pdf"}


def get_db() -> sqlite3.Connection:
    conn = get_connection(DB_PATH)
    init_db(conn)
    return conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db().close()  # ensure the schema exists before the first request
    yield


app = FastAPI(title="Leather Patterns", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["layer_names"] = json.loads(d["layer_names"] or "[]")
    d["tag_list"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
    return d


def _fetch_filter_options(conn: sqlite3.Connection) -> dict:
    categories = [
        r["category"]
        for r in conn.execute(
            "SELECT DISTINCT category FROM patterns WHERE category != '' ORDER BY category"
        )
    ]
    tag_set: set[str] = set()
    for r in conn.execute("SELECT tags FROM patterns WHERE tags != ''"):
        tag_set.update(t.strip() for t in r["tags"].split(",") if t.strip())
    return {"categories": categories, "tags": sorted(tag_set)}


def _query_patterns(conn: sqlite3.Connection, q: str, category: str, tag: str) -> list[dict]:
    sql = "SELECT * FROM patterns WHERE 1=1"
    params: list[str] = []
    if q:
        sql += " AND (name LIKE ? OR notes LIKE ?)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        sql += " AND category = ?"
        params.append(category)
    if tag:
        sql += " AND (',' || tags || ',') LIKE ?"
        params.append(f"%,{tag},%")
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


@app.get("/", response_class=HTMLResponse)
def library(request: Request, q: str = "", category: str = "", tag: str = ""):
    conn = get_db()
    try:
        patterns = _query_patterns(conn, q.strip(), category.strip(), tag.strip())
        options = _fetch_filter_options(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "patterns": patterns,
            "q": q,
            "category": category,
            "tag": tag,
            **options,
        },
    )


@app.get("/api/patterns")
def api_patterns(q: str = "", category: str = "", tag: str = ""):
    conn = get_db()
    try:
        patterns = _query_patterns(conn, q.strip(), category.strip(), tag.strip())
    finally:
        conn.close()
    return patterns


@app.get("/patterns/new", response_class=HTMLResponse)
def new_pattern_form(request: Request):
    conn = get_db()
    try:
        options = _fetch_filter_options(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "upload.html", options)


@app.post("/patterns")
async def create_pattern(
    name: str = Form(""),
    category: str = Form(""),
    tags: str = Form(""),
    notes: str = Form(""),
    pattern_file: UploadFile = File(...),
    reference_pdf: Optional[UploadFile] = File(None),
):
    original_ext = Path(pattern_file.filename or "").suffix.lower()
    if original_ext not in ALLOWED_PATTERN_EXTS:
        raise HTTPException(
            400,
            f"Unsupported pattern file type '{original_ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_PATTERN_EXTS))}",
        )

    pattern_bytes = await pattern_file.read()

    pdf_bytes: Optional[bytes] = None
    if original_ext == ".pdf":
        pdf_bytes = pattern_bytes
    elif reference_pdf is not None and reference_pdf.filename:
        ref_ext = Path(reference_pdf.filename).suffix.lower()
        if ref_ext not in ALLOWED_PDF_EXTS:
            raise HTTPException(400, "The reference file must be a .pdf")
        pdf_bytes = await reference_pdf.read()

    layer_names: list[str] = []
    shape_count: Optional[int] = None
    canvas_w_mm: Optional[float] = None
    canvas_h_mm: Optional[float] = None
    if original_ext == ".lcc":
        try:
            summary = parse_lcc_summary(pattern_bytes)
            layer_names = summary.layer_names
            shape_count = summary.shape_count
            canvas_w_mm = summary.canvas_w_mm
            canvas_h_mm = summary.canvas_h_mm
        except Exception as exc:
            # Cataloging metadata is a nice-to-have, never a reason to
            # reject the upload -- but log it, since a silently-empty
            # summary (e.g. the BOM-decoding bug this once hid) is
            # otherwise invisible.
            logging.getLogger(__name__).warning(
                "Could not parse .lcc metadata for %r: %s", pattern_file.filename, exc
            )

    resolved_name = name.strip() or clean_title(pattern_file.filename or "Untitled pattern")
    now = _now()

    conn = get_db()
    try:
        cur = conn.execute(
            """INSERT INTO patterns
               (name, category, tags, notes, original_filename, original_ext,
                has_pdf, has_thumbnail, layer_names, shape_count,
                canvas_w_mm, canvas_h_mm, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)""",
            (
                resolved_name,
                category.strip(),
                _normalize_tags(tags),
                notes.strip(),
                pattern_file.filename,
                original_ext,
                1 if pdf_bytes else 0,
                json.dumps(layer_names),
                shape_count,
                canvas_w_mm,
                canvas_h_mm,
                now,
                now,
            ),
        )
        pattern_id = cur.lastrowid
        conn.commit()

        storage.save_bytes(storage.original_path(DATA_DIR, pattern_id, original_ext), pattern_bytes)

        has_thumbnail = False
        if pdf_bytes:
            if original_ext != ".pdf":
                storage.save_bytes(storage.pdf_path(DATA_DIR, pattern_id), pdf_bytes)
            has_thumbnail = storage.make_pdf_thumbnail(
                pdf_bytes, storage.thumbnail_path(DATA_DIR, pattern_id)
            )

        if has_thumbnail:
            conn.execute("UPDATE patterns SET has_thumbnail = 1 WHERE id = ?", (pattern_id,))
            conn.commit()
    finally:
        conn.close()

    return RedirectResponse(f"/patterns/{pattern_id}", status_code=303)


def _normalize_tags(raw: str) -> str:
    tags = [t.strip() for t in raw.split(",") if t.strip()]
    # de-dupe while keeping the order the user typed them in
    seen: set[str] = set()
    ordered = []
    for t in tags:
        key = t.lower()
        if key not in seen:
            seen.add(key)
            ordered.append(t)
    return ", ".join(ordered)


def _get_pattern_or_404(conn: sqlite3.Connection, pattern_id: int) -> dict:
    row = conn.execute("SELECT * FROM patterns WHERE id = ?", (pattern_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No such pattern")
    return _row_to_dict(row)


@app.get("/patterns/{pattern_id}", response_class=HTMLResponse)
def pattern_detail(request: Request, pattern_id: int):
    conn = get_db()
    try:
        pattern = _get_pattern_or_404(conn, pattern_id)
        options = _fetch_filter_options(conn)
    finally:
        conn.close()
    return templates.TemplateResponse(request, "detail.html", {"p": pattern, **options})


@app.post("/patterns/{pattern_id}/edit")
def edit_pattern(
    pattern_id: int,
    name: str = Form(...),
    category: str = Form(""),
    tags: str = Form(""),
    notes: str = Form(""),
):
    conn = get_db()
    try:
        _get_pattern_or_404(conn, pattern_id)
        conn.execute(
            "UPDATE patterns SET name = ?, category = ?, tags = ?, notes = ?, updated_at = ? WHERE id = ?",
            (name.strip() or "Untitled pattern", category.strip(), _normalize_tags(tags), notes.strip(), _now(), pattern_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(f"/patterns/{pattern_id}", status_code=303)


@app.post("/patterns/{pattern_id}/delete")
def delete_pattern(pattern_id: int):
    conn = get_db()
    try:
        _get_pattern_or_404(conn, pattern_id)
        conn.execute("DELETE FROM patterns WHERE id = ?", (pattern_id,))
        conn.commit()
    finally:
        conn.close()
    storage.delete_pattern_dir(DATA_DIR, pattern_id)
    return RedirectResponse("/", status_code=303)


@app.get("/patterns/{pattern_id}/download/original")
def download_original(pattern_id: int):
    conn = get_db()
    try:
        p = _get_pattern_or_404(conn, pattern_id)
    finally:
        conn.close()
    path = storage.original_path(DATA_DIR, pattern_id, p["original_ext"])
    if not path.exists():
        raise HTTPException(404, "Original file is missing from disk")
    return FileResponse(path, filename=p["original_filename"])


@app.get("/patterns/{pattern_id}/download/pdf")
def download_pdf(pattern_id: int):
    conn = get_db()
    try:
        p = _get_pattern_or_404(conn, pattern_id)
    finally:
        conn.close()
    if not p["has_pdf"]:
        raise HTTPException(404, "This pattern has no reference PDF")
    path = (
        storage.original_path(DATA_DIR, pattern_id, p["original_ext"])
        if p["original_ext"] == ".pdf"
        else storage.pdf_path(DATA_DIR, pattern_id)
    )
    if not path.exists():
        raise HTTPException(404, "PDF file is missing from disk")
    return FileResponse(path, filename=f"{p['name']}.pdf", media_type="application/pdf")


@app.get("/patterns/{pattern_id}/thumbnail")
def thumbnail(pattern_id: int):
    conn = get_db()
    try:
        p = _get_pattern_or_404(conn, pattern_id)
    finally:
        conn.close()
    if not p["has_thumbnail"]:
        raise HTTPException(404, "No thumbnail for this pattern")
    path = storage.thumbnail_path(DATA_DIR, pattern_id)
    if not path.exists():
        raise HTTPException(404, "Thumbnail is missing from disk")
    return FileResponse(path, media_type="image/png")
