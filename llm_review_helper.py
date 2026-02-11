from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Iterable, List, Tuple


DEFAULT_REVIEW_FILES = [
    "ui_game_generator.py",
    "dev_builder.py",
    "math_pool_engine.py",
    "pgs_packager.py",
    "cocos_creator_builder.py",
    "core_paths.py",
    "spec.py",
    "README_RUN.txt",
    "LOCATE_COMMON_ELEMENTS.md",
]


def _existing_files(repo_root: Path, rel_paths: Iterable[str]) -> List[Path]:
    out: List[Path] = []
    for rel in rel_paths:
        p = repo_root / rel
        if p.exists() and p.is_file():
            out.append(p)
    return out


def build_llm_review_prompt(*, files: List[Path], repo_root: Path) -> str:
    rels = [p.relative_to(repo_root).as_posix() for p in files]
    rel_block = "\n".join(f"- {r}" for r in rels)
    return (
        "You are reviewing a slot-game generator codebase.\n\n"
        "Please review for:\n"
        "1) Architecture and separation of concerns\n"
        "2) Runtime reliability (audio, assets, free-spin flow, reel stop behavior)\n"
        "3) Math correctness and RTP calibration safety\n"
        "4) Streamlit UI-to-backend mapping completeness\n"
        "5) Packaging correctness for PGS base/configurable exports\n"
        "6) Error handling and edge cases\n"
        "7) Maintainability and testability\n\n"
        "Provide findings as:\n"
        "- Severity (High/Medium/Low)\n"
        "- File + line references\n"
        "- Why it matters\n"
        "- Suggested fix\n\n"
        "Files to review:\n"
        f"{rel_block}\n"
    )


def build_llm_review_bundle_zip(*, repo_root: Path, selected_rel_paths: List[str] | None = None) -> Tuple[bytes, List[str]]:
    root = Path(repo_root).resolve()
    wanted = selected_rel_paths or DEFAULT_REVIEW_FILES
    files = _existing_files(root, wanted)

    warnings: List[str] = []
    missing = [r for r in wanted if not (root / r).exists()]
    if missing:
        warnings.append("Missing selected files:\n- " + "\n- ".join(missing))

    prompt = build_llm_review_prompt(files=files, repo_root=root)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("LLM_REVIEW_PROMPT.md", prompt.encode("utf-8"))
        for fp in files:
            rel = fp.relative_to(root).as_posix()
            zf.writestr(rel, fp.read_bytes())

    return buf.getvalue(), warnings
