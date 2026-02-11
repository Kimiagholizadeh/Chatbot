# UI Control Implementation Map (Spin / Stop / Bet / Auto)

This file is the **single reference** for control PNGs, locations, and actions.

It now has two clearly-separated scopes so there is no ambiguity:

1. **Runtime in this repository** (`dev_builder.py`): what the generated Dev Web scene actually wires today.
2. **Panda Shores (Game 9486) reference mapping**: shared PGS dashboard mapping you provided (useful when aligning with PGS-Igaming project assets/prefabs).

---

## A) Runtime-accurate map in this repo (source of truth here)

Runtime source: `dev_builder.py` (`_SCENE_SLOT` string and dashboard handlers)

### A1) Control locations used in generated runtime (960x540 canvas)

- `spinButtonsPanel`: `(840, 100)`
  - `spinBtn`: local `(0,0)`
  - `stopBtn`: local `(0,0)` (shown while spinning)
- `autoButton`: `(760, 52)`
- `autoStopButton`: `(760, 20)`
- `betPanelButton`: `(930, 52)`
- `maxBetButton`: `(930, 20)`
- `betInfoPanel` root: `(480, 250)`
- `autoPanelInfo` root: `(480, 250)`

#### Bet popup child local positions
- `betPanelCloseButton`: `(300, 95)`
- `betPanel_incBet`: `(210, -5)`
- `betPanel_decBet`: `(-210, -5)`
- `betPanelMaxBtn`: `(0, -78)`

#### Auto popup child local positions
- `autoPanelCloseButton`: `(340, 126)`
- `20/50/100/200/500/1000` buttons: grid positions from `(-240..240, 35/-25)`
- `btnTurboSpin`: `(-120, -88)`
- `btnQuickSpin`: `(120, -88)`
- `btnAutoSpin`: `(0, -138)`

### A2) PNG mapping per button (runtime state mapping)

Resolved via `assets_manifest.ui_by_stem` (UI upload filename stems).

#### Spin / Stop
- `spinBtn`
  - normal: `btn_spin`
  - pressed/hover: `btn_spin_on`
  - disabled: `btn_spin_off`
- `stopBtn`
  - normal/pressed: `btn_stop_on` (fallback `btn_stop`)
  - disabled: `btn_stop_off`

#### Bet controls
- `betPanelButton`
  - normal: `btn_bet`
  - pressed/hover: `btn_bet_on`
  - disabled: `btn_bet_off`
- `betPanel_incBet` (plus)
  - normal: `btn_bet_plus`
  - pressed/hover: `btn_bet_plus_on`
  - disabled: `btn_bet_plus_off`
- `betPanel_decBet` (minus)
  - normal: `btn_bet_minus`
  - pressed/hover: `btn_bet_minus_on`
  - disabled: `btn_bet_minus_off`
- `betPanelMaxBtn` + `maxBetButton`
  - normal: `btn_auto_amt` (fallback `btn_bet_max`)
  - pressed/selected: `btn_auto_amt_on`
- `betPanelCloseButton`
  - normal: `btn_menu_close`
  - pressed/hover: `btn_close_on_menu` (fallback `btn_menu_close_on`)
  - disabled: `btn_menu_close_off`

#### Auto controls
- `autoButton`
  - normal: `btn_auto`
  - pressed/hover: `btn_auto_on`
  - disabled: `btn_auto_off`
- `autoStopButton`
  - normal/pressed: `btn_auto_active`
- `btnAutoSpin`
  - normal: `btn_auto_spin`
  - pressed/active: `btn_auto_spin_on`
  - disabled/no-count-selected: `btn_auto_spin_off`
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
  - pressed/hover: `btn_menu_close_on`
  - disabled: `btn_menu_close_off`

### A3) Actions wired in runtime

#### Spin / Stop
- `onSpinButtonClick` (internally calls spin flow)
- `onStopButtonClick`

#### Bet popup
- `onOpenBetPanelClick`
- `onCloseBetPanelClick`
- `onIncreaseBetClick`
- `onDecreaseBetClick`
- `onSetMaxBetClick`
- `_updateBetBtnVisibility`

#### Auto popup
- `onOpenAutoPanelClick`
- `onCloseAutoPanelClick`
- `enableAutoSpin`
- `onAutoButtonClick`
- `onStopAutoButtonClick`
- `onQuickSpinButtonClick`
- `onTurboSpinButtonClick`
- `setSpinMode`

---

## B) Panda Shores (Game 9486) reference mapping (PGS shared dashboard)

Use this section when validating against PGS-Igaming project-side prefab/controller naming.

### B1) Game identity

- Game ID: `9486`
- Game name: `Panda Shores`
- Config: `assets/gameAssets/games/9486/configs/conf.json`
- Scene: `assets/gameAssets/games/9486/GameScene.scene`

### B2) Shared handler set (reference)

- Spin / Stop: `onSpinButtonClick()`, `onStopButtonClick()`
- Bet popup:
  - `onOpenBetPanelClick()`
  - `onCloseBetPanelClick(_event, forcedClose)`
  - `onIncreaseBetClick()`
  - `onDecreaseBetClick()`
  - `onSetMaxBetClick()`
  - `updateBetBtnVisibility(currentBet, minBet, maxBet)`
