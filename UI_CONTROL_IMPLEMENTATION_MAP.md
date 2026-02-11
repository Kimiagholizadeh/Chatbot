# UI Control Implementation Map (PNG + Location + Action)

Runtime source: `dev_builder.py` (`_SCENE_SLOT` string)

## 1) Control locations used in generated runtime (960x540 canvas)

- `spinButtonsPanel`: `(840, 100)`
  - `spinBtn`: local `(0,0)`
  - `stopBtn`: local `(0,0)`
- `autoButton`: `(760, 52)`
- `autoStopButton`: `(760, 20)`
- `betPanelButton`: `(930, 52)`
- `maxBetButton`: `(930, 20)`
- `betInfoPanel` root: `(480, 250)`
- `autoPanelInfo` root: `(480, 250)`

### Bet popup child local positions
- `betPanelCloseButton`: `(300, 95)`
- `betPanel_incBet`: `(210, -5)`
- `betPanel_decBet`: `(-210, -5)`
- `betPanelMaxBtn`: `(0, -78)`

### Auto popup child local positions
- `autoPanelCloseButton`: `(340, 126)`
- `20/50/100/200/500/1000` buttons: grid positions from `(-240..240, 35/-25)`
- `btnTurboSpin`: `(-120, -88)`
- `btnQuickSpin`: `(120, -88)`
- `btnAutoSpin`: `(0, -138)`

---

## 2) Exact PNG mapping per button (runtime image states)

Resolved from `assets_manifest.ui_by_stem` (uploaded UI files by filename stem).

### Spin / Stop
- `spinBtn`
  - normal: `btn_spin`
  - pressed: `btn_spin_on`
  - disabled: `btn_spin_off`
- `stopBtn`
  - normal/pressed: `btn_stop_on` (fallback `btn_stop`)
  - disabled: `btn_stop_off`

### Bet controls
- `betPanelButton`
  - normal: `btn_bet`
  - pressed: `btn_bet_on`
  - disabled: `btn_bet_off`
- `betPanel_incBet`
  - normal: `btn_bet_plus`
  - pressed: `btn_bet_plus_on`
  - disabled: `btn_bet_plus_off`
- `betPanel_decBet`
  - normal: `btn_bet_minus`
  - pressed: `btn_bet_minus_on`
  - disabled: `btn_bet_minus_off`
- `betPanelMaxBtn` + `maxBetButton`
  - normal: `btn_auto_amt` (fallback `btn_bet_max`)
  - pressed: `btn_auto_amt_on`
- `betPanelCloseButton`
  - normal: `btn_menu_close`
  - pressed: `btn_close_on_menu` (fallback `btn_menu_close_on`)
  - disabled: `btn_menu_close_off`

### Auto controls
- `autoButton`
  - normal: `btn_auto`
  - pressed: `btn_auto_on`
  - disabled: `btn_auto_off`
- `autoStopButton`
  - normal/pressed: `btn_auto_active`
- `btnAutoSpin`
  - normal: `btn_auto_spin`
  - pressed: `btn_auto_spin_on`
  - disabled: `btn_auto_spin_off`
- `btnQuickSpin`
  - normal: `btn_quick_off`
  - selected/pressed: `btn_quick_on`
- `btnTurboSpin`
  - normal: `btn_turbo_off`
  - selected/pressed: `btn_turbo`
- autoplay count buttons (`20/50/100/200/500/1000`)
  - normal: `btn_auto_amt`
  - selected/pressed: `btn_auto_amt_on`
- `autoPanelCloseButton`
  - normal: `btn_menu_close`
  - pressed: `btn_menu_close_on`
  - disabled: `btn_menu_close_off`

---

## 3) Action handlers wired in runtime

- Spin / Stop:
  - `onSpinButtonClick` (internally uses `_onSpin`)
  - `onStopButtonClick`
- Bet popup:
  - `onOpenBetPanelClick`
  - `onCloseBetPanelClick`
  - `onIncreaseBetClick`
  - `onDecreaseBetClick`
  - `onSetMaxBetClick`
  - `_updateBetBtnVisibility`
- Auto popup:
  - `onOpenAutoPanelClick`
  - `onCloseAutoPanelClick`
  - `enableAutoSpin`
  - `onAutoButtonClick`
  - `onStopAutoButtonClick`
  - `onQuickSpinButtonClick`
  - `onTurboSpinButtonClick`
  - `setSpinMode`

---

## 4) Note on required uploads

To use PNG buttons exactly (instead of fallback colored buttons), upload UI images in the wizard with stems matching the names above (e.g. `btn_spin.png`, `btn_spin_on.png`, `btn_spin_off.png`, etc.).
