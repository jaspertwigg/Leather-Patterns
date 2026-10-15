"""A deliberately lightweight reader for LeathercraftCAD .lcc files.

This only extracts cataloguing metadata (layer names, a rough shape count,
and the overall canvas size) for the library view -- it does not flatten
curves, merge mirrored duplicates, or do anything else that would require
reproducing the full geometry engine from the leathercraft-pdf converter.
"shape_count" is the number of distinct line groups ("gid"), which is close
to but not exactly the number of cut pieces (e.g. it won't notice that two
groups are mirror images of the same piece).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LccSummary:
    layer_names: List[str]
    shape_count: int
    canvas_w_mm: Optional[float]
    canvas_h_mm: Optional[float]


def parse_lcc_summary(raw_bytes: bytes) -> LccSummary:
    # LeathercraftCAD writes its .lcc files with a UTF-8 BOM, which plain
    # "utf-8" decoding rejects as invalid JSON -- utf-8-sig strips it if
    # present and behaves exactly like "utf-8" if it isn't.
    data = json.loads(raw_bytes.decode("utf-8-sig"))

    layer_names = [
        layer["nam"]
        for layer in data.get("layers", [])
        if layer.get("nam") and not _is_default_layer_name(layer["nam"])
    ]

    shapes = data.get("shapes", [])
    group_ids = {shape.get("gid") for shape in shapes if shape.get("gid") is not None}
    shape_count = len(group_ids) if group_ids else len(shapes)

    xs: List[float] = []
    ys: List[float] = []
    for shape in shapes:
        for point in (shape.get("sp"), shape.get("ep")):
            if point and len(point) == 2:
                xs.append(point[0])
                ys.append(point[1])

    if xs and ys:
        canvas_w_mm = max(xs) - min(xs)
        canvas_h_mm = max(ys) - min(ys)
    else:
        canvas_w_mm = None
        canvas_h_mm = None

    return LccSummary(
        layer_names=layer_names,
        shape_count=shape_count,
        canvas_w_mm=canvas_w_mm,
        canvas_h_mm=canvas_h_mm,
    )


def _is_default_layer_name(name: str) -> bool:
    # LeathercraftCAD's own placeholder, e.g. "Layer 1" -- not a real name
    # the user chose, so it's not worth showing in the catalog.
    prefix = "layer "
    rest = name.strip().lower()
    return rest.startswith(prefix) and rest[len(prefix):].isdigit()
