# Finding Common Elements (Spin Button, Fonts, Help, Win UI, etc.)

Use this quick map to locate **where shared UI/game elements are defined** and where your configurable payload is written.

## 1) In this repo (`/workspace/Chatbot`)

### A) Runtime button logic for the generated Dev Web game
File: `dev_builder.py`

- Spin button creation: search for `spinBtn`.
- Other core buttons (`+/-`, BET LVL, REELS, ROWS, PAYLINES, VOL): search for `_makeButton(` calls.
- Shared button drawing/style: `_makeButton` function.

Useful command:
```bash
rg -n "spinBtn|_makeButton\(|BET LVL|PAYLINES|REELS|ROWS|VOL" dev_builder.py
```

### B) Help content source from Streamlit UI
File: `ui_game_generator.py`

- Help text user input is collected in Localization step (`help_<lang>`).
- Help texts are passed to the build functions (`build_dev_web_zip`, creator build).

Useful command:
```bash
rg -n "help_texts|help_" ui_game_generator.py dev_builder.py
```

### C) Where configurable assets are injected for PGS package mode
File: `pgs_packager.py`

- Symbols: `assets/gameAssets/games/<id>/sprites/generated_symbols/*`
- Audio: `assets/gameAssets/games/<id>/sounds/generated_events/*`
- Background: `assets/gameAssets/games/<id>/sprites/generated_background/*`
- Config/maths: `assets/gameAssets/games/<id>/configs/generated_identity.json`, `generated_math.json`, optional `math_pool.zip`

Useful command:
```bash
rg -n "generated_symbols|generated_events|generated_background|generated_math|generated_identity|math_pool.zip" pgs_packager.py
```

---

## 2) In your company repos (where shared/common elements usually live)

From your notes, these are the canonical shared locations in **PGS-Igaming**:

- `assets/resources/common/assets/default_ui` (common UI parts like dashboard/buttons)
- `assets/resources/common/assets/default_ui/dashboard`
- `assets/resources/common/assets/default_ui/reels`
- `assets/resources/common/assets/font`
- `assets/resources/common/assets/help`
- `assets/resources/common/assets/bigwin`
- `assets/resources/common/sounds`
- `assets/scripts/core/...` (shared engine behavior)

If you set PowerShell env vars as:

- `$env:PONGGAMECORE_ROOT = "C:\Users\kimia.g\Workspace\PGS_Assistant\.core_cache\PongGameCore\PongGameCore"`

Then run searches like:

```powershell
rg -n "spin|bet|payline|menu|dashboard|help|bigwin|font" "$env:PONGGAMECORE_ROOT/assets/resources/common"
rg -n "spin|bet|payline|menu|help|free|bonus|reel" "$env:PONGGAMECORE_ROOT/assets/scripts/core"
```

> Tip: start with file names first (`rg --files ... | rg "dashboard|button|help|font|bigwin|spin"`) then inspect exact scripts/prefabs/scenes.

---

## 3) Practical workflow to identify and reuse common elements

1. Locate visual asset path under `assets/resources/common/...` (png, spine, prefab, font).
2. Locate script/controller usage under `assets/scripts/core/...`.
3. Keep those paths unchanged in base package exports.
4. Inject only configurable content (symbols/audio/background/math/help text) in designated generated paths.
5. Keep `.meta` pairs for all copied Creator assets.

This is exactly the pattern implemented by the current **PGS Base Package** + **PGS Configurable Package** modes.
