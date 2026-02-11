from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import List, Sequence, Tuple


def _required_roots(game_id: str) -> List[Path]:
    gid = str(game_id).strip()
    if not gid:
        raise ValueError("game_id is required")

    return [
        Path("assets") / "gameAssets" / "games" / gid,
        Path("assets") / "gameAssets" / "games" / f"{gid}_splash",
        Path("assets") / "resources" / "common",
        Path("assets") / "scripts" / "core" / "components",
        Path("assets") / "scripts" / "core" / "constants",
        Path("assets") / "scripts" / "core" / "msg",
        Path("assets") / "scripts" / "core" / "parser",
        Path("assets") / "scripts" / "core" / "scenes",
        Path("assets") / "scripts" / "core" / "ui",
        Path("assets") / "scripts" / "util",
    ]


def _collect_missing_metas(files: Sequence[Path]) -> List[Path]:
    missing: List[Path] = []
    for fp in files:
        if fp.suffix == ".meta":
            continue
        meta = fp.with_name(fp.name + ".meta")
        if not meta.exists():
            missing.append(meta)
    return missing


def build_pgs_game_package_zip(*, igaming_root: Path, game_id: str) -> Tuple[bytes, List[str]]:
    """Create a zip package for a single PGS-Igaming game with core dependencies.

    Returns a tuple (zip_bytes, warnings). Warnings currently include missing .meta pairs.
    """

    root = Path(igaming_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Invalid PGS-Igaming root: {root}")

    relative_roots = _required_roots(game_id)
    abs_roots = [root / rel for rel in relative_roots]

    missing_roots = [rel.as_posix() for rel, abs_root in zip(relative_roots, abs_roots) if not abs_root.exists()]
    if missing_roots:
        raise FileNotFoundError(
            "Missing required game/core folders under PGS-Igaming root:\n- " + "\n- ".join(missing_roots)
        )

    files_to_copy: List[Path] = []
    for abs_root in abs_roots:
        files_to_copy.extend([p for p in abs_root.rglob("*") if p.is_file()])

    warnings: List[str] = []
    missing_metas = _collect_missing_metas(files_to_copy)
    if missing_metas:
        preview = "\n- ".join(str(p.relative_to(root)).replace("\\", "/") for p in missing_metas[:50])
        suffix = "" if len(missing_metas) <= 50 else f"\n... and {len(missing_metas) - 50} more"
        warnings.append(f"Missing .meta pair files detected ({len(missing_metas)}):\n- {preview}{suffix}")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in files_to_copy:
            rel = fp.relative_to(root).as_posix()
            zf.write(fp, rel)

    return buffer.getvalue(), warnings
