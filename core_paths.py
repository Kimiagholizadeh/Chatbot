from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple


def _normalize_core_root(p: Path) -> Path:
    base = p
    if (base / "frameworks" / "cocos2d-html5").exists():
        return base
    if (base / "PongGameCore" / "frameworks" / "cocos2d-html5").exists():
        return base / "PongGameCore"
    return base


def _find_upwards(start: Path) -> Path | None:
    for p in [start] + list(start.parents):
        cand = p / ".core_cache" / "PongGameCore"
        if cand.exists():
            return _normalize_core_root(cand)
    return None


def get_core_root() -> Path:
    """Return the local PongGameCore root.

    1) Env var PONGGAMECORE_ROOT
    2) Search upwards for `.core_cache/PongGameCore`
    3) Fallback: `slot_maker/.core_cache/PongGameCore`
    """
    env = os.environ.get("PONGGAMECORE_ROOT", "").strip()
    if env:
        return _normalize_core_root(Path(env).expanduser())

    here = Path(__file__).resolve()
    found = _find_upwards(here.parents[2])
    if found:
        return found

    project_root = here.parents[1]
    return _normalize_core_root(project_root / ".core_cache" / "PongGameCore")


def core_health_report(core_root: Path) -> Tuple[bool, str]:
    needed = [
        core_root / "frameworks" / "cocos2d-html5",
        core_root / "frameworks" / "cocos2d-html5" / "CCBoot.js",
        core_root / "frameworks" / "cocos2d-html5" / "cocos2d" / "core" / "platform" / "CCClass.js",
        core_root / "frameworks" / "cocos2d-html5" / "cocos2d" / "core" / "renderer" / "RendererWebGL.js",
    ]
    missing = [p for p in needed if not p.exists()]
    if missing:
        msg = "Core not ready. Missing:\n" + "\n".join(f"- {p}" for p in missing)
        msg += "\n\nFix options:\n"
        msg += "1) Paste the correct core path in the UI field (PongGameCore root).\n"
        msg += "2) Or set env var PONGGAMECORE_ROOT.\n"
        msg += "3) Or move this project under your PGS_Assistant workspace so it can find `.core_cache`."
        msg += "\n4) Ensure your core copy is complete (RendererWebGL.js and related cocos2d/core files must exist)."
        return False, msg
    return True, f"Core OK: {core_root}"
