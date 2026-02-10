from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Iterable, Optional

import streamlit as st


def safe_internal_name(text: str) -> str:
    """Turns any string into a safe folder/key: letters/numbers/_ only."""
    text = (text or "").strip().replace(" ", "_")
    text = re.sub(r"[^A-Za-z0-9_]+", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "Game"


def ensure_dir(p: Path) -> Path:
    """Ensure directory exists; return the Path for chaining."""
    p.mkdir(parents=True, exist_ok=True)
    return p


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def copy_file(src: Path, dst: Path) -> None:
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def write_text(path: Path, content: str) -> None:
    ensure_dir(path.parent)
    path.write_text(content, encoding="utf-8")


def write_bytes(path: Path, data: bytes) -> None:
    ensure_dir(path.parent)
    path.write_bytes(data)


def write_json(path: Path, data: object) -> None:
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def copy_uploaded_files(
    files: Iterable[Optional[st.runtime.uploaded_file_manager.UploadedFile]],
    dst_dir: Path,
) -> list[str]:
    """Copy Streamlit uploads into dst_dir; return filenames copied."""
    ensure_dir(dst_dir)
    copied: list[str] = []
    for f in files:
        if not f:
            continue
        out = dst_dir / f.name
        out.write_bytes(f.getvalue())
        copied.append(f.name)
    return copied


def copy_uploaded_files_named(
    files: Iterable[tuple[st.runtime.uploaded_file_manager.UploadedFile, str]],
    dst_dir: Path,
) -> list[str]:
    """Copy uploads to dst_dir under provided target filenames."""
    ensure_dir(dst_dir)
    copied: list[str] = []
    for f, target_name in files:
        if not f or not target_name:
            continue
        out = dst_dir / target_name
        out.write_bytes(f.getvalue())
        copied.append(target_name)
    return copied
