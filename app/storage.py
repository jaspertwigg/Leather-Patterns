"""The one piece of file handling left once everything lives in the
database as bytes: turning a PDF's first page into a thumbnail PNG.
"""

from __future__ import annotations

from typing import Optional


def make_pdf_thumbnail(pdf_bytes: bytes) -> Optional[bytes]:
    """Rasterize a PDF's first page to a PNG thumbnail. Returns None if
    PyMuPDF isn't available or the PDF can't be read -- a missing
    thumbnail is a cosmetic gap, not a hard failure.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = doc[0].get_pixmap(dpi=96)
        return pix.tobytes("png")
    except Exception:
        return None
