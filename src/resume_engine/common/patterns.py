"""Shared regex patterns used by both segmentation and extraction.

Kept in one place so a fix (like the phone-regex false-positive on date
ranges found during the parsing/segmentation task) only has to happen
once instead of drifting between two copies.
"""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")

# Requires a realistic phone-number grouping (optional country code plus a
# 3-3-4-style split) rather than "any digit ... any digit" -- the looser
# version originally here matched date ranges like "2019 - 2022" as a
# phone number.
PHONE_RE = re.compile(r"(?<!\d)(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}(?!\d)")

URL_RE = re.compile(
    r"\b(?:https?://|www\.)[^\s,;]+"
    r"|(?<!@)\b[a-zA-Z0-9-]+\.(?:com|org|net|io|dev|me|co)(?:/[^\s,;]*)?",
    re.IGNORECASE,
)
