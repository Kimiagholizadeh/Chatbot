from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class GameIdentity:
    game_id: str
    internal_name: str
    display_name: str
    version: str


@dataclass(frozen=True)
class JurisdictionConfig:
    jurisdiction: str
    profile_id: str
    currencies: List[str]
    selection_method: str
    replacement_policy: str


@dataclass(frozen=True)
class LocalizationConfig:
    languages: List[str]
    help_texts: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SymbolConfig:
    """Symbol definition used by the engine."""
    id: str                   # e.g., "A", "K", "WILD", "SCAT"
    name: str                 # display name
    is_wild: bool = False
    is_scatter: bool = False
    is_bonus: bool = False


@dataclass(frozen=True)
class FeatureConfig:
    """Feature parameters. Keep this extensible."""
    free_spins_award: Dict[int, int] = field(default_factory=lambda: {3: 8, 4: 12, 5: 20})  # scatterCount->FS
    free_spins_multiplier: int = 1
    jackpot_enabled: bool = False
    jackpot_trigger: str = "none"  # "none" | "5_wild_on_line" | ...
    autoplay_enabled: bool = False


@dataclass(frozen=True)
class MathConfig:
    reel_count: int
    row_count: int
    payline_count: int

    denomination: float
    coins_per_line: int
    bet_levels: List[float]  # in currency, total bet per spin or per line? (we treat as total bet)
    max_win_multiplier: int

    symbols: List[SymbolConfig] = field(default_factory=list)

    # Data-driven math
    reel_strips: List[List[str]] = field(default_factory=list)     # list[reel] of symbol ids
    paytable: Dict[str, Dict[int, int]] = field(default_factory=dict)  # symbol -> count -> payout multiplier (coins per line)
    paylines: Optional[List[List[int]]] = None                     # generated if None

    features: FeatureConfig = field(default_factory=FeatureConfig)


@dataclass(frozen=True)
class GameSpec:
    identity: GameIdentity
    jurisdiction: JurisdictionConfig
    localization: LocalizationConfig
    math: MathConfig
