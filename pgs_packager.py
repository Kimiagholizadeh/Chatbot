from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple


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


def _upload_bytes(upload_obj) -> bytes:
    if hasattr(upload_obj, "getvalue"):
        return bytes(upload_obj.getvalue())
    if hasattr(upload_obj, "read"):
        return bytes(upload_obj.read())
    raise TypeError("Unsupported upload object: missing getvalue()/read()")


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


def build_pgs_configurable_package_zip(
    *,
    igaming_root: Path,
    game_id: str,
    spec_identity: Dict[str, str],
    math_config: Dict[str, object],
    paylines: Dict[str, object],
    paytable: Dict[str, object],
    reel_strips: Dict[str, object],
    symbol_uploads_named: Optional[List[Tuple[object, str]]] = None,
    audio_uploads_named: Optional[List[Tuple[object, str]]] = None,
    background_upload: Optional[Tuple[object, str]] = None,
    math_pool_zip: Optional[bytes] = None,
) -> Tuple[bytes, List[str]]:
    """Build a PGS package + inject configurable game payload in canonical game locations.

    Base code/assets keep original relative locations while user-selected content is written under
    assets/gameAssets/games/<game_id>/... so the package can be used as a configurable baseline.
    """

    data, warnings = build_pgs_game_package_zip(igaming_root=igaming_root, game_id=game_id)
    gid = str(game_id).strip()
    if not gid:
        raise ValueError("game_id is required")

    game_root = f"assets/gameAssets/games/{gid}"

    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data), mode="r") as zin, zipfile.ZipFile(out, mode="w", compression=zipfile.ZIP_DEFLATED) as zout:
        # copy base package first
        for info in zin.infolist():
            zout.writestr(info, zin.read(info.filename))

        # inject configurable manifests
        zout.writestr(f"{game_root}/configs/generated_identity.json", json.dumps(spec_identity, ensure_ascii=False, indent=2).encode("utf-8"))
        zout.writestr(
            f"{game_root}/configs/generated_math.json",
            json.dumps(
                {
                    "math": math_config,
                    "paylines": paylines,
                    "paytable": paytable,
                    "reel_strips": reel_strips,
                },
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8"),
        )

        if math_pool_zip:
            zout.writestr(f"{game_root}/configs/math_pool.zip", math_pool_zip)

        # symbols -> canonical sprite location
        for upload_obj, target_name in (symbol_uploads_named or []):
            safe_name = Path(target_name).name
            zout.writestr(f"{game_root}/sprites/generated_symbols/{safe_name}", _upload_bytes(upload_obj))

        # event audio -> canonical sounds location
        for upload_obj, target_name in (audio_uploads_named or []):
            safe_name = Path(target_name).name
            zout.writestr(f"{game_root}/sounds/generated_events/{safe_name}", _upload_bytes(upload_obj))

        if background_upload is not None:
            upload_obj, target_name = background_upload
            safe_name = Path(target_name).name
            zout.writestr(f"{game_root}/sprites/generated_background/{safe_name}", _upload_bytes(upload_obj))

    return out.getvalue(), warnings
