from __future__ import annotations

import csv
import io
import json
import random
import time
import uuid
import zipfile
from dataclasses import asdict, dataclass
from typing import Any, Dict, Iterable, List, Literal, Optional

SelectionMethod = Literal["sequential", "random_uniform", "random_weighted", "rng_stream"]
ReplacementPolicy = Literal["with_replacement", "without_replacement"]


@dataclass(frozen=True)
class PoolConfig:
    game_id: str
    game_name: str
    jurisdiction: str
    profile_id: str
    currency: str

    selection_method: SelectionMethod
    replacement_policy: ReplacementPolicy

    denom: float
    entry_levels: List[int]
    bet_levels: List[float]
    coins_per_line: int
    payline_count: int

    rtp_target_percent: float
    hit_rate_target_percent: float
    volatility_target: float
    max_win_multiplier_cap: int

    base_win_multipliers: List[float]
    base_win_weights: List[float]

    bonus_trigger_percent: float
    bonus_win_multipliers: List[float]
    bonus_win_weights: List[float]

    progressive_trigger_percent: float
    progressive_win_multiplier: float


@dataclass(frozen=True)
class TicketRow:
    ticket_id: int
    ticket_num: str
    game_id: str
    correlation_id: str

    jurisdiction: str
    profile_id: str
    currency: str

    entryLevel: int
    denom: float
    betLevel: float
    bet_amount: float

    mainGame: Dict[str, Any]

    base_win: float
    bonus_win: float
    progressive_win: float
    ticketWin: float
    totalWin: float

    hit: bool
    bonus_trigger: bool
    progressive_trigger: bool

    metrics: Optional[Dict[str, Any]] = None


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def apply_hit_rate(multipliers: List[float], weights: List[float], hit_rate_target_percent: float) -> List[float]:
    if hit_rate_target_percent <= 0:
        return weights[:]

    zero_idx = [i for i, m in enumerate(multipliers) if m == 0]
    nonzero_idx = [i for i, m in enumerate(multipliers) if m != 0]
    if not zero_idx:
        raise RuntimeError("Hit-rate targeting requires a 0 multiplier in base_win_multipliers.")
    if not nonzero_idx:
        raise RuntimeError("Hit-rate targeting requires at least one non-zero multiplier.")

    desired = hit_rate_target_percent / 100.0
    if not (0.0 < desired < 1.0):
        raise RuntimeError("Hit-rate target must be between 0 and 100 (exclusive).")

    total_nonzero = sum(weights[i] for i in nonzero_idx)
    if total_nonzero <= 0:
        raise RuntimeError("Non-zero weights must sum to > 0.")
    target_zero_total = total_nonzero * (1 - desired) / desired

    updated = weights[:]
    existing_zero_total = sum(updated[i] for i in zero_idx)
    if existing_zero_total > 0:
        scale = target_zero_total / existing_zero_total
        for i in zero_idx:
            updated[i] *= scale
    else:
        per = target_zero_total / len(zero_idx)
        for i in zero_idx:
            updated[i] = per
    return updated


def _generate_outcome(rng: random.Random, cfg: PoolConfig, adjusted_base_weights: List[float]) -> tuple[float, bool, float, bool, float, bool]:
    base_mult = rng.choices(cfg.base_win_multipliers, weights=adjusted_base_weights, k=1)[0]
    hit = base_mult > 0

    bonus_trigger = rng.random() < (cfg.bonus_trigger_percent / 100.0)
    bonus_mult = 0.0
    if bonus_trigger:
        bonus_mult = rng.choices(cfg.bonus_win_multipliers, weights=cfg.bonus_win_weights, k=1)[0]

    prog_trigger = rng.random() < (cfg.progressive_trigger_percent / 100.0)
    prog_mult = cfg.progressive_win_multiplier if prog_trigger else 0.0
    return base_mult, hit, bonus_mult, bonus_trigger, prog_mult, prog_trigger


