# dev_builder.py  (FULL, FIXED)
# Fixes:
# - Background reliably loads (preloaded + forced texture load + fit after ready)
# - Audio mapping works with your UI uploads (and unlocks on first user tap)
# - Reel “ribbon” spin is stable (no adidas diagonal, no row-count glitches, no symbol swapping after stop)
# - 4 rows x 5 reels supported by default, AND reels/rows are selectable IN-GAME (UI) without breaking spin
# - Bet levels selectable (cycle button + +/-)

from __future__ import annotations

import io
import os
import json
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st
from PIL import Image

from .spec import GameSpec
from .util_fs import (
    copy_tree,
    copy_file,
    copy_uploaded_files,
    copy_uploaded_files_named,
    ensure_dir,
    write_bytes,
    write_json,
    write_text,
)

# ---------------------------
# Cocos2d-HTML5 boot files
# ---------------------------

_INDEX_HTML = r"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no"/>
  <title>__GAME_TITLE__</title>
  <style>
    html, body { margin:0; padding:0; width:100%; height:100%; background:#0b1020; overflow:hidden; }
    #gameCanvas { width:100vw; height:100vh; display:block; margin:0 auto; background:#0b1020; }
    #fatalError{
      display:none; position:fixed; left:0; top:0; right:0;
      max-height:55vh; overflow:auto; padding:12px 14px;
      font:12px/1.35 Consolas, Menlo, monospace;
      background:rgba(0,0,0,0.85); color:#ffb3b3;
      z-index:999999; white-space:pre-wrap;
    }
  </style>
</head>
<body>
  <div id="fatalError"></div>
  <canvas id="gameCanvas" width="960" height="540"></canvas>

  <script>
    document.ccConfig = {
      project_type: "javascript",
      debugMode: 1,
      showFPS: false,
      frameRate: 60,
      id: "gameCanvas",
      renderMode: 0,
      width: 960,
      height: 540,
      engineDir: "frameworks/cocos2d-html5",
      modules: ["core", "actions", "audio"],
      jsList: __JS_LIST__
    };

    function showFatal(msg){
      var el = document.getElementById('fatalError');
      if (!el) return;
      el.style.display='block';
      el.textContent=String(msg || 'Unknown error');
    }

    window.addEventListener('error', function(ev){
      var err = ev.error;
      var msg = (err && (err.stack || err.message)) || ev.message || 'Unhandled error';
      console.error('Unhandled error:', err || ev.message);
      showFatal(msg);
    });

    window.addEventListener('unhandledrejection', function(ev){
      console.error('Unhandled rejection:', ev.reason);
      showFatal(String(ev.reason && (ev.reason.stack || ev.reason.message) || ev.reason));
    });
  </script>

  <script cocos src="frameworks/cocos2d-html5/CCBoot.js"></script>
  <script src="main.js"></script>
  <script>
    cc.game.run();
  </script>
</body>
</html>
"""

# IMPORTANT: main.js must not call cc.game.run() (index does it)
_MAIN_JS = r"""/* global cc, g_resources, SlotScene */
cc.game.onStart = function () {
  cc.view.adjustViewPort(true);
  cc.view.setDesignResolutionSize(960, 540, cc.ResolutionPolicy.SHOW_ALL);
  cc.view.resizeWithBrowserSize(true);

  cc.LoaderScene.preload(g_resources, function () {
    cc.director.runScene(new SlotScene());
  }, this);
};
"""

COMPAT_JS = r'''/* compat.js — small polyfills to keep older cocos2d-html5 builds happy */
(function () {
  if (!window.cc) return;

  if (cc.Node && cc.Node.prototype && typeof cc.Node.prototype.setIgnoreAnchorPointForPosition !== "function") {
    cc.Node.prototype.setIgnoreAnchorPointForPosition = function (ignore) {
      if (this.ignoreAnchorPointForPosition !== undefined) {
        this.ignoreAnchorPointForPosition = !!ignore;
      } else if (this._ignoreAnchorPointForPosition !== undefined) {
        this._ignoreAnchorPointForPosition = !!ignore;
      }
    };
  }

  if (cc.LayerColor && cc.LayerColor.prototype && typeof cc.LayerColor.prototype.setIgnoreAnchorPointForPosition !== "function") {
    cc.LayerColor.prototype.setIgnoreAnchorPointForPosition = cc.Node && cc.Node.prototype && cc.Node.prototype.setIgnoreAnchorPointForPosition
      ? cc.Node.prototype.setIgnoreAnchorPointForPosition
      : function () {};
  }
})();'''

_RUN_LOCAL_PY = """import http.server
import socketserver
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)
    def do_GET(self):
        if self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        return super().do_GET()

def main():
    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
        host, port = httpd.server_address
        url = f"http://{host}:{port}/index.html"
        print(f"Serving: {ROOT}")
        print(f"Open: {url}")
        try:
            webbrowser.open(url)
        except Exception:
            pass
        httpd.serve_forever()

if __name__ == "__main__":
    main()