- Auto popup:
  - `onOpenAutoPanelClick()`
  - `onCloseAutoPanelClick(_event, forcedClose)`
  - `enableAutoSpin(_event, autoSpinCount)`
  - `onAutoButtonClick()`
  - `onStopAutoButtonClick()`
  - `onQuickSpinButtonClick()`
  - `onTurboSpinButtonClick()`
  - `setSpinMode()` / `refreshSpinSpeedButton()`

### B3) Shared prefab wiring (reference)

Prefab: `assets/resources/editor_prefabs/dashboard/dashboard.prefab`

- `spinButton` -> `onSpinButtonClick`
- `stopButton` -> `onStopButtonClick`
- `betPanelButton` -> `onOpenBetPanelClick`
- `betPanelCloseButton` -> `onCloseBetPanelClick`
- `betPanel_incBet` -> `onIncreaseBetClick`
- `betPanel_decBet` -> `onDecreaseBetClick`
- `maxbtn` -> `onSetMaxBetClick`
- `autoButton` -> `onOpenAutoPanelClick`
- `autoStopButton` -> `onStopAutoButtonClick`
- `autoPanelCloseButton` -> `onCloseAutoPanelClick`
- `btnAutoSpin` -> `onAutoButtonClick`
- `btnTurboSpin` -> `onTurboSpinButtonClick`
- `btnQuickSpin` -> `onQuickSpinButtonClick`

Autoplay count buttons:
- `20Btn/50Btn/100Btn/200Btn/500Btn/1000Btn` -> `enableAutoSpin` with corresponding `customEventData`

### B4) Shared positions (reference)

Runtime anchors:
- `btnPos3` (`spinButtonsPanel`)
  - Landscape: `(1189, -384)`, scale `0.65`
  - Portrait: `(426, -1569)`, scale `1`
- `btnPos4` (`autoSpinPanel`)
  - Landscape: `(1233, -634)`, scale `0.65`
  - Portrait: `(715, -1673)`, scale `1`
- `btnPos5` (`betPanelButton`)
  - Landscape: `(1276, -546)`, scale `0.65`
  - Portrait: `(910, -1673)`, scale `1`

Popup roots:
- `autoPanelInfo`
  - Landscape: `(320, -335)`, scale `0.65`
  - Portrait: `(0, -1210)`, scale `1`
- `betInfoPanel`
  - Landscape: `(320, -335)`, scale `0.65`
  - Portrait: `(0, -1210)`, scale `1`

Popup child locals:
- Bet popup:
  - `betPanelCloseButton`: `(950, -1162, 0)`
  - `betPanel_incBet`: `(805, -1365, 0)`
  - `betPanel_decBet`: `(150, -1365, 0)`
  - `maxbtn`: `(540, -1580, 0)`
- Auto popup:
  - `autoPanelCloseButton`: `(950, -888.485, 0)`
  - `btnAutoSpin`: `(427.071, -1443.775, 0)`
  - `btnTurboSpin`: `(239.246, -1100.331, 0)`
  - `btnQuickSpin`: `(702.043, -1100.331, 0)`
  - `200Btn`: `(-258.299, 71.417, 0)`
  - `500Btn`: `(-4.016, 71.417, 0)`
  - `1000Btn`: `(252.409, 71.417, 0)`
  - `20Btn`: `(-258.299, -69.276, 0)`
  - `50Btn`: `(-4.016, -69.276, 0)`
  - `100Btn`: `(252.409, -69.276, 0)`

Displayed position formula:
- `DisplayedPosition = PopupRootPosition + (ChildLocalPosition × PopupRootScale)`

### B5) Dashboard assets noted

Folders:
- `assets/resources/common/assets/default_ui/dashboard`
- `assets/resources/common/assets/default_ui/dashboard/buttons`

Asset stems noted:
- `bet_popup_panel`, `popup_panel_bg`
- `btn_auto`, `btn_auto_active`
- `btn_auto_amt`, `btn_auto_amt_on`
- `btn_auto_spin`, `btn_auto_spin_off`, `btn_auto_spin_on`
- `btn_back`, `btn_back_on`
- `btn_bet`, `btn_bet_off`, `btn_bet_on`, `btn_bet_max`
- `btn_bet_minus`, `btn_bet_minus_off`, `btn_bet_minus_on`
- `btn_bet_plus`, `btn_bet_plus_off`, `btn_bet_plus_on`
- `btn_spin`, `btn_spin_off`, `btn_spin_on`
- `btn_stop`, `btn_stop_off`, `btn_stop_on`
- `btn_turbo`, `btn_turbo_off`

---

## C) Practical behavior checklist (requested controls)

- Spin button location/action is mapped; stop button appears in same spin slot while spin is running.
- Bet Level button location/action is mapped; Bet popup includes close, increase, decrease, and max controls.
- Auto Play button location/action is mapped; Auto popup includes count buttons, quick/turbo, autoplay spin trigger, and close control.