def _build_ticket(ticket_id: int, rng: random.Random, cfg: PoolConfig, adjusted_base_weights: List[float], pool_seed_u64: int) -> TicketRow:
    bet_level = rng.choice(cfg.bet_levels)
    entry_level = rng.choice(cfg.entry_levels)
    bet_amount = float(bet_level)

    base_mult, hit, bonus_mult, bonus_trigger, prog_mult, prog_trigger = _generate_outcome(rng, cfg, adjusted_base_weights)
    base_win = bet_amount * base_mult
    bonus_win = bet_amount * bonus_mult
    progressive_win = bet_amount * prog_mult

    pre_cap_total = base_win + bonus_win + progressive_win
    cap_value = bet_amount * float(cfg.max_win_multiplier_cap)
    total_win = min(pre_cap_total, cap_value)

    wls: List[List[int]] = []
    if total_win > 0 and cfg.payline_count > 0:
        base_line_total = min(base_win, total_win)
        remaining = int(round(base_line_total))
        line_hits = min(cfg.payline_count, max(1, int(rng.random() * 4) + 1))
        for _ in range(line_hits):
            if remaining <= 0:
                break
            piece = remaining if line_hits == 1 else rng.randint(1, remaining)
            remaining -= piece
            line_id = rng.randrange(cfg.payline_count)
            sym_count = rng.choice([3, 4, 5])
            sym_id = rng.choice([1, 2, 3, 4, 5, 6, 7, 8, 9])
            wls.append([line_id, sym_count, sym_id, int(piece)])

    reel_count = 5
    row_count = 3
    window = [rng.randint(1, 12) for _ in range(reel_count * row_count)]
    ticket_win_int = float(int(round(total_win)))

    main_game = {"reels": [window], "wls": [wls], "win": ticket_win_int}

    return TicketRow(
        ticket_id=ticket_id,
        ticket_num=str(ticket_id),
        game_id=cfg.game_id,
        correlation_id=f"{cfg.game_id}-{pool_seed_u64}-{ticket_id}",
        jurisdiction=cfg.jurisdiction,
        profile_id=cfg.profile_id,
        currency=cfg.currency,
        entryLevel=entry_level,
        denom=float(cfg.denom),
        betLevel=float(bet_level),
        bet_amount=float(bet_amount),
        mainGame=main_game,
        base_win=float(base_win),
        bonus_win=float(bonus_win),
        progressive_win=float(progressive_win),
        ticketWin=ticket_win_int,
        totalWin=ticket_win_int,
        hit=hit,
        bonus_trigger=bonus_trigger,
        progressive_trigger=prog_trigger,
        metrics={"poolSeed": str(pool_seed_u64), "notes": "distribution-template"},
    )


def tickets_to_csv_bytes(tickets: Iterable[TicketRow]) -> bytes:
    out = io.StringIO()
    writer: Optional[csv.DictWriter] = None
    for t in tickets:
        row = asdict(t)
        row["mainGame"] = json.dumps(row["mainGame"], separators=(",", ":"))
        if row.get("metrics") is not None:
            row["metrics"] = json.dumps(row["metrics"], separators=(",", ":"))
        if writer is None:
            writer = csv.DictWriter(out, fieldnames=list(row.keys()))
            writer.writeheader()
        writer.writerow(row)
    return out.getvalue().encode("utf-8")


def tickets_to_jsonl_bytes(tickets: Iterable[TicketRow]) -> bytes:
    out = io.StringIO()
    for t in tickets:
        out.write(json.dumps(asdict(t), separators=(",", ":")))
        out.write("\n")
    return out.getvalue().encode("utf-8")


