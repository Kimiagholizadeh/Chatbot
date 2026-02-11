How to run (Windows PowerShell)
-------------------------------
1) Create & activate venv (recommended)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

2) Install deps
   pip install -U pip
   pip install streamlit pillow

3) Run
   streamlit run streamlit_app.py

Notes
-----
- The Dev Web Builder needs a local PongGameCore (Cocos2d-html5) folder.
  Set env var PONGGAMECORE_ROOT to your PongGameCore root, OR place it in:
      .core_cache/PongGameCore
  next to this folder, OR keep your project under a workspace that already has .core_cache.

- To generate a **real Cocos Creator runnable package**:
  1) Install Cocos Creator locally.
  2) Prepare a **template Cocos Creator project** that already runs (scenes/prefabs/scripts).
     - It must contain placeholder assets + matching .meta files.
     - The wizard overwrites the placeholder file bytes (fast/safe mode).
  3) In the wizard's Build step, choose "Option B — Cocos Creator ZIP" and provide:
     - Cocos Creator executable path
     - Creator major version (2.x uses --path, 3.x uses --project)
     - Template project (ZIP upload recommended)
  4) After download, unzip and serve the build output via a web server:
       python -m http.server 8080

- To build a **single PGS-Igaming game package** (for example game 9452):
  1) Set "PGS-Igaming root" in Step 1 of the wizard.
  2) Open step "PGS Package (9452)".
  3) Use **Generate PGS Base Package ZIP** to export only required base folders.
  4) Use **Generate PGS Configurable Package ZIP** to export base folders plus user-selected symbols/audio/background and generated math payload.
  5) Configurable payload is written in canonical game locations under `assets/gameAssets/games/<id>/configs`, `sprites/generated_symbols`, and `sounds/generated_events`.
  6) The wizard warns if expected `.meta` pairs are missing in the copied base source.


- Reference: see `LOCATE_COMMON_ELEMENTS.md` for exact commands and path map to find shared buttons/fonts/help/win UI and core script locations.

- To use an LLM to review this code quickly:
  1) Open step "LLM Code Review" in the wizard.
  2) Click "Generate LLM Review Bundle ZIP".
  3) Upload the ZIP to your LLM and start with `LLM_REVIEW_PROMPT.md`.


- Reference: see `UI_CONTROL_IMPLEMENTATION_MAP.md` for spin/stop, bet popup, max bet, auto count, quick/turbo button actions and locations in code.

- If `PGS-Igaming root` is set, Dev Web build auto-imports dashboard button PNGs from `assets/resources/common/assets/default_ui/dashboard` and `.../dashboard/buttons` into runtime UI assets.

- If `PGS-Igaming root` field is blank, the app also tries to infer `.../Workspace/PGS-Igaming` from `PONGGAMECORE_ROOT`.
