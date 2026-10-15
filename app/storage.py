"""Where a pattern's actual files live on disk, under DATA_DIR/patterns/<id>/.

Kept separate from the database row so callers never have to think about
on-disk layout -- just "save the original", "save a PDF", "get me the
thumbnail path".
"""

from __future__ import annotations

from pathlib import Path

ORIGINAL_STEM = "original"
PDF_NAME = "reference.pdf"
THUMBNAIL_NAME = "thumbnail.png"


def pattern_dir(data_dir: Path, pattern_id: int) -> Path:
    return data_dir / "patterns" / str(pattern_id)


def original_path(data_dir: Path, pattern_id: int, ext: str) -> Path:
    return pattern_dir(data_dir, pattern_id) / f"{ORIGINAL_STEM}{ext}"


def pdf_path(data_dir: Path, pattern_id: int) -> Path:
    return pattern_dir(data_dir, pattern_id) / PDF_NAME


def thumbnail_path(data_dir: Path, pattern_id: int) -> Path:
    return pattern_dir(data_dir, pattern_id) / THUMBNAIL_NAME


def save_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def delete_pattern_dir(data_dir: Path, pattern_id: int) -> None:
    import shutil

    d = pattern_dir(data_dir, pattern_id)
    if d.exists():
        shutil.rmtree(d)


def make_pdf_thumbnail(pdf_bytes: bytes, out_path: Path) -> bool:
    """Rasterize a PDF's first page to a PNG thumbnail. Returns False (and
    leaves out_path untouched) if PyMuPDF isn't available or the PDF can't
    be read -- a missing thumbnail is a cosmetic gap, not a hard failure.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return False

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pix = doc[0].get_pixmap(dpi=96)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pix.save(out_path)
        return True
    except Exception:
        return False
