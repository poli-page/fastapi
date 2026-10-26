"""Well-formed API keys (pp_{environment}_{32 lowercase hex}) shared by the unit tests."""

from __future__ import annotations

HEX32 = "0123456789abcdef0123456789abcdef"
SANDBOX_KEY = f"pp_sandbox_{HEX32}"
LIVE_KEY = f"pp_live_{HEX32}"