"""

_RUN_GAME_BAT = r"""@echo off
cd /d %~dp0
py run_local.py
"""

# ---------------------------
# Engine JS templates
# ---------------------------

_ENGINE_RNG = """var RNG = {
  int: function(minIncl, maxIncl){ return minIncl + Math.floor(Math.random() * (maxIncl - minIncl + 1)); },
  pick: function(arr){ return arr[this.int(0, arr.length - 1)]; }
};"""

# IMPORTANT: browsers require a user gesture before audio can play.
# We'll "unlock" audio on first tap in the Scene.
_ENGINE_AUDIO = """var Audio = {
  map: {},
  _unlocked: false,
  _activeWinId: null,
  _freeSpinLoopId: null,

  setMap: function(m){ this.map = m || {}; },

  unlock: function(){
    if (this._unlocked) return;
    this._unlocked = true;
    try {
      if (cc && cc.audioEngine) {
        cc.audioEngine.setEffectsVolume(1.0);
      }
    } catch (e) {}
  },

  _resolveMany: function(f){
    if (!f) return [];
    if (/^(https?:)?\/\//.test(f)) return [f];
    var out = [];
    if (f.indexOf("res/") === 0) out.push(f);
    else {
      out.push("res/assets/audio/" + f);
      out.push(f);
    }
    return out;
  },

  _lookup: function(k){
    if (!this.map) return null;
    var direct = this.map[k];
    if (direct) return direct;

    var alt = [
      String(k || "").toLowerCase(),
      String(k || "").replace(/_/g, "").toLowerCase(),
      String(k || "").replace(/_/g, "-").toLowerCase()
    ];
    for (var i=0;i<alt.length;i++){
      if (this.map[alt[i]]) return this.map[alt[i]];
    }
    return null;
  },

  stopWin: function(){
    if (this._activeWinId === null || this._activeWinId === undefined) return;
    try { cc.audioEngine.stopEffect(this._activeWinId); } catch (e) {}
    this._activeWinId = null;
  },

  startFreeSpinLoop: function(){
    if (!this._unlocked) {
      try { this.unlock(); } catch (e0) {}
      if (!this._unlocked) return;
    }
    if (this._freeSpinLoopId !== null && this._freeSpinLoopId !== undefined) return;
    var f = this._lookup("freespin");
    var cands = this._resolveMany(f);
    if (!cands.length) return;
    for (var i=0;i<cands.length;i++){
      try {
        var id = cc.audioEngine.playEffect(cands[i], true);
        if (id !== undefined && id !== null && id !== -1) {
          this._freeSpinLoopId = id;
          return;
        }
      } catch (e) {}
    }
  },

  stopFreeSpinLoop: function(){
    if (this._freeSpinLoopId === null || this._freeSpinLoopId === undefined) return;
    try { cc.audioEngine.stopEffect(this._freeSpinLoopId); } catch (e) {}
    this._freeSpinLoopId = null;
  },

  play: function(k){
    if (!this._unlocked) {
      try { this.unlock(); } catch (e0) {}
      if (!this._unlocked) return;
    }
    var f = this._lookup(k);
    var cands = this._resolveMany(f);
    if (!cands.length) return;

    var kk = String(k || "").toLowerCase();
    var isWinCue = (kk === "win" || kk === "bigwin");

    for (var i=0;i<cands.length;i++){
      try {
        var id = cc.audioEngine.playEffect(cands[i], false);
        if (id !== undefined && id !== null && id !== -1) {
          if (isWinCue) this._activeWinId = id;
          return;
        }
      } catch (e) {}
    }
  }
};"""

_ENGINE_I18N = """var I18N = {
  lang: "en",
  dict: {},
  load: function(lang, cb){
    var self = this;
    self.lang = lang || "en";
    cc.loader.loadJson("res/i18n/" + self.lang + ".json", function(err, data){
      self.dict = (err || !data) ? {} : data;
      if (cb) cb();
    });
  },
  t: function(key, fallback){
    return (this.dict && this.dict[key]) ? this.dict[key] : (fallback || key);
  }
};"""

_ENGINE_SLOT_MATH = r"""var SlotMath = {
  _isWildOrBase: function(sym, base, wildId){ return sym === base || sym === wildId; },

  evalPaylines: function(grid, paylines, paytable, wildId, betPerLine, multiplier){
    var reels = grid[0].length;
    var rows = grid.length;
    var total = 0;
    var wins = [];

    function getCell(rowIndex, reelIndex){ return grid[rowIndex][reelIndex]; }

    for (var i=0;i<paylines.length;i++){
      var line = paylines[i];
      if (!line || line.length !== reels) continue;

      var symbols = [];
      var ok = true;
      for (var r=0;r<reels;r++){
        var rr = line[r];
        if (rr < 0 || rr >= rows){ ok = false; break; }
        symbols.push(getCell(rr, r));
      }
      if (!ok) continue;

      var base = null;
      for (var k=0;k<symbols.length;k++){
        if (symbols[k] !== wildId){ base = symbols[k]; break; }
      }
      if (!base) base = wildId;

      var count = 0;
      for (var j=0;j<symbols.length;j++){
        if (this._isWildOrBase(symbols[j], base, wildId)) count++;
        else break;
      }

      if (count >= 3){
        var payDef = (paytable && paytable[base]) ? paytable[base] : null;
        var mul = payDef ? (payDef[String(count)] || payDef[count] || 0) : 0;
        if (mul > 0){
          var amount = mul * betPerLine * (multiplier || 1);
          total += amount;
          wins.push({ type:"line", lineIndex:i, count:count, base:base, amount:amount, path:line });
        }
      }
    }

    return { total: total, wins: wins };
  },

  evalScatters: function(grid, scatterId, scatterPaytable, totalBet){
    var cnt = 0;
    for (var r=0;r<grid.length;r++){
      for (var c=0;c<grid[r].length;c++){
        if (grid[r][c] === scatterId) cnt++;
      }
    }
    var mul = (scatterPaytable && scatterPaytable[String(cnt)]) ? scatterPaytable[String(cnt)] : 0;
    var amount = mul > 0 ? (mul * totalBet) : 0;
    return { count: cnt, amount: amount };
  }
};"""

# SlotModel upgraded:
# - Allows changing reels/rows at runtime (in-game UI)
# - Ensures paylines always match current reels/rows (generates safe defaults if mismatch)
_ENGINE_SLOT_MODEL = r"""var SlotModel = {
  cfg: null,
  math: null,
  assets: null,
  paylines: null,
  reelStrips: null,

  state: {
    balance: 0,
    betIndex: 0,
    freeSpins: 0,
    inFreeSpins: false
  },

  initFromFiles: function(cb){
    var self = this;
    cc.loader.loadJson("res/config.json", function(e1, cfg){
      if (e1 || !cfg){ cc.log("config.json load failed", e1); return; }
      self.cfg = cfg;

      cc.loader.loadJson("res/assets_manifest.json", function(e2, assets){
        self.assets = (e2 || !assets) ? {} : assets;

        cc.loader.loadJson("res/conf/paylines.json", function(e3, pls){
          self.paylines = (e3 || !pls) ? [] : pls;

          cc.loader.loadJson("res/conf/reel_strips.json", function(e4, strips){
            self.reelStrips = (e4 || !strips) ? [] : strips;

            cc.loader.loadJson("res/conf/paytable.json", function(e5, pt){
              self.math = self.math || {};
              self.math.paytable = (e5 || !pt) ? {} : pt;

              cc.loader.loadJson("res/conf/symbols.json", function(e6, sym){
                self.math.symbols = (e6 || !sym) ? {} : sym;

                self._initStateDefaults();

                if (self.assets && self.assets.audio) Audio.setMap(self.assets.audio);

                var lang = (self.cfg && self.cfg.localization && self.cfg.localization.languages && self.cfg.localization.languages[0]) ? self.cfg.localization.languages[0] : "en";
                I18N.load(lang, function(){ if (cb) cb(); });
              });
            });
          });
        });
      });
    });
  },

  _initStateDefaults: function(){
    var baseBet = this.baseBet();
    this.state.balance = baseBet * 1000;
    this.state.betIndex = 0;
    var levels = (this.cfg && this.cfg.math && this.cfg.math.bet_levels) ? this.cfg.math.bet_levels : [1];
    if (!levels || !levels.length) levels = [1];
    var norm = [];
    for (var i=0;i<levels.length;i++) {
      var v = Number(levels[i]);
      if (!isNaN(v) && isFinite(v) && v > 0) norm.push(v);
    }
    if (!norm.length) norm = [1];
    this.cfg.math.bet_levels = norm;
    this.state.freeSpins = 0;
    this.state.inFreeSpins = false;
  },

  baseBet: function(){
    var denom = (this.cfg && this.cfg.math && this.cfg.math.denomination) ? this.cfg.math.denomination : 0.01;
    var cpl = (this.cfg && this.cfg.math && this.cfg.math.coins_per_line) ? this.cfg.math.coins_per_line : 1;
    var pl = (this.cfg && this.cfg.math && this.cfg.math.payline_count) ? this.cfg.math.payline_count : 1;
    return denom * cpl * pl;
  },

  betLevel: function(){
    var levels = (this.cfg && this.cfg.math && this.cfg.math.bet_levels) ? this.cfg.math.bet_levels : [1];
    var idx = this.state.betIndex || 0;
    if (idx < 0) idx = 0;
    if (idx >= levels.length) idx = levels.length - 1;
    return levels[idx] || levels[0] || 1;
  },

  totalBet: function(){
    return this.baseBet() * this.betLevel();
  },

  betPerLine: function(){
    var pl = (this.cfg && this.cfg.math && this.cfg.math.payline_count) ? this.cfg.math.payline_count : 1;
    return this.totalBet() / pl;
  },

  wildId: function(){ return (this.cfg && this.cfg.math && this.cfg.math.special && this.cfg.math.special.wild) ? this.cfg.math.special.wild : "WILD"; },
  scatterId: function(){ return (this.cfg && this.cfg.math && this.cfg.math.special && this.cfg.math.special.scatter) ? this.cfg.math.special.scatter : "SCAT"; },

  // -------- Runtime settings --------

  setDimensions: function(reels, rows){
    reels = Math.max(3, Math.min(7, reels|0));
    rows  = Math.max(3, Math.min(6, rows|0));
    if (!this.cfg) return;

    this.cfg.math.reel_count = reels;
    this.cfg.math.row_count  = rows;

    // Ensure reel strips exist for reel_count (fallback repeats)
    if (!this.reelStrips || !this.reelStrips.length) {
      this.reelStrips = [];
    }
    while (this.reelStrips.length < reels) {
      this.reelStrips.push(this.reelStrips[this.reelStrips.length - 1] || ["A","K","Q","J","10","9","WILD","SCAT"]);
    }
    if (this.reelStrips.length > reels) {
      this.reelStrips = this.reelStrips.slice(0, reels);
    }

    // Ensure paylines match current dims
    this._ensurePaylines();
  },

  setPaylineCount: function(count){
    if (!this.cfg || !this.cfg.math) return;
    count = Math.max(1, Math.min(200, count|0));
    this.cfg.math.payline_count = count;
    this.paylines = this._genPaylines(
      this.cfg.math.reel_count || 5,
      this.cfg.math.row_count || 3,
      count
    );
  },

  _ensurePaylines: function(){
    var reels = (this.cfg && this.cfg.math && this.cfg.math.reel_count) ? this.cfg.math.reel_count : 5;
    var rows  = (this.cfg && this.cfg.math && this.cfg.math.row_count) ? this.cfg.math.row_count : 3;
    var wantCount = (this.cfg && this.cfg.math && this.cfg.math.payline_count) ? this.cfg.math.payline_count : 25;

    var pls = this.paylines || [];
    var ok = (pls && pls.length && pls[0] && pls[0].length === reels);
    if (ok) {
      // also validate entries in range
      for (var i=0;i<Math.min(pls.length, 5);i++){
        for (var r=0;r<reels;r++){
          var rr = pls[i][r];
          if (rr < 0 || rr >= rows) { ok = false; break; }
        }
        if (!ok) break;
      }
    }
    if (ok) return;

    // generate safe default paylines that always match reels/rows
    this.paylines = this._genPaylines(reels, rows, wantCount);
  },

  _genPaylines: function(reels, rows, count){
    var out = [];

    // 1) straight lines per row
    for (var rr=0; rr<rows && out.length<count; rr++){
      var line = [];
      for (var c=0;c<reels;c++) line.push(rr);
      out.push(line);
    }

    // 2) simple zigzags
    function clamp(v){ return Math.max(0, Math.min(rows-1, v)); }

    var patterns = [
      function(c){ return clamp((c%2===0)?0:1); },
      function(c){ return clamp((c%2===0)?1:0); },
      function(c){ return clamp((c%3===0)?0:(c%3===1)?1:2); },
      function(c){ return clamp((c%3===0)?2:(c%3===1)?1:0); },
      function(c){ return clamp(Math.floor((rows-1) * (c/(reels-1||1)))); },
      function(c){ return clamp((rows-1) - Math.floor((rows-1) * (c/(reels-1||1)))); }
    ];

    var p = 0;
    while (out.length < count) {
      var fn = patterns[p % patterns.length];
      var line2 = [];
      for (var cc=0; cc<reels; cc++) line2.push(fn(cc));
      out.push(line2);
      p++;
      if (p > 200) break;
    }
    return out;
  },

  // -------- Spin --------

  spin: function(){
    var reels = (this.cfg && this.cfg.math && this.cfg.math.reel_count) ? this.cfg.math.reel_count : 5;
    var rows  = (this.cfg && this.cfg.math && this.cfg.math.row_count) ? this.cfg.math.row_count : 3;

    this._ensurePaylines();

    var inFS = this.state.inFreeSpins && this.state.freeSpins > 0;
    var totalBet = this.totalBet();
    if (!inFS){
      if (this.state.balance < totalBet) return { error: "NO_BALANCE" };
      this.state.balance -= totalBet;
    }

    var grid = [];
    for (var r=0;r<rows;r++){ grid.push(new Array(reels)); }

    for (var reel=0;reel<reels;reel++){
      var strip = (this.reelStrips && this.reelStrips[reel]) ? this.reelStrips[reel] : ["A","K","Q","J","10","9","WILD","SCAT"];
      var stop = RNG.int(0, strip.length - 1);
      for (var row=0;row<rows;row++){
        var idx = (stop + row) % strip.length;
        grid[row][reel] = strip[idx];
      }
    }

    var paytable = this.math && this.math.paytable ? this.math.paytable : {};
    var wild = this.wildId();
    var scatter = this.scatterId();

    var mult = (inFS && this.cfg && this.cfg.math && this.cfg.math.features && this.cfg.math.features.free_spins_multiplier) ? this.cfg.math.features.free_spins_multiplier : 1;

    var lineRes = SlotMath.evalPaylines(grid, this.paylines || [], paytable, wild, this.betPerLine(), mult);

    var scatPaytable = (paytable && paytable[scatter]) ? paytable[scatter] : {};
    var scatRes = SlotMath.evalScatters(grid, scatter, scatPaytable, totalBet);

    var totalWin = lineRes.total + scatRes.amount;

    var fsAward = 0;
    if (this.cfg && this.cfg.math && this.cfg.math.features && this.cfg.math.features.free_spins_award){
      var awardMap = this.cfg.math.features.free_spins_award;
      fsAward = awardMap[String(scatRes.count)] || awardMap[scatRes.count] || 0;
    }
    if (fsAward > 0){
      this.state.freeSpins += fsAward;
      this.state.inFreeSpins = true;
    }

    if (inFS){
      this.state.freeSpins -= 1;
      if (this.state.freeSpins <= 0){
        this.state.freeSpins = 0;
        this.state.inFreeSpins = false;
      }
    }

    this.state.balance += totalWin;

    return {
      grid: grid,
      totalBet: totalBet,
      inFreeSpins: inFS,
      freeSpinsRemaining: this.state.freeSpins,
      wins: lineRes.wins,
      scatter: scatRes,
      totalWin: totalWin,
      balance: this.state.balance
    };
  }
};"""

# ---------------------------
# Scene JS (FIXED: background, audio unlock, stable reels, selectable reels/rows & bet levels)
# ---------------------------

_SCENE_SLOT = r"""
/* global cc, SlotModel, Audio, I18N */

var SlotScene = cc.Scene.extend({
  ctor: function () {
    this._super();
    this.ui = {};
    this.busy = false;

    this.gridLayer = null;
    this.uiLayer = null;

    // grid
    this.cellFrames = [];
    this.symbolCells = [];

    // spin
    this._spinElapsed = 0;
    this._spinActive = false;

    // audio
    this._muted = false;
    this._audioUnlocked = false;

    // draw
    this.lineDraw = null;
    this._showAllPaylines = false;

    // ribbon reels
    this.reelStrips = []; // per reel: { node, sprites[], cellH, rows }
    this._spinOffsets = [];
    this._spinStopTimes = [];
    this._spinLocked = [];

    // background
    this._bgNode = null;

    // dashboard-like controls
    this._forceStopRequested = false;
    this._autoPanelOpen = false;
    this._betPanelOpen = false;
    this._autoRemaining = 0;
    this._spinMode = "normal"; // normal|quick|turbo

    return true;
  },

  onEnter: function () {
    this._super();
    var self = this;

    // temporary background until assets loaded
    this._bgNode = new cc.LayerColor(cc.color(11,16,32,255), 960, 540);
    this.addChild(this._bgNode, 0);

    var title = new cc.LabelTTF("Slot Maker Engine", "Arial", 22);
    title.setPosition(480, 520);
    this._title = title;
    this.addChild(title, 1);

    this.gridLayer = new cc.Node();
    this.addChild(this.gridLayer, 2);

    this.uiLayer = new cc.Node();
    this.addChild(this.uiLayer, 50);

    SlotModel.initFromFiles(function(){
      try {
        if (self._title && SlotModel.cfg && SlotModel.cfg.identity && SlotModel.cfg.identity.display_name) {
          self._title.setString(String(SlotModel.cfg.identity.display_name));
        }
      } catch (eTitle) {}

      // Respect wizard-configured dimensions from game_config.json
      try { SlotModel.setDimensions(SlotModel.cfg.math.reel_count || 5, SlotModel.cfg.math.row_count || 4); } catch (e) {}

      self._loadBackground();
      self._buildUI();
      self._rebuildGrid();      // builds based on SlotModel.cfg.math reels/rows
      self._refreshUI();
      self._renderInitialGrid();
    });
  },

  // ---------------- Background ----------------

  _loadBackground: function(){
    try {
      var bgFile = SlotModel.assets && (SlotModel.assets.background || SlotModel.assets.bg);
      if (!bgFile) return;

      var candidates = [];
      if (String(bgFile).indexOf("res/") === 0) candidates.push(String(bgFile));
      else {
        candidates.push("res/assets/backgrounds/" + bgFile);
        candidates.push(String(bgFile));
      }

      var self = this;
      var applyBg = function(bg){
        if (!bg) return;
        if (self._bgNode) self._bgNode.removeFromParent(true);
        bg.setPosition(480, 270);
        self.addChild(bg, 0);
        self._fitSpriteTo(bg, 960, 540, true);
        if (typeof self.scheduleOnce === "function") {
          self.scheduleOnce(function(){ self._fitSpriteTo(bg, 960, 540, true); }, 0.05);
        }
        self._bgNode = bg;
      };

      var bg = null;
      for (var i=0; i<candidates.length; i++){
        try {
          bg = new cc.Sprite(candidates[i]);
          var sz = bg.getContentSize && bg.getContentSize();
          if (sz && sz.width > 0 && sz.height > 0) { applyBg(bg); return; }
        } catch (e1) { bg = null; }
      }

      for (var j=0; j<candidates.length; j++){
        (function(path){
          try {
            cc.textureCache.addImage(path, function(tex){
              if (!tex) return;
              applyBg(new cc.Sprite(tex));
            });
          } catch (e2) {}
        })(candidates[j]);
      }
    } catch (e) {}
  },

  // ---------------- Helpers ----------------

  _fitSpriteTo: function(sprite, w, h, cover){
    var s = sprite.getContentSize();
    if (!s || !s.width || !s.height) return;
    var sx = w / s.width;
    var sy = h / s.height;
    var sc = cover ? Math.max(sx, sy) : Math.min(sx, sy);
    sprite.setScale(sc);
  },

  _fitToBox: function(sprite, maxW, maxH){
    var s = sprite.getContentSize();
    if (!s || !s.width || !s.height) return;
    var sx = maxW / s.width;
    var sy = maxH / s.height;
    sprite.setScale(Math.min(sx, sy));
  },

  _setSpriteSymbol: function(sprite, symId){
    var symMap = (SlotModel.assets && SlotModel.assets.symbols) ? SlotModel.assets.symbols : {};
    var fn = symMap ? symMap[symId] : null;
    if (!fn && typeof symId === "string") fn = symMap[symId.toUpperCase()] || symMap[symId.toLowerCase()] || null;

    if (fn) {
      var texPath = "res/assets/symbols/" + fn;
      try { sprite.setTexture(texPath); } catch(e) {}
      this._fitToBox(sprite, 108, 86);
      sprite._baseScale = sprite.getScale();
      sprite.setVisible(true);
    } else {
      sprite.setVisible(false);
    }
  },

  // Gentle “ribbon” (NO adidas diagonal): depends only on slot index
  _applyRibbonLookBySlotIndex: function(sprite, slotIndex, rows){
    var visIndex = Math.max(0, Math.min(rows - 1, slotIndex - 1)); // visible rows correspond to sprites[1..rows]
    var mid = (rows - 1) * 0.5;
    var d = Math.min(1, Math.abs(visIndex - mid) / (mid || 1));
    var ribbonFactor = 1.0 - 0.10 * d; // gentle only
    var base = (sprite._baseScale != null) ? sprite._baseScale : sprite.getScale();
    sprite.setScale(base * ribbonFactor);
    sprite.setOpacity(255 - Math.floor(35 * d));
  },

  _unlockAudioOnce: function(){
    if (this._audioUnlocked) return;
    this._audioUnlocked = true;
    try { Audio.unlock(); } catch (e) {}
  },

  // ---------------- UI ----------------

  _uiAsset: function(keys){
    var byStem = (SlotModel.assets && SlotModel.assets.ui_by_stem) ? SlotModel.assets.ui_by_stem : {};
    for (var i=0;i<keys.length;i++) {
      var k = String(keys[i] || '').toLowerCase();
      if (byStem[k]) return "res/assets/ui/" + byStem[k];
    }
    return null;
  },

  _applyButtonTexture: function(node, path, w, h){
    if (!node || !node._bg || !path) return false;
    try {
      node._bg.setTexture(path);
      var s = node._bg.getContentSize();
      if (s && s.width > 0 && s.height > 0) {
        var targetW = w || s.width;
        var targetH = h || s.height;
        var sc = Math.min(targetW / s.width, targetH / s.height);
        node._bg.setScale(sc);
      }
      if (node._fallbackBg) node._fallbackBg.setVisible(false);
      if (node._label && node._hideLabelWhenTextured) node._label.setVisible(false);
      return true;
    } catch (e) {}
    return false;
  },

  _setButtonDisabled: function(node, disabled){
    if (!node) return;
    node._disabled = !!disabled;
    if (node._setState) node._setState(node._disabled ? "off" : "normal");
    if (node._label) node._label.setOpacity(node._disabled ? 140 : 255);
  },

  _makeImageButton: function(x, y, label, onClick, states, w, h){
    var node = this._makeButton(x, y, label, onClick, w, h);
    var cfg = states || {};
    node._hideLabelWhenTextured = (cfg.hideLabelWhenTextured !== false);
    var normal = this._uiAsset(cfg.normal || []);
    var onPath = this._uiAsset(cfg.on || cfg.normal || []);
    var offPath = this._uiAsset(cfg.off || cfg.normal || []);

    node._img = { normal: normal, on: onPath, off: offPath };
    var self = this;
    node._setState = function(st){
      var pick = node._img && node._img[st] ? node._img[st] : (node._img ? node._img.normal : null);
      if (!pick) {
        if (node._fallbackBg) node._fallbackBg.setVisible(true);
        if (node._label) node._label.setVisible(true);
        return;
      }
      var ok = self._applyButtonTexture(node, pick, w, h);
      if (!ok) {
        if (node._fallbackBg) node._fallbackBg.setVisible(true);
        if (node._label) node._label.setVisible(true);
      }
    };
    node._setState("normal");
    return node;
  },

  _makePanel: function(x, y, w, h, bgKeys){
    var n = new cc.Node();
    n.setPosition(x, y);
    n.setContentSize(w, h);

    var bgPath = this._uiAsset(bgKeys || []);
    if (bgPath) {
      var sp = new cc.Sprite(bgPath);
      var sz = sp.getContentSize();
      if (sz && sz.width && sz.height) {
        var sc = Math.min(w / sz.width, h / sz.height);
        sp.setScale(sc);
      }
      n.addChild(sp);
    } else {
      var bg = new cc.LayerColor(cc.color(16, 20, 36, 230), w, h);
      if (bg.setIgnoreAnchorPointForPosition) bg.setIgnoreAnchorPointForPosition(false);
      bg.setPosition(-w/2, -h/2);
      n.addChild(bg);
    }
    return n;
  },


  _fromBaseLandscape: function(x, y){
    // Map Panda dashboard landscape coordinates into the dev canvas.
    // Use a 2732x1536 reference so X/Y scale stays uniform and slot spacing
    // matches the source layout (spin top, speed+bet row, auto below).
    var baseHalfW = 1366.0;
    var baseHalfH = 768.0;
    var targetHalfW = 480.0;
    var targetHalfH = 270.0;
    return cc.p(480 + (x / baseHalfW) * targetHalfW, 270 + (y / baseHalfH) * targetHalfH);
  },

  _buildUI: function(){
    var self = this;

    var balance = new cc.LabelTTF("", "Arial", 18);
    balance.setColor(cc.color(255, 215, 0));
    balance.setAnchorPoint(0, 0.5);
    balance.setPosition(20, 490);
    this.uiLayer.addChild(balance);
    this.ui.balance = balance;

    var bet = new cc.LabelTTF("", "Arial", 18);
    bet.setColor(cc.color(255, 215, 0));
    bet.setAnchorPoint(1, 0.5);
    bet.setPosition(940, 490);
    this.uiLayer.addChild(bet);
    this.ui.bet = bet;

    var fs = new cc.LabelTTF("", "Arial", 18);
    fs.setAnchorPoint(0.5, 0.5);
    fs.setPosition(480, 490);
    this.uiLayer.addChild(fs);
    this.ui.fs = fs;

    var msg = new cc.LabelTTF("", "Arial", 18);
    msg.setPosition(480, 60);
    this.uiLayer.addChild(msg);
    this.ui.msg = msg;

    var paylineInfo = new cc.LabelTTF("", "Arial", 14);
    paylineInfo.setAnchorPoint(0, 1);
    paylineInfo.setPosition(20, 455);
    this.uiLayer.addChild(paylineInfo);
    this.ui.paylineInfo = paylineInfo;

    var winBreakdown = new cc.LabelTTF("", "Arial", 13);
    winBreakdown.setAnchorPoint(1, 1);
    winBreakdown.setPosition(940, 455);
    this.uiLayer.addChild(winBreakdown);
    this.ui.winBreakdown = winBreakdown;

    // Dev-canvas layout tuned to preserve Panda stack structure without overlap:
    // spin top, speed+bet middle row, auto bottom row.
    var spinAnchor = cc.p(860, 218);
    var speedAnchor = cc.p(825, 126);
    var betAnchor  = cc.p(895, 126);
    var autoAnchor = cc.p(860, 72);
    var popupAnchor = cc.p(420, 188);

    this.ui.spinButtonsPanel = new cc.Node();
    this.ui.spinButtonsPanel.setPosition(spinAnchor);
    this.ui.spinButtonsPanel.setScale(0.50);
    this.uiLayer.addChild(this.ui.spinButtonsPanel);

    this.ui.spinBtn = this._makeImageButton(0, 0, I18N.t("spin","SPIN"), function(){
      self._unlockAudioOnce();
      self._closeBetPanel(true);
      self._closeAutoPanel(true);
      self._onSpin();
    }, {
      normal:["btn_spin"],
      on:["btn_spin_on","btn_spin"],
      off:["btn_spin_off","btn_spin"]
    }, 228, 230);
    this.ui.spinButtonsPanel.addChild(this.ui.spinBtn);

    this.ui.stopBtn = this._makeImageButton(0, 0, "STOP", function(){
      self._unlockAudioOnce();
      self.onStopButtonClick();
    }, {
      normal:["btn_stop_on","btn_stop"],
      on:["btn_stop_on","btn_stop"],
      off:["btn_stop_off","btn_stop"]
    }, 228, 230);
    this.ui.spinButtonsPanel.addChild(this.ui.stopBtn);
    this.ui.stopBtn.setVisible(false);

    this.ui.speedModeButton = this._makeImageButton(speedAnchor.x, speedAnchor.y, "SPEED", function(){
      self._unlockAudioOnce();
      self.onSpeedModeButtonClick();
    }, {
      normal:["btn_speed","btn_speed_quick","btn_quick_off"],
      on:["btn_speed_on","btn_speed_quick_on","btn_quick_on","btn_speed"],
      off:["btn_speed_off","btn_speed_quick_off","btn_quick_off","btn_speed"]
    }, 125, 125);
    this.ui.speedModeButton.setScale(0.60);
    this.uiLayer.addChild(this.ui.speedModeButton);

    this.ui.betPanelButton = this._makeImageButton(betAnchor.x, betAnchor.y, "BET", function(){
      self._unlockAudioOnce();
      self.onOpenBetPanelClick();
    }, {
      normal:["btn_bet"],
      on:["btn_bet_on","btn_bet"],
      off:["btn_bet_off","btn_bet"]
    }, 125, 125);
    this.ui.betPanelButton.setScale(0.60);
    this.uiLayer.addChild(this.ui.betPanelButton);

    this.ui.autoSpinPanel = new cc.Node();
    this.ui.autoSpinPanel.setPosition(autoAnchor);
    this.ui.autoSpinPanel.setScale(0.60);
    this.uiLayer.addChild(this.ui.autoSpinPanel);

    this.ui.autoButton = this._makeImageButton(0, 0, "AUTO", function(){
      self._unlockAudioOnce();
      self.onOpenAutoPanelClick();
    }, {
      normal:["btn_auto"],
      on:["btn_auto_on","btn_auto"],
      off:["btn_auto_off","btn_auto"]
    }, 125, 125);
    this.ui.autoSpinPanel.addChild(this.ui.autoButton);

    this.ui.autoStopButton = this._makeImageButton(0, 0, "AUTO", function(){
      self._unlockAudioOnce();
      self.onStopAutoButtonClick();
    }, {
      normal:["btn_auto_active","btn_stop_on"],
      on:["btn_auto_active","btn_stop_on"],
      off:["btn_auto_active","btn_stop_off"]
    }, 125, 125);
    this.ui.autoSpinPanel.addChild(this.ui.autoStopButton);
    this.ui.autoStopButton.setVisible(false);

    this.ui.betInfoPanel = new cc.Node();
    this.ui.betInfoPanel.setPosition(popupAnchor);
    this.ui.betInfoPanel.setScale(0.58 * 2.0);
    this.uiLayer.addChild(this.ui.betInfoPanel, 200);
    this.ui.betInfoPanel.setVisible(false);

    var betBgPath = this._uiAsset(["bet_popup_panel_bg","popup_panel_bg","auto_popup_panel","auto_panel"]);
    if (betBgPath) {
      var betBg = new cc.Sprite(betBgPath);
      betBg.setPosition(538, -290);
      this._fitSpriteTo(betBg, 2200, 476, false);
      betBg.setOpacity(235);
      this.ui.betInfoPanel.addChild(betBg);
    }

    this.ui.betHeader = new cc.LabelTTF("BET LEVEL", "Arial", 30);
    this.ui.betHeader.setColor(cc.color(255, 215, 0));
    this.ui.betHeader.setPosition(538, -1040);
    this.ui.betInfoPanel.addChild(this.ui.betHeader);

    this.ui.betButtons = new cc.Node();
    this.ui.betButtons.setPosition(0, 1214.677);
    this.ui.betInfoPanel.addChild(this.ui.betButtons);

    this.ui.betPanelCloseButton = this._makeImageButton(950, -1162, "", function(){ self.onCloseBetPanelClick(); }, { normal:["btn_menu_close"], on:["btn_close_on_menu","btn_menu_close_on","btn_menu_close"], off:["btn_menu_close_off","btn_menu_close"] }, 90, 90);
    this.ui.betButtons.addChild(this.ui.betPanelCloseButton);
    this.ui.betPanel_decBet = this._makeImageButton(150, -1365, "", function(){ self.onDecreaseBetClick(); }, { normal:["btn_bet_minus"], on:["btn_bet_minus_on","btn_bet_minus"], off:["btn_bet_minus_off","btn_bet_minus"] }, 125, 125);
    this.ui.betButtons.addChild(this.ui.betPanel_decBet);
    this.ui.betPanel_incBet = this._makeImageButton(805, -1365, "", function(){ self.onIncreaseBetClick(); }, { normal:["btn_bet_plus"], on:["btn_bet_plus_on","btn_bet_plus"], off:["btn_bet_plus_off","btn_bet_plus"] }, 125, 125);
    this.ui.betButtons.addChild(this.ui.betPanel_incBet);
    this.ui.betPanelMaxBtn = this._makeImageButton(540, -1580, "MAX", function(){ self.onSetMaxBetClick(); }, { normal:["btn_auto_amt","btn_bet_max"], on:["btn_auto_amt_on","btn_bet_max","btn_auto_amt"], off:["btn_auto_amt","btn_bet_max"], hideLabelWhenTextured:false }, 208, 82);
    this.ui.betButtons.addChild(this.ui.betPanelMaxBtn);
    this.ui.betPanelText = new cc.LabelTTF("", "Arial", 19);
    this.ui.betPanelText.setColor(cc.color(255, 215, 0));
    this.ui.betPanelText.setPosition(540, -1260);
    this.ui.betButtons.addChild(this.ui.betPanelText);

    this.ui.autoPanelInfo = new cc.Node();
    this.ui.autoPanelInfo.setPosition(popupAnchor);
    this.ui.autoPanelInfo.setScale(0.62);
    this.uiLayer.addChild(this.ui.autoPanelInfo, 200);
    this.ui.autoPanelInfo.setVisible(false);

    var autoBgPath = this._uiAsset(["popup_panel_bg","auto_popup_panel","bet_popup_panel","auto_panel"]);
    if (autoBgPath) {
      var autoBg = new cc.Sprite(autoBgPath);
      autoBg.setPosition(530, 142.632);
      autoBg.setAnchorPoint(0.5, 1);
      this._fitSpriteTo(autoBg, 1100, 667.7, false);
      autoBg.setOpacity(235);
      this.ui.autoPanelInfo.addChild(autoBg);
    }

    this.ui.autoButtonContainer = new cc.Node();
    this.ui.autoButtonContainer.setPosition(0, 1151.176);
    this.ui.autoPanelInfo.addChild(this.ui.autoButtonContainer);

    this.ui.autoPanelCloseButton = this._makeImageButton(950, -888.485, "", function(){ self.onCloseAutoPanelClick(); }, { normal:["btn_menu_close"], on:["btn_menu_close_on","btn_menu_close"], off:["btn_menu_close_off","btn_menu_close"] }, 125, 125);
    this.ui.autoButtonContainer.addChild(this.ui.autoPanelCloseButton);

    this.ui.autoPlayHeader = new cc.LabelTTF("AUTO PLAY", "Arial", 32);
    this.ui.autoPlayHeader.setColor(cc.color(255, 215, 0));
    this.ui.autoPlayHeader.setPosition(538, -930);
    this.ui.autoButtonContainer.addChild(this.ui.autoPlayHeader);

    this.ui.autoCountLabel = new cc.LabelTTF("Auto count: 0", "Arial", 18);
    this.ui.autoCountLabel.setColor(cc.color(255, 215, 0));
    this.ui.autoCountLabel.setPosition(538, -1140);
    this.ui.autoButtonContainer.addChild(this.ui.autoCountLabel);

    this.ui.autoBtnContainer = new cc.Node();
    this.ui.autoBtnContainer.setPosition(538, -1300.128);
    this.ui.autoButtonContainer.addChild(this.ui.autoBtnContainer);

    var counts = [20, 50, 100, 200, 500, 1000];
    var pos = {
      20:[-320, -69.276],
      50:[-10, -69.276],
      100:[300, -69.276],
      200:[-320, 71.417],
      500:[-10, 71.417],
      1000:[300, 71.417]
    };
    this.ui.autoCountButtons = [];
    for (var ci=0; ci<counts.length; ci++) {
      (function(idx){
        var cnt = counts[idx];
        var xy = pos[cnt];
        var b = self._makeImageButton(xy[0], xy[1], String(cnt), function(){ self.enableAutoSpin(null, cnt); }, { normal:["btn_auto_amt"], on:["btn_auto_amt_on","btn_auto_amt"], off:["btn_auto_amt","btn_auto_amt_off"], hideLabelWhenTextured:false }, 208, 82);
        self.ui.autoBtnContainer.addChild(b);
        self.ui.autoCountButtons.push(b);
      })(ci);
    }

    this.ui.btnQuickSpin = this._makeImageButton(702.043, -1100.331, "", function(){ self.onQuickSpinButtonClick(); }, { normal:["btn_quick_on","btn_quick_off","btn_speed_quick"], on:["btn_quick_on","btn_speed_quick_on","btn_speed_quick"], off:["btn_quick_on","btn_quick_off","btn_speed_quick"] }, 225, 132);
    this.ui.autoButtonContainer.addChild(this.ui.btnQuickSpin);
    this.ui.quickLabel = new cc.LabelTTF("FAST\nSPIN", "Arial", 20, cc.size(95.01, 67.8), cc.TEXT_ALIGNMENT_CENTER, cc.VERTICAL_TEXT_ALIGNMENT_CENTER);
    this.ui.quickLabel.setAnchorPoint(0.5, 0.5);
    this.ui.quickLabel.setPosition(134.128, 4.286);
    this.ui.btnQuickSpin.addChild(this.ui.quickLabel, 5);

    this.ui.btnTurboSpin = this._makeImageButton(239.246, -1100.331, "", function(){ self.onTurboSpinButtonClick(); }, { normal:["btn_turbo","btn_turbo_off","btn_speed_turbo"], on:["btn_turbo","btn_speed_turbo_on","btn_speed_turbo"], off:["btn_turbo","btn_turbo_off","btn_speed_turbo"] }, 225, 132);
    this.ui.autoButtonContainer.addChild(this.ui.btnTurboSpin);
    this.ui.turboLabel = new cc.LabelTTF("TURBO\nSPIN", "Arial", 20, cc.size(105, 67.8), cc.TEXT_ALIGNMENT_CENTER, cc.VERTICAL_TEXT_ALIGNMENT_CENTER);
    this.ui.turboLabel.setAnchorPoint(0.5, 0.5);
    this.ui.turboLabel.setPosition(134.128, 4.286);
    this.ui.btnTurboSpin.addChild(this.ui.turboLabel, 5);
    this.ui.btnAutoSpin = this._makeImageButton(427.071, -1443.775, "", function(){ self.onAutoButtonClick(); }, { normal:["btn_auto_spin"], on:["btn_auto_spin_on","btn_auto_spin"], off:["btn_auto_spin_off","btn_auto_spin"] }, 225, 225);
    this.ui.autoButtonContainer.addChild(this.ui.btnAutoSpin);

    // Settings / info controls (top-right) so audio + help are always available.
    this.ui.settingsButton = this._makeImageButton(64, 58, "SET", function(){
      self._unlockAudioOnce();
      self._toggleSettingsMenu();
    }, {
      normal:["btn_setting","btn_settings","btn_menu"],
      on:["btn_setting_on","btn_settings_on","btn_menu_on","btn_setting"],
      off:["btn_setting_off","btn_settings_off","btn_menu_off","btn_setting"]
    }, 70, 70);
    this.uiLayer.addChild(this.ui.settingsButton);

    this.ui.settingsPanel = new cc.Node();
    this.ui.settingsPanel.setPosition(154, 118);
    this.uiLayer.addChild(this.ui.settingsPanel, 220);
    this.ui.settingsPanel.setVisible(false);

    this.ui.audioButton = this._makeButton(0, 0, "AUDIO: ON", function(){
      self._unlockAudioOnce();
      self._muted = !self._muted;
      if (self.ui && self.ui.audioButton && self.ui.audioButton._label) {
        self.ui.audioButton._label.setString(self._muted ? "AUDIO: OFF" : "AUDIO: ON");
      }
      try { Audio.unlock(); } catch(e){}
    }, 160, 34);
    this.ui.settingsPanel.addChild(this.ui.audioButton);

    this.ui.infoButton = this._makeButton(0, -44, "INFO", function(){
      self._toggleInfoPanel();
    }, 160, 34);
    this.ui.settingsPanel.addChild(this.ui.infoButton);

    this.ui.infoPanel = this._makePanel(480, 270, 680, 330, ["popup_panel_bg","help_popup_panel"]);
    this.uiLayer.addChild(this.ui.infoPanel, 230);
    this.ui.infoPanel.setVisible(false);
    this.ui.infoPanelClose = this._makeButton(300, 140, "X", function(){ self._toggleInfoPanel(false); }, 52, 32);
    this.ui.infoPanel.addChild(this.ui.infoPanelClose);
    this.ui.infoText = new cc.LabelTTF(this._getInfoText(), "Arial", 16, cc.size(610, 250), cc.TEXT_ALIGNMENT_LEFT, cc.VERTICAL_TEXT_ALIGNMENT_TOP);
    this.ui.infoText.setAnchorPoint(0, 1);
    this.ui.infoText.setPosition(-300, 120);
    this.ui.infoPanel.addChild(this.ui.infoText);

    if (cc.DrawNode) {
      try { this.lineDraw = new cc.DrawNode(); this.gridLayer.addChild(this.lineDraw, 30); } catch (e) { this.lineDraw = null; }
    }
    if (!this.lineDraw) this.lineDraw = { clear:function(){}, drawSegment:function(){} };

    this.setSpinMode("normal");
    this._refreshControlStates();
    this._refreshUI();
  },

  _toggleSettingsMenu: function(forceOpen){
    var show = (typeof forceOpen === "boolean") ? forceOpen : !(this.ui && this.ui.settingsPanel && this.ui.settingsPanel.isVisible());
    if (this.ui && this.ui.settingsPanel) this.ui.settingsPanel.setVisible(show);
    if (!show) this._toggleInfoPanel(false);
  },

  _getInfoText: function(){
    var cfg = SlotModel && SlotModel.cfg ? SlotModel.cfg : {};
    var h = cfg.help_texts || cfg.helpTexts || {};
    var lines = [];
    if (h.how_to_play) lines.push("How to play: " + h.how_to_play);
    if (h.paytable_note) lines.push("Paytable: " + h.paytable_note);
    if (h.rtp) lines.push("RTP: " + h.rtp);
    if (h.volatility) lines.push("Volatility: " + h.volatility);
    if (!lines.length) {
      lines.push("Spin to start.");
      lines.push("Use BET to open bet controls.");
      lines.push("Use AUTO to configure autoplay counts.");
      lines.push("Use STOP while reels are spinning.");
    }
    return lines.join("\n\n");
  },

  _toggleInfoPanel: function(forceOpen){
    if (!this.ui || !this.ui.infoPanel) return;
    var show = (typeof forceOpen === "boolean") ? forceOpen : !this.ui.infoPanel.isVisible();
    if (show && this.ui.infoText && this.ui.infoText.setString) this.ui.infoText.setString(this._getInfoText());
    this.ui.infoPanel.setVisible(show);
    if (show) this._toggleSettingsMenu(true);
  },

  _setSpinButtonsState: function(spinning){
    if (!this.ui) return;
    if (this.ui.spinBtn) this.ui.spinBtn.setVisible(!spinning);
    if (this.ui.stopBtn) this.ui.stopBtn.setVisible(!!spinning);
  },

  onSpinButtonClick: function(){ this._onSpin(); },

  onStopButtonClick: function(){
    if (!this.busy) return;
    this._forceStopRequested = true;
    this._setMessage("Stopping...");
  },

  onOpenBetPanelClick: function(){
    if (this.busy) return;
    this._closeAutoPanel(true);
    this._betPanelOpen = true;
    if (this.ui && this.ui.betInfoPanel) this.ui.betInfoPanel.setVisible(true);
    this._refreshControlStates();
    this._updateBetBtnVisibility();
    try { if (!this._muted) Audio.play("click"); } catch(e){}
  },

  onCloseBetPanelClick: function(){ this._closeBetPanel(); },

  _closeBetPanel: function(forcedClose){
    this._betPanelOpen = false;
    if (this.ui && this.ui.betInfoPanel) this.ui.betInfoPanel.setVisible(false);
    this._refreshControlStates();
    if (!forcedClose) { try { if (!this._muted) Audio.play("click"); } catch(e){} }
  },

  onIncreaseBetClick: function(){
    if (this.busy) return;
    var levels = SlotModel.cfg.math.bet_levels || [1];
    SlotModel.state.betIndex = Math.min(levels.length - 1, (SlotModel.state.betIndex||0) + 1);
    this._updateBetBtnVisibility();
    this._refreshControlStates();
    this._refreshUI();
  },

  onDecreaseBetClick: function(){
    if (this.busy) return;
    SlotModel.state.betIndex = Math.max(0, (SlotModel.state.betIndex||0) - 1);
    this._updateBetBtnVisibility();
    this._refreshControlStates();
    this._refreshUI();
  },

  onSetMaxBetClick: function(){
    if (this.busy) return;
    var levels = SlotModel.cfg.math.bet_levels || [1];
    SlotModel.state.betIndex = Math.max(0, levels.length - 1);
    this._updateBetBtnVisibility();
    this._refreshControlStates();
    this._refreshUI();
  },

  _updateBetBtnVisibility: function(){
    var levels = SlotModel.cfg.math.bet_levels || [1];
    var idx = SlotModel.state.betIndex || 0;
    var min = 0, max = Math.max(0, levels.length - 1);
    if (this.ui && this.ui.betPanel_decBet) this._setButtonDisabled(this.ui.betPanel_decBet, !(idx > min));
    if (this.ui && this.ui.betPanel_incBet) this._setButtonDisabled(this.ui.betPanel_incBet, !(idx < max));
    if (this.ui && this.ui.betPanelMaxBtn) this._setButtonDisabled(this.ui.betPanelMaxBtn, !(idx < max));
    if (this.ui && this.ui.betPanelText) this.ui.betPanelText.setString("BET LEVEL x" + String(SlotModel.betLevel()));
  },

  onOpenAutoPanelClick: function(){
    if (this.busy) return;
    this._closeBetPanel(true);
    this._autoPanelOpen = true;
    if (this.ui && this.ui.autoPanelInfo) this.ui.autoPanelInfo.setVisible(true);
    this._refreshControlStates();
    this._updateAutoPanelLabel();
    try { if (!this._muted) Audio.play("click"); } catch(e){}
  },

  onCloseAutoPanelClick: function(){ this._closeAutoPanel(); },

  _closeAutoPanel: function(forcedClose){
    this._autoPanelOpen = false;
    if (this.ui && this.ui.autoPanelInfo) this.ui.autoPanelInfo.setVisible(false);
    this._refreshControlStates();
    if (!forcedClose) { try { if (!this._muted) Audio.play("click"); } catch(e){} }
  },

  enableAutoSpin: function(_event, autoSpinCount){
    this._autoRemaining = Math.max(0, parseInt(autoSpinCount || 0, 10) || 0);
    this._updateAutoPanelLabel();
    this._refreshControlStates();
  },

  onAutoButtonClick: function(){
    if (this.busy) return;
    if ((this._autoRemaining || 0) <= 0) this._autoRemaining = 20;
    this._closeAutoPanel(true);
    if (this.ui && this.ui.autoStopButton) this.ui.autoStopButton.setVisible(true);
    this._onSpin();
  },

  onStopAutoButtonClick: function(){
    this._autoRemaining = 0;
    if (this.ui && this.ui.autoStopButton) this.ui.autoStopButton.setVisible(false);
    this._setMessage("Auto stopped");
    this._refreshControlStates();
  },

  setSpinMode: function(mode){
    this._spinMode = mode || "normal";
    if (this.ui && this.ui.btnQuickSpin && this.ui.btnQuickSpin._setState) this.ui.btnQuickSpin._setState(this._spinMode === "quick" ? "on" : "normal");
    if (this.ui && this.ui.btnTurboSpin && this.ui.btnTurboSpin._setState) this.ui.btnTurboSpin._setState(this._spinMode === "turbo" ? "on" : "normal");
    if (this.ui && this.ui.speedModeButton && this.ui.speedModeButton._setState) this.ui.speedModeButton._setState(this._spinMode === "normal" ? "normal" : "on");
  },

  onQuickSpinButtonClick: function(){ this.setSpinMode("quick"); this._updateAutoPanelLabel(); },
  onTurboSpinButtonClick: function(){ this.setSpinMode("turbo"); this._updateAutoPanelLabel(); },

  onSpeedModeButtonClick: function(){
    var mode = this._spinMode || "normal";
    if (mode === "normal") this.setSpinMode("quick");
    else if (mode === "quick") this.setSpinMode("turbo");
    else this.setSpinMode("normal");
    this._updateAutoPanelLabel();
    this._refreshControlStates();
  },

  _updateAutoPanelLabel: function(){
    if (this.ui && this.ui.autoCountLabel) {
      this.ui.autoCountLabel.setString("Auto count: " + String(this._autoRemaining || 0) + " | Speed: " + String(this._spinMode || "normal").toUpperCase());
    }
  },

  _refreshControlStates: function(){
    var hasOverlay = !!(this._autoPanelOpen || this._betPanelOpen || this.busy);
    if (this.ui && this.ui.spinBtn) this._setButtonDisabled(this.ui.spinBtn, hasOverlay);
    if (this.ui && this.ui.betPanelButton) this._setButtonDisabled(this.ui.betPanelButton, !!(this.busy || this._autoPanelOpen));
    if (this.ui && this.ui.speedModeButton) this._setButtonDisabled(this.ui.speedModeButton, !!(this.busy || this._autoPanelOpen || this._betPanelOpen));
    if (this.ui && this.ui.autoButton) this._setButtonDisabled(this.ui.autoButton, !!(this.busy || this._betPanelOpen));

    var canAutoStart = (this._autoRemaining || 0) > 0;
    if (this.ui && this.ui.btnAutoSpin) this._setButtonDisabled(this.ui.btnAutoSpin, !canAutoStart);

    if (this.ui && this.ui.autoStopButton && this.ui.autoStopButton._setState) {
      var active = (this._autoRemaining || 0) > 0;
      this.ui.autoStopButton._setState(active ? "normal" : "off");
    }
  },

  _makeButton: function (x, y, label, onClick, w, h){
    w = w || 160;
    h = h || 44;

    var node = new cc.Node();
    node.setPosition(x,y);
    node.setContentSize(w,h);

    // Fallback color background (used only when no texture is available).
    var fallbackBg = new cc.LayerColor(cc.color(30,44,80,220), w, h);
    if (fallbackBg.setIgnoreAnchorPointForPosition) fallbackBg.setIgnoreAnchorPointForPosition(false);
    fallbackBg.setPosition(-w/2, -h/2);
    node.addChild(fallbackBg);
    node._fallbackBg = fallbackBg;

    // Real texture target for stateful button images.
    var bg = new cc.Sprite();
    bg.setPosition(0, 0);
    node.addChild(bg, 1);
    node._bg = bg;

    var txt = new cc.LabelTTF(label, "Arial", Math.max(14, Math.floor(h*0.40)));
    txt.setPosition(0,0);
    node.addChild(txt);
    node._label = txt;

    cc.eventManager.addListener({
      event: cc.EventListener.TOUCH_ONE_BY_ONE,
      swallowTouches: true,
      onTouchBegan: function(t){
        if (!node.isVisible || !node.isVisible()) return false;
        if (node._disabled) return false;
        var p = node.convertToNodeSpace(t.getLocation());
        var s = node.getContentSize();
        var r = cc.rect(-s.width/2, -s.height/2, s.width, s.height);
        var hit = cc.rectContainsPoint(r, p);
        if (hit && node._setState) node._setState("on");
        return hit;
      },
      onTouchEnded: function(){
        if (node._setState) node._setState(node._disabled ? "off" : "normal");
        if (onClick && !node._disabled) onClick();
      },
      onTouchCancelled: function(){
        if (node._setState) node._setState(node._disabled ? "off" : "normal");
      }
    }, node);

    // Desktop hover support: show "on" state when mouse pointer is over button.
    if (cc.EventListener && cc.EventListener.MOUSE) {
      cc.eventManager.addListener({
        event: cc.EventListener.MOUSE,
        onMouseMove: function(e){
          if (!node.isVisible || !node.isVisible()) return;
          var p = node.convertToNodeSpace(e.getLocation());
          var s = node.getContentSize();
          var r = cc.rect(-s.width/2, -s.height/2, s.width, s.height);
          var hit = cc.rectContainsPoint(r, p);
          if (!node._disabled && hit) {
            if (node._setState) node._setState("on");
          } else {
            if (node._setState) node._setState(node._disabled ? "off" : "normal");
          }
        }
      }, node);
    }

    return node;
  },

  // ---------------- Grid ----------------

  _clearGridLayer: function(){
    if (!this.gridLayer) return;
    this.gridLayer.removeAllChildren(true);
    this.cellFrames = [];
    this.symbolCells = [];
    this.reelStrips = [];
  },

  _rebuildGrid: function(){
    this._clearGridLayer();
    this._buildGrid();
  },

  _buildGrid: function(){
    var reels = SlotModel.cfg.math.reel_count;
    var rows  = SlotModel.cfg.math.row_count;

    // Layout that stays aligned for any 3..7 reels and 3..6 rows
    var cellW = 132;
    var cellH = 102;

    // auto-fit keeps grid clear of bottom controls
    if (rows >= 4) cellH = 92;
    if (rows >= 5) cellH = 82;
    if (rows >= 6) cellH = 74;

    var frameW = Math.floor(cellW * 0.9);
    var frameH = Math.floor(cellH * 0.86);

    var startX = 480 - ((reels - 1) * cellW) / 2;
    var startY = 324 - ((rows - 1) * cellH) / 2;

    this._cellW = cellW;
    this._cellH = cellH;
    this._startX = startX;
    this._startY = startY;

    this.symbolCells = [];
    this.cellFrames = [];
    for (var r=0;r<rows;r++){
      this.symbolCells.push(new Array(reels));
      this.cellFrames.push(new Array(reels));
    }

    // No big grid plate (you asked to remove grid background)
    for (var c=0;c<reels;c++){
      for (var rr=0; rr<rows; rr++){
        var x = startX + c*cellW;
        var y = startY + (rows - 1 - rr)*cellH;

        var holder = new cc.Node();
        holder.setPosition(x,y);
        this.gridLayer.addChild(holder, 5);

        // Keep slots fully transparent so selected background is clean (no matrix overlay).
        var framePath = this._uiAsset(["reel_frame","frame_reel","reels_frame"]);
        var frame = null;
        if (framePath) {
          frame = new cc.Sprite(framePath);
          frame.setPosition(0, 0);
          this._fitSpriteTo(frame, Math.floor(frameW * 1.05), Math.floor(frameH * 1.05), false);
          holder.addChild(frame, 12);
        } else {
          frame = new cc.LayerColor(cc.color(18,26,48,0), frameW, frameH);
          if (frame.setIgnoreAnchorPointForPosition) frame.setIgnoreAnchorPointForPosition(false);
          frame.setPosition(-frameW/2, -frameH/2);
          holder.addChild(frame, 1);
        }

        var label = new cc.LabelTTF("?", "Arial", 20);
        label.setPosition(0,0);
        holder.addChild(label, 10);

        this.cellFrames[rr][c] = frame;
        this.symbolCells[rr][c] = { holder: holder, node: label, kind: "label" };
      }
    }

    // Ribbon strips overlay
    this.reelStrips = [];
    this._spinOffsets = new Array(reels);
    this._spinLocked  = new Array(reels);
    this._spinStopTimes = new Array(reels);

    for (var c2=0;c2<reels;c2++){
      var stripNode = new cc.Node();
      stripNode.setPosition(startX + c2*cellW, startY);
      this.gridLayer.addChild(stripNode, 20);

      var sprites = [];
      for (var i=0;i<rows+2;i++){
        var sp = new cc.Sprite();
        sp.setPosition(0, (rows - i) * cellH);
        stripNode.addChild(sp, 5);
        sp.setVisible(false);
        sprites.push(sp);
      }

      this.reelStrips.push({ node: stripNode, sprites: sprites, cellH: cellH, rows: rows });
      this._spinOffsets[c2] = 0;
      this._spinLocked[c2] = false;
      this._spinStopTimes[c2] = 0;
    }
  },

  _renderInitialGrid: function(){
    this._setMessage(I18N.t("ready","Ready"));
    this._renderGrid(this._randomGrid());
  },

  _randomGrid: function(){
    var reels = SlotModel.cfg.math.reel_count;
    var rows  = SlotModel.cfg.math.row_count;

    var ids = [];
    for (var k in SlotModel.math.symbols) ids.push(k);
    if (!ids.length) ids = ["A","K","Q","J","10","9","WILD","SCAT"];

    var grid = [];
    for (var r=0;r<rows;r++){
      var row = [];
      for (var c=0;c<reels;c++) row.push(ids[Math.floor(Math.random()*ids.length)]);
      grid.push(row);
    }
    return grid;
  },

  _renderGrid: function(grid){
    var reels = SlotModel.cfg.math.reel_count;
    var rows  = SlotModel.cfg.math.row_count;
    for (var r=0;r<rows;r++){
      for (var c=0;c<reels;c++){
        this._setSymbol(r, c, grid[r][c]);
      }
    }
  },

  _setSymbol: function(row, reel, symId){
    if (!this.symbolCells || !this.symbolCells[row] || !this.symbolCells[row][reel]) return;
    var cell = this.symbolCells[row][reel];

    var symMap = (SlotModel.assets && SlotModel.assets.symbols) ? SlotModel.assets.symbols : {};
    var fn = symMap ? symMap[symId] : null;
    if (!fn && typeof symId === "string") fn = symMap[symId.toUpperCase()] || symMap[symId.toLowerCase()] || null;
    if (!fn && typeof symId === "string" && (/\.(png|jpg|jpeg|webp)$/i.test(symId))) fn = symId;

    if (fn) {
      var texPath = "res/assets/symbols/" + fn;
      var targetW = 90, targetH = 64;

      if (cell.kind === "label") {
        cell.node.removeFromParent(true);
        var sp = new cc.Sprite(texPath);
        sp.setPosition(0,0);
        cell.holder.addChild(sp, 10);
        this._fitToBox(sp, targetW, targetH);
        cell.node = sp;
        cell.kind = "sprite";
      } else {
        try { cell.node.setTexture(texPath); this._fitToBox(cell.node, targetW, targetH); } catch(e){}
      }
    } else {
      if (cell.kind === "sprite") {
        cell.node.removeFromParent(true);
        var lbl = new cc.LabelTTF(String(symId), "Arial", 18);
        lbl.setPosition(0,0);
        cell.holder.addChild(lbl, 10);
        cell.node = lbl;
        cell.kind = "label";
      } else {
        cell.node.setString(String(symId));
      }
    }
  },

  // ---------------- Gameplay ----------------

  _refreshUI: function(){
    var reels = SlotModel.cfg.math.reel_count || 5;
    var rows  = SlotModel.cfg.math.row_count || 4;

    this.ui.balance.setString(I18N.t("balance","Balance") + ": " + SlotModel.state.balance.toFixed(2));
    this.ui.bet.setString(
      I18N.t("bet","Bet") + ": " + SlotModel.totalBet().toFixed(2) +
      "  (Lvl " + ((SlotModel.state.betIndex||0)+1) + "/" + ((SlotModel.cfg.math.bet_levels||[1]).length) + " = x" + SlotModel.betLevel() + ")" +
      "  [" + reels + "x" + rows + "]"
    );

    if (SlotModel.state.inFreeSpins && SlotModel.state.freeSpins > 0) {
      this.ui.fs.setString(I18N.t("free_spins","Free Spins") + ": " + SlotModel.state.freeSpins);
    } else if ((this._autoRemaining||0) > 0) {
      this.ui.fs.setString("AUTO: " + this._autoRemaining + " (" + String(this._spinMode||"normal").toUpperCase() + ")");
    } else {
      this.ui.fs.setString("");
    }

    var pls = SlotModel.paylines || [];
    var title = "Paylines: " + pls.length;
    this._updateBetBtnVisibility();
    this._updateAutoPanelLabel();

    if (this._showAllPaylines && pls.length) {
      var lines = [];
      for (var i=0; i<pls.length && i<12; i++) lines.push("L" + (i+1) + " " + pls[i].join("-"));
      this.ui.paylineInfo.setString(title + "\n" + lines.join("\n"));
    } else {
      this.ui.paylineInfo.setString(title + "\n(Tap PAYLINES to expand)");
    }
  },

  _setMessage: function(txt){
    if (this.ui && this.ui.msg) this.ui.msg.setString(txt || "");
  },

  _formatWinBreakdown: function(wins){
    if (!wins || !wins.length) return I18N.t("no_line_wins", "No line wins");
    var out = [];
    for (var i=0; i<wins.length; i++){
      var w = wins[i];
      if (!w || w.type !== "line") continue;
      out.push("L" + (w.lineIndex + 1) + ": " + w.amount.toFixed(2));
      if (out.length >= 6) break;
    }
    return out.length ? out.join("\n") : I18N.t("no_line_wins", "No line wins");
  },

  _showFreeSpinIntro: function(done){
    var banner = new cc.LabelTTF("FREE SPINS BONUS!", "Arial", 44);
    banner.setPosition(480, 300);
    banner.setColor(cc.color(255, 215, 0));
    banner.setOpacity(0);
    this.uiLayer.addChild(banner, 1200);

    var fadeIn = cc.fadeIn(0.18);
    var hold = cc.delayTime(0.65);
    var pulse = cc.sequence(cc.scaleTo(0.20, 1.08), cc.scaleTo(0.16, 1.0));
    var fadeOut = cc.fadeOut(0.25);
    var remove = cc.callFunc(function(){ banner.removeFromParent(true); if (done) done(); });
    banner.runAction(cc.sequence(fadeIn, cc.spawn(hold, pulse), fadeOut, remove));
  },

  _onSpin: function(){
    var self = this;
    if (this.busy) return;

    this.lineDraw.clear();
    this._setMessage("");

    var beforeFS = (SlotModel.state && SlotModel.state.inFreeSpins) ? (SlotModel.state.freeSpins || 0) : 0;
    var wasInFS = !!(SlotModel.state && SlotModel.state.inFreeSpins && SlotModel.state.freeSpins > 0);

    // Stop previous long win cue as soon as player starts the next spin.
    try { Audio.stopWin(); } catch (e1) {}

    var res = SlotModel.spin();
    if (res.error) {
      if (res.error === "NO_BALANCE") this._setMessage(I18N.t("no_balance","Not enough balance"));
      return;
    }

    this.busy = true;
    this._forceStopRequested = false;
    this._setSpinButtonsState(true);
    this._refreshControlStates();

    if (!this._muted) { try { Audio.play("spin"); } catch(e){} }

    var spinSec = 2.8;
    if (this._spinMode === "quick") spinSec = 1.8;
    if (this._spinMode === "turbo") spinSec = 1.2;

    // Spin then land exactly on res.grid (no symbol swapping after stop)
    this._startSpinAnimation(spinSec, res.grid, function(){
      try {
      self._renderGrid(res.grid);

      var fsStarted = (!res.inFreeSpins && res.freeSpinsRemaining > 0);
      var fsEnded = (res.inFreeSpins && res.freeSpinsRemaining <= 0);
      var expectedNoAward = wasInFS ? Math.max(0, beforeFS - 1) : 0;
      var fsAwarded = Math.max(0, (res.freeSpinsRemaining || 0) - expectedNoAward);

      if (!self._muted && fsStarted) {
        try { Audio.play("freespin"); } catch(e0){}
      }

      // Keep free-spin audio continuous through all FS rounds.
      if (res.freeSpinsRemaining > 0) {
        try { Audio.startFreeSpinLoop(); } catch(eFS1){}
      }

      if (!self._muted && ((res.wins && res.wins.length) || (res.scatter && res.scatter.amount > 0))) {
        try { Audio.play("win"); } catch(e2){}
      }

      if (!self._muted && fsEnded) {
        // Reuse freespin event as "feature finished" cue when dedicated end audio is not provided.
        try { Audio.play("freespin"); } catch(e3){}
      }
      if (fsEnded || res.freeSpinsRemaining <= 0) {
        try { Audio.stopFreeSpinLoop(); } catch(eFS2){}
      }

      self._drawWinLines(res.wins);
      if (self.ui && self.ui.winBreakdown) self.ui.winBreakdown.setString(self._formatWinBreakdown(res.wins));

      var msgParts = [];
      if (res.totalWin > 0) msgParts.push(I18N.t("win","Win") + ": " + res.totalWin.toFixed(2));
      if (res.scatter && res.scatter.count >= 3) msgParts.push(I18N.t("scatter","Scatter") + " x" + res.scatter.count);
      if (res.freeSpinsRemaining > 0) msgParts.push(I18N.t("fs_left","FS Left") + ": " + res.freeSpinsRemaining);
      if (!msgParts.length) msgParts.push(I18N.t("lose","No win"));

      self._setMessage(msgParts.join(" | "));
      self._refreshUI();

      var releaseBusy = function(){ self.busy = false; self._setSpinButtonsState(false); self._refreshControlStates(); };
      if (typeof self.scheduleOnce === "function") self.scheduleOnce(releaseBusy, 0.2);
      else setTimeout(releaseBusy, 200);

      // Auto-play remaining free spins + optional user-selected autoplay count.
      var hasFeatureAuto = (res.freeSpinsRemaining > 0);
      var hasUserAuto = ((self._autoRemaining || 0) > 0);
      if (hasFeatureAuto || hasUserAuto) {
        var autoNext = function(){
          if (self.busy) return;
          var stillFeature = (SlotModel.state && SlotModel.state.inFreeSpins && SlotModel.state.freeSpins > 0);
          var stillUser = ((self._autoRemaining || 0) > 0);
          if (!stillFeature && !stillUser) return;
          self._onSpin();
        };

        var queueAutoSpin = function(delaySec){
          if (typeof self.scheduleOnce === "function") self.scheduleOnce(autoNext, delaySec);
          else setTimeout(autoNext, Math.floor(delaySec * 1000));
        };

        if (!hasFeatureAuto && (self._autoRemaining || 0) > 0) self._autoRemaining = Math.max(0, (self._autoRemaining || 0) - 1);
        if ((self._autoRemaining || 0) <= 0 && self.ui && self.ui.autoStopButton) self.ui.autoStopButton.setVisible(false);

        if (fsAwarded > 0) self._showFreeSpinIntro(function(){ queueAutoSpin(0.20); });
        else queueAutoSpin(self._spinMode === "turbo" ? 0.12 : 0.25);
      }
      } catch (spinErr) {
        self._setMessage("Spin flow recovered");
        self.busy = false;
        self._spinActive = false;
        self._setSpinButtonsState(false);
        self._refreshControlStates();
      }
    });
  },

  // ======== FIXED RIBBON SPIN ========
  // - Reels spin in place (same vertical axis)
  // - No overlap / disappearing symbols
  // - Each reel lands deterministically on finalGrid for ALL rows
  _startSpinAnimation: function(totalSeconds, finalGrid, onDone){
    var self = this;
    var reels = SlotModel.cfg.math.reel_count;
    var rows  = SlotModel.cfg.math.row_count;

    var ids = [];
    for (var k in SlotModel.math.symbols) ids.push(k);
    if (!ids.length) ids = ["A","K","Q","J","10","9","WILD","SCAT"];

    // stagger stops
    for (var c=0;c<reels;c++){
      this._spinStopTimes[c] = totalSeconds * (0.60 + 0.40 * (c / Math.max(1, reels - 1)));
      this._spinOffsets[c] = 0;
      this._spinLocked[c] = false;
    }

    this._spinActive = true;
    this._spinElapsed = 0;

    // hide normal symbols while spinning
    for (var r=0;r<rows;r++){
      for (var c2=0;c2<reels;c2++){
        var cell = this.symbolCells[r][c2];
        if (cell && cell.node) cell.node.setVisible(false);
      }
    }

    // show ribbon sprites
    for (var c3=0;c3<reels;c3++){
      var strip = this.reelStrips[c3];
      for (var i=0;i<strip.sprites.length;i++){
        var sym = ids[Math.floor(Math.random()*ids.length)];
        this._setSpriteSymbol(strip.sprites[i], sym);
        strip.sprites[i].setVisible(true);
        this._applyRibbonLookBySlotIndex(strip.sprites[i], i, rows);
      }
    }

    var cellH = this._cellH || 90;
    var baseSpeed = 620;       // fast spin
    var landWindow = 0.90;     // longer easing window for softer stops
    var clipTop = (rows - 1) * cellH + cellH * 0.55;
    var clipBot = -cellH * 0.55;

    function layoutReel(reelIndex){
      var strip = self.reelStrips[reelIndex];
      var off = self._spinOffsets[reelIndex];

      for (var j=0;j<strip.sprites.length;j++){
        var yLocal = (rows - j) * cellH - off;
        var sp = strip.sprites[j];
        sp.setPosition(0, yLocal);

        self._applyRibbonLookBySlotIndex(sp, j, rows);

        // local clip: only show within the reel window
        sp.setVisible(yLocal <= clipTop && yLocal >= clipBot);
      }
    }

    function rotateOnce(reelIndex){
      var strip = self.reelStrips[reelIndex];
      var sprites = strip.sprites;
      var last = sprites.pop();
      sprites.unshift(last);
      return last;
    }

    var tick = function(dt){
      try {
      if (!self._spinActive) return;
      self._spinElapsed += dt;

      var allStopped = true;

      for (var c=0;c<reels;c++){
        if (self._spinLocked[c]) continue;

        var tStop = self._spinStopTimes[c];
        var timeLeft = tStop - self._spinElapsed;

        if (self._forceStopRequested && timeLeft > 0.22) {
          self._spinStopTimes[c] = self._spinElapsed + 0.10 + 0.05 * c;
          tStop = self._spinStopTimes[c];
          timeLeft = tStop - self._spinElapsed;
        }
        if (timeLeft <= 0) {
          self._spinOffsets[c] = 0;
          layoutReel(c);
          self._spinLocked[c] = true;
          try { if (!self._muted) Audio.play("reel_stop"); } catch(eStop){}
          continue;
        }
        allStopped = false;

        var inLanding = (timeLeft <= landWindow);
        var speed = baseSpeed;
        if (inLanding) {
          var t = Math.max(0, Math.min(1, timeLeft / landWindow)); // 1 -> start of landing, 0 -> final stop
          speed = baseSpeed * (0.14 + 0.86 * t * t * t);           // ease-out cubic
        }

        self._spinOffsets[c] += speed * dt;

        while (self._spinOffsets[c] >= cellH) {
          self._spinOffsets[c] -= cellH;

          // rotate sprites to simulate movement
          var entering = rotateOnce(c);

          if (inLanding) {
            // During landing, keep everything deterministic:
            // entering sprite goes to TOP extra slot (index 0) which visually feeds row 0 next.
            self._setSpriteSymbol(entering, finalGrid[0][c]);
          } else {
            self._setSpriteSymbol(entering, ids[Math.floor(Math.random()*ids.length)]);
          }
          entering.setVisible(true);
        }

        if (inLanding) {
          // Force visible rows to be EXACTLY finalGrid every frame
          var strip2 = self.reelStrips[c];
          // visible row rr corresponds to sprite index rr+1 (because sprites[0] is extra above)
          for (var rr=0; rr<rows; rr++){
            var spv = strip2.sprites[rr + 1];
            self._setSpriteSymbol(spv, finalGrid[rr][c]);
            spv.setVisible(true);
          }
          // extras
          self._setSpriteSymbol(strip2.sprites[0], finalGrid[0][c]);
          self._setSpriteSymbol(strip2.sprites[rows + 1], finalGrid[rows - 1][c]);

          // As we get very close, gently settle into perfect alignment
          if (timeLeft <= 0.16) {
            self._spinOffsets[c] = self._spinOffsets[c] * 0.60;
            if (self._spinOffsets[c] < 0.75) self._spinOffsets[c] = 0;
            layoutReel(c);
            if (self._spinOffsets[c] === 0) {
              self._spinLocked[c] = true;
              try { if (!self._muted) Audio.play("reel_stop"); } catch(e){}
              continue;
            }
          }
        }

        layoutReel(c);
      }

      if (allStopped) {
        self._spinActive = false;
        if (typeof self.unschedule === "function") self.unschedule(tick);

        // hide ribbon sprites
        for (var c4=0;c4<reels;c4++){
          var st = self.reelStrips[c4];
          for (var s=0;s<st.sprites.length;s++) st.sprites[s].setVisible(false);
        }

        // show normal symbols again
        for (var r2=0;r2<rows;r2++){
          for (var c5=0;c5<reels;c5++){
            var cell2 = self.symbolCells[r2][c5];
            if (cell2 && cell2.node) cell2.node.setVisible(true);
          }
        }

        if (onDone) onDone();
      }
      } catch (tickErr) {
        self._spinActive = false;
        if (typeof self.unschedule === "function") self.unschedule(tick);
        self.busy = false;
        self._setSpinButtonsState(false);
        self._refreshControlStates();
        self._setMessage("Recovered from spin error");
      }
    };

    if (typeof this.schedule === "function") this.schedule(tick, 0);
    else {
      var id = setInterval(function(){
        tick(0.016);
        if (!self._spinActive) clearInterval(id);
      }, 16);
    }
  },

  _drawWinLines: function(wins){
    if (!wins || !wins.length) return;

    var reels = SlotModel.cfg.math.reel_count;
    var rows  = SlotModel.cfg.math.row_count;

    var reelW = this._cellW || 120;
    var reelH = this._cellH || 90;
    var startX = this._startX || (480 - ((reels - 1) * reelW) / 2);
    var startY = this._startY || 290;

    for (var i=0;i<wins.length;i++){
      var w = wins[i];
      if (w.type !== "line") continue;

      var pts = [];
      for (var r=0;r<reels;r++){
        var rowIndex = w.path[r];
        var x = startX + r * reelW;
        var y = startY + (rows - 1 - rowIndex) * reelH;
        pts.push(cc.p(x,y));
      }

      for (var k=0;k<pts.length-1;k++){
        this.lineDraw.drawSegment(pts[k], pts[k+1], 2, cc.color(255,215,0,255));
      }
    }
  }
});
"""

def _resources_js(preload: List[str]) -> str:
    preload = [p for p in preload if p]
    return "var g_resources = [];\n" + "g_resources = g_resources.concat(" + json.dumps(preload, indent=2) + ");\n"

def _project_json(js_list: List[str]) -> dict:
    return {
        "project_type": "javascript",
        "debugMode": 1,
        "showFPS": True,
        "frameRate": 60,
        "id": "gameCanvas",
        "tag": "gameCanvas",
        "renderMode": 0,
        "engineDir": "frameworks/cocos2d-html5/",
        "modules": ["core", "actions", "audio"],
        "jsList": js_list,
    }

def _build_asset_manifest(
    symbol_files: List[str],
    ui_files: List[str],
    audio_files: List[str],
) -> dict:
    # Symbol mapping: file stem => symbol id (uppercase)
    symbols: Dict[str, str] = {}
    for fn in symbol_files:
        stem = Path(fn).stem.upper()
        symbols[stem] = fn

    # UI mapping: file stem => filename (lowercased key)
    ui_by_stem: Dict[str, str] = {}
    for fn in ui_files:
        stem = Path(fn).stem.lower()
        ui_by_stem[stem] = fn

    # Audio mapping: key is file stem
    audio: Dict[str, str] = {}
    for fn in audio_files:
        key = Path(fn).stem.lower()
        audio[key] = fn

    return {
        "symbols": symbols,
        "ui": ui_files,
        "ui_by_stem": ui_by_stem,
        "audio": audio,
    }

def build_dev_web_zip(
    core_root: Path,
    spec: GameSpec,
    paylines: dict,
    reel_strips: dict,
    paytable: dict,
    symbol_uploads: Optional[List[st.runtime.uploaded_file_manager.UploadedFile]] = None,
    ui_uploads: Optional[List[st.runtime.uploaded_file_manager.UploadedFile]] = None,
    audio_uploads: Optional[List[st.runtime.uploaded_file_manager.UploadedFile]] = None,
    help_texts: Optional[dict] = None,
    background_upload: Optional[st.runtime.uploaded_file_manager.UploadedFile] = None,
    symbol_uploads_named: Optional[List[Tuple[st.runtime.uploaded_file_manager.UploadedFile, str]]] = None,
    audio_uploads_named: Optional[List[Tuple[st.runtime.uploaded_file_manager.UploadedFile, str]]] = None,
    math_pool_zip: Optional[bytes] = None,
    dashboard_assets_root: Optional[Path] = None,
    dashboard_assets_required: bool = False,
) -> bytes:
    """Build a runnable Cocos2d-HTML5 web build zip."""
    required_core_files = [
        core_root / "frameworks" / "cocos2d-html5" / "CCBoot.js",
        core_root / "frameworks" / "cocos2d-html5" / "cocos2d" / "core" / "platform" / "CCClass.js",
        core_root / "frameworks" / "cocos2d-html5" / "cocos2d" / "core" / "renderer" / "RendererWebGL.js",
    ]
    missing_core = [str(p) for p in required_core_files if not p.exists()]
    if missing_core:
        raise FileNotFoundError(
            "PongGameCore is incomplete for HTML5 build. Missing required engine files:\n- " + "\n- ".join(missing_core) +
            "\n\nPlease set a full PongGameCore root that contains frameworks/cocos2d-html5/cocos2d/core."
        )

    tmp = Path(tempfile.mkdtemp(prefix="slotmaker_"))
    try:
        web = tmp / "web_build"
        ensure_dir(web)

        # Copy frameworks
        copy_tree(core_root / "frameworks", web / "frameworks")

        js_list = [
            "src/compat.js",
            "src/resources.js",
            "src/engine/rng.js",
            "src/engine/audio.js",
            "src/engine/i18n.js",
            "src/engine/slot_math.js",
            "src/engine/slot_model.js",
            "src/scenes/slot_scene.js",
            "main.js",
        ]

        write_text(web / "index.html", _INDEX_HTML.replace("__JS_LIST__", json.dumps(js_list)).replace("__GAME_TITLE__", spec.identity.display_name))
        write_text(web / "src" / "compat.js", COMPAT_JS)
        write_text(web / "main.js", _MAIN_JS)
        write_text(web / "run_local.py", _RUN_LOCAL_PY)
        write_text(web / "Run_Game.bat", _RUN_GAME_BAT)

        # Structure
        ensure_dir(web / "src" / "engine")
        ensure_dir(web / "src" / "scenes")
        ensure_dir(web / "res" / "conf")
        ensure_dir(web / "res" / "assets" / "symbols")
        ensure_dir(web / "res" / "assets" / "backgrounds")
        ensure_dir(web / "res" / "res" / "assets" / "ui")  # harmless legacy
        ensure_dir(web / "res" / "assets" / "ui")
        ensure_dir(web / "res" / "assets" / "audio")
        ensure_dir(web / "res" / "i18n")

        # Symbols
        if symbol_uploads_named:
            sym_files = copy_uploaded_files_named(symbol_uploads_named, web / "res" / "assets" / "symbols")
        else:
            sym_files = copy_uploaded_files(symbol_uploads or [], web / "res" / "assets" / "symbols")

        # UI images
        ui_files = copy_uploaded_files(ui_uploads or [], web / "res" / "assets" / "ui")

        # Optional: auto-import shared dashboard UI files from local PGS-Igaming root.
        # Keep dashboard structure in output:
        #   res/assets/ui/dashboard/*.png
        #   res/assets/ui/dashboard/buttons/*.png
        copied_dashboard_count = 0
        if dashboard_assets_root:
            dash_root = Path(dashboard_assets_root)
            buttons_dir = dash_root / "buttons"
            wanted_stems = [
                "bet_popup_panel", "popup_panel_bg",
                "btn_spin", "btn_spin_on", "btn_spin_off",
                "btn_stop", "btn_stop_on", "btn_stop_off",
                "btn_bet", "btn_bet_on", "btn_bet_off",
                "btn_bet_plus", "btn_bet_plus_on", "btn_bet_plus_off",
                "btn_bet_minus", "btn_bet_minus_on", "btn_bet_minus_off",
                "btn_bet_max",
                "btn_auto", "btn_auto_on", "btn_auto_off",
                "btn_auto_active",
                "btn_auto_spin", "btn_auto_spin_on", "btn_auto_spin_off",
                "btn_auto_amt", "btn_auto_amt_on",
                "btn_menu_close", "btn_menu_close_on", "btn_menu_close_off",
                "btn_close_on_menu",
                "btn_back", "btn_back_on",
                "btn_quick_on", "btn_quick_off",
                "btn_turbo", "btn_turbo_off",
                "btn_speed_quick", "btn_speed_quick_on",
                "btn_speed_turbo", "btn_speed_turbo_on",
            ]
            allowed_ext = {".png", ".webp", ".jpg", ".jpeg"}

            # Build a case-insensitive candidate map and preserve which source folder supplied the file.
            # Prefer buttons/ over dashboard root when stems overlap.
            candidates: Dict[str, Tuple[Path, str]] = {}
            for src_dir, source_kind in [(buttons_dir, "buttons"), (dash_root, "dashboard")]:
                if not src_dir.exists() or not src_dir.is_dir():
                    continue
                for f in src_dir.iterdir():
                    if not f.is_file():
                        continue
                    ext = f.suffix.lower()
                    if ext not in allowed_ext:
                        continue
                    candidates.setdefault(f.stem.lower(), (f, source_kind))

            ensure_dir(web / "res" / "assets" / "ui" / "dashboard")
            ensure_dir(web / "res" / "assets" / "ui" / "dashboard" / "buttons")
            existing = set(ui_files)
            for stem in wanted_stems:
                found = candidates.get(stem)
                if found:
                    src, source_kind = found
                    ext = src.suffix.lower()
                    dst_rel = f"dashboard/buttons/{stem}.png" if source_kind == "buttons" else f"dashboard/{stem}.png"
                    dst = web / "res" / "assets" / "ui" / dst_rel

                    if ext == ".png":
                        copy_file(src, dst)
                    else:
                        try:
                            with Image.open(src) as im:
                                im.save(dst, format="PNG")
                        except Exception:
                            # Fallback: keep original bytes/name if conversion fails.
                            dst_rel = f"dashboard/buttons/{stem}{ext}" if source_kind == "buttons" else f"dashboard/{stem}{ext}"
                            dst = web / "res" / "assets" / "ui" / dst_rel
                            copy_file(src, dst)

                    if dst_rel not in existing:
                        ui_files.append(dst_rel)
                        existing.add(dst_rel)
                    copied_dashboard_count += 1

            if dashboard_assets_required and copied_dashboard_count == 0:
                raise FileNotFoundError(
                    f"Dashboard assets were requested but no supported UI images were found under: {dash_root} or {buttons_dir}. "
                    "Expected stems like btn_spin / btn_bet / btn_auto with extensions .png/.webp/.jpg/.jpeg."
                )

        # Background
        bg_file = None
        if background_upload:
            ext = os.path.splitext(getattr(background_upload, "name", "") or "")[1].lower() or ".png"
            bg_file = f"background{ext}"
            copy_uploaded_files_named([(background_upload, bg_file)], web / "res" / "assets" / "backgrounds")

        # Audio
        if audio_uploads_named:
            aud_files = copy_uploaded_files_named(audio_uploads_named, web / "res" / "assets" / "audio")
        else:
            aud_files = copy_uploaded_files(audio_uploads or [], web / "res" / "assets" / "audio")

        assets_manifest = _build_asset_manifest(sym_files, ui_files, aud_files)
        if bg_file:
            assets_manifest["background"] = bg_file
            assets_manifest["bg"] = bg_file
        write_json(web / "res" / "assets_manifest.json", assets_manifest)

        # Config
        cfg = {
            "identity": {
                "game_id": spec.identity.game_id,
                "internal_name": spec.identity.internal_name,
                "display_name": spec.identity.display_name,
                "version": spec.identity.version,
            },
            "jurisdiction": {
                "jurisdiction": spec.jurisdiction.jurisdiction,
                "profile_id": spec.jurisdiction.profile_id,
                "currencies": spec.jurisdiction.currencies,
                "selection_method": spec.jurisdiction.selection_method,
                "replacement_policy": spec.jurisdiction.replacement_policy,
            },
            "localization": {
                "languages": spec.localization.languages,
                "help_texts": help_texts or spec.localization.help_texts,
            },
            "math": {
                # Your wizard already sets these. In-game UI can override too.
                "reel_count": spec.math.reel_count,
                "row_count": spec.math.row_count,
                "payline_count": spec.math.payline_count,
                "denomination": spec.math.denomination,
                "coins_per_line": spec.math.coins_per_line,
                "bet_levels": spec.math.bet_levels,
                "max_win_multiplier": spec.math.max_win_multiplier,
                "special": {
                    "wild": next((s.id for s in spec.math.symbols if s.is_wild), "WILD"),
                    "scatter": next((s.id for s in spec.math.symbols if s.is_scatter), "SCAT"),
                },
                "features": {
                    "free_spins_award": spec.math.features.free_spins_award,
                    "free_spins_multiplier": spec.math.features.free_spins_multiplier,
                    "jackpot_enabled": spec.math.features.jackpot_enabled,
                    "jackpot_trigger": spec.math.features.jackpot_trigger,
                    "autoplay_enabled": spec.math.features.autoplay_enabled,
                },
            },
        }
        write_json(web / "res" / "config.json", cfg)

        # i18n
        en = {
            "spin": "SPIN",
            "balance": "Balance",
            "bet": "Bet",
            "win": "Win",
            "scatter": "Scatter",
            "free_spins": "Free Spins",
            "fs_left": "FS Left",
            "ready": "Ready",
            "no_balance": "Not enough balance",
            "lose": "No win",
        }
        write_json(web / "res" / "i18n" / "en.json", en)

        # Math content
        write_json(web / "res" / "conf" / "paylines.json", paylines)
        write_json(web / "res" / "conf" / "reel_strips.json", reel_strips)
        write_json(web / "res" / "conf" / "paytable.json", paytable)
        if math_pool_zip:
            write_bytes(web / "res" / "conf" / "math_pool.zip", math_pool_zip)

        symbols_dict = {
            s.id: {"name": s.name, "is_wild": s.is_wild, "is_scatter": s.is_scatter, "is_bonus": s.is_bonus}
            for s in spec.math.symbols
        }
        write_json(web / "res" / "conf" / "symbols.json", symbols_dict)

        # Engine JS
        write_text(web / "src" / "engine" / "rng.js", _ENGINE_RNG)
        write_text(web / "src" / "engine" / "audio.js", _ENGINE_AUDIO)
        write_text(web / "src" / "engine" / "i18n.js", _ENGINE_I18N)
        write_text(web / "src" / "engine" / "slot_math.js", _ENGINE_SLOT_MATH)
        write_text(web / "src" / "engine" / "slot_model.js", _ENGINE_SLOT_MODEL)

        # Scene JS
        write_text(web / "src" / "scenes" / "slot_scene.js", _SCENE_SLOT)

        # resources.js + project.json
        preload = [
            "res/config.json",
            "res/assets_manifest.json",
            "res/conf/paylines.json",
            "res/conf/reel_strips.json",
            "res/conf/paytable.json",
            "res/conf/symbols.json",
            "res/i18n/en.json",
        ]
        for _, fn in (assets_manifest.get("symbols") or {}).items():
            preload.append(f"res/assets/symbols/{fn}")
        for fn in (assets_manifest.get("ui") or []):
            preload.append(f"res/assets/ui/{fn}")
        for _, fn in (assets_manifest.get("audio") or {}).items():
            preload.append(f"res/assets/audio/{fn}")
        if assets_manifest.get("background"):
            preload.append(f"res/assets/backgrounds/{assets_manifest['background']}")
        if math_pool_zip:
            preload.append("res/conf/math_pool.zip")

        write_text(web / "src" / "resources.js", _resources_js(preload))
        write_json(web / "project.json", _project_json(js_list))

        # Zip
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in web.rglob("*"):
                if p.is_file():
                    z.write(p, p.relative_to(web).as_posix())
        return buf.getvalue()

    finally:
        try:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:
            pass
