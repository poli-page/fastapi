"""Internal: RFC 6266 / RFC 8187 (ex-5987) Content-Disposition encoding.

Same contract as the other Poli Page framework integrations (django-poli-page's
``_build_disposition`` is the reference): control characters are stripped, ``\\``
and ``"`` are escaped as quoted-pairs, and non-ASCII filenames get the dual
``filename="<ascii-fallback>"; filename*=UTF-8''<percent-encoded>`` notation.
"""

from __future__ import annotations

import re
from urllib.parse import quote

# C0 controls (incl. TAB, CR, LF), DEL and C1 controls. None of them belong in a
# filename, and CR/LF would split the header (response splitting).
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def build_content_disposition(filename: str, *, inline: bool = False) -> str:
    """Return a Content-Disposition header value with correct filename encoding.

    ASCII filenames: ``attachment; filename="..."``.
    Non-ASCII filenames: dual form —
    ``attachment; filename="<ascii-fallback>"; filename*=UTF-8''<percent-encoded>``.
    """
    disposition = "inline" if inline else "attachment"
    clean = _CONTROL_CHARS.sub("", filename)
    if clean.isascii():
        return f'{disposition}; filename="{_quoted_string_content(clean)}"'
    ascii_fallback = clean.encode("ascii", "replace").decode("ascii")
    encoded = quote(clean, safe="")
    return (
        f'{disposition}; filename="{_quoted_string_content(ascii_fallback)}"; '
        f"filename*=UTF-8''{encoded}"
    )


def _quoted_string_content(value: str) -> str:
    """Escape ``\\`` and ``"`` as quoted-pairs (RFC 9110 §5.6.4)."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
