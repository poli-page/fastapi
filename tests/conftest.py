"""Root pytest conftest — loads the workspace-root .env once at collection time.

Single source of truth (INTEGRATIONS_PLAN.md §"Cross-cutting DX patterns" §2):
no per-app .env.local. Real shell exports always win.
"""

from __future__ import annotations

import os
from pathlib import Path


def _load_root_env() -> None:
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)


_load_root_env()