def build_pool_manifest(*, meta: Dict[str, Any], files: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {"schema": "pgs.mathpool.v1", "pool_id": meta["pool_id"], "created_at": meta["created_at"], "meta": meta, "files": files}


def export_math_pool_zip(*, cfg: PoolConfig, ticket_count: int, seed_u64: Optional[int] = None, progress_callback: Optional[callable] = None) -> bytes:
    if ticket_count <= 0:
        raise ValueError("ticket_count must be > 0")

    if len(cfg.base_win_multipliers) != len(cfg.base_win_weights):
        raise ValueError("base_win_multipliers and base_win_weights must have same length")
    if len(cfg.bonus_win_multipliers) != len(cfg.bonus_win_weights):
        raise ValueError("bonus_win_multipliers and bonus_win_weights must have same length")

    adjusted_base_weights = apply_hit_rate(cfg.base_win_multipliers, cfg.base_win_weights, cfg.hit_rate_target_percent)

    pool_seed_u64 = int(seed_u64) if seed_u64 is not None else random.getrandbits(64)
    rng = random.Random(pool_seed_u64)

    tickets: List[TicketRow] = []
    for i in range(1, ticket_count + 1):
        tickets.append(_build_ticket(i, rng, cfg, adjusted_base_weights, pool_seed_u64))
        if progress_callback and (i % 10_000 == 0 or i == ticket_count):
            progress_callback(i, ticket_count)

    total_bet = sum(t.bet_amount for t in tickets)
    total_win = sum(t.totalWin for t in tickets)
    hit_rate = (sum(1 for t in tickets if t.hit) / ticket_count) if ticket_count else 0.0
    bonus_rate = (sum(1 for t in tickets if t.bonus_trigger) / ticket_count) if ticket_count else 0.0
    prog_rate = (sum(1 for t in tickets if t.progressive_trigger) / ticket_count) if ticket_count else 0.0
    rtp = (total_win / total_bet) if total_bet else 0.0

    pool_id = str(uuid.uuid4())
    created_at = _utc_now_iso()

    meta: Dict[str, Any] = {
        "pool_id": pool_id,
        "created_at": created_at,
        "game_id": cfg.game_id,
        "game_name": cfg.game_name,
        "jurisdiction": cfg.jurisdiction,
        "profile_id": cfg.profile_id,
        "currency": cfg.currency,
        "selection_method": cfg.selection_method,
        "replacement_policy": cfg.replacement_policy,
        "ticket_count": ticket_count,
        "seed_u64": str(pool_seed_u64),
        "wager": {"denom": cfg.denom, "entry_levels": cfg.entry_levels, "bet_levels": cfg.bet_levels, "coins_per_line": cfg.coins_per_line},
        "layout": {"payline_count": cfg.payline_count},
        "targets": {
            "rtp_target_percent": cfg.rtp_target_percent,
            "hit_rate_target_percent": cfg.hit_rate_target_percent,
            "volatility_target": cfg.volatility_target,
            "max_win_multiplier_cap": cfg.max_win_multiplier_cap,
            "bonus_trigger_percent": cfg.bonus_trigger_percent,
            "progressive_trigger_percent": cfg.progressive_trigger_percent,
        },
        "observed": {
            "rtp_total_percent": rtp * 100,
            "hit_rate_any_win_percent": hit_rate * 100,
            "bonus_trigger_rate_percent": bonus_rate * 100,
            "progressive_trigger_rate_percent": prog_rate * 100,
        },
    }

    csv_bytes = tickets_to_csv_bytes(tickets)
    jsonl_bytes = tickets_to_jsonl_bytes(tickets)

    files: List[Dict[str, Any]] = [
        {"path": "math_pool.csv", "format": "csv", "rows": ticket_count},
        {"path": "math_pool.jsonl", "format": "jsonl", "rows": ticket_count},
    ]
    manifest = build_pool_manifest(meta=meta, files=files)
    manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")

    written: set[str] = set()
    def writestr_unique(zf: zipfile.ZipFile, name: str, data: bytes) -> None:
        if name in written:
            raise RuntimeError(f"Duplicate file in zip: {name}")
        zf.writestr(name, data)
        written.add(name)

    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            writestr_unique(zf, "math_pool.csv", csv_bytes)
            writestr_unique(zf, "math_pool.jsonl", jsonl_bytes)
            writestr_unique(zf, "manifest.json", manifest_bytes)
        return buffer.getvalue()
