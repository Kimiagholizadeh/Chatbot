# UI Control Implementation Map (Spin/Stop, Bet Popup, Auto Popup)

This map links the requested shared controls to the generated game runtime implementation.

## Runtime file
- `dev_builder.py` embeds generated scene logic in `_SCENE_SLOT`.

## Implemented controls and actions

### Spin / Stop
- `spinButtonsPanel` (runtime anchor in generated scene)
- `spinBtn` -> starts spin (`_onSpin`)
- `stopBtn` -> stop request during spin (`onStopButtonClick`)
- During spin, UI toggles from SPIN to STOP via `_setSpinButtonsState(true)`.

### Bet controls
- `betPanelButton` -> open bet popup (`onOpenBetPanelClick`)
- Bet popup root: `betInfoPanel`
- `betPanel_decBet` -> decrease bet (`onDecreaseBetClick`)
- `betPanel_incBet` -> increase bet (`onIncreaseBetClick`)
- `betPanelMaxBtn` / `maxBetButton` -> max bet (`onSetMaxBetClick`)
- `betPanelCloseButton` -> close popup (`onCloseBetPanelClick`)
- Visibility logic for +/-/max states: `_updateBetBtnVisibility`

### Auto controls
- `autoButton` -> open auto popup (`onOpenAutoPanelClick`)
- Auto popup root: `autoPanelInfo`
- Count buttons: `20/50/100/200/500/1000` -> `enableAutoSpin`
- `btnAutoSpin` -> starts autoplay sequence (`onAutoButtonClick`)
- `autoStopButton` -> stops autoplay (`onStopAutoButtonClick`)
- `btnQuickSpin` -> quick mode (`onQuickSpinButtonClick`)
- `btnTurboSpin` -> turbo mode (`onTurboSpinButtonClick`)
- `autoPanelCloseButton` -> close auto popup (`onCloseAutoPanelClick`)

## Stop-spin behavior
- Stop button sets `_forceStopRequested = true`.
- Reel animation loop shortens stop timers when forced stop is requested so reels settle early.

## Search commands
```bash
rg -n "spinButtonsPanel|spinBtn|stopBtn|onStopButtonClick|_setSpinButtonsState" dev_builder.py
rg -n "onOpenBetPanelClick|onCloseBetPanelClick|onIncreaseBetClick|onDecreaseBetClick|onSetMaxBetClick|betInfoPanel" dev_builder.py
rg -n "onOpenAutoPanelClick|onCloseAutoPanelClick|enableAutoSpin|onAutoButtonClick|onStopAutoButtonClick|onQuickSpinButtonClick|onTurboSpinButtonClick|autoPanelInfo" dev_builder.py
```


## Button image binding
- Runtime resolves button/panel textures from `assets_manifest.ui_by_stem` (generated from uploaded UI files).
- Upload files using shared stems such as: `btn_spin`, `btn_stop`, `btn_bet`, `btn_bet_plus`, `btn_bet_minus`, `btn_bet_max`, `btn_auto`, `btn_auto_spin`, `btn_auto_amt`, `btn_speed_quick`, `btn_speed_turbo`, `btn_menu_close`, `bet_popup_panel`.
- If an image stem is missing, runtime falls back to the default colored button style.
