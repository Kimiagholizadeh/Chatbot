from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import streamlit as st

from .spec import GameSpec
from .util_fs import copy_uploaded_files_named, ensure_dir, write_json, write_text


def _zip_dir(folder: Path) -> bytes:
    """Zip a folder and return bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in folder.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(folder))
    return buf.getvalue()


def _extract_zip_to_temp(zip_bytes: bytes, *, prefix: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
        z.extractall(tmp)
    # Some zips wrap the project in a single top folder; if so, unwrap.
    kids = [p for p in tmp.iterdir() if p.is_dir()]
    if len(kids) == 1 and (kids[0] / "assets").exists():
        return kids[0]
    return tmp


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _write_game_pack_into_project(
    project_root: Path,
    *,
    spec: GameSpec,
    paylines: List[List[int]],
    reel_strips: List[List[str]],
    paytable: Dict[str, Dict[int, int]],
    help_texts: Dict[str, str],
    symbol_uploads_named: List[Tuple[st.runtime.uploaded_file_manager.UploadedFile, str]],
    audio_uploads_named: Optional[List[Tuple[st.runtime.uploaded_file_manager.UploadedFile, str]]],
    background_upload: Optional[st.runtime.uploaded_file_manager.UploadedFile],
    template_game_rel: str = "assets/game",
    placeholder_symbol_names: Sequence[str] = (),
) -> None:
    """Write/overwrite a data-driven game pack inside a Cocos Creator project.

    IMPORTANT: This function is designed for the safe/fast approach where a template
    project already contains placeholder assets + .meta files, and we only overwrite
    the file bytes (keeping filenames stable).

    By default, we write into assets/game/...
    """

    game_root = project_root / template_game_rel

    upload_name_map = {}
    try:
        for _up, _name in (symbol_uploads_named or []):
            if _name:
                upload_name_map[Path(_name).stem] = _name
    except Exception:
        upload_name_map = {}

    cfg_dir = ensure_dir(game_root / "configs")
    sym_dir = ensure_dir(game_root / "sprites" / "symbols")
    snd_dir = ensure_dir(game_root / "sounds")
    bg_dir = ensure_dir(game_root / "sprites" / "backgrounds")

    # 1) Copy uploaded symbol images
    # If template uses fixed placeholder filenames (Symbol_1.png...), map uploads in order.
    if placeholder_symbol_names:
        uploads_sorted = list(symbol_uploads_named)
        for i, (up, _name) in enumerate(uploads_sorted):
            if i >= len(placeholder_symbol_names):
                break
            target = sym_dir / placeholder_symbol_names[i]
            target.write_bytes(up.getbuffer())
    else:
        # If template allows symbol-id filenames, just copy as-is.
        copy_uploaded_files_named(symbol_uploads_named, sym_dir)

    # 2) Background
    if background_upload is not None:
        # overwrite base.webp (template should have meta for this)
        ext = Path(background_upload.name).suffix.lower() or ".webp"
        target = bg_dir / f"base{ext}"
        target.write_bytes(background_upload.getbuffer())

    # 3) Audio mapping
    if audio_uploads_named:
        copy_uploaded_files_named(audio_uploads_named, snd_dir)

    # 4) Config files
    # We keep the schema close to what your engine should consume.
    symbols_cfg = []
    if placeholder_symbol_names:
        # map symbol ids in spec order to placeholder filenames
        for i, s in enumerate(spec.math.symbols):
            filename = placeholder_symbol_names[min(i, len(placeholder_symbol_names) - 1)]
            symbols_cfg.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "isWild": bool(getattr(s, "is_wild", False)),
                    "isScatter": bool(getattr(s, "is_scatter", False)),
                    "isBonus": bool(getattr(s, "is_bonus", False)),
                    "sprite": f"{template_game_rel}/sprites/symbols/{filename}",
                }
            )
    else:
        for s in spec.math.symbols:
            # assume upload kept id.ext
            symbols_cfg.append(
                {
                    "id": s.id,
                    "name": s.name,
                    "isWild": bool(getattr(s, "is_wild", False)),
                    "isScatter": bool(getattr(s, "is_scatter", False)),
                    "isBonus": bool(getattr(s, "is_bonus", False)),
                    "sprite": f"{template_game_rel}/sprites/symbols/{upload_name_map.get(s.id, s.id + '.png')}",
                }
            )

    conf = {
        "schema": "slot.game.v1",
        "gameId": spec.identity.game_id,
        "name": spec.identity.display_name,
        "version": spec.identity.version,
        "layout": {"reels": spec.math.reel_count, "rows": spec.math.row_count, "paylines": spec.math.payline_count},
        "bet": {
            "denomination": spec.math.denomination,
            "coinsPerLine": spec.math.coins_per_line,
            "betLevels": spec.math.bet_levels,
        },
        "dataFiles": {
            "symbols": "configs/symbol.json",
            "paylines": "configs/paylines.json",
            "paytable": "configs/paytable.json",
            "reelStrips": "configs/reel_strips.json",
            "help": "configs/help.json",
        },
    }

    write_json(cfg_dir / "conf.json", conf)
    write_json(cfg_dir / "symbol.json", symbols_cfg)
    write_json(cfg_dir / "paylines.json", paylines)
    write_json(cfg_dir / "paytable.json", paytable)
    write_json(cfg_dir / "reel_strips.json", reel_strips)
    write_json(cfg_dir / "help.json", help_texts)

    # Also write a small manifest file so your bootstrap can find it quickly.
    write_text(cfg_dir / "manifest.txt", f"GAME_ID={spec.identity.game_id}\n")


def build_cocos_creator_web_zip(
    *,
    cocos_creator_exe: Path,
    cocos_major_version: int,
    template_project_path: Optional[Path] = None,
    template_project_zip_bytes: Optional[bytes] = None,
    platform: str = "web-mobile",
    spec: GameSpec,
    paylines: List[List[int]],
    reel_strips: List[List[str]],
    paytable: Dict[str, Dict[int, int]],
    help_texts: Dict[str, str],
    symbol_uploads_named: List[Tuple[st.runtime.uploaded_file_manager.UploadedFile, str]],
    audio_uploads_named: Optional[List[Tuple[st.runtime.uploaded_file_manager.UploadedFile, str]]] = None,
    background_upload: Optional[st.runtime.uploaded_file_manager.UploadedFile] = None,
    build_debug: bool = False,
    md5_cache: bool = True,
    # If your template keeps fixed names for symbol placeholders, set them here.
    placeholder_symbol_names: Optional[List[str]] = None,
) -> bytes:
    """Create a runnable Cocos Creator web build zip.

    This function:
      1) copies/extracts a template Cocos Creator project
      2) overwrites placeholder assets + writes configs under assets/game
      3) calls Cocos Creator CLI build for the requested platform
      4) zips the build output folder and returns bytes

    The caller is responsible for providing a template project that already contains
    valid .meta files and any scenes/prefabs/scripts needed to run.
    """

    if template_project_zip_bytes is None and template_project_path is None:
        raise ValueError("Provide either template_project_path or template_project_zip_bytes")
    if not cocos_creator_exe.exists():
        raise FileNotFoundError(f"Cocos Creator executable not found: {cocos_creator_exe}")
    if cocos_major_version not in (2, 3):
        raise ValueError("cocos_major_version must be 2 or 3")

    with tempfile.TemporaryDirectory(prefix="slot_cc_build_") as tmpdir:
        tmp = Path(tmpdir)
        # Prepare working project
        if template_project_zip_bytes is not None:
            base = _extract_zip_to_temp(template_project_zip_bytes, prefix="slot_cc_tpl_")
        else:
            base = Path(template_project_path).expanduser().resolve()
        work_project = tmp / "project"
        _copy_tree(base, work_project)

        _write_game_pack_into_project(
            work_project,
            spec=spec,
            paylines=paylines,
            reel_strips=reel_strips,
            paytable=paytable,
            help_texts=help_texts,
            symbol_uploads_named=symbol_uploads_named,
            audio_uploads_named=audio_uploads_named,
            background_upload=background_upload,
            placeholder_symbol_names=placeholder_symbol_names or (),
        )

        build_out = tmp / "build"
        build_out.mkdir(parents=True, exist_ok=True)

        build_args = f"platform={platform};debug={'true' if build_debug else 'false'};md5Cache={'true' if md5_cache else 'false'};buildPath={build_out.as_posix()}"

        if cocos_major_version == 2:
            cmd = [str(cocos_creator_exe), "--path", str(work_project), "--build", build_args]
        else:
            cmd = [str(cocos_creator_exe), "--project", str(work_project), "--build", build_args]

        env = os.environ.copy()
        env["GAME_ID"] = str(spec.identity.game_id)

        # Run build
        subprocess.run(cmd, check=True, env=env)

        # Zip build output
        return _zip_dir(build_out)
