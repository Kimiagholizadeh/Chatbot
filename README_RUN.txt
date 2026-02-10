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
