from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import psycopg
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import storage
from .database import get_connection, init_db
from .lcc_parser import parse_lcc_summary
from .naming import clean_title

BASE_DIR = Path(__file__).resolve().parent

ALLOWED_PATTERN_EXTS = {".lcc", ".dxf", ".svg", ".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_PDF_EXTS = {".pdf"}


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Leather Patterns stores everything in "
            "Postgres (e.g. a free database from neon.com) -- see the README."
        )
    return url


def get_db() -> psycopg.Connection:
    conn = get_connection(_database_url())
    init_db(conn)
    return conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db().close()  # ensure the schema exists before the first request
    yield


app = FastAPI(title="Leather Patterns", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _row_to_dict(row: dict) -> dict:
    d = dict(row)
    for key in ("created_at", "updated_at"):
        if key in d and d[key] is not None:
            d[key] = d[key].isoformat()
    d["layer_names"] = json.loads(d["layer_names"] or "[]")
    d["tag_list"] = [t.strip() for t in d["tags"].split(",") if t.strip()]
    if "has_pdf" not in d:
        d["has_pdf"] = d.get("pdf_bytes") is not None or d.get("original_ext") == ".pdf"
    if "has_thumbnail" not in d:
        d["has_thumbnail"] = d.get("thumbnail_bytes") is not None
    d.pop("original_bytes", None)
    d.pop("pdf_bytes", None)
    d.pop("thumbnail_bytes", None)
    return d


# Deliberately selects booleans rather than the pdf/thumbnail blobs
# themselves -- the library and detail views only need to know whether
# they exist, not pull the actual bytes over the wire.
_LIST_COLUMNS = """
    id, name, category, tags, notes, original_filename, original_ext,
    (pdf_bytes IS NOT NULL OR original_ext = '.pdf') AS has_pdf,
    (thumbnail_bytes IS NOT NULL) AS has_thumbnail,
    layer_names, shape_count, canvas_w_mm, canvas_h_mm, created_at, updated_at
"""


def _fetch_filter_options(conn: psycopg.Connection) -> dict:
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


def _query_patterns(conn: psycopg.Connection, q: str, category: str, tag: str) -> list[dict]:
    sql = f"SELECT {_LIST_COLUMNS} FROM patterns WHERE 1=1"
    params: list[str] = []
    if q:
        sql += " AND (name ILIKE %s OR notes ILIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if category:
        sql += " AND category = %s"
        params.append(category)
    if tag:
        sql += " AND (',' || tags || ',') LIKE %s"
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

    thumbnail_bytes: Optional[bytes] = None
    if pdf_bytes:
        thumbnail_bytes = storage.make_pdf_thumbnail(pdf_bytes)

    # The original file is kept separately from the reference PDF -- unless
    # the original *is* the PDF, in which case one copy serves both roles.
    stored_pdf_bytes = None if original_ext == ".pdf" else pdf_bytes
    resolved_name = name.strip() or clean_title(pattern_file.filename or "Untitled pattern")

    conn = get_db()
    try:
        row = conn.execute(
            """INSERT INTO patterns
               (name, category, tags, notes, original_filename, original_ext,
                original_bytes, pdf_bytes, thumbnail_bytes, layer_names,
                shape_count, canvas_w_mm, canvas_h_mm)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (
                resolved_name,
                category.strip(),
                _normalize_tags(tags),
                notes.strip(),
                pattern_file.filename,
                original_ext,
                pattern_bytes,
                stored_pdf_bytes,
                thumbnail_bytes,
                json.dumps(layer_names),
                shape_count,
                canvas_w_mm,
                canvas_h_mm,
            ),
        ).fetchone()
        pattern_id = row["id"]
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


def _get_pattern_or_404(conn: psycopg.Connection, pattern_id: int, columns: str = _LIST_COLUMNS) -> dict:
    row = conn.execute(f"SELECT {columns} FROM patterns WHERE id = %s", (pattern_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "No such pattern")
    return row


@app.get("/patterns/{pattern_id}", response_class=HTMLResponse)
def pattern_detail(request: Request, pattern_id: int):
    conn = get_db()
    try:
        pattern = _row_to_dict(_get_pattern_or_404(conn, pattern_id))
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
        _get_pattern_or_404(conn, pattern_id, columns="id")
        conn.execute(
            """UPDATE patterns SET name = %s, category = %s, tags = %s, notes = %s,
               updated_at = now() WHERE id = %s""",
            (name.strip() or "Untitled pattern", category.strip(), _normalize_tags(tags), notes.strip(), pattern_id),
        )
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse(f"/patterns/{pattern_id}", status_code=303)


@app.post("/patterns/{pattern_id}/delete")
def delete_pattern(pattern_id: int):
    conn = get_db()
    try:
        _get_pattern_or_404(conn, pattern_id, columns="id")
        conn.execute("DELETE FROM patterns WHERE id = %s", (pattern_id,))
        conn.commit()
    finally:
        conn.close()
    return RedirectResponse("/", status_code=303)


@app.get("/patterns/{pattern_id}/download/original")
def download_original(pattern_id: int):
    conn = get_db()
    try:
        p = _get_pattern_or_404(conn, pattern_id, columns="original_filename, original_bytes")
    finally:
        conn.close()
    return Response(
        content=bytes(p["original_bytes"]),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{p["original_filename"]}"'},
    )


@app.get("/patterns/{pattern_id}/download/pdf")
def download_pdf(pattern_id: int):
    conn = get_db()
    try:
        p = _get_pattern_or_404(conn, pattern_id, columns="name, original_ext, original_bytes, pdf_bytes")
    finally:
        conn.close()
    pdf_bytes = p["original_bytes"] if p["original_ext"] == ".pdf" else p["pdf_bytes"]
    if pdf_bytes is None:
        raise HTTPException(404, "This pattern has no reference PDF")
    return Response(
        content=bytes(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{p["name"]}.pdf"'},
    )


@app.get("/patterns/{pattern_id}/thumbnail")
def thumbnail(pattern_id: int):
    conn = get_db()
    try:
        p = _get_pattern_or_404(conn, pattern_id, columns="thumbnail_bytes")
    finally:
        conn.close()
    if p["thumbnail_bytes"] is None:
        raise HTTPException(404, "No thumbnail for this pattern")
    return Response(content=bytes(p["thumbnail_bytes"]), media_type="image/png")
