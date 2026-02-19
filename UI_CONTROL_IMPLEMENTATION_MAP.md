# Panda Shores (9486) — Exact UI Coordinates, Sizes, PNG Wiring (Base Dashboard)

This document uses the **base prefab values directly** (no guessed screen conversion), so you can copy values safely into your engine.

## Source of truth
- Prefab: `assets/resources/editor_prefabs/dashboard/dashboard.prefab`
- Runtime anchor config: `assets/scripts/core/vendor/connectors/BaseVendor.ts`
- Runtime actions: `assets/scripts/core/components/dashboard/DashboardComponent.ts`
- PNG folder: `assets/resources/common/assets/default_ui/dashboard/buttons/`

---

## 1) Runtime anchor positions (from BaseVendor)

| Slot / Popup | Landscape `(x,y)` scale | Portrait `(x,y)` scale |
|---|---:|---:|
| `btnPos3` -> `spinButtonsPanel` | `(1189, -384)` `0.65` | `(426, -1569)` `1` |
| `btnPos4` -> `autoSpinPanel` | `(1233, -634)` `0.65` | `(715, -1673)` `1` |
| `btnPos5` -> `betPanelButton` | `(1276, -546)` `0.65` | `(910, -1673)` `1` |
| `autoPanelInfo` | `(320, -335)` `0.65` | `(0, -1210)` `1` |
| `betInfoPanel` | `(320, -335)` `0.65` | `(0, -1210)` `1` |

---

## 2) Popup base panels

| Requested item | Node | Parent | Local Pos `(x,y)` | Size `(w,h)` | Anchor `(x,y)` |
|---|---|---|---:|---:|---:|
| `popup_panel_bg` | `popup_panel_bg` | `autoPanelInfo` | `(530, 142.632)` | `(1100, 667.7)` | `(0.5, 1)` |
| `bet_popup_panel_bg` | `bet_popup_panel_bg` | `betInfoPanel` | `(538, -290)` | `(1100, 476)` | `(0.5, 0.5)` |
| `bet_popup_panel` | *(asset only)* | *(not wired in this prefab)* | `N/A` | `N/A` | `N/A` |

---

## 3) Auto panel controls + numbers

Hierarchy:
- `autoPanelInfo` -> `buttonContainer (0,1151.176)` -> `BtnContainer (538,-1300.128)` -> number button nodes

| Requested item | Node | Parent | Local Pos `(x,y)` | Size `(w,h)` | PNG wiring |
|---|---|---|---:|---:|---|
| `btn_auto_active` | `autoStopButton` | `autoSpinPanel` | `(0, 0)` | `(125, 125)` | `btn_auto_active.png` |
| `btn_auto_spin` | `btnAutoSpin` | `buttonContainer` | `(427.071, -1443.775)` | `(210, 210)` | `btn_auto_spin.png` |
| `btn_auto_spin_off` | `btnAutoSpin` disabled | `buttonContainer` | same | same | `btn_auto_spin_off.png` |
| `btn_auto_spin_on` | `btnAutoSpin` hover/pressed | `buttonContainer` | same | same | `btn_auto_spin_on.png` |
| `btn_auto_amt` | number frames | count button nodes | `(0,0)` | `(208,82)` | `btn_auto_amt.png` |
| `btn_auto_amt_on` | selected frames | count button nodes | `(0,0)` | `(208,82)` | `btn_auto_amt_on.png` |
| `200Btn` | `200Btn` | `BtnContainer` | `(-258.299, 71.417)` | `(208,82)` | auto_amt frame |
| `500Btn` | `500Btn` | `BtnContainer` | `(-4.016, 71.417)` | `(208,82)` | auto_amt frame |
| `1000Btn` | `1000Btn` | `BtnContainer` | `(252.409, 71.417)` | `(208,82)` | auto_amt frame |
| `20Btn` | `20Btn` | `BtnContainer` | `(-258.299, -69.276)` | `(208,82)` | auto_amt frame |
| `50Btn` | `50Btn` | `BtnContainer` | `(-4.016, -69.276)` | `(208,82)` | auto_amt frame |
| `100Btn` | `100Btn` | `BtnContainer` | `(252.409, -69.276)` | `(208,82)` | auto_amt frame |
| `btnTurboSpin` | turbo container | `buttonContainer` | `(239.246, -1100.331)` | `(210,125)` | click target |
| `btnQuickSpin` | quick container | `buttonContainer` | `(702.043, -1100.331)` | `(210,125)` | click target |
| `autoPanelCloseButton` | close | `buttonContainer` | `(950, -888.485)` | `(125,125)` | close sprite states |

---

## 4) Bet controls

Hierarchy:
- `betInfoPanel` -> `betButtons (0,1214.677)` -> controls

| Requested item | Node | Parent | Local Pos `(x,y)` | Size `(w,h)` | PNG wiring |
|---|---|---|---:|---:|---|
| `betPanelButton` | bet level | `btnBank` | `(0,0)` | `(125,125)` | `btn_bet(.off/.on).png` |
| `betPanel_incBet` | plus | `betButtons` | `(805,-1365)` | `(125,125)` | `btn_bet_plus(.off/.on).png` |
| `betPanel_decBet` | minus | `betButtons` | `(150,-1365)` | `(125,125)` | `btn_bet_minus(.off/.on).png` |
| `maxbtn` | max action | `betButtons` | `(540,-1580)` | `(208,82)` | `btn_auto_amt(.on).png` |
| `betPanelCloseButton` | close | `betButtons` | `(950,-1162)` | `(90,90)` | close sprite states |

---

## 5) Spin / Stop controls

| Requested item | Node | Parent | Local Pos `(x,y)` | Size `(w,h)` | PNG wiring |
|---|---|---|---:|---:|---|
| `spinButton` | spin | `spinButtonsPanel` | `(0,0)` | `(228,230)` | `btn_spin(.off/.on).png` |
| `stopButton` | stop | `spinButtonsPanel` | `(0,0)` | `(228,230)` | `btn_stop_on/btn_stop_off.png` |

---

## 6) Back button

| Requested item | Node | Parent | Local Pos `(x,y)` | Size `(w,h)` | PNG wiring |
|---|---|---|---:|---:|---|
| `backButton` | back | `lobby` | `(0,0)` | `(103,103)` | `btn_back(.on).png` |
| `lobby` | container | `btnBank` | `(0,50)` | `(103,103)` | container offset |

---

## 7) Handler mapping

- `spinButton` -> `onSpinButtonClick`
- `stopButton` -> `onStopButtonClick`
- `betPanelButton` -> `onOpenBetPanelClick`
- `betPanel_incBet` -> `onIncreaseBetClick`
- `betPanel_decBet` -> `onDecreaseBetClick`
- `maxbtn` -> `onSetMaxBetClick`
- `autoButton` -> `onOpenAutoPanelClick`
- `autoStopButton` -> `onStopAutoButtonClick`
- `btnAutoSpin` -> `onAutoButtonClick`
- `btnTurboSpin` -> `onTurboSpinButtonClick`
- `btnQuickSpin` -> `onQuickSpinButtonClick`
- `20/50/100/200/500/1000` -> `enableAutoSpin`
