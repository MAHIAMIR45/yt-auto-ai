import os
import json
import re
import threading
from datetime import datetime, timezone, timedelta
from flask import Flask, render_template_string, jsonify, request, send_from_directory

app = Flask(__name__)
OUTPUT_DIR = "output"
DB_PATH = "data/trends_db.json"
EST_OFFSET = timedelta(hours=-5)

_trending_cache = []
_trending_lock = threading.Lock()


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<meta name="theme-color" content="#0a0a12">
<title>🎬 YT Shorts AI Producer</title>
<style>
/* ── RESET & BASE ── */
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html{font-size:16px}
body{background:#0a0a12;color:#e2e8f0;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;min-height:100vh;padding-bottom:72px}
a{text-decoration:none;color:inherit}
img,video{display:block;max-width:100%}
button{cursor:pointer;font-family:inherit}
input,select,textarea{font-family:inherit}
::-webkit-scrollbar{width:4px;height:4px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#2d2d4e;border-radius:4px}

/* ── CSS VARIABLES ── */
:root{
  --red:#e94560;--red2:#ff1744;
  --green:#10b981;--blue:#60a5fa;
  --purple:#a78bfa;--gold:#fbbf24;
  --bg0:#0a0a12;--bg1:#0f0f1a;
  --bg2:#141420;--bg3:#1a1a2e;
  --border:#1f2937;--border2:#2d2d4e;
  --text:#e2e8f0;--muted:#6b7280;--muted2:#9ca3af;
  --radius:12px;--radius-sm:8px;
  --shadow:0 4px 24px rgba(0,0,0,.4);
}

/* ── HEADER ── */
.header{
  background:linear-gradient(135deg,#0f0f1a 0%,#141428 100%);
  border-bottom:1px solid var(--border2);
  padding:0 16px;height:56px;
  display:flex;align-items:center;gap:12px;
  position:sticky;top:0;z-index:200;
}
.logo{display:flex;align-items:center;gap:8px;flex:1;min-width:0}
.logo-icon{font-size:1.4rem;flex-shrink:0}
.logo-text{font-size:1rem;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.logo-sub{font-size:0.6rem;color:var(--muted);display:none}
.header-meta{display:flex;align-items:center;gap:8px;flex-shrink:0}
.countdown-pill{background:var(--bg3);border:1px solid var(--border2);border-radius:20px;padding:5px 12px;text-align:center}
.countdown-num{font-size:0.85rem;font-weight:700;color:var(--gold);font-variant-numeric:tabular-nums;line-height:1}
.countdown-lbl{font-size:0.5rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px}
.pilot-btn{display:flex;align-items:center;gap:6px;background:var(--bg3);border:1px solid var(--border2);border-radius:20px;padding:6px 12px;transition:.2s}
.pilot-btn:hover{border-color:var(--green)}
.pilot-dot-sm{width:7px;height:7px;border-radius:50%;background:var(--muted);transition:.3s;flex-shrink:0}
.pilot-dot-sm.on{background:var(--green);box-shadow:0 0 6px var(--green);animation:glow 2s infinite}
.pilot-txt{font-size:0.72rem;font-weight:700;color:var(--muted2)}
.pilot-txt.on{color:var(--green)}
@keyframes glow{0%,100%{opacity:1}50%{opacity:.5}}

/* ── STATS BAR ── */
.stats-scroll{overflow-x:auto;background:var(--bg1);border-bottom:1px solid var(--border);display:flex;-webkit-overflow-scrolling:touch;scrollbar-width:none}
.stats-scroll::-webkit-scrollbar{display:none}
.stat-chip{flex:0 0 auto;padding:10px 16px;display:flex;flex-direction:column;align-items:center;border-right:1px solid var(--border);min-width:80px}
.stat-chip:last-child{border-right:none}
.stat-n{font-size:1.2rem;font-weight:800;color:var(--red);line-height:1}
.stat-n.g{color:var(--green)}.stat-n.b{color:var(--blue)}.stat-n.p{color:var(--purple)}.stat-n.gold{color:var(--gold)}
.stat-l{font-size:0.55rem;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-top:3px;white-space:nowrap}

/* ── DESKTOP TOP TABS ── */
.top-tabs{display:none;background:var(--bg1);border-bottom:1px solid var(--border);padding:0 16px;gap:0;overflow-x:auto}
.top-tab{padding:13px 16px;cursor:pointer;font-size:0.78rem;font-weight:600;color:var(--muted);border-bottom:2px solid transparent;transition:.2s;white-space:nowrap;flex-shrink:0}
.top-tab:hover{color:var(--text)}
.top-tab.active{color:var(--red);border-bottom-color:var(--red)}

/* ── MOBILE BOTTOM NAV ── */
.bottom-nav{
  position:fixed;bottom:0;left:0;right:0;
  background:var(--bg2);border-top:1px solid var(--border2);
  display:flex;z-index:200;
  padding-bottom:env(safe-area-inset-bottom);
}
.bnav-item{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:10px 4px;cursor:pointer;transition:.15s;border:none;background:none;color:var(--muted);gap:3px}
.bnav-item.active{color:var(--red)}
.bnav-icon{font-size:1.2rem;line-height:1}
.bnav-lbl{font-size:0.52rem;font-weight:600;text-transform:uppercase;letter-spacing:.5px}

/* ── TAB CONTENT ── */
.tab-body{display:none;padding:16px}
.tab-body.active{display:block}

/* ── PANELS ── */
.panel{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);padding:16px;margin-bottom:16px}
.panel-hd{font-size:0.65rem;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:2px;margin-bottom:14px;display:flex;align-items:center;gap:6px}
.panel-hd .ico{font-size:.9rem}

/* ── GRIDS ── */
.grid-2{display:grid;grid-template-columns:1fr;gap:16px}
.cards-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:12px}

/* ── AUTO-PILOT ── */
.ap-status{display:flex;align-items:center;gap:10px;padding:12px 14px;border-radius:var(--radius-sm);margin-bottom:12px}
.ap-status.running{background:rgba(16,185,129,.07);border:1px solid rgba(16,185,129,.2)}
.ap-status.stopped{background:rgba(255,255,255,.03);border:1px solid var(--border)}
.ap-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.ap-dot.running{background:var(--green);box-shadow:0 0 8px var(--green);animation:glow 2s infinite}
.ap-dot.stopped{background:var(--muted)}
.ap-msg{flex:1;font-size:0.82rem;color:var(--text)}
.next-plan{background:linear-gradient(135deg,rgba(167,139,250,.06),rgba(96,165,250,.06));border:1px solid rgba(167,139,250,.15);border-radius:var(--radius-sm);padding:14px;margin-bottom:12px}
.next-plan-lbl{font-size:0.6rem;color:var(--purple);text-transform:uppercase;letter-spacing:2px;margin-bottom:5px}
.next-plan-txt{font-size:0.82rem;color:var(--text);line-height:1.5}

/* ── LOG ── */
.log-box{background:var(--bg0);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;max-height:220px;overflow-y:auto;font-family:monospace;font-size:0.7rem}
.log-row{padding:3px 0;border-bottom:1px solid rgba(255,255,255,.03);display:flex;gap:8px;align-items:flex-start}
.log-t{color:#374151;flex-shrink:0;font-size:.65rem;padding-top:1px}
.log-m{color:var(--muted2);line-height:1.4;word-break:break-word}
.log-m.ok{color:var(--green)}.log-m.err{color:#ef4444}.log-m.info{color:var(--blue)}

/* ── SCHEDULE ── */
.sched-row{display:flex;align-items:center;gap:8px;padding:10px 0;border-bottom:1px solid var(--border)}
.sched-row:last-child{border:none}
.sched-time-box{text-align:center;min-width:72px}
.sched-time-lbl{font-size:.55rem;color:var(--muted);text-transform:uppercase}
.sched-time-val{font-size:.9rem;font-weight:700}
.sched-arr{color:var(--muted);font-size:.75rem;flex-shrink:0}
.badge{font-size:.6rem;font-weight:700;padding:3px 9px;border-radius:20px;flex-shrink:0}
.badge.done{background:rgba(16,185,129,.1);color:var(--green);border:1px solid rgba(16,185,129,.2)}
.badge.active{background:rgba(251,191,36,.1);color:var(--gold);border:1px solid rgba(251,191,36,.2);animation:glow 2s infinite}
.badge.pending{background:rgba(107,114,128,.1);color:var(--muted);border:1px solid var(--border)}

/* ── TRENDS ── */
.trend-item{background:var(--bg1);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;display:flex;align-items:center;gap:10px;margin-bottom:8px;transition:.2s}
.trend-item:hover{border-color:var(--red)}
.trend-rank{font-size:1.1rem;font-weight:800;color:var(--red);min-width:28px;flex-shrink:0}
.trend-name{flex:1;font-size:.85rem;font-weight:600;word-break:break-word}
.trend-acts{display:flex;gap:5px;flex-shrink:0}

/* ── VIDEO CARDS ── */
.vid-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:.2s}
.vid-card:hover{border-color:var(--red);box-shadow:0 6px 20px rgba(233,69,96,.12)}
.vid-thumb{width:100%;aspect-ratio:9/16;max-height:200px;background:#000;object-fit:cover;cursor:pointer}
.vid-no-thumb{width:100%;aspect-ratio:9/16;max-height:200px;background:var(--bg3);display:flex;align-items:center;justify-content:center;font-size:2rem;color:#374151}
.vid-body{padding:12px}
.vid-topic{font-size:.6rem;color:var(--red);text-transform:uppercase;letter-spacing:1px;margin-bottom:3px}
.vid-title{font-size:.8rem;font-weight:700;color:#fff;line-height:1.3;margin-bottom:8px}
.vid-tags{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}
.vtag{font-size:.58rem;padding:2px 7px;border-radius:10px;font-weight:600}
.vtag.g{background:rgba(16,185,129,.1);color:var(--green)}
.vtag.b{background:rgba(96,165,250,.1);color:var(--blue)}
.vtag.r{background:rgba(239,68,68,.1);color:#ef4444}
.vtag.gold{background:rgba(251,191,36,.1);color:var(--gold)}
.vtag.base{background:var(--bg3);color:var(--muted2)}
.vid-script{background:var(--bg0);border:1px solid var(--border);border-radius:6px;padding:7px;font-size:.68rem;color:var(--muted);line-height:1.5;max-height:52px;overflow:hidden;position:relative;margin-bottom:8px}
.vid-script::after{content:'';position:absolute;bottom:0;left:0;right:0;height:20px;background:linear-gradient(transparent,var(--bg0))}
.vid-acts{display:flex;gap:5px;flex-wrap:wrap}
.yt-link-sm{display:flex;align-items:center;gap:4px;margin-top:5px;color:#ff6b6b;font-size:.7rem}

/* ── BUTTONS ── */
.btn{border:none;border-radius:var(--radius-sm);font-size:.8rem;font-weight:700;padding:10px 16px;transition:.15s;display:inline-flex;align-items:center;justify-content:center;gap:5px;min-height:40px;white-space:nowrap}
.btn:hover{filter:brightness(1.1)}
.btn:disabled{opacity:.5;cursor:not-allowed;filter:none}
.btn:active{transform:scale(.97)}
.btn-red{background:var(--red);color:#fff}
.btn-green{background:var(--green);color:#fff}
.btn-blue{background:var(--blue);color:#000}
.btn-purple{background:var(--purple);color:#000}
.btn-gold{background:var(--gold);color:#000}
.btn-yt{background:#ff0000;color:#fff}
.btn-ghost{background:transparent;border:1px solid var(--border2);color:var(--text)}
.btn-ghost:hover{border-color:var(--red);color:var(--red)}
.btn-sm{padding:6px 12px;font-size:.72rem;min-height:34px}
.btn-xs{padding:4px 9px;font-size:.65rem;min-height:28px;border-radius:6px}
.btn-full{width:100%}

/* ── CHANNEL STATS ── */
.ch-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px}
.ch-box{background:var(--bg1);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;text-align:center}
.ch-n{font-size:1.3rem;font-weight:800;line-height:1}
.ch-l{font-size:.55rem;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;margin-top:3px}

/* ── FORM ── */
.input{width:100%;background:var(--bg0);border:1px solid var(--border);color:var(--text);padding:10px 13px;border-radius:var(--radius-sm);font-size:.85rem;outline:none;-webkit-appearance:none}
.input:focus{border-color:var(--red)}
.select{width:100%;background:var(--bg0);border:1px solid var(--border);color:var(--text);padding:10px 13px;border-radius:var(--radius-sm);font-size:.82rem;outline:none;-webkit-appearance:none;cursor:pointer}
.select:focus{border-color:var(--red)}
.form-gap{display:flex;flex-direction:column;gap:10px}

/* ── STATUS MSG ── */
.smsg{margin-top:10px;padding:10px 13px;border-radius:var(--radius-sm);font-size:.8rem;display:none;line-height:1.4}
.smsg.loading{background:#1e3a5f;color:var(--blue);display:flex;align-items:center;gap:8px}
.smsg.ok{background:#064e3b;color:#34d399;display:block}
.smsg.err{background:#450a0a;color:#f87171;display:block}
.smsg.info{background:var(--bg3);color:var(--muted2);display:block}

/* ── SPINNER ── */
.spin{width:13px;height:13px;border:2px solid rgba(96,165,250,.25);border-top-color:var(--blue);border-radius:50%;animation:rot .7s linear infinite;flex-shrink:0}
@keyframes rot{to{transform:rotate(360deg)}}

/* ── CONN BOX ── */
.conn-box{display:flex;align-items:center;gap:10px;padding:11px 14px;border-radius:var(--radius-sm);margin-bottom:12px}
.conn-box.ok{background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.2)}
.conn-box.fail{background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.2)}
.conn-box.unknown{background:rgba(255,255,255,.03);border:1px solid var(--border)}
.conn-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0}
.conn-dot.g{background:var(--green);box-shadow:0 0 6px var(--green)}
.conn-dot.r{background:#ef4444}.conn-dot.gray{background:var(--muted)}

/* ── AUTH STEPS ── */
.steps{display:flex;flex-direction:column;gap:12px;margin-bottom:14px}
.step{display:flex;gap:10px}
.step-n{width:24px;height:24px;background:var(--red);border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;flex-shrink:0}
.step-b strong{color:var(--text);font-size:.82rem}
.step-b p{color:var(--muted);font-size:.75rem;margin-top:3px;line-height:1.5}

/* ── CODE DISPLAY ── */
.code-block{background:var(--bg0);border:1px solid var(--border2);border-radius:var(--radius-sm);padding:12px 16px;font-family:monospace;font-size:.75rem;color:var(--blue);word-break:break-all;margin:8px 0}
.auth-code-big{font-size:2rem;font-weight:800;letter-spacing:6px;color:#fff;background:var(--bg3);padding:10px 20px;border-radius:var(--radius-sm);display:inline-block;text-align:center;margin:8px 0}

/* ── EMPTY ── */
.empty-state{text-align:center;padding:40px 20px;color:#374151}
.empty-ico{font-size:2.2rem;margin-bottom:10px}

/* ── MODAL ── */
.modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.94);z-index:500;align-items:flex-end;justify-content:center}
.modal.active{display:flex}
.modal-inner{background:var(--bg2);border-radius:16px 16px 0 0;width:100%;max-width:480px;max-height:92vh;overflow-y:auto;position:relative}
.modal-vid{width:100%;max-height:55vw;min-height:180px;background:#000;border-radius:16px 16px 0 0;object-fit:contain}
.modal-body{padding:16px}
.modal-close{position:absolute;top:10px;right:10px;background:rgba(0,0,0,.6);border:none;color:#fff;width:30px;height:30px;border-radius:50%;font-size:.85rem;z-index:10;display:flex;align-items:center;justify-content:center}

/* ── QUEUE ITEM ── */
.q-item{display:flex;align-items:center;gap:10px;padding:10px 12px;background:var(--bg1);border:1px solid var(--border);border-radius:var(--radius-sm);margin-bottom:8px}
.q-virality{font-size:1.1rem;font-weight:800;color:var(--red);min-width:30px}
.q-info{flex:1;min-width:0}
.q-topic{font-size:.8rem;font-weight:700;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.q-meta{font-size:.65rem;color:var(--muted);margin-top:2px}

/* ── UPLOAD ITEM ── */
.up-item{display:flex;gap:10px;align-items:center;padding:10px;background:var(--bg1);border:1px solid var(--border);border-radius:var(--radius-sm);margin-bottom:8px}
.up-thumb{width:40px;height:72px;object-fit:cover;border-radius:6px;background:#000;flex-shrink:0}

/* ── DESKTOP OVERRIDES ── */
@media(min-width:768px){
  body{padding-bottom:0}
  .header{padding:0 24px;height:60px}
  .logo-sub{display:block}
  .logo-text{font-size:1.1rem}
  .countdown-num{font-size:.95rem}
  .top-tabs{display:flex}
  .bottom-nav{display:none}
  .tab-body{padding:24px}
  .grid-2{grid-template-columns:1fr 1fr}
  .cards-grid{grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
  .modal{align-items:center}
  .modal-inner{border-radius:16px;max-height:90vh}
  .modal-vid{max-height:300px;border-radius:16px 16px 0 0}
  .stat-chip{min-width:100px}
  .stat-n{font-size:1.4rem}
}
@media(min-width:1024px){
  .tab-body{padding:28px 32px}
  .cards-grid{grid-template-columns:repeat(auto-fill,minmax(260px,1fr))}
}
</style>
</head>
<body>

<!-- HEADER -->
<header class="header">
  <div class="logo">
    <div class="logo-icon">🎬</div>
    <div>
      <div class="logo-text">YT Shorts AI Producer</div>
      <div class="logo-sub">Cloudflare AI · Pollinations · edge-tts · FFmpeg</div>
    </div>
  </div>
  <div class="header-meta">
    <div class="countdown-pill">
      <div class="countdown-num" id="countdown">--:--</div>
      <div class="countdown-lbl">Next Upload</div>
    </div>
    <button class="pilot-btn" onclick="togglePilot()">
      <div class="pilot-dot-sm" id="pilotDot"></div>
      <span class="pilot-txt" id="pilotTxt">AUTO</span>
    </button>
  </div>
</header>

<!-- STATS BAR -->
<div class="stats-scroll">
  <div class="stat-chip"><div class="stat-n" id="sQueue">-</div><div class="stat-l">📋 Queue</div></div>
  <div class="stat-chip"><div class="stat-n b" id="sVideos">-</div><div class="stat-l">🎬 Videos</div></div>
  <div class="stat-chip"><div class="stat-n g" id="sUploaded">-</div><div class="stat-l">✅ Done</div></div>
  <div class="stat-chip"><div class="stat-n gold" id="sToday">0/4</div><div class="stat-l">📅 Today</div></div>
  <div class="stat-chip"><div class="stat-n p" id="sSubs">-</div><div class="stat-l">👥 Subs</div></div>
  <div class="stat-chip"><div class="stat-n" id="sViews">-</div><div class="stat-l">👁 Views</div></div>
  <div class="stat-chip"><div class="stat-n g">$0</div><div class="stat-l">💰 Cost</div></div>
</div>

<!-- DESKTOP TOP TABS -->
<nav class="top-tabs" id="topTabs">
  <div class="top-tab active" onclick="switchTab('dashboard')">📊 Dashboard</div>
  <div class="top-tab" onclick="switchTab('trending')">🔥 Trending</div>
  <div class="top-tab" onclick="switchTab('videos')">🎬 My Videos</div>
  <div class="top-tab" onclick="switchTab('manual')">⚡ Manual</div>
  <div class="top-tab" onclick="switchTab('schedule')">📅 Schedule</div>
  <div class="top-tab" onclick="switchTab('settings')">⚙️ Settings</div>
</nav>

<!-- ══════════ DASHBOARD ══════════ -->
<div class="tab-body active" id="tab-dashboard">
  <div class="grid-2">
    <div>
      <div class="panel">
        <div class="panel-hd"><span class="ico">🤖</span> Auto-Pilot</div>
        <div class="ap-status stopped" id="apBox">
          <div class="ap-dot stopped" id="apDot"></div>
          <div class="ap-msg" id="apMsg">Loading...</div>
        </div>
        <div class="next-plan">
          <div class="next-plan-lbl">⏭ Next Action</div>
          <div class="next-plan-txt" id="nextAction">Auto-Pilot start karo</div>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button class="btn btn-green" onclick="pilotStart()">▶ Start</button>
          <button class="btn btn-ghost" onclick="pilotStop()">⏹ Stop</button>
        </div>
      </div>
      <div class="panel">
        <div class="panel-hd"><span class="ico">📡</span> AI Activity Log</div>
        <div class="log-box" id="logBox"><div class="log-row"><div class="log-m">Waiting for activity...</div></div></div>
      </div>
    </div>
    <div>
      <div class="panel">
        <div class="panel-hd"><span class="ico">📅</span> Today's Schedule (EST)</div>
        <div id="scheduleBox"><div style="color:var(--muted);font-size:.8rem">Loading...</div></div>
      </div>
      <div class="panel">
        <div class="panel-hd"><span class="ico">📺</span> YouTube Channel</div>
        <div class="ch-grid">
          <div class="ch-box"><div class="ch-n p" id="chSubs">-</div><div class="ch-l">Subs</div></div>
          <div class="ch-box"><div class="ch-n" id="chViews">-</div><div class="ch-l">Views</div></div>
          <div class="ch-box"><div class="ch-n g" id="chVids">-</div><div class="ch-l">Videos</div></div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="loadYTStats()">🔄 Refresh</button>
      </div>
      <div class="panel">
        <div class="panel-hd"><span class="ico">🔥</span> Live Trends (USA)</div>
        <div id="dashTrends" style="font-size:.78rem;color:var(--muted)">Loading...</div>
        <button class="btn btn-ghost btn-sm" style="margin-top:10px" onclick="loadTrends()">🔄 Refresh</button>
      </div>
    </div>
  </div>
</div>

<!-- ══════════ TRENDING ══════════ -->
<div class="tab-body" id="tab-trending">
  <div class="panel">
    <div class="panel-hd"><span class="ico">🔥</span> USA Live Trending Topics</div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">
      <button class="btn btn-red" onclick="loadTrends()">🔄 Refresh</button>
      <button class="btn btn-gold" onclick="autoPickBest()">🤖 AI Best Pick</button>
    </div>
    <div id="trendList"><div class="empty-state"><div class="empty-ico">🔍</div>Loading...</div></div>
    <div class="smsg" id="trendMsg"></div>
  </div>
</div>

<!-- ══════════ MY VIDEOS ══════════ -->
<div class="tab-body" id="tab-videos">
  <div class="panel">
    <div class="panel-hd"><span class="ico">🎬</span> Generated Videos</div>
    <div class="cards-grid" id="videoGrid">
      <div class="empty-state"><div class="empty-ico">🎬</div><div>Koi video nahi. Generate karo!</div></div>
    </div>
    <div class="smsg" id="vidMsg"></div>
  </div>
</div>

<!-- ══════════ MANUAL ══════════ -->
<div class="tab-body" id="tab-manual">
  <div class="grid-2">
    <div>
      <div class="panel">
        <div class="panel-hd"><span class="ico">⚡</span> Manual Generate</div>
        <div class="form-gap">
          <input class="input" id="manualTopic" placeholder="Topic (ya khali = auto trending)" />
          <select class="select" id="manualModel">
            <option value="meta-llama/llama-3.1-8b-instruct:free" selected>🦙 Llama 3.1 8B (FREE ✅)</option>
            <option value="google/gemini-2.0-flash-exp:free">🌟 Gemini 2.0 Flash (FREE ✅)</option>
            <option value="deepseek/deepseek-r1-0528:free">🧠 DeepSeek R1 (FREE ✅)</option>
            <option value="mistralai/mistral-7b-instruct:free">⚡ Mistral 7B (FREE ✅)</option>
          </select>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-red" onclick="manualGen(true)" style="flex:1">🎬 + Video</button>
            <button class="btn btn-ghost" onclick="manualGen(false)" style="flex:1">📝 Package</button>
          </div>
        </div>
        <div class="smsg" id="manualMsg"></div>
      </div>
      <div class="panel">
        <div class="panel-hd"><span class="ico">📋</span> Queue</div>
        <div id="queueList"><div style="color:var(--muted);font-size:.8rem">Loading...</div></div>
      </div>
    </div>
    <div class="panel">
      <div class="panel-hd"><span class="ico">📤</span> Upload to YouTube</div>
      <div id="uploadList"><div class="empty-state"><div class="empty-ico">📤</div><div>Video ready hone ke baad yahan aayega.</div></div></div>
      <div class="smsg" id="uploadMsg"></div>
    </div>
  </div>
</div>

<!-- ══════════ SCHEDULE ══════════ -->
<div class="tab-body" id="tab-schedule">
  <div class="grid-2">
    <div class="panel">
      <div class="panel-hd"><span class="ico">📅</span> Daily Schedule (EST)</div>
      <p style="color:var(--muted);font-size:.78rem;margin-bottom:14px;line-height:1.5">AI videos 2 hours pehle generate karta hai aur peak traffic time pe automatically upload karta hai.</p>
      <div id="fullSchedule"></div>
    </div>
    <div class="panel">
      <div class="panel-hd"><span class="ico">⏰</span> Peak Traffic Times</div>
      <div style="display:flex;flex-direction:column;gap:0">
        <div class="sched-row">
          <div class="sched-time-box"><div class="sched-time-lbl">Upload</div><div class="sched-time-val" style="color:var(--gold)">8:00 AM</div></div>
          <div class="sched-arr">→</div>
          <div style="flex:1;font-size:.78rem;color:var(--muted);line-height:1.5">🌅 Morning peak — News & tech. USA East Coast wakes up.</div>
        </div>
        <div class="sched-row">
          <div class="sched-time-box"><div class="sched-time-lbl">Upload</div><div class="sched-time-val" style="color:var(--red)">12:00 PM</div></div>
          <div class="sched-arr">→</div>
          <div style="flex:1;font-size:.78rem;color:var(--muted);line-height:1.5">☀️ Lunch peak — Highest engagement. Viral entertainment.</div>
        </div>
        <div class="sched-row">
          <div class="sched-time-box"><div class="sched-time-lbl">Upload</div><div class="sched-time-val" style="color:var(--purple)">5:00 PM</div></div>
          <div class="sched-arr">→</div>
          <div style="flex:1;font-size:.78rem;color:var(--muted);line-height:1.5">🌆 Evening peak — After-work browsing. Sports & lifestyle.</div>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ══════════ SETTINGS ══════════ -->
<div class="tab-body" id="tab-settings">

  <!-- 🚨 RESTART-SAFE WARNING BANNER -->
  <div id="restartWarnBanner" style="display:none;background:rgba(233,69,96,.12);border:2px solid rgba(233,69,96,.5);border-radius:var(--radius);padding:14px 16px;margin-bottom:16px">
    <div style="display:flex;align-items:flex-start;gap:10px">
      <div style="font-size:1.4rem;flex-shrink:0">🚨</div>
      <div style="flex:1">
        <div style="font-size:.85rem;font-weight:800;color:#e94560;margin-bottom:4px">RENDER RESTART PROBLEM — Action Zaroor Lena Hai!</div>
        <div style="font-size:.75rem;color:#e2e8f0;line-height:1.6;margin-bottom:10px">
          <strong style="color:#fbbf24">YOUTUBE_TOKENS</strong> env var Render pe set nahi hai.<br>
          Har restart pe YouTube logout ho jaata hai aur Auto-Pilot ruk jaata hai.<br>
          Neeche "YouTube Token — Render Restart Fix" section mein jaao aur token copy karke Render pe save karo.
        </div>
        <button class="btn btn-red btn-sm" onclick="scrollToTokenFix()">🔧 Fix Karo Abhi →</button>
      </div>
    </div>
  </div>

  <div class="grid-2">

    <!-- LEFT COL -->
    <div>
      <!-- CONNECTION STATUS -->
      <div class="panel">
        <div class="panel-hd"><span class="ico">📺</span> YouTube Connection Status</div>
        <div class="conn-box unknown" id="ytConnBox">
          <div class="conn-dot gray" id="ytConnDot"></div>
          <div id="ytConnTxt" style="font-size:.82rem;line-height:1.5">Checking...</div>
        </div>
        <button class="btn btn-ghost btn-sm" onclick="checkYTConn()">🔄 Check Status</button>
      </div>

      <!-- STEP-BY-STEP CONNECT -->
      <div class="panel" id="authPanel">
        <div class="panel-hd"><span class="ico">🔗</span> Connect YouTube Account</div>

        <!-- PHASE 0 — enter creds -->
        <div id="phase0">
          <p style="color:var(--muted);font-size:.78rem;line-height:1.6;margin-bottom:14px">
            Pehli baar Render pe deploy karne ke baad yahan se YouTube connect karo.<br>
            Google Cloud Console se Client ID aur Secret lo.
          </p>
          <div class="form-gap">
            <input class="input" id="clientId" type="text" placeholder="Client ID (xxxx.apps.googleusercontent.com)" autocomplete="off"/>
            <input class="input" id="clientSecret" type="password" placeholder="Client Secret (GOCSPX-...)" autocomplete="off"/>
            <button class="btn btn-red btn-full" onclick="saveAndConnect()">🔑 Save &amp; Get Auth Code</button>
          </div>
          <div class="smsg" id="credsMsg"></div>
        </div>

        <!-- PHASE 1 — show code -->
        <div id="phase1" style="display:none;text-align:center">
          <div style="background:rgba(251,191,36,.06);border:1px solid rgba(251,191,36,.25);border-radius:var(--radius-sm);padding:16px 12px;margin-bottom:14px">
            <p style="color:var(--muted);font-size:.72rem;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Step 1 — Yeh link kholo</p>
            <a id="authUrl" href="https://www.google.com/device" target="_blank"
               style="display:inline-block;background:var(--blue);color:#000;font-weight:800;font-size:.9rem;padding:10px 22px;border-radius:8px;margin-bottom:10px;text-decoration:none">
              🌐 google.com/device ↗
            </a>
            <p style="color:var(--muted);font-size:.72rem;margin-bottom:8px;text-transform:uppercase;letter-spacing:1px">Step 2 — Yeh code wahan paste karo</p>
            <div class="auth-code-big" id="authCode" onclick="copyCode()" style="cursor:copy" title="Tap to copy">------</div>
            <p style="color:#374151;font-size:.65rem;margin-top:6px">Tap to copy</p>
          </div>

          <!-- AUTO-POLL STATUS -->
          <div style="background:rgba(16,185,129,.06);border:1px solid rgba(16,185,129,.2);border-radius:var(--radius-sm);padding:12px;margin-bottom:12px">
            <div style="display:flex;align-items:center;gap:8px;justify-content:center">
              <div class="spin" id="pollSpin"></div>
              <span style="font-size:.8rem;color:var(--green)" id="pollTxt">Waiting — code enter karo Google pe...</span>
            </div>
            <div style="margin-top:8px;background:var(--bg0);border-radius:6px;height:4px;overflow:hidden">
              <div id="pollBar" style="height:4px;background:var(--green);width:0%;transition:width .5s"></div>
            </div>
            <p style="font-size:.65rem;color:var(--muted);margin-top:6px;text-align:center" id="pollTimer">Auto-checking in 5s...</p>
          </div>

          <button class="btn btn-ghost btn-sm btn-full" onclick="resetAuthPhase()">↩ Back</button>
        </div>

        <!-- PHASE 2 — success -->
        <div id="phase2" style="display:none;padding:16px 0">
          <div style="text-align:center;margin-bottom:14px">
            <div style="font-size:2.5rem;margin-bottom:6px">🎉</div>
            <h3 style="color:var(--green);font-size:1.1rem;margin-bottom:4px">YouTube Connected!</h3>
            <p style="color:var(--muted);font-size:.78rem">Ab Auto-Pilot videos automatically upload karega.</p>
          </div>
          <!-- TOKEN BACKUP BOX -->
          <div style="background:rgba(251,191,36,.07);border:1px solid rgba(251,191,36,.3);border-radius:var(--radius-sm);padding:12px;margin-bottom:12px">
            <p style="font-size:.7rem;color:#fbbf24;font-weight:700;margin-bottom:6px">⚠️ ZAROORI — Render Restart Fix</p>
            <p style="font-size:.68rem;color:var(--muted);line-height:1.5;margin-bottom:8px">
              Yeh token copy karo aur Render Dashboard → Environment Variables mein<br>
              <strong style="color:#fff">YOUTUBE_TOKENS</strong> naam se paste karo.<br>
              Iske baad restart pe bhi YouTube connected rahega! 🔒
            </p>
            <div style="background:var(--bg0);border:1px solid var(--border2);border-radius:6px;padding:8px;font-family:monospace;font-size:.6rem;color:var(--blue);word-break:break-all;max-height:60px;overflow-y:auto;margin-bottom:8px" id="tokenBackupBox">Loading...</div>
            <button class="btn btn-red btn-full btn-sm" onclick="copyTokenBackup()">📋 Copy Token (Render ke liye)</button>
          </div>
          <button class="btn btn-green btn-full" onclick="checkYTConn();resetAuthPhase()">✅ Done</button>
        </div>
      </div>
    </div>

    <!-- RIGHT COL -->
    <div>
      <!-- RENDER ENV VARS GUIDE -->
      <div class="panel">
        <div class="panel-hd"><span class="ico">🚀</span> Render Deployment Guide</div>
        <p style="color:var(--muted);font-size:.75rem;line-height:1.6;margin-bottom:12px">
          Render pe credentials permanent rakhne ke liye <strong style="color:#fff">Environment Variables</strong> set karo — restart pe bhi saved rahenge.
        </p>
        <div style="display:flex;flex-direction:column;gap:8px">
          <div style="background:var(--bg0);border:1px solid var(--border2);border-radius:var(--radius-sm);padding:10px 12px">
            <div style="font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Variable 1</div>
            <div style="font-family:monospace;font-size:.8rem;color:var(--blue)" onclick="copyText('YOUTUBE_CLIENT_ID')" style="cursor:pointer">YOUTUBE_CLIENT_ID</div>
            <div style="font-size:.68rem;color:var(--muted);margin-top:2px">Value: apna Client ID</div>
          </div>
          <div style="background:var(--bg0);border:1px solid var(--border2);border-radius:var(--radius-sm);padding:10px 12px">
            <div style="font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Variable 2</div>
            <div style="font-family:monospace;font-size:.8rem;color:var(--blue)">YOUTUBE_CLIENT_SECRET</div>
            <div style="font-size:.68rem;color:var(--muted);margin-top:2px">Value: apna Client Secret</div>
          </div>
          <div style="background:var(--bg0);border:1px solid var(--border2);border-radius:var(--radius-sm);padding:10px 12px">
            <div style="font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Variable 3</div>
            <div style="font-family:monospace;font-size:.8rem;color:var(--blue)">CF_ACCOUNT_ID</div>
            <div style="font-size:.68rem;color:var(--muted);margin-top:2px">Value: apna Cloudflare Account ID</div>
          </div>
          <div style="background:var(--bg0);border:1px solid var(--border2);border-radius:var(--radius-sm);padding:10px 12px">
            <div style="font-size:.6rem;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Variable 4</div>
            <div style="font-family:monospace;font-size:.8rem;color:var(--blue)">CF_API_TOKEN</div>
            <div style="font-size:.68rem;color:var(--muted);margin-top:2px">Value: apna Cloudflare API Token</div>
          </div>
        </div>
        <div style="margin-top:12px;background:rgba(96,165,250,.06);border:1px solid rgba(96,165,250,.2);border-radius:var(--radius-sm);padding:10px">
          <p style="font-size:.72rem;color:var(--blue);line-height:1.6">
            ℹ️ Render → Dashboard → Your Service → <strong>Environment</strong> tab → Add these 4 variables
          </p>
        </div>
      </div>

      <!-- CLOUDFLARE AI CREDENTIALS -->
      <div class="panel">
        <div class="panel-hd"><span class="ico">☁️</span> Cloudflare Workers AI</div>
        <p style="color:var(--muted);font-size:.75rem;line-height:1.6;margin-bottom:12px">
          Account ID aur API Token daalo. Bilkul <strong style="color:var(--green)">FREE</strong> hai — koi credit card nahi chahiye.
        </p>
        <div class="form-gap">
          <div>
            <label style="font-size:.68rem;color:var(--muted);display:block;margin-bottom:4px">Account ID</label>
            <input class="input" id="cfAccountId" type="text"
              placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              autocomplete="off"/>
          </div>
          <div style="position:relative">
            <label style="font-size:.68rem;color:var(--muted);display:block;margin-bottom:4px">API Token</label>
            <input class="input" id="cfApiToken" type="password"
              placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
              autocomplete="off"
              style="padding-right:44px"/>
            <button onclick="toggleCfToken()" title="Show/Hide"
              style="position:absolute;right:10px;bottom:10px;background:none;border:none;cursor:pointer;font-size:1rem;color:var(--muted)">
              👁️
            </button>
          </div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-red" style="flex:1" onclick="saveCfCreds()">💾 Save Credentials</button>
            <button class="btn btn-ghost btn-sm" onclick="testCfCreds()">🧪 Test</button>
          </div>
        </div>
        <div class="smsg" id="cfCredsMsg" style="margin-top:8px"></div>
        <div style="margin-top:10px;background:rgba(251,191,36,.06);border:1px solid rgba(251,191,36,.2);border-radius:var(--radius-sm);padding:10px">
          <p style="font-size:.7rem;color:#fbbf24;line-height:1.5">
            ⚡ <strong>Kaise milega:</strong><br>
            1. <a href="https://dash.cloudflare.com" target="_blank" style="color:var(--blue)">dash.cloudflare.com</a> pe login karo<br>
            2. Right sidebar mein <strong>Account ID</strong> copy karo<br>
            3. <strong>My Profile → API Tokens → Create Token</strong><br>
            4. Template: <em>"Workers AI (Read)"</em> select karo → Create
          </p>
        </div>
      </div>

      <!-- YOUTUBE TOKEN BACKUP/RESTORE -->
      <div class="panel" data-token-fix>
        <div class="panel-hd"><span class="ico">🔒</span> YouTube Token — Render Restart Fix</div>
        <p style="color:var(--muted);font-size:.75rem;line-height:1.6;margin-bottom:10px">
          Render pe restart hone ke baad bhi YouTube connected rahe — token backup karo.
        </p>
        <!-- Export -->
        <div style="margin-bottom:12px">
          <div style="font-size:.68rem;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:1px">Step 1 — Token Copy karo</div>
          <button class="btn btn-ghost btn-full btn-sm" onclick="fetchAndShowToken()">📤 Get My Token</button>
          <div id="exportTokenBox" style="display:none;margin-top:8px;background:var(--bg0);border:1px solid var(--border2);border-radius:6px;padding:8px;font-family:monospace;font-size:.58rem;color:var(--blue);word-break:break-all;max-height:70px;overflow-y:auto"></div>
          <button id="copyExportBtn" class="btn btn-red btn-full btn-sm" style="display:none;margin-top:6px" onclick="copyExportToken()">📋 Copy Token</button>
        </div>
        <div style="background:rgba(96,165,250,.06);border:1px solid rgba(96,165,250,.2);border-radius:var(--radius-sm);padding:8px;margin-bottom:12px">
          <p style="font-size:.68rem;color:var(--blue);line-height:1.5">
            ℹ️ <strong>Step 2</strong> — Token copy karo → Render Dashboard → <strong>Environment</strong> tab → Variable naam: <strong>YOUTUBE_TOKENS</strong> → Paste karo → Save
          </p>
        </div>
        <!-- Import -->
        <div style="border-top:1px solid var(--border2);padding-top:12px">
          <div style="font-size:.68rem;color:var(--muted);margin-bottom:5px;text-transform:uppercase;letter-spacing:1px">Token Restore (naya deploy ke baad)</div>
          <textarea class="input" id="importTokenInput" rows="2"
            placeholder="Apna YOUTUBE_TOKENS value yahan paste karo..."
            style="font-family:monospace;font-size:.65rem;resize:none"></textarea>
          <button class="btn btn-green btn-full btn-sm" style="margin-top:6px" onclick="importToken()">🔄 Restore Token</button>
          <div class="smsg" id="importTokenMsg" style="margin-top:6px"></div>
        </div>
      </div>

      <!-- AUTO-PILOT CONFIG -->
      <div class="panel">
        <div class="panel-hd"><span class="ico">⚙️</span> Auto-Pilot Config</div>
        <div class="form-gap">
          <div>
            <label style="font-size:.68rem;color:var(--muted);display:block;margin-bottom:5px">Daily Video Limit</label>
            <select class="select" id="dailyLimit">
              <option value="3">3 videos/day</option>
              <option value="4" selected>4 videos/day (recommended)</option>
              <option value="5">5 videos/day</option>
            </select>
          </div>
          <div>
            <label style="font-size:.68rem;color:var(--muted);display:block;margin-bottom:5px">Default AI Model (Cloudflare FREE)</label>
            <select class="select" id="apModel">
              <option value="@cf/meta/llama-3.1-8b-instruct" selected>🦙 Llama 3.1 8B (FREE ✅)</option>
              <option value="@cf/meta/llama-3.2-3b-instruct">🦙 Llama 3.2 3B (FREE ✅)</option>
              <option value="@cf/mistral/mistral-7b-instruct-v0.1">⚡ Mistral 7B (FREE ✅)</option>
              <option value="@cf/google/gemma-7b-it">🌟 Gemma 7B (FREE ✅)</option>
              <option value="@cf/qwen/qwen1.5-7b-chat-awq">🧠 Qwen 1.5 7B (FREE ✅)</option>
            </select>
          </div>
        </div>
      </div>
    </div>

  </div>
</div>

<!-- MOBILE BOTTOM NAV -->
<nav class="bottom-nav">
  <button class="bnav-item active" id="bn-dashboard" onclick="switchTab('dashboard')"><div class="bnav-icon">📊</div><div class="bnav-lbl">Home</div></button>
  <button class="bnav-item" id="bn-trending" onclick="switchTab('trending')"><div class="bnav-icon">🔥</div><div class="bnav-lbl">Trending</div></button>
  <button class="bnav-item" id="bn-videos" onclick="switchTab('videos')"><div class="bnav-icon">🎬</div><div class="bnav-lbl">Videos</div></button>
  <button class="bnav-item" id="bn-manual" onclick="switchTab('manual')"><div class="bnav-icon">⚡</div><div class="bnav-lbl">Generate</div></button>
  <button class="bnav-item" id="bn-settings" onclick="switchTab('settings')"><div class="bnav-icon">⚙️</div><div class="bnav-lbl">Settings</div></button>
</nav>

<!-- VIDEO MODAL -->
<div class="modal" id="modal" onclick="modalBg(event)">
  <div class="modal-inner">
    <button class="modal-close" onclick="closeModal()">✕</button>
    <video id="modalVid" class="modal-vid" controls playsinline></video>
    <div class="modal-body" id="modalBody"></div>
  </div>
</div>

<script>
// ── STATE ──
let _pilotOn = false;
let _trends = [];
let _cntSecs = 0;
let _currentTab = 'dashboard';
const TABS = ['dashboard','trending','videos','manual','schedule','settings'];

// ── TAB SWITCH ──
function switchTab(name) {
  _currentTab = name;
  TABS.forEach(t => {
    document.getElementById('tab-' + t).classList.toggle('active', t === name);
  });
  // desktop top tabs
  const topTabs = document.querySelectorAll('.top-tab');
  const idx = TABS.indexOf(name);
  topTabs.forEach((el, i) => el.classList.toggle('active', i === idx));
  // mobile bottom nav
  ['dashboard','trending','videos','manual','settings'].forEach(t => {
    const el = document.getElementById('bn-' + t);
    if (el) el.classList.toggle('active', t === name || (name === 'schedule' && t === 'dashboard'));
  });
  if (name === 'trending') loadTrends();
  if (name === 'videos') loadVideos();
  if (name === 'manual') { loadVideos(); loadQueue(); }
  if (name === 'settings') { checkYTConn(); checkEnvTokenStatus(); }
  if (name === 'schedule') loadSchedule();
}

// ── COUNTDOWN ──
function fmtTime(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  if (h > 0) return `${h}h ${String(m).padStart(2,'0')}m`;
  return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}
setInterval(() => {
  if (_cntSecs > 0) _cntSecs--;
  document.getElementById('countdown').textContent = fmtTime(_cntSecs);
}, 1000);
async function refreshCountdown() {
  try { const d = await fetch('/api/countdown').then(r=>r.json()); _cntSecs = d.seconds; } catch(e){}
}
setInterval(refreshCountdown, 30000);
refreshCountdown();

// ── AUTO-PILOT ──
async function loadPilot() {
  try {
    const d = await fetch('/api/autopilot').then(r=>r.json());
    _pilotOn = d.running;
    const dot = document.getElementById('pilotDot');
    const txt = document.getElementById('pilotTxt');
    const apBox = document.getElementById('apBox');
    const apDot = document.getElementById('apDot');
    const apMsg = document.getElementById('apMsg');
    if (d.running) {
      dot.className = 'pilot-dot-sm on'; txt.className = 'pilot-txt on'; txt.textContent = 'ON';
      apBox.className = 'ap-status running'; apDot.className = 'ap-dot running';
    } else {
      dot.className = 'pilot-dot-sm'; txt.className = 'pilot-txt'; txt.textContent = 'AUTO';
      apBox.className = 'ap-status stopped'; apDot.className = 'ap-dot stopped';
    }
    apMsg.textContent = d.status_msg || 'Stopped';
    const na = document.getElementById('nextAction');
    if (na) na.textContent = d.next_action || 'Auto-Pilot start karo';
    document.getElementById('sToday').textContent = `${d.daily_uploads||0}/4`;
    const lb = document.getElementById('logBox');
    if (lb && d.log && d.log.length) {
      lb.innerHTML = d.log.map(e => {
        const c = e.msg.includes('✅')||e.msg.includes('🎉') ? 'ok' : e.msg.includes('❌') ? 'err' : 'info';
        return `<div class="log-row"><div class="log-t">${e.time}</div><div class="log-m ${c}">${e.msg}</div></div>`;
      }).join('');
    }
  } catch(e){}
}
async function togglePilot() { _pilotOn ? pilotStop() : pilotStart(); }
async function pilotStart() { await fetch('/api/autopilot/start',{method:'POST'}); await loadPilot(); }
async function pilotStop() { await fetch('/api/autopilot/stop',{method:'POST'}); await loadPilot(); }

// ── STATS ──
function fmtNum(n) {
  if (n >= 1000000) return (n/1000000).toFixed(1)+'M';
  if (n >= 1000) return (n/1000).toFixed(1)+'K';
  return String(n);
}
async function loadStats() {
  try {
    const d = await fetch('/api/status').then(r=>r.json());
    document.getElementById('sQueue').textContent = d.total_queued;
    document.getElementById('sVideos').textContent = d.total_videos;
    document.getElementById('sUploaded').textContent = d.total_uploaded;
    renderDashTrends(d.trending_cache || []);
    if (_currentTab === 'videos') renderVideos(d.videos || []);
    if (_currentTab === 'manual') { renderUploadList(d.videos || []); renderQueue(d.queue_items || []); }
  } catch(e){}
}
async function loadYTStats() {
  try {
    const d = await fetch('/api/youtube/stats').then(r=>r.json());
    if (d.success) {
      const s = fmtNum(d.subscribers||0), v = fmtNum(d.views||0), vc = d.video_count||0;
      document.getElementById('sSubs').textContent = s;
      document.getElementById('sViews').textContent = v;
      document.getElementById('chSubs').textContent = s;
      document.getElementById('chViews').textContent = v;
      document.getElementById('chVids').textContent = vc;
    }
  } catch(e){}
}

// ── TRENDS ──
async function loadTrends() {
  const el = document.getElementById('trendList');
  if (el) el.innerHTML = '<div class="empty-state"><div class="spin" style="margin:auto"></div></div>';
  try {
    const d = await fetch('/api/trends/live').then(r=>r.json());
    _trends = d.topics || [];
    renderTrends(_trends);
    renderDashTrends(_trends);
  } catch(e) {
    if (el) el.innerHTML = '<div class="empty-state">❌ Load error</div>';
  }
}
function renderTrends(topics) {
  const el = document.getElementById('trendList');
  if (!el) return;
  if (!topics.length) { el.innerHTML = '<div class="empty-state">Koi trend nahi mila</div>'; return; }
  el.innerHTML = topics.map((t,i) => `
    <div class="trend-item">
      <div class="trend-rank">#${i+1}</div>
      <div class="trend-name">${t}</div>
      <div class="trend-acts">
        <button class="btn btn-red btn-xs" onclick="genTrend('${t.replace(/'/g,"\\'")}',true)">🎬</button>
        <button class="btn btn-ghost btn-xs" onclick="genTrend('${t.replace(/'/g,"\\'")}',false)">📝</button>
      </div>
    </div>`).join('');
}
function renderDashTrends(topics) {
  const el = document.getElementById('dashTrends');
  if (!el || !topics.length) return;
  el.innerHTML = topics.slice(0,5).map((t,i) =>
    `<div style="padding:6px 0;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:center">
      <span style="color:var(--red);font-weight:700;min-width:22px;font-size:.8rem">#${i+1}</span>
      <span style="font-size:.78rem">${t}</span>
    </div>`).join('');
}
async function genTrend(topic, withVideo) {
  const msg = document.getElementById('trendMsg');
  msg.className = 'smsg loading';
  msg.innerHTML = `<div class="spin"></div> "${topic}" — ${withVideo ? 'Video bana raha hoon (4-6 min)' : 'Package generate ho raha hai'}...`;
  try {
    const d = await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({topic,with_video:withVideo})}).then(r=>r.json());
    msg.className = d.success ? 'smsg ok' : 'smsg err';
    msg.innerHTML = d.success ? '✅ '+d.message : '❌ '+d.error;
  } catch(e) { msg.className='smsg err'; msg.innerHTML='❌ Network error'; }
}
async function autoPickBest() {
  if (!_trends.length) await loadTrends();
  if (_trends[0]) await genTrend(_trends[0], true);
}

// ── VIDEOS ──
async function loadVideos() {
  try {
    const d = await fetch('/api/status').then(r=>r.json());
    renderVideos(d.videos || []);
    renderUploadList(d.videos || []);
    renderQueue(d.queue_items || []);
  } catch(e){}
}
function renderVideos(videos) {
  const grid = document.getElementById('videoGrid');
  if (!grid) return;
  if (!videos.length) {
    grid.innerHTML = '<div class="empty-state"><div class="empty-ico">🎬</div><div>Koi video nahi. Generate karo!</div></div>';
    return;
  }
  grid.innerHTML = videos.map(v => `
    <div class="vid-card">
      ${v.has_video
        ? `<video class="vid-thumb" src="/output/${v.id}/shorts_video.mp4" preload="metadata" muted
             onclick="openModal('/output/${v.id}/shorts_video.mp4','${encodeURIComponent(JSON.stringify(v))}')" ></video>`
        : `<div class="vid-no-thumb">📝</div>`}
      <div class="vid-body">
        <div class="vid-topic">${v.topic}</div>
        <div class="vid-title">${v.title||'N/A'}</div>
        <div class="vid-tags">
          <span class="vtag gold">⭐${v.virality}/10</span>
          <span class="vtag b">⏰${v.upload_hour}:00</span>
          ${v.has_video ? '<span class="vtag g">✅ Ready</span>' : '<span class="vtag base">📝 No Vid</span>'}
          ${v.youtube_url ? '<span class="vtag r">🔴 Live</span>' : ''}
        </div>
        ${v.youtube_url ? `<a class="yt-link-sm" href="${v.youtube_url}" target="_blank">▶ YouTube pe dekho →</a>` : ''}
        <div class="vid-script">${v.script||'Script nahi mila.'}</div>
        <div class="vid-acts">
          ${v.has_video ? `<button class="btn btn-red btn-xs" onclick="openModal('/output/${v.id}/shorts_video.mp4','${encodeURIComponent(JSON.stringify(v))}')">▶</button>` : ''}
          ${v.has_video ? `<a href="/download/${v.id}" download><button class="btn btn-purple btn-xs">⬇</button></a>` : ''}
          ${v.has_video && !v.youtube_url ? `<button class="btn btn-yt btn-xs" onclick="uploadNow('${v.id}',this)">🔴 YT</button>` : ''}
          <a href="/output/${v.id}/full_package.json" target="_blank"><button class="btn btn-ghost btn-xs">📄</button></a>
        </div>
      </div>
    </div>`).join('');
}
function renderUploadList(videos) {
  const el = document.getElementById('uploadList');
  if (!el) return;
  const up = videos.filter(v => v.has_video);
  if (!up.length) { el.innerHTML = '<div class="empty-state"><div class="empty-ico">📤</div><div>Video ready hone ke baad yahan aayega.</div></div>'; return; }
  el.innerHTML = up.map(v => `
    <div class="up-item">
      <video class="up-thumb" src="/output/${v.id}/shorts_video.mp4" muted preload="metadata"></video>
      <div style="flex:1;min-width:0">
        <div style="font-weight:700;color:#fff;font-size:.78rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${v.title||'N/A'}</div>
        <div style="color:var(--muted);font-size:.65rem;margin-top:2px">⭐${v.virality}/10 · ⏰${v.upload_hour}:00 EST</div>
        <div style="margin-top:6px">
          ${v.youtube_url
            ? `<a href="${v.youtube_url}" target="_blank" class="yt-link-sm">✅ Uploaded →</a>`
            : `<button class="btn btn-yt btn-xs" onclick="uploadNow('${v.id}',this)">🔴 Upload YT</button>`}
        </div>
      </div>
    </div>`).join('');
}
function renderQueue(items) {
  const el = document.getElementById('queueList');
  if (!el) return;
  if (!items.length) { el.innerHTML = '<div style="color:var(--muted);font-size:.78rem;padding:8px 0">Queue khaali hai.</div>'; return; }
  el.innerHTML = items.map(q => `
    <div class="q-item">
      <div class="q-virality">${q.virality}/10</div>
      <div class="q-info">
        <div class="q-topic">${q.topic}</div>
        <div class="q-meta">📺 ${q.title||'N/A'} · ⏰ ${q.upload_hour}:00 EST</div>
      </div>
      <span class="badge pending">${q.status}</span>
    </div>`).join('');
}
async function uploadNow(itemId, btn) {
  btn.disabled = true; btn.textContent = '⏳';
  const msg = document.getElementById('uploadMsg') || document.getElementById('vidMsg');
  if (msg) { msg.className='smsg loading'; msg.innerHTML='<div class="spin"></div> Uploading...'; }
  try {
    const d = await fetch('/api/upload',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({item_id:itemId})}).then(r=>r.json());
    if (d.success) {
      btn.textContent='✅'; btn.style.background='var(--green)';
      if (msg) { msg.className='smsg ok'; msg.innerHTML=`✅ Uploaded! <a href="${d.url}" target="_blank" style="color:#34d399">${d.url}</a>`; }
      setTimeout(loadVideos, 2000);
    } else {
      btn.disabled=false; btn.textContent='🔴 YT';
      if (msg) { msg.className='smsg err'; msg.innerHTML='❌ '+d.error; }
    }
  } catch(e) { btn.disabled=false; btn.textContent='🔴 YT'; if(msg){msg.className='smsg err';msg.innerHTML='❌ Error';} }
}

// ── MANUAL ──
async function manualGen(withVideo) {
  const topic = document.getElementById('manualTopic').value.trim()||null;
  const model = document.getElementById('manualModel').value;
  const msg = document.getElementById('manualMsg');
  msg.className='smsg loading';
  msg.innerHTML=`<div class="spin"></div> ${withVideo?'Video bana raha hoon (4-6 min)':'Package generate ho raha hai'}...`;
  try {
    const d = await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic,with_video:withVideo,model})}).then(r=>r.json());
    msg.className = d.success?'smsg ok':'smsg err';
    msg.innerHTML = d.success?'✅ '+d.message:'❌ '+d.error;
    if (d.success) setTimeout(()=>{loadVideos();loadQueue();},3000);
  } catch(e){msg.className='smsg err';msg.innerHTML='❌ Error: '+e.message;}
}

// ── SCHEDULE ──
async function loadSchedule() {
  try {
    const d = await fetch('/api/schedule').then(r=>r.json());
    const slots = d.schedule||[];
    const html = slots.map(s=>`
      <div class="sched-row">
        <div class="sched-time-box"><div class="sched-time-lbl">Gen</div><div class="sched-time-val" style="color:var(--blue)">${s.generate_at}</div></div>
        <div class="sched-arr">→</div>
        <div class="sched-time-box"><div class="sched-time-lbl">Upload</div><div class="sched-time-val" style="color:var(--gold)">${s.upload_at}</div></div>
        <div style="flex:1"></div>
        <span class="badge ${s.status}">${s.status.toUpperCase()}</span>
      </div>`).join('');
    const a = document.getElementById('scheduleBox');
    const b = document.getElementById('fullSchedule');
    if (a) a.innerHTML = html;
    if (b) b.innerHTML = html;
  } catch(e){}
}

// ── SETTINGS — YouTube Auth ──
let _authDevCode = '';
let _pollInterval = null;
let _pollCountdown = 5;
let _pollProgress = 0;

async function checkEnvTokenStatus() {
  try {
    const d = await fetch('/api/youtube/env-token-status').then(r => r.json());
    const banner = document.getElementById('restartWarnBanner');
    if (banner) {
      if (!d.restart_safe && d.file_token_exists) {
        banner.style.display = 'block';
      } else {
        banner.style.display = 'none';
      }
    }
  } catch(e) {}
}

function scrollToTokenFix() {
  const el = document.querySelector('[data-token-fix]');
  if (el) el.scrollIntoView({behavior:'smooth', block:'start'});
  else window.scrollTo({top: document.body.scrollHeight, behavior:'smooth'});
}

async function checkYTConn() {
  const box = document.getElementById('ytConnBox');
  const dot = document.getElementById('ytConnDot');
  const txt = document.getElementById('ytConnTxt');
  try {
    const d = await fetch('/api/youtube/auth-status').then(r => r.json());
    if (d.step === 'ready') {
      box.className = 'conn-box ok';
      dot.className = 'conn-dot g';
      txt.innerHTML = '✅ <b>YouTube Connected</b> — Auto upload ready hai!';
      checkEnvTokenStatus();
    } else if (d.step === 'no_creds') {
      box.className = 'conn-box fail';
      dot.className = 'conn-dot r';
      txt.innerHTML = '⚠️ Client ID/Secret nahi hai — neeche "Connect YouTube" se setup karo';
    } else {
      box.className = 'conn-box fail';
      dot.className = 'conn-dot r';
      txt.innerHTML = '❌ ' + d.message;
    }
  } catch(e) {}
}

async function saveAndConnect() {
  const cid = document.getElementById('clientId').value.trim();
  const cs  = document.getElementById('clientSecret').value.trim();
  const msg = document.getElementById('credsMsg');

  if (!cid || !cs) {
    msg.className = 'smsg err';
    msg.innerHTML = '❌ Client ID aur Client Secret dono fill karo';
    return;
  }

  msg.className = 'smsg loading';
  msg.innerHTML = '<div class="spin"></div> Credentials save ho rahe hain...';

  try {
    const saved = await fetch('/api/youtube/save-creds', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({client_id: cid, client_secret: cs})
    }).then(r => r.json());

    if (!saved.success) {
      msg.className = 'smsg err';
      msg.innerHTML = '❌ ' + saved.error;
      return;
    }

    msg.className = 'smsg loading';
    msg.innerHTML = '<div class="spin"></div> Auth code generate ho raha hai...';

    const auth = await fetch('/api/youtube/start-auth', {method: 'POST'}).then(r => r.json());

    if (!auth.success) {
      msg.className = 'smsg err';
      msg.innerHTML = '❌ ' + auth.error;
      return;
    }

    _authDevCode = auth.device_code;
    document.getElementById('authCode').textContent = auth.user_code;
    const urlEl = document.getElementById('authUrl');
    urlEl.href = auth.verification_url || 'https://www.google.com/device';
    urlEl.textContent = '🌐 ' + (auth.verification_url || 'google.com/device') + ' ↗';

    // Show phase 1
    document.getElementById('phase0').style.display = 'none';
    document.getElementById('phase1').style.display = 'block';

    // Start auto-polling
    startAutoPoll();

  } catch(e) {
    msg.className = 'smsg err';
    msg.innerHTML = '❌ Network error: ' + e.message;
  }
}

function startAutoPoll() {
  _pollCountdown = 5;
  _pollProgress  = 0;
  stopAutoPoll();

  _pollInterval = setInterval(async () => {
    _pollCountdown--;
    _pollProgress = Math.min(99, _pollProgress + 2);

    const bar   = document.getElementById('pollBar');
    const timer = document.getElementById('pollTimer');
    if (bar)   bar.style.width = _pollProgress + '%';
    if (timer) timer.textContent = _pollCountdown > 0
      ? `Auto-checking in ${_pollCountdown}s...`
      : 'Checking now...';

    if (_pollCountdown <= 0) {
      _pollCountdown = 5;
      _pollProgress  = 0;
      await doPoll();
    }
  }, 1000);
}

function stopAutoPoll() {
  if (_pollInterval) { clearInterval(_pollInterval); _pollInterval = null; }
}

async function doPoll() {
  if (!_authDevCode) return;
  try {
    const txt = document.getElementById('pollTxt');
    if (txt) txt.textContent = 'Checking Google...';

    const d = await fetch('/api/youtube/verify-auth', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({device_code: _authDevCode})
    }).then(r => r.json());

    if (d.success) {
      stopAutoPoll();
      document.getElementById('phase1').style.display = 'none';
      document.getElementById('phase2').style.display = 'block';
      checkYTConn();
      // Token backup box mein token dikhao
      if (d.token_b64) {
        document.getElementById('tokenBackupBox').textContent = d.token_b64;
      } else {
        fetchTokenBackup();
      }
    } else if (!d.pending) {
      // Expired or error
      stopAutoPoll();
      const txt = document.getElementById('pollTxt');
      if (txt) { txt.style.color = '#ef4444'; txt.textContent = '❌ ' + d.error; }
    } else {
      const txt = document.getElementById('pollTxt');
      if (txt) txt.textContent = 'Waiting — code enter karo Google pe...';
    }
  } catch(e) {}
}

function copyCode() {
  const code = document.getElementById('authCode').textContent;
  navigator.clipboard.writeText(code).then(() => {
    const el = document.getElementById('authCode');
    const orig = el.textContent;
    el.textContent = 'Copied!';
    setTimeout(() => { el.textContent = orig; }, 1200);
  }).catch(() => {});
}

function copyText(txt) {
  navigator.clipboard.writeText(txt).catch(() => {});
}

async function fetchAndShowToken() {
  try {
    const r = await fetch('/api/youtube/export-token');
    const d = await r.json();
    const box = document.getElementById('exportTokenBox');
    const btn = document.getElementById('copyExportBtn');
    if (d.token_b64) {
      box.textContent = d.token_b64;
      box.style.display = 'block';
      btn.style.display = 'block';
    } else {
      box.textContent = '❌ Token nahi mila — pehle YouTube connect karo.';
      box.style.display = 'block';
    }
  } catch(e) {}
}

function copyExportToken() {
  const box = document.getElementById('exportTokenBox');
  const btn = document.getElementById('copyExportBtn');
  if (!box) return;
  navigator.clipboard.writeText(box.textContent.trim()).then(() => {
    const orig = btn.textContent;
    btn.textContent = '✅ Copied! Render pe YOUTUBE_TOKENS mein paste karo.';
    setTimeout(() => { btn.textContent = orig; }, 2500);
  }).catch(() => { box.style.userSelect = 'all'; });
}

async function fetchTokenBackup() {
  try {
    const r = await fetch('/api/youtube/export-token');
    const d = await r.json();
    if (d.token_b64) {
      const box = document.getElementById('tokenBackupBox');
      if (box) box.textContent = d.token_b64;
    }
  } catch(e) {}
}

function copyTokenBackup() {
  const box = document.getElementById('tokenBackupBox');
  if (!box) return;
  const txt = box.textContent.trim();
  if (!txt || txt === 'Loading...') return;
  navigator.clipboard.writeText(txt).then(() => {
    box.style.color = 'var(--green)';
    const origTxt = box.textContent;
    box.textContent = '✅ Copied! Ab Render pe YOUTUBE_TOKENS mein paste karo.';
    setTimeout(() => { box.textContent = origTxt; box.style.color = ''; }, 2500);
  }).catch(() => {
    box.style.userSelect = 'all';
    box.focus();
  });
}

async function importToken() {
  const val = document.getElementById('importTokenInput').value.trim();
  const msg = document.getElementById('importTokenMsg');
  if (!val) { msg.className='smsg err'; msg.textContent='Token string khali hai!'; return; }
  msg.className='smsg'; msg.textContent='Importing...';
  try {
    const r = await fetch('/api/youtube/import-token', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({token_b64: val})
    });
    const d = await r.json();
    if (d.success) {
      msg.className='smsg ok'; msg.textContent='✅ Token import ho gaya! YouTube connected.';
      document.getElementById('importTokenInput').value = '';
      checkYTConn();
    } else {
      msg.className='smsg err'; msg.textContent='❌ ' + (d.error||'Invalid token');
    }
  } catch(e) { msg.className='smsg err'; msg.textContent='❌ Network error'; }
}

function resetAuthPhase() {
  stopAutoPoll();
  _authDevCode = '';
  document.getElementById('phase0').style.display = 'block';
  document.getElementById('phase1').style.display = 'none';
  document.getElementById('phase2').style.display = 'none';
  document.getElementById('credsMsg').className = 'smsg';
  document.getElementById('credsMsg').innerHTML = '';
}

// ── CLOUDFLARE CREDENTIALS ──
function toggleCfToken() {
  const inp = document.getElementById('cfApiToken');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

async function saveCfCreds() {
  const account_id = document.getElementById('cfAccountId').value.trim();
  const api_token  = document.getElementById('cfApiToken').value.trim();
  const msg = document.getElementById('cfCredsMsg');
  if (!account_id || !api_token) {
    msg.className='smsg err'; msg.textContent='Account ID aur API Token dono chahiye!'; return;
  }
  msg.className='smsg'; msg.textContent='Saving...';
  try {
    const r = await fetch('/api/update-cf-creds', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_id, api_token})
    });
    const d = await r.json();
    if (d.success) {
      msg.className='smsg ok'; msg.textContent='✅ Credentials save ho gaye! AI generation ready hai.';
      document.getElementById('cfApiToken').value='';
    } else {
      msg.className='smsg err'; msg.textContent='❌ ' + (d.error||'Error aaya');
    }
  } catch(e) { msg.className='smsg err'; msg.textContent='❌ Network error'; }
}

async function testCfCreds() {
  const account_id = document.getElementById('cfAccountId').value.trim();
  const api_token  = document.getElementById('cfApiToken').value.trim();
  const msg = document.getElementById('cfCredsMsg');
  msg.className='smsg'; msg.textContent='🧪 Testing Cloudflare AI...';
  try {
    const r = await fetch('/api/test-cf-creds', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({account_id: account_id||null, api_token: api_token||null})
    });
    const d = await r.json();
    if (d.success) {
      msg.className='smsg ok'; msg.textContent='✅ Connected! Model: ' + (d.model||'OK');
    } else {
      msg.className='smsg err'; msg.textContent='❌ ' + (d.error||'Invalid credentials');
    }
  } catch(e) { msg.className='smsg err'; msg.textContent='❌ Network error'; }
}

// ── MODAL ──
function openModal(src, dataEnc) {
  const v = JSON.parse(decodeURIComponent(dataEnc));
  document.getElementById('modalVid').src = src;
  document.getElementById('modalBody').innerHTML = `
    <h3 style="color:#fff;font-size:.9rem;margin-bottom:5px">${v.title||''}</h3>
    <p style="color:var(--muted);font-size:.72rem;margin-bottom:8px">🎯 ${v.topic}</p>
    <p style="color:var(--text);font-size:.75rem;line-height:1.6;margin-bottom:12px">${v.script||''}</p>
    <div style="display:flex;gap:8px">
      <a href="/download/${v.id}" download style="flex:1;text-decoration:none"><button class="btn btn-purple btn-full">⬇ Download</button></a>
      ${!v.youtube_url ? `<button class="btn btn-yt" style="flex:1" onclick="uploadNow('${v.id}',this)">🔴 Upload</button>` : ''}
    </div>
    ${v.youtube_url ? `<a href="${v.youtube_url}" target="_blank" class="yt-link-sm" style="justify-content:center;margin-top:8px">✅ YouTube pe dekho →</a>` : ''}`;
  document.getElementById('modal').classList.add('active');
  document.getElementById('modalVid').play();
}
function closeModal(){document.getElementById('modal').classList.remove('active');document.getElementById('modalVid').pause();}
function modalBg(e){if(e.target===document.getElementById('modal'))closeModal();}

// ── INIT ──
function refreshAll(){loadStats();loadPilot();}
refreshAll();
loadYTStats();
loadTrends();
loadSchedule();
setInterval(refreshAll, 8000);
setInterval(loadYTStats, 60000);
</script>
</body>
</html>"""


def _load_db():
    if not os.path.exists(DB_PATH):
        return {"queue": [], "uploaded": [], "failed": [], "meta": {}}
    with open(DB_PATH) as f:
        return json.load(f)

def _save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def _scan_output():
    videos = []
    if not os.path.exists(OUTPUT_DIR):
        return videos
    db = _load_db()
    uploaded_map = {u.get("id"): u.get("youtube_url", "") for u in db.get("uploaded", [])}
    for folder_name in sorted(os.listdir(OUTPUT_DIR), reverse=True):
        fp = os.path.join(OUTPUT_DIR, folder_name)
        if not os.path.isdir(fp):
            continue
        pkg_path = os.path.join(fp, "full_package.json")
        if not os.path.exists(pkg_path):
            continue
        try:
            data = json.load(open(pkg_path))
            pkg = data.get("package", {})
            has_video = os.path.exists(os.path.join(fp, "shorts_video.mp4"))
            script = pkg.get("production_assets", {}).get("voiceover_script", "")
            videos.append({
                "id": folder_name,
                "topic": data.get("topic", "Unknown"),
                "title": pkg.get("youtube_metadata", {}).get("title", "N/A"),
                "description": pkg.get("youtube_metadata", {}).get("description", ""),
                "tags": pkg.get("youtube_metadata", {}).get("tags", []),
                "virality": pkg.get("trend_analysis", {}).get("virality_score_1_to_10", 0),
                "upload_hour": pkg.get("trend_analysis", {}).get("target_upload_hour_est", 12),
                "has_video": has_video,
                "script": script[:300] if script else "",
                "youtube_url": uploaded_map.get(folder_name, ""),
            })
        except Exception:
            continue
    return videos


@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)

@app.route("/download/<item_id>")
def download_video(item_id):
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", item_id)
    return send_from_directory(OUTPUT_DIR, f"{safe_id}/shorts_video.mp4",
                               as_attachment=True, download_name=f"{safe_id}_shorts.mp4")

@app.route("/api/status")
def api_status():
    db = _load_db()
    videos = _scan_output()
    with _trending_lock:
        tc = list(_trending_cache)
    return jsonify({
        "total_queued": len(db.get("queue", [])),
        "total_videos": sum(1 for v in videos if v["has_video"]),
        "total_uploaded": len(db.get("uploaded", [])),
        "videos": videos,
        "queue_items": [
            {"id": i["id"], "topic": i["trending_topic"],
             "title": i.get("youtube_metadata", {}).get("title", "N/A"),
             "virality": i["virality_score"], "upload_hour": i["target_upload_hour_est"], "status": i["status"]}
            for i in db.get("queue", [])
        ],
        "trending_cache": tc,
    })

@app.route("/api/countdown")
def api_countdown():
    from autopilot import get_next_upload_seconds
    return jsonify({"seconds": get_next_upload_seconds()})

@app.route("/api/autopilot")
def api_autopilot():
    from autopilot import get_state
    return jsonify(get_state())

@app.route("/api/autopilot/start", methods=["POST"])
def api_autopilot_start():
    from autopilot import start
    return jsonify(start())

@app.route("/api/autopilot/stop", methods=["POST"])
def api_autopilot_stop():
    from autopilot import stop
    return jsonify(stop())

@app.route("/api/trends/live")
def api_trends_live():
    global _trending_cache
    from trends import fetch_trending_topics
    topics = fetch_trending_topics(limit=15)
    with _trending_lock:
        _trending_cache = topics
    return jsonify({"topics": topics})

@app.route("/api/schedule")
def api_schedule():
    from autopilot import get_schedule_today
    return jsonify({"schedule": get_schedule_today()})

@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.json or {}
    topic = data.get("topic") or None
    with_video = data.get("with_video", True)
    model = data.get("model", "meta-llama/llama-3.1-8b-instruct:free")
    def _run():
        try:
            from agent import generate_autonomous_package
            from trends import get_single_topic
            from queue_manager import save_to_queue
            from output_generator import save_package_to_file, generate_images_pollinations, generate_voiceover_edgetts
            from video_editor import create_shorts_video
            t = get_single_topic(topic)
            pkg = generate_autonomous_package(t, model=model)
            iid = save_to_queue(t, pkg)
            save_package_to_file(iid, pkg, t)
            if with_video:
                imgs = generate_images_pollinations(pkg.get("production_assets", {}).get("image_prompts", []), iid)
                audio = generate_voiceover_edgetts(pkg.get("production_assets", {}).get("voiceover_script", ""), iid)
                if imgs:
                    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", iid)
                    folder = os.path.join("output", safe_id)
                    create_shorts_video(iid, imgs, audio, pkg.get("youtube_metadata", {}).get("title", ""), folder)
        except Exception as e:
            print(f"[Generate Error] {e}")
    threading.Thread(target=_run, daemon=True).start()
    msg = "Video generation shuru! 7 images + Ken Burns + audio — 4-6 min lagenge." if with_video else "Package generate ho raha hai!"
    return jsonify({"success": True, "message": msg})

@app.route("/api/upload", methods=["POST"])
def api_upload():
    data = request.json or {}
    item_id = data.get("item_id", "")
    if not item_id:
        return jsonify({"success": False, "error": "item_id required"})
    safe_id = re.sub(r"[^a-zA-Z0-9_]", "_", item_id)
    video_path = os.path.join(OUTPUT_DIR, safe_id, "shorts_video.mp4")
    pkg_path = os.path.join(OUTPUT_DIR, safe_id, "full_package.json")
    if not os.path.exists(video_path):
        return jsonify({"success": False, "error": "Video file nahi mili."})
    try:
        pkg_data = json.load(open(pkg_path))
        pkg = pkg_data.get("package", {})
        title = pkg.get("youtube_metadata", {}).get("title", "YouTube Short")
        description = pkg.get("youtube_metadata", {}).get("description", "")
        tags = pkg.get("youtube_metadata", {}).get("tags", [])
    except Exception:
        title, description, tags = "YouTube Short", "", []
    from youtube_uploader import upload_to_youtube
    result = upload_to_youtube(video_path, title, description, tags)
    if result["success"]:
        db = _load_db()
        db.setdefault("uploaded", []).append({
            "id": safe_id, "youtube_url": result["url"],
            "video_id": result["video_id"],
            "uploaded_at": datetime.utcnow().isoformat()
        })
        _save_db(db)
        return jsonify({"success": True, "url": result["url"], "video_id": result["video_id"]})
    return jsonify({"success": False, "error": result.get("error", "Upload fail.")})

@app.route("/api/youtube/stats")
def api_yt_stats():
    try:
        from youtube_uploader import _get_valid_access_token
        import requests as req
        token = _get_valid_access_token()
        r = req.get("https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "statistics", "mine": "true"},
                    headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if r.status_code == 200:
            items = r.json().get("items", [])
            if items:
                s = items[0].get("statistics", {})
                return jsonify({"success": True,
                    "subscribers": int(s.get("subscriberCount", 0)),
                    "views": int(s.get("viewCount", 0)),
                    "video_count": int(s.get("videoCount", 0))})
        return jsonify({"success": False, "error": f"API {r.status_code}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/youtube/auth-status")
def api_yt_auth():
    from youtube_uploader import get_auth_status
    return jsonify(get_auth_status())

@app.route("/api/youtube/save-creds", methods=["POST"])
def api_save_creds():
    data = request.json or {}
    cid = data.get("client_id", "").strip()
    cs = data.get("client_secret", "").strip()
    if not cid or not cs:
        return jsonify({"success": False, "error": "Client ID aur Secret dono chahiye"})
    from youtube_uploader import save_oauth_creds
    save_oauth_creds(cid, cs)
    return jsonify({"success": True})

@app.route("/api/youtube/start-auth", methods=["POST"])
def api_start_auth():
    try:
        from youtube_uploader import get_device_code
        r = get_device_code()
        return jsonify({"success": True, "user_code": r["user_code"],
                        "device_code": r["device_code"], "url": r["verification_url"]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/youtube/verify-auth", methods=["POST"])
def api_verify_auth():
    data = request.json or {}
    dc = data.get("device_code", "")
    if not dc:
        return jsonify({"success": False, "error": "device_code required"})
    try:
        from youtube_uploader import poll_for_token
        return jsonify(poll_for_token(dc))
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/api/youtube/export-token")
def api_export_token():
    from youtube_uploader import export_tokens_b64
    b64 = export_tokens_b64()
    if b64:
        return jsonify({"success": True, "token_b64": b64})
    return jsonify({"success": False, "error": "Token nahi mila — pehle authorize karo."})

@app.route("/api/youtube/import-token", methods=["POST"])
def api_import_token():
    data = request.json or {}
    b64  = data.get("token_b64", "").strip()
    if not b64:
        return jsonify({"success": False, "error": "token_b64 required"})
    from youtube_uploader import import_tokens_b64
    ok = import_tokens_b64(b64)
    if ok:
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid token — dobara copy karo."})

@app.route("/api/youtube/env-token-status")
def api_env_token_status():
    """Check karo YOUTUBE_TOKENS env var Render pe set hai ya nahi."""
    has_env_token = bool(os.environ.get("YOUTUBE_TOKENS", "").strip())
    has_file_token = os.path.exists("data/youtube_tokens.json")
    return jsonify({
        "env_token_set": has_env_token,
        "file_token_exists": has_file_token,
        "restart_safe": has_env_token,
    })

@app.route("/api/cookies/verify")
def api_cookies_verify():
    from youtube_uploader import verify_cookies
    return jsonify(verify_cookies())

@app.route("/api/update-cf-creds", methods=["POST"])
def api_update_cf_creds():
    data = request.json or {}
    account_id = data.get("account_id", "").strip()
    api_token  = data.get("api_token", "").strip()
    if not account_id or not api_token:
        return jsonify({"success": False, "error": "Account ID aur API Token dono chahiye"})
    if len(account_id) < 10 or len(api_token) < 10:
        return jsonify({"success": False, "error": "Credentials bahut chhote hain — poori values paste karo"})
    os.environ["CF_ACCOUNT_ID"] = account_id
    os.environ["CF_API_TOKEN"]  = api_token
    try:
        import agent
        agent.CF_ACCOUNT_ID = account_id
        agent.CF_API_TOKEN  = api_token
    except Exception:
        pass
    creds_file = os.path.join("data", "cf_creds.json")
    os.makedirs("data", exist_ok=True)
    with open(creds_file, "w") as f:
        json.dump({"account_id": account_id, "api_token": api_token}, f)
    return jsonify({"success": True})


@app.route("/api/test-cf-creds", methods=["POST"])
def api_test_cf_creds():
    import requests as req_lib
    data = request.json or {}
    account_id = (data.get("account_id") or "").strip() or os.environ.get("CF_ACCOUNT_ID", "")
    api_token  = (data.get("api_token")  or "").strip() or os.environ.get("CF_API_TOKEN", "")
    if not account_id or not api_token:
        return jsonify({"success": False, "error": "Credentials nahi mile — pehle save karo"})
    test_model = "@cf/meta/llama-3.2-3b-instruct"
    try:
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{test_model}"
        r = req_lib.post(
            url,
            headers={"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"},
            json={"messages": [{"role": "user", "content": "Say hi"}], "max_tokens": 5},
            timeout=20
        )
        if r.status_code == 200 and r.json().get("success"):
            return jsonify({"success": True, "model": test_model})
        if r.status_code == 401:
            return jsonify({"success": False, "error": "❌ Invalid API Token — Cloudflare ne reject kiya"})
        if r.status_code == 404:
            return jsonify({"success": False, "error": "❌ Account ID galat hai ya model nahi mila"})
        return jsonify({"success": False, "error": f"HTTP {r.status_code}: {r.text[:200]}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def _on_startup():
    """Server start hone pe auto-resume karo."""
    try:
        from autopilot import auto_resume
        resumed = auto_resume()
        if resumed:
            print("[Startup] ✅ Auto-Pilot auto-resumed after restart")
        else:
            print("[Startup] ℹ️ Auto-Pilot was stopped — waiting for manual start")
    except Exception as e:
        print(f"[Startup] Auto-resume error: {e}")


_on_startup()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
