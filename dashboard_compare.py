#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class NodeInfo:
    name: str
    x: Optional[float]
    y: Optional[float]
    w: Optional[float]
    h: Optional[float]


def _load_prefab(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_xy(v: Any) -> Tuple[Optional[float], Optional[float]]:
    if isinstance(v, dict):
        x = v.get("x", v.get("_x"))
        y = v.get("y", v.get("_y"))
        return (float(x) if x is not None else None, float(y) if y is not None else None)
    if isinstance(v, list) and len(v) >= 2:
        return (float(v[0]), float(v[1]))
    return (None, None)


def _node_info(obj: Dict[str, Any]) -> Optional[NodeInfo]:
    name = obj.get("_name") or obj.get("name")
    if not isinstance(name, str):
        return None

    x, y = _as_xy(obj.get("_position") if "_position" in obj else obj.get("position"))
    w, h = _as_xy(obj.get("_contentSize") if "_contentSize" in obj else obj.get("contentSize"))

    # Some prefabs store scalar keys directly.
    if x is None and "_position" not in obj and "x" in obj and "y" in obj:
        try:
            x = float(obj.get("x"))
            y = float(obj.get("y"))
        except Exception:
            pass

    return NodeInfo(name=name, x=x, y=y, w=w, h=h)


def _walk_json(root: Any) -> Iterable[Dict[str, Any]]:
    stack: List[Any] = [root]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            yield cur
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)


def extract_nodes(prefab_path: Path, wanted: List[str]) -> Dict[str, NodeInfo]:
    data = _load_prefab(prefab_path)
    out: Dict[str, NodeInfo] = {}
    wanted_lower = {w.lower(): w for w in wanted}

    for obj in _walk_json(data):
        ni = _node_info(obj)
        if not ni:
            continue
        k = ni.name.lower()
        if k in wanted_lower and wanted_lower[k] not in out:
            out[wanted_lower[k]] = ni

    return out


def fmt(v: Optional[float]) -> str:
    return "N/A" if v is None else f"{v:.3f}"


def compare_nodes(left: Dict[str, NodeInfo], right: Dict[str, NodeInfo], wanted: List[str]) -> str:
    lines = []
    hdr = "| Node | Left (x,y,w,h) | Right (x,y,w,h) | Δx | Δy |"
    sep = "|---|---:|---:|---:|---:|"
    lines.extend([hdr, sep])

    for n in wanted:
        l = left.get(n)
        r = right.get(n)
        if not l and not r:
            lines.append(f"| {n} | missing | missing | N/A | N/A |")
            continue

        def pack(i: Optional[NodeInfo]) -> str:
            if not i:
                return "missing"
            return f"({fmt(i.x)}, {fmt(i.y)}, {fmt(i.w)}, {fmt(i.h)})"

        dx = dy = "N/A"
        if l and r and l.x is not None and r.x is not None:
            dx = f"{(r.x - l.x):.3f}"
        if l and r and l.y is not None and r.y is not None:
            dy = f"{(r.y - l.y):.3f}"

        lines.append(f"| {n} | {pack(l)} | {pack(r)} | {dx} | {dy} |")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract/compare dashboard node positions from Cocos prefabs.")
    ap.add_argument("left", type=Path, help="Left prefab path (baseline)")
    ap.add_argument("right", type=Path, nargs="?", help="Right prefab path (for comparison)")
    ap.add_argument(
        "--nodes",
        type=str,
        default=(
            "spinButtonsPanel,spinButton,stopButton,autoSpinPanel,autoButton,autoStopButton,"
            "betPanelButton,betInfoPanel,autoPanelInfo,betPanelCloseButton,betPanel_incBet,"
            "betPanel_decBet,maxbtn,autoPanelCloseButton,btnAutoSpin,btnTurboSpin,btnQuickSpin,"
            "20Btn,50Btn,100Btn,200Btn,500Btn,1000Btn"
        ),
        help="Comma-separated node names to extract/compare",
    )
    args = ap.parse_args()

    wanted = [n.strip() for n in args.nodes.split(",") if n.strip()]

    left = extract_nodes(args.left, wanted)
    if not args.right:
        for n in wanted:
            i = left.get(n)
            if i:
                print(f"{n}: x={fmt(i.x)} y={fmt(i.y)} w={fmt(i.w)} h={fmt(i.h)}")
            else:
                print(f"{n}: missing")
        return

    right = extract_nodes(args.right, wanted)
    print(compare_nodes(left, right, wanted))


if __name__ == "__main__":
    main()
