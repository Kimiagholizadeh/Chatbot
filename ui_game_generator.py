from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st

from .core_paths import core_health_report, get_core_root
from .dev_builder import build_dev_web_zip
from .cocos_creator_builder import build_cocos_creator_web_zip
from .math_pool_engine import PoolConfig, export_math_pool_zip
from .paylines import generate_paylines
from .spec import (
    FeatureConfig,
    GameIdentity,
    GameSpec,
    JurisdictionConfig,
    LocalizationConfig,
    MathConfig,
    SymbolConfig,
)
from .util_fs import safe_internal_name


AUDIO_KEYS = [
    ("spin", "Spin"),
    ("reel_stop", "Reel stop"),
    ("win", "Win"),
    ("bigwin", "Big win"),
    ("freespin", "Free spins"),
    ("click", "UI click"),
]


class _MemoryUpload:
    """Small adapter with UploadedFile-like API for build functions."""

    def __init__(self, *, name: str, data: bytes) -> None:
        self.name = name
        self._data = data

    def getvalue(self) -> bytes:
        return self._data

    def getbuffer(self):
        return memoryview(self._data)


def _resolve_core_root(override: str) -> Path:
    override = (override or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return get_core_root()


def _parse_csv_floats(text: str) -> List[float]:
    out: List[float] = []
    for p in (text or "").replace(";", ",").split(","):
        p = p.strip()
        if not p:
            continue
        out.append(float(p))
    return out or [1.0]


def _parse_csv_ints(text: str) -> List[int]:
    out: List[int] = []
    for p in (text or "").replace(";", ",").split(","):
        p = p.strip()
        if not p:
            continue
        out.append(int(p))
    return out or [1]


def _step_header(title: str, step: int, total: int) -> None:
    st.progress((step + 1) / total)
    st.subheader(f"Step {step+1}/{total}: {title}")
    st.markdown("---")


def _nav(step: int, total: int) -> None:
    c1, c2, c3 = st.columns([1,1,3])
    with c1:
        if st.button("Back", disabled=(step <= 0)):
            st.session_state.wiz_step = max(0, step - 1)
            st.rerun()
    with c2:
        if st.button("Next", disabled=(step >= total - 1)):
            st.session_state.wiz_step = min(total - 1, step + 1)
            st.rerun()


def show_game_generator() -> None:
    st.title("Slot Maker Wizard")
    st.caption("Multi-step wizard that generates: runnable web build + (optional) math pool zip embedded in output.")
    st.markdown("")

    if "wiz_step" not in st.session_state:
        st.session_state.wiz_step = 0

    # persistent shared keys with defaults
    st.session_state.setdefault("core_root_override", "")
    st.session_state.setdefault("igaming_root_override", "")
    st.session_state.setdefault("display_name", "My Slot Game")
    # internal name handling: use a separate widget key to avoid Streamlit "cannot modify after instantiation"
    st.session_state.setdefault("lock_internal_name", True)
    st.session_state.setdefault("internal_name_manual", False)
    st.session_state.setdefault("internal_name_widget", safe_internal_name(st.session_state["display_name"]))
    # one-time migration: older versions used key="internal_name" for the widget
    if not st.session_state.get("_migrated_internal_name_key", False):
        if "internal_name" in st.session_state and "internal_name_widget" not in st.session_state:
            st.session_state["internal_name_widget"] = str(st.session_state.get("internal_name", ""))
        # remove old widget-bound key to prevent StreamlitAPIException
        try:
            st.session_state.pop("internal_name", None)
        except Exception:
            pass
        st.session_state["_migrated_internal_name_key"] = True
    st.session_state.setdefault("game_id", "9462")
    st.session_state.setdefault("version", "0.1.0")

    steps = [
        ("Core Paths", _step_core_paths),
        ("Identity", _step_identity),
        ("Math + Layout", _step_math_layout),
        ("Symbols + Paytable", _step_symbols),
        ("Features", _step_features),
        ("Assets (BG + Audio)", _step_assets),
        ("Localization", _step_localization),
        ("Math Pool (optional)", _step_math_pool),
        ("Build", _step_build),
    ]

    step = int(st.session_state.wiz_step)
    total = len(steps)

    title, fn = steps[step]
    _step_header(title, step, total)
    fn()

    _nav(step, total)


def _step_core_paths() -> None:
    st.text_input(
        "PongGameCore root (optional)",
        key="core_root_override",
        help="Folder that contains frameworks/cocos2d-html5. If empty, uses env var PONGGAMECORE_ROOT.",
    )
    st.text_input(
        "PGS-Igaming root (optional)",
        key="igaming_root_override",
        help="Optional for future 'production packaging' mode. Example: C:\\Users\\...\\Workspace\\PGS-Igaming",
    )

    core_root = _resolve_core_root(st.session_state["core_root_override"])
    ok, msg = core_health_report(core_root)
    if ok:
        st.success(f"Core OK: {core_root}")
    else:
        st.warning(msg)


def _step_identity() -> None:
    def _sync_from_display() -> None:
        if st.session_state.get("lock_internal_name", True) and not st.session_state.get("internal_name_manual", False):
            st.session_state["internal_name_widget"] = safe_internal_name(st.session_state.get("display_name", ""))

    def _mark_internal_manual() -> None:
        # If user edits internal name directly, stop auto-syncing.
        st.session_state["internal_name_manual"] = True

    st.text_input("Game display name", key="display_name", on_change=_sync_from_display)
    st.checkbox("Lock internal name to display name", key="lock_internal_name")

    # Ensure internal_name_widget is set BEFORE rendering the widget (avoids StreamlitAPIException)
    if st.session_state.get("lock_internal_name", True) and not st.session_state.get("internal_name_manual", False):
        st.session_state.setdefault("internal_name_widget", safe_internal_name(st.session_state.get("display_name", "")))
        st.session_state["internal_name_widget"] = safe_internal_name(st.session_state.get("display_name", ""))

    st.text_input("Internal name (folder-safe)", key="internal_name_widget", on_change=_mark_internal_manual)
    # Canonical value used elsewhere
    st.session_state["internal_name"] = str(st.session_state.get("internal_name_widget", "")).strip() or safe_internal_name(st.session_state.get("display_name", ""))

    st.text_input("Game ID", key="game_id")
    st.text_input("Version", key="version")

def _step_math_layout() -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.number_input("Reels", min_value=3, max_value=7, value=5, step=1, key="reel_count")
        st.number_input("Rows", min_value=3, max_value=6, value=3, step=1, key="row_count")
    with c2:
        st.number_input("Paylines", min_value=1, max_value=200, value=25, step=1, key="payline_count")
        st.number_input("Denomination", min_value=0.001, max_value=10.0, value=0.01, step=0.001, format="%.3f", key="denomination")
    with c3:
        st.number_input("Coins per line", min_value=1, max_value=100, value=1, step=1, key="coins_per_line")
        st.number_input("Max win multiplier", min_value=10, max_value=100000, value=5000, step=10, key="max_win_multiplier")

    st.text_input("Bet levels (comma-separated)", "1,2,5,10,20", key="bet_levels_txt")

    try:
        bet_levels = _parse_csv_floats(st.session_state.get("bet_levels_txt", ""))
        denom = float(st.session_state.get("denomination", 0.01))
        cpl = int(st.session_state.get("coins_per_line", 1))
        paylines = int(st.session_state.get("payline_count", 25))
        base_bet = denom * cpl * max(1, paylines)
        st.caption(
            f"Current math selection → Reels: {int(st.session_state.get('reel_count', 5))}, "
            f"Rows: {int(st.session_state.get('row_count', 3))}, "
            f"Paylines: {paylines}, Bet levels: {bet_levels}, "
            f"Base total bet (x1): {base_bet:.4f}"
        )
    except Exception:
        st.warning("Bet levels must be comma-separated numbers (example: 1,2,5,10).")


def _step_symbols() -> None:
    st.number_input("How many symbols?", min_value=4, max_value=40, value=12, step=1, key="symbol_count")
    st.caption("Upload an image for each symbol. The wizard renames them to match Symbol ID (e.g., A.png, WILD.png).")

    symbol_count = int(st.session_state["symbol_count"])
    symbols: List[Dict[str, object]] = []
    paytable: Dict[str, Dict[int, int]] = {}
    uploads: List[Tuple[st.runtime.uploaded_file_manager.UploadedFile, str]] = []

    for idx in range(symbol_count):
        with st.expander(f"Symbol {idx+1}", expanded=(idx < 6)):
            c1, c2, c3 = st.columns([2, 3, 3])
            sym_id = st.text_input("Symbol ID", value=f"S{idx+1}", key=f"sym_id_{idx}").strip()
            sym_name = st.text_input("Display name", value=sym_id, key=f"sym_name_{idx}").strip()
            kind = st.selectbox("Type", ["normal", "wild", "scatter", "bonus"], index=0, key=f"sym_kind_{idx}")

            is_wild = kind == "wild"
            is_scatter = kind == "scatter"
            is_bonus = kind == "bonus"

            pc1, pc2, pc3 = st.columns(3)
            p3 = st.number_input("Pay for 3", min_value=0, value=5, step=1, key=f"pay3_{idx}")
            p4 = st.number_input("Pay for 4", min_value=0, value=10, step=1, key=f"pay4_{idx}")
            p5 = st.number_input("Pay for 5", min_value=0, value=20, step=1, key=f"pay5_{idx}")

            up = st.file_uploader(f"Image for {sym_id}", type=["png","jpg","jpeg","webp"], key=f"sym_upload_{idx}")
            if up is not None and sym_id:
                ext = Path(up.name).suffix or ".png"
                uploads.append((up, f"{sym_id}{ext}"))

            if sym_id:
                symbols.append({"id": sym_id, "name": sym_name or sym_id, "is_wild": is_wild, "is_scatter": is_scatter, "is_bonus": is_bonus})
                paytable[sym_id] = {3: int(p3), 4: int(p4), 5: int(p5)}

    st.session_state["symbols_json"] = json.dumps(symbols)
    st.session_state["paytable_json"] = json.dumps(paytable)
    st.session_state["symbol_uploads_named"] = uploads  # keep in session


def _step_features() -> None:
    st.checkbox("Autoplay enabled", value=True, key="autoplay_enabled")
    st.checkbox("Jackpot enabled", value=False, key="jackpot_enabled")
    st.selectbox("Jackpot trigger", ["none", "5_wild_on_line", "max_scatter"], index=0, key="jackpot_trigger")

    st.markdown("### Free Spins (scatter count → FS award)")
    fs3 = st.number_input("3 scatters → FS", min_value=0, value=8, step=1, key="fs_3")
    fs4 = st.number_input("4 scatters → FS", min_value=0, value=12, step=1, key="fs_4")
    fs5 = st.number_input("5 scatters → FS", min_value=0, value=20, step=1, key="fs_5")
    st.number_input("Free spins win multiplier", min_value=1, value=1, step=1, key="fs_mult")

    st.session_state["fs_award"] = {3: int(fs3), 4: int(fs4), 5: int(fs5)}


def _step_assets() -> None:
    st.caption("Background + per-event audio. If you don't upload, defaults are silent/flat.")
    st.file_uploader("Background image (optional)", type=["png","jpg","jpeg","webp"], key="bg_upload")

    bg = st.session_state.get("bg_upload")
    if bg is not None:
        st.session_state["bg_upload_name"] = str(getattr(bg, "name", "background.png"))
        st.session_state["bg_upload_bytes"] = bytes(bg.getvalue())
    bg_name = st.session_state.get("bg_upload_name")
    bg_bytes = st.session_state.get("bg_upload_bytes")
    if bg_name and bg_bytes:
        st.success(f"Background selected: {bg_name}")
        st.image(bg_bytes, caption=f"Selected background preview: {bg_name}", use_container_width=True)

    st.markdown("### Audio per event (optional)")
    for k, label in AUDIO_KEYS:
        st.file_uploader(label, type=["mp3","wav","ogg"], key=f"aud_{k}")
        aud = st.session_state.get(f"aud_{k}")
        if aud is not None:
            st.session_state[f"aud_{k}_name"] = str(getattr(aud, "name", f"{k}.mp3"))
            st.session_state[f"aud_{k}_bytes"] = bytes(aud.getvalue())
        aud_name = st.session_state.get(f"aud_{k}_name")
        aud_bytes = st.session_state.get(f"aud_{k}_bytes")
        if aud_name and aud_bytes:
            st.caption(f"{label}: {aud_name}")
            st.audio(aud_bytes)

    st.markdown("### Extra UI images (optional)")
    st.file_uploader("UI images", type=["png","jpg","jpeg","webp"], accept_multiple_files=True, key="ui_uploads")


def _step_localization() -> None:
    st.text_input("Languages (comma separated)", "en", key="langs_txt")
    langs = [x.strip() for x in st.session_state["langs_txt"].split(",") if x.strip()] or ["en"]
    st.session_state["languages"] = langs

    help_texts: Dict[str, str] = {}
    for lang in langs:
        help_texts[lang] = st.text_area(f"Help text ({lang})", "Tap SPIN to play.", height=100, key=f"help_{lang}")
    st.session_state["help_texts"] = help_texts


def _step_math_pool() -> None:
    st.info("Optional: generate a math pool zip and embed it into the runnable build at res/conf/math_pool.zip.")
    st.caption("Tip: math-pool settings are separate. Use the sync toggle below if you want these values to also update Build settings.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.text_input("Jurisdiction", "ON", key="mp_jurisdiction")
        st.text_input("Profile ID", "ON-DEFAULT", key="mp_profile_id")
    with c2:
        st.text_input("Currency", "CAD", key="mp_currency")
        st.selectbox("Selection method", ["random_uniform","sequential","rng_stream","random_weighted"], index=0, key="mp_selection_method")
    with c3:
        st.selectbox("Replacement policy", ["with_replacement","without_replacement"], index=0, key="mp_replacement_policy")
        st.number_input("Ticket count", min_value=100, value=10_000, step=100, key="mp_ticket_count")

    st.text_input("Entry levels (comma-separated ints)", "1,2,3,5,10", key="mp_entry_levels")
    st.text_input("Bet levels (comma-separated floats)", st.session_state.get("bet_levels_txt","1,2,5,10"), key="mp_bet_levels")
    st.number_input("Denom", min_value=0.0001, value=float(st.session_state.get("denomination",0.01)), step=0.0001, format="%.4f", key="mp_denom")
    st.number_input("Coins per line", min_value=1, value=int(st.session_state.get("coins_per_line",1)), step=1, key="mp_coins_per_line")
    st.number_input("Payline count", min_value=1, value=int(st.session_state.get("payline_count",25)), step=1, key="mp_payline_count")
    st.checkbox("Sync these Bet/Denom/Coins/Paylines values to Build settings", value=True, key="mp_sync_to_build")

    if st.session_state.get("mp_sync_to_build", True):
        st.session_state["bet_levels_txt"] = str(st.session_state.get("mp_bet_levels", st.session_state.get("bet_levels_txt", "1")))
        st.session_state["denomination"] = float(st.session_state.get("mp_denom", st.session_state.get("denomination", 0.01)))
        st.session_state["coins_per_line"] = int(st.session_state.get("mp_coins_per_line", st.session_state.get("coins_per_line", 1)))
        st.session_state["payline_count"] = int(st.session_state.get("mp_payline_count", st.session_state.get("payline_count", 25)))

    st.markdown("### Targets")
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        st.number_input("Target RTP (%)", min_value=0.0, max_value=100.0, value=96.0, step=0.1, key="mp_rtp")
    with t2:
        st.number_input("Hit-rate target (%)", min_value=0.0, max_value=99.9, value=35.0, step=0.1, key="mp_hit_rate")
    with t3:
        st.number_input("Volatility target (index)", min_value=0.0, value=3.0, step=0.1, key="mp_volatility")
    with t4:
        st.number_input("Max win multiplier cap", min_value=1, value=int(st.session_state.get("max_win_multiplier",5000)), step=100, key="mp_max_win_cap")

    st.markdown("### Base distribution")
    st.text_input("Base win multipliers", "0,1,2,5,10,20,50", key="mp_base_mults")
    st.text_input("Base win weights", "55,25,10,5,3,1,1", key="mp_base_ws")

    st.markdown("### Bonus / Progressive")
    b1, b2, b3 = st.columns(3)
    with b1:
        st.number_input("Bonus trigger (%)", min_value=0.0, max_value=100.0, value=5.0, step=0.1, key="mp_bonus_trigger")
    with b2:
        st.number_input("Progressive trigger (%)", min_value=0.0, max_value=100.0, value=0.1, step=0.1, key="mp_prog_trigger")
    with b3:
        st.number_input("Progressive win multiplier", min_value=0.0, value=5000.0, step=100.0, key="mp_prog_mult")

    st.text_input("Bonus win multipliers", "2,5,10,25", key="mp_bonus_mults")
    st.text_input("Bonus win weights", "70,20,8,2", key="mp_bonus_ws")

    c = st.columns([1,1,3])
    with c[0]:
        if st.button("Generate math pool"):
            try:
                cfg = PoolConfig(
                    game_id=str(st.session_state.get("game_id","9462")).strip(),
                    game_name=str(st.session_state.get("display_name","NewGame")).strip(),
                    jurisdiction=str(st.session_state["mp_jurisdiction"]).strip(),
                    profile_id=str(st.session_state["mp_profile_id"]).strip(),
                    currency=str(st.session_state["mp_currency"]).strip(),
                    selection_method=st.session_state["mp_selection_method"],
                    replacement_policy=st.session_state["mp_replacement_policy"],
                    denom=float(st.session_state["mp_denom"]),
                    entry_levels=_parse_csv_ints(st.session_state["mp_entry_levels"]),
                    bet_levels=_parse_csv_floats(st.session_state["mp_bet_levels"]),
                    coins_per_line=int(st.session_state["mp_coins_per_line"]),
                    payline_count=int(st.session_state["mp_payline_count"]),
                    rtp_target_percent=float(st.session_state["mp_rtp"]),
                    hit_rate_target_percent=float(st.session_state["mp_hit_rate"]),
                    volatility_target=float(st.session_state["mp_volatility"]),
                    max_win_multiplier_cap=int(st.session_state["mp_max_win_cap"]),
                    base_win_multipliers=_parse_csv_floats(st.session_state["mp_base_mults"]),
                    base_win_weights=_parse_csv_floats(st.session_state["mp_base_ws"]),
                    bonus_trigger_percent=float(st.session_state["mp_bonus_trigger"]),
                    bonus_win_multipliers=_parse_csv_floats(st.session_state["mp_bonus_mults"]),
                    bonus_win_weights=_parse_csv_floats(st.session_state["mp_bonus_ws"]),
                    progressive_trigger_percent=float(st.session_state["mp_prog_trigger"]),
                    progressive_win_multiplier=float(st.session_state["mp_prog_mult"]),
                )
                zip_bytes = export_math_pool_zip(cfg=cfg, ticket_count=int(st.session_state["mp_ticket_count"]))
                st.session_state["math_pool_zip"] = zip_bytes
                st.success("Math pool generated.")
            except Exception as e:
                st.exception(e)

    mp = st.session_state.get("math_pool_zip")
    if mp:
        st.download_button("Download math pool ZIP", data=mp, file_name=f'{st.session_state.get("game_id","game")}_math_pool.zip', mime="application/zip")


def _step_build() -> None:
    core_root = _resolve_core_root(st.session_state.get("core_root_override",""))
    ok, msg = core_health_report(core_root)
    if not ok:
        st.error(msg)
        st.stop()

    # Assemble spec
    display_name = str(st.session_state.get("display_name","Slot")).strip() or "Slot"
    internal_name = str(st.session_state.get("internal_name_widget", st.session_state.get("internal_name", safe_internal_name(display_name)))).strip() or safe_internal_name(display_name)

    identity = GameIdentity(
        game_id=str(st.session_state.get("game_id", internal_name)).strip() or internal_name,
        internal_name=internal_name,
        display_name=display_name,
        version=str(st.session_state.get("version","0.1.0")).strip() or "0.1.0",
    )

    jurisdiction = JurisdictionConfig(
        jurisdiction="Ontario",
        profile_id="default_profile",
        currencies=["USD"],
        selection_method="random_uniform",
        replacement_policy="with_replacement",
    )

    # parse symbols/paytable from session
    symbols_raw = json.loads(st.session_state.get("symbols_json","[]"))
    paytable = json.loads(st.session_state.get("paytable_json","{}"))
    symbols: List[SymbolConfig] = [SymbolConfig(**s) for s in symbols_raw]

    reel_count = int(st.session_state.get("reel_count",5))
    row_count = int(st.session_state.get("row_count",3))
    payline_count = int(st.session_state.get("payline_count",25))

    bet_levels = _parse_csv_floats(st.session_state.get("bet_levels_txt","1,2,5,10,20"))

    feature_cfg = FeatureConfig(
        free_spins_award=st.session_state.get("fs_award",{3:8,4:12,5:20}),
        free_spins_multiplier=int(st.session_state.get("fs_mult",1)),
        jackpot_enabled=bool(st.session_state.get("jackpot_enabled",False)),
        jackpot_trigger=str(st.session_state.get("jackpot_trigger","none")),
        autoplay_enabled=bool(st.session_state.get("autoplay_enabled",True)),
    )

    math = MathConfig(
        reel_count=reel_count,
        row_count=row_count,
        payline_count=payline_count,
        denomination=float(st.session_state.get("denomination",0.01)),
        coins_per_line=int(st.session_state.get("coins_per_line",1)),
        bet_levels=bet_levels,
        max_win_multiplier=int(st.session_state.get("max_win_multiplier",5000)),
        symbols=symbols,
        features=feature_cfg,
    )

    languages = st.session_state.get("languages",["en"])
    localization = LocalizationConfig(languages=languages, help_texts=st.session_state.get("help_texts",{}))

    spec = GameSpec(identity=identity, jurisdiction=jurisdiction, localization=localization, math=math)

    # generated math content
    paylines = generate_paylines(payline_count, reel_count, row_count)

    # simplest strips: repeat symbol ids
    ids = [s.id for s in symbols] or ["A","K","Q","J","10","9","WILD","SCAT"]
    strip = []
    for _ in range(5):
        strip.extend(ids)
    reel_strips = [strip[:] for _ in range(reel_count)]

    # uploads
    symbol_uploads_named = st.session_state.get("symbol_uploads_named", [])
    ui_uploads = st.session_state.get("ui_uploads") or []
    background_upload = st.session_state.get("bg_upload")
    # Prefer persisted bytes from Assets step (stable across reruns/navigation)
    if st.session_state.get("bg_upload_name") and st.session_state.get("bg_upload_bytes"):
        background_upload = _MemoryUpload(
            name=str(st.session_state["bg_upload_name"]),
            data=bytes(st.session_state["bg_upload_bytes"]),
        )

    # audio mapping (named)
    audio_named: List[Tuple[st.runtime.uploaded_file_manager.UploadedFile, str]] = []
    for k, _label in AUDIO_KEYS:
        # Prefer persisted bytes (stable); fallback to current widget object.
        b = st.session_state.get(f"aud_{k}_bytes")
        n = st.session_state.get(f"aud_{k}_name")
        if b and n:
            ext = Path(str(n)).suffix or ".mp3"
            audio_named.append((_MemoryUpload(name=str(n), data=bytes(b)), f"{k}{ext}"))
            continue

        f = st.session_state.get(f"aud_{k}")
        if f is not None:
            ext = Path(f.name).suffix or ".mp3"
            audio_named.append((f, f"{k}{ext}"))

    math_pool_zip = st.session_state.get("math_pool_zip")

    st.markdown("### Build outputs")
    st.caption(
        "Choose a packaging mode. The **Dev Web ZIP** is the lightweight in-wizard demo (Cocos2d-HTML5). "
        "The **Cocos Creator ZIP** calls the local Cocos Creator CLI to produce an actual Creator web build."
    )

    with st.expander("Option A — Dev Web ZIP (lightweight demo)", expanded=True):
        if st.button("Generate Dev Web ZIP"):
            try:
                data = build_dev_web_zip(
                    core_root=core_root,
                    spec=spec,
                    paylines=paylines,
                    reel_strips=reel_strips,
                    paytable=paytable,
                    symbol_uploads_named=symbol_uploads_named,
                    ui_uploads=ui_uploads,
                    audio_uploads=[],
                    help_texts=st.session_state.get("help_texts", {}),
                    background_upload=background_upload,
                    audio_uploads_named=audio_named or None,
                    math_pool_zip=math_pool_zip,
                )
            except Exception as e:
                st.exception(e)
                return

            zip_name = f"{spec.identity.internal_name}_dev_web.zip"
            st.download_button("Download Dev Web ZIP", data=data, file_name=zip_name, mime="application/zip")
            st.success("Done. Unzip, then run `Run_Game.bat` (Windows) or `python run_local.py`.")

    with st.expander("Option B — Cocos Creator ZIP (real Creator web build)", expanded=True):
        st.caption(
            "You must provide a **Cocos Creator template project** that already contains the scenes/prefabs/scripts to run, "
            "and placeholder assets with matching .meta files. The wizard will overwrite the placeholder file bytes and then build via CLI."
        )

        st.text_input(
            "Cocos Creator executable path",
            key="cc_exe",
            placeholder=r"C:\Program Files\CocosCreator\CocosCreator.exe  (or .app/Contents/MacOS/CocosCreator)",
        )
        st.selectbox("Cocos major version", [2, 3], index=0, key="cc_major")
        st.selectbox("Build platform", ["web-mobile", "web-desktop"], index=0, key="cc_platform")
        st.file_uploader("Template project ZIP (recommended)", type=["zip"], key="cc_tpl_zip")
        st.text_input("…or template project folder path", key="cc_tpl_path", placeholder=r"D:\work\SlotTemplate")

        st.markdown("#### Placeholder symbol files")
        st.caption(
            "Fast/safe mode: your template keeps fixed files like Symbol_1.png, Symbol_2.png… with stable .meta. "
            "Enter the filenames (comma-separated) in the order you want uploads applied."
        )
        st.text_input(
            "Symbol placeholder filenames",
            key="cc_symbol_placeholders",
            value=",".join([f"Symbol_{i}.png" for i in range(1, min(21, int(st.session_state.get('symbol_count', 12)) + 1))]),
        )

        if st.button("Generate Cocos Creator Build ZIP"):
            exe = Path(str(st.session_state.get("cc_exe", "")).strip())
            major = int(st.session_state.get("cc_major", 2))
            platform = str(st.session_state.get("cc_platform", "web-mobile"))

            tpl_zip = st.session_state.get("cc_tpl_zip")
            tpl_zip_bytes: Optional[bytes] = None
            if tpl_zip is not None:
                tpl_zip_bytes = tpl_zip.getvalue()

            tpl_path_txt = str(st.session_state.get("cc_tpl_path", "")).strip()
            tpl_path = Path(tpl_path_txt).expanduser().resolve() if tpl_path_txt else None

            placeholder_txt = str(st.session_state.get("cc_symbol_placeholders", "")).strip()
            placeholders = [x.strip() for x in placeholder_txt.split(",") if x.strip()] or None

            try:
                data = build_cocos_creator_web_zip(
                    cocos_creator_exe=exe,
                    cocos_major_version=major,
                    template_project_path=tpl_path,
                    template_project_zip_bytes=tpl_zip_bytes,
                    platform=platform,
                    spec=spec,
                    paylines=paylines,
                    reel_strips=reel_strips,
                    paytable=paytable,
                    help_texts=st.session_state.get("help_texts", {}),
                    symbol_uploads_named=symbol_uploads_named,
                    audio_uploads_named=audio_named or None,
                    background_upload=background_upload,
                    placeholder_symbol_names=placeholders,
                )
            except Exception as e:
                st.exception(e)
                return

            zip_name = f"{spec.identity.internal_name}_{platform}_creator_build.zip"
            st.download_button("Download Cocos Creator ZIP", data=data, file_name=zip_name, mime="application/zip")
            st.success("Done. Unzip and serve the folder with a web server (e.g., `python -m http.server`).")
