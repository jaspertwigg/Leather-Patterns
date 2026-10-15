"""Turn an uploaded filename into a readable default pattern name."""

from __future__ import annotations

import os
import re


def clean_title(filename: str) -> str:
    name = os.path.splitext(os.path.basename(filename))[0]
    name = re.sub(r"^[0-9a-f]{6,12}-(?=[A-Za-z])", "", name)
    name = name.replace("_", " ")
    name = re.sub(r"\s*-\s*Copy\s*$", "", name, flags=re.IGNORECASE)
    return " ".join(name.split())
