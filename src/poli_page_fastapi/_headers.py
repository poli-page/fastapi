"""Internal: RFC 5987 / RFC 6266 Content-Disposition encoding.

Ported character-for-character from symfony-bundle's PoliPageResponseFactory
and nextjs's headers.ts. The bundle's unit tests are the canonical reference.
"""

from __future__ import annotations

from urllib.parse import quote


def build_content_disposition(filename: str, *, inline: bool = False) -> str:
    """Return a Content-Disposition header value with correct filename encoding.

    ASCII-safe filenames: `attachment; filename="..."`.
    Non-ASCII filenames: dual form —
    `attachment; filename="<ascii-fallback>"; filename*=UTF-8''<percent-encoded>`.
    """
    disposition = "inline" if inline else "attachment"
    try:
        filename.encode("ascii")
        return f'{disposition}; filename="{filename}"'
    except UnicodeEncodeError:
        ascii_fallback = filename.encode("ascii", "replace").decode("ascii")
        encoded = quote(filename, safe="")
        return f"{disposition}; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"
