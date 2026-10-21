"""Live view of the US100.cash FTMO $100k Pass Bot. Read only. Sends no orders.

The page listens on this PC, ports 8765 and 18765.
127.0.0.1 only works in a browser on this PC. From the laptop, open the
PC's own address on the same network, or the tunnel URL printed at startup.
"""

import json
import math
import re
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class _Mt5:
    def __getattr__(self, name):
        import MetaTrader5 as module
        globals()["mt5"] = module
        return getattr(module, name)


mt5 = _Mt5()

SYMBOL = "US100.cash"
MAGIC = 26101201
SPREAD_MAX = 250
SHOT_POINTS = 60.0
SHOT_STOP = 20.0
SHOT_TARGET = 155.0
SHOT_RISK = 1100.0
FALLBACK_MIN = 10.0
FALLBACK_STOP = 20.0
FALLBACK_TARGET = 120.0
FALLBACK_RISK = 660.0
PM_DRIVE_POINTS = 80.0
PM_DRIVE_STOP = 20.0
PM_DRIVE_TARGET = 100.0
PM_DRIVE_RISK = 660.0
LONDON_MIN = 5.0
LONDON_MAX = 30.0
LONDON_STOP = 15.0
LONDON_TARGET = 90.0
LONDON_RISK = 660.0
HOST = "0.0.0.0"
PORTS = (8765, 18765)
JOURNAL = Path(r"C:\Users\user\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\logs")

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PASS BOT — US100.cash FTMO $100k</title>
<style>
  :root {
    --bg: #0b0e14;
    --panel: #121722;
    --panel-alt: #171e2c;
    --border: #232c3d;
    --text: #e6edf3;
    --muted: #8b949e;
    --green: #2ea043;
    --green-bright: #3fb950;
    --red: #f85149;
    --blue: #388bfd;
    --gold: #d29922;
    --gold-bright: #e3b341;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0;
    min-height: 100%;
    background: var(--bg);
    color: var(--text);
    font: 13px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, sans-serif;
  }
  body { display: flex; flex-direction: column; padding-bottom: 20px; }

  /* Top Bar */
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 14px;
    padding: 12px 20px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
  }
  .brand { display: flex; align-items: center; gap: 12px; }
  .badge-bot {
    background: rgba(56, 139, 253, 0.16);
    color: #58a6ff;
    border: 1px solid rgba(56, 139, 253, 0.4);
    padding: 4px 10px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.4px;
  }
  .symbol-tag { font-weight: 700; font-size: 15px; color: #fff; }
  .sub-tag { color: var(--muted); font-size: 12px; }

  .clocks {
    display: flex;
    align-items: center;
    gap: 16px;
    background: var(--bg);
    padding: 6px 14px;
    border-radius: 8px;
    border: 1px solid var(--border);
    font-variant-numeric: tabular-nums;
  }
  .clock-item span { color: var(--muted); font-size: 11px; text-transform: uppercase; margin-right: 6px; }
  .clock-item b { color: #fff; font-size: 13px; }
  .pulse {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--green-bright);
    display: inline-block;
    box-shadow: 0 0 8px var(--green-bright);
    animation: pulse 1.6s ease-in-out infinite;
  }
  @keyframes pulse { 50% { opacity: 0.3; } }

  /* FTMO Metrics Strip */
  .metrics-bar {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 10px;
    padding: 12px 20px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
  }
  .metric-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
  }
  .metric-card .lbl { color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.4px; }
  .metric-card .val { font-size: 16px; font-weight: 700; color: #fff; margin-top: 3px; font-variant-numeric: tabular-nums; }
  .metric-card .sub { color: var(--muted); font-size: 11px; margin-top: 2px; }
  .good { color: var(--green-bright) !important; }
  .bad { color: var(--red) !important; }
  .warn { color: var(--gold-bright) !important; }

  /* Status Banner */
  .banner {
    margin: 12px 20px 0;
    padding: 10px 16px;
    background: var(--panel-alt);
    border: 1px solid var(--border);
    border-left: 4px solid var(--blue);
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
  }
  .banner-text { font-weight: 600; color: #fff; font-size: 13px; }
  .runner-pill {
    font-size: 12px;
    color: #c9d1d9;
    background: rgba(255,255,255,0.05);
    padding: 4px 10px;
    border-radius: 6px;
    border: 1px solid var(--border);
  }

  /* 5-Rule Playbook Grid */
  .section-head {
    padding: 14px 20px 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .section-head h2 {
    margin: 0;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    color: var(--muted);
  }
  .ideas {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
    padding: 0 20px;
  }
  .idea {
    background: var(--panel);
    border: 1px solid var(--border);
    border-top: 3px solid #30363d;
    border-radius: 10px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: border-color 0.2s, transform 0.15s;
  }
  .idea.weighing { border-top-color: var(--blue); }
  .idea.close { border-top-color: var(--gold-bright); background: #161c28; }
  .idea.ready.buy { border-top-color: var(--green-bright); box-shadow: 0 0 16px rgba(63,185,80,0.15); }
  .idea.ready.sell { border-top-color: var(--red); box-shadow: 0 0 16px rgba(248,81,73,0.15); }
  .idea.in { border-top-color: var(--green-bright); background: #14201b; }
  .idea.passed, .idea.aside { opacity: 0.72; }

  .idea-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border);
  }
  .idea-title { font-weight: 700; font-size: 14px; color: #fff; }
  .idea-time { color: var(--muted); font-size: 11px; margin-top: 2px; }
  .state {
    font-size: 11px;
    font-weight: 700;
    padding: 3px 8px;
    border-radius: 99px;
    white-space: nowrap;
    background: rgba(255,255,255,0.06);
    color: var(--muted);
  }
  .state.watching { color: #58a6ff; background: rgba(56,139,253,0.14); }
  .state.close { color: var(--gold-bright); background: rgba(210,153,34,0.18); }
  .state.ready.buy { color: #fff; background: var(--green); }
  .state.ready.sell { color: #fff; background: var(--red); }
  .state.in { color: #fff; background: var(--green); }

  .lead {
    margin: 10px 0;
    color: #fff;
    font-size: 13px;
    font-weight: 500;
    min-height: 36px;
  }
  .facts {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px 10px;
    padding: 10px;
    background: var(--bg);
    border-radius: 8px;
    border: 1px solid var(--border);
    margin-bottom: 10px;
  }
  .fact span { display: block; color: var(--muted); font-size: 11px; }
  .fact b {
    display: block;
    margin-top: 2px;
    color: #fff;
    font-weight: 700;
    font-size: 13px;
    font-variant-numeric: tabular-nums;
  }
  .fact b.tick, .clock-val.tick { animation: settle 0.8s ease; }
  @keyframes settle { from { color: var(--gold-bright); } to { color: #fff; } }
  .idea-foot { color: var(--muted); font-size: 11.5px; line-height: 1.4; }

  /* Main Workspace: Chart + Side Panel */
  .workspace {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 14px;
    padding: 14px 20px 0;
  }
  .card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }
  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 14px;
    background: var(--panel-alt);
    border-bottom: 1px solid var(--border);
    font-weight: 700;
    color: #fff;
  }
  .card-head .px { font-weight: 400; color: var(--muted); font-variant-numeric: tabular-nums; }
  .card-head .px b { color: #fff; font-weight: 700; margin-left: 4px; }

  .chartwrap { position: relative; height: 390px; background: #090c10; }
  svg { width: 100%; height: 100%; display: block; }
  .corner {
    position: absolute; left: 12px; top: 10px;
    color: #c9d1d9; font-size: 12px; white-space: pre;
    line-height: 1.4; text-shadow: 1px 1px 2px #000;
    pointer-events: none;
    background: rgba(11,14,20,0.75);
    padding: 6px 10px;
    border-radius: 6px;
    border: 1px solid var(--border);
  }

  .side-stack { display: flex; flex-direction: column; gap: 14px; }
  table { width: 100%; border-collapse: collapse; font-variant-numeric: tabular-nums; }
  th {
    text-align: left; color: var(--muted); font-weight: 600;
    font-size: 11px; text-transform: uppercase;
    padding: 8px 12px; background: var(--bg);
    border-bottom: 1px solid var(--border);
  }
  td { padding: 9px 12px; border-bottom: 1px solid var(--border); color: var(--text); }
  td.up { color: var(--green-bright); font-weight: 700; }
  td.down { color: var(--red); font-weight: 700; }
  .side.buy { color: var(--green-bright); font-weight: 700; text-transform: uppercase; }
  .side.sell { color: var(--red); font-weight: 700; text-transform: uppercase; }
  .empty { padding: 16px; color: var(--muted); font-size: 12.5px; }

  #lines { padding: 8px 14px; max-height: 220px; overflow-y: auto; }
  .jrow {
    display: flex; gap: 12px; padding: 5px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
    font-size: 12px;
  }
  .jrow:last-child { border-bottom: none; }
  .jrow span { color: var(--muted); min-width: 48px; font-variant-numeric: tabular-nums; }
  .jrow b { font-weight: 500; color: #d0d7de; }
  .jrow.buy b, .jrow.sell b { color: var(--green-bright); }
  .jrow.reject b { color: var(--red); }

  @media (max-width: 1300px) {
    .ideas { grid-template-columns: repeat(3, 1fr); }
    .metrics-bar { grid-template-columns: repeat(3, 1fr); }
    .workspace { grid-template-columns: 1fr; }
  }
  @media (max-width: 780px) {
    .ideas { grid-template-columns: 1fr; }
    .metrics-bar { grid-template-columns: repeat(2, 1fr); }
  }
</style>
</head>
<body>

<header>
  <div class="brand">
    <span class="badge-bot">PASS BOT v6.30</span>
    <div>
      <div class="symbol-tag">US100.cash (Nasdaq 100) · M5</div>
      <div class="sub-tag">5-Rule Book · 2-Stage Smart Runner (40% @ +1R &amp; -0.60R Cushion · +4R Locks +1.5R)</div>
    </div>
  </div>
  <div class="clocks">
    <div class="clock-item"><span>UK Time</span><b class="clock-val" id="clock-uk">--:--:--</b></div>
    <div class="clock-item"><span>NY Time</span><b class="clock-val" id="clock-ny">--:--:--</b></div>
    <i class="pulse" title="Live connection to MT5"></i>
  </div>
</header>

<section class="metrics-bar" id="metrics"></section>

<div class="banner">
  <div class="banner-text" id="board">Connecting to MetaTrader 5...</div>
  <div class="runner-pill">Shot Risk: <b>$1,100</b> (Full TP <b>+$5,555</b>) · Half-Shot Risk: <b>$660</b> (Full TP <b>+$2,640</b>)</div>
</div>

<div class="section-head">
  <h2>Daily 5-Rule Schedule (Monday – Friday)</h2>
</div>
<section class="ideas" id="think"></section>

<section class="workspace">
  <div class="card">
    <div class="card-head" id="head-nas"><span>US100.cash · M5 Live Chart</span></div>
    <div class="chartwrap">
      <svg id="chart-nas" viewBox="0 0 820 400" preserveAspectRatio="none"></svg>
      <div class="corner" id="note-nas"></div>
    </div>
  </div>

  <div class="side-stack">
    <div class="card">
      <div class="card-head"><span>Open Position</span></div>
      <div id="trades"><div class="empty">No open trade — bot is flat and watching the next window.</div></div>
    </div>

    <div class="card">
      <div class="card-head"><span>Weekly Schedule Overview (UK Time)</span></div>
      <table>
        <tr><th>Window (UK)</th><th>Setup</th><th>Active Days</th><th>Risk / Target</th></tr>
        <tr><td><b>08:30 UK</b> (03:30 NY)</td><td>London Range-Fade (5..30 pts)</td><td>Mon Tue Wed Thu Fri</td><td>$660 · 15 SL / 90 TP</td></tr>
        <tr><td><b>15:00 UK</b> (10:00 NY)</td><td>Thu 10am Snapback Fade (60+ pts)</td><td>Thursday only</td><td>$1,100 · 20 SL / 155 TP</td></tr>
        <tr><td><b>16:00 UK</b> (11:00 NY)</td><td>11am Big Trend Shot (60+ pts)</td><td>Mon Wed Thu Fri</td><td>$1,100 · 20 SL / 155 TP</td></tr>
        <tr><td><b>16:00 UK</b> (11:00 NY)</td><td>11am Mod Range-Fade (10..60 pts)</td><td>Mon Tue Wed</td><td>$660 · 20 SL / 120 TP</td></tr>
        <tr><td><b>19:30 UK</b> (14:30 NY)</td><td>Afternoon Drive (80+ pts)</td><td>Wed Thu Fri</td><td>$660 · 20 SL / 100 TP</td></tr>
      </table>
    </div>

    <div class="card">
      <div class="card-head"><span>Recent MT5 Journal</span></div>
      <div id="lines"></div>
    </div>
  </div>
</section>

<script>
function esc(s) {
  return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;");
}
function htag(parts, y, price, color, text, x0, x1, dash) {
  const yy = y(price);
  const dashAttr = dash ? ' stroke-dasharray="4 4"' : "";
  parts.push('<line x1="'+x0+'" x2="'+x1+'" y1="'+yy+'" y2="'+yy+'" stroke="'+color+'" stroke-width="1.2"'+dashAttr+'/>');
  const w = Math.max(54, text.length * 7.2);
  parts.push('<rect x="'+(x1+4)+'" y="'+(yy-9)+'" width="'+w+'" height="18" rx="3" fill="'+color+'"/>');
  parts.push('<text x="'+(x1+4+w/2)+'" y="'+(yy+4)+'" fill="#000" font-weight="700" font-size="11" text-anchor="middle">'+text+'</text>');
}
function draw(id, chart) {
  const svg = document.getElementById(id);
  const bars = (chart && chart.bars) || [];
  if (!bars.length) { svg.innerHTML = ""; return; }
  const levels = chart.levels || [];
  const left = 10, right = 735, top = 16, bottom = 372;
  let lo = Math.min(...bars.map(b => b.l));
  let hi = Math.max(...bars.map(b => b.h));
  levels.forEach(level => {
    if (level.price) { lo = Math.min(lo, level.price); hi = Math.max(hi, level.price); }
  });
  const span0 = Math.max(hi - lo, 0.5);
  lo -= span0 * 0.08;
  hi += span0 * 0.08;
  const span = hi - lo;
  const y = p => top + (hi - p) / span * (bottom - top);
  const cw = (right - left) / bars.length;
  const parts = [];
  for (let i = 0; i <= 5; i++) {
    const p = lo + span * i / 5;
    const yy = y(p);
    parts.push('<line x1="'+left+'" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" stroke="#1b2230"/>');
    parts.push('<text x="742" y="'+(yy+4)+'" fill="#8b949e" font-size="11">'+p.toFixed(2)+'</text>');
  }
  const step = Math.max(8, Math.round(bars.length / 6));
  for (let i = 0; i < bars.length; i += step) {
    const x = left + i * cw;
    parts.push('<line x1="'+x+'" x2="'+x+'" y1="'+top+'" y2="'+bottom+'" stroke="#1b2230"/>');
    parts.push('<text x="'+(x+2)+'" y="392" fill="#8b949e" font-size="11">'+bars[i].t+' NY</text>');
  }
  bars.forEach((b, i) => {
    const x = left + i * cw + cw * 0.5;
    const up = b.c >= b.o;
    const stroke = up ? "#3fb950" : "#f85149";
    const fill = up ? "#2ea043" : "#f85149";
    parts.push('<line x1="'+x+'" x2="'+x+'" y1="'+y(b.h)+'" y2="'+y(b.l)+'" stroke="'+stroke+'" stroke-width="1.2"/>');
    const topY = y(Math.max(b.o, b.c));
    const botY = y(Math.min(b.o, b.c));
    parts.push('<rect x="'+(x-Math.max(1.2, cw*0.34))+'" y="'+topY+'" width="'+Math.max(2.4, cw*0.68)+'" height="'+Math.max(1.5, botY-topY)+'" fill="'+fill+'" stroke="'+stroke+'"/>');
  });
  levels.forEach(level => {
    if (!level.price) return;
    htag(parts, y, level.price, level.color, esc(level.label), left, right, level.dash);
    if (level.name) {
      const yy = y(level.price);
      parts.push('<text x="'+(left+6)+'" y="'+(yy-5)+'" fill="'+level.color+'" font-weight="600" font-size="11">'+esc(level.name)+'</text>');
    }
  });
  svg.innerHTML = parts.join("");
}
function head(id, chart) {
  const el = document.getElementById(id);
  if (!chart) { el.innerHTML = ""; return; }
  el.innerHTML = "<span>" + esc(chart.title) + "</span><span class='px'>Bid <b>" + esc(chart.bid) + "</b> &nbsp; Ask <b>" + esc(chart.ask) + "</b> &nbsp; Spread <b>" + esc(chart.spread || "-") + "</b></span>";
}
function markTicks(root) {
  if (!markTicks.prev) markTicks.prev = {};
  const scope = root.id || "root";
  root.querySelectorAll("[data-k]").forEach(el => {
    const key = scope + ":" + el.getAttribute("data-k");
    const now = el.textContent;
    if (markTicks.prev[key] != null && markTicks.prev[key] !== now) el.classList.add("tick");
    markTicks.prev[key] = now;
  });
}
function render(data) {
  document.getElementById("clock-uk").textContent = data.uk_clock || "--:--:--";
  document.getElementById("clock-ny").textContent = data.ny_clock || "--:--:--";
  document.getElementById("board").textContent = data.board || "";

  const mbox = document.getElementById("metrics");
  mbox.innerHTML = (data.metrics || []).map(m => {
    return "<div class='metric-card'><div class='lbl'>" + esc(m.label) + "</div><div class='val " + esc(m.cls || "") + "'>" + esc(m.value) + "</div><div class='sub'>" + esc(m.sub || "") + "</div></div>";
  }).join("");

  const charts = {};
  (data.charts || []).forEach(chart => { charts[chart.id] = chart; });
  head("head-nas", charts.nas);
  document.getElementById("note-nas").textContent = charts.nas ? (charts.nas.note || "") : "";
  draw("chart-nas", charts.nas);

  const root = document.getElementById("think");
  root.innerHTML = (data.thinking || []).map(card => {
    const side = card.side ? " " + esc(card.side) : "";
    const weighing = (card.state === "Watching" || card.state === "Getting close" || card.state === "Ready" || card.state === "In a trade") ? " weighing" : "";
    const facts = (card.facts || []).map(fact => {
      return "<div class='fact'><span>" + esc(fact.label) + "</span><b class='live' data-k='" + esc(card.id) + ":" + esc(fact.label) + "'>" + esc(fact.value) + "</b></div>";
    }).join("");
    const lines = (card.lines || []).map(line => "<div class='idea-foot'>" + esc(line) + "</div>").join("");
    return "<article class='idea" + weighing + " " + esc(card.tone || "") + side + "' id='idea-" + esc(card.id) + "'>" +
      "<div><div class='idea-top'><div><div class='idea-title'>" + esc(card.name) + "</div><div class='idea-time'>" + esc(card.subtitle || "") + "</div></div>" +
      "<span class='state " + esc(card.tone || "") + side + "'>" + esc(card.state) + "</span></div>" +
      "<div class='lead'>" + esc(card.lead || "") + "</div></div>" +
      "<div><div class='facts'>" + facts + "</div>" + lines + "</div></article>";
  }).join("");
  markTicks(root);

  const trades = data.trades || [];
  const box = document.getElementById("trades");
  if (!trades.length) {
    box.innerHTML = "<div class='empty'>No open trade — bot is flat and watching the next window.</div>";
  } else {
    const rows = trades.map(row => {
      const cls = row.profit > 0 ? "up" : (row.profit < 0 ? "down" : "");
      const word = row.side === "buy" ? "BUY" : "SELL";
      const key = esc(row.ticket || row.symbol);
      return "<tr><td><b>" + esc(row.symbol) + "</b></td><td class='side " + esc(row.side) + "'>" + word + "</td><td>" + esc(row.volume) + "</td><td>" + esc(row.price) + "</td><td data-k='" + key + ":current'>" + esc(row.current) + "</td><td>" + esc(row.sl) + "</td><td>" + esc(row.tp) + "</td><td class='pnl " + cls + "' data-k='" + key + ":profit'>$" + esc(row.profit_text) + "</td></tr>";
    }).join("");
    box.innerHTML = "<table><tr><th>Symbol</th><th>Side</th><th>Lots</th><th>Entry</th><th>Current</th><th>Stop</th><th>Target</th><th>Open P&amp;L</th></tr>" + rows + "</table>";
    markTicks(box);
  }
  document.getElementById("lines").innerHTML = (data.journal || []).map(row => {
    return "<div class='jrow " + esc(row.kind || "") + "'><span>" + esc(row.time || "") + "</span><b>" + esc(row.text || "") + "</b></div>";
  }).join("");
}
async function tick() {
  try {
    const data = await (await fetch("/api")).json();
    render(data);
  } catch (err) {
    document.getElementById("board").textContent = "Waiting for viewer API...";
  }
}
tick();
setInterval(tick, 1000);
</script>
</body>
</html>
"""


def decode_log(path):
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        raw = raw[2:]
    return raw.decode("utf-16-le", errors="replace")


def lot_words(volume):
    number = float(volume)
    if abs(number - round(number)) < 0.001:
        return f"{number:.0f} lots"
    return f"{number:.2f} lots"


def plain_trade(text):
    deal = re.search(r"deal #\d+ (buy|sell) ([\d.]+) \S+ at ([\d.]+) done", text, re.I)
    if deal:
        side, volume, price = deal.groups()
        word = "Bought" if side.lower() == "buy" else "Sold"
        return word.lower(), f"{word} {lot_words(volume)} at {float(price):.2f}"
    failed = re.search(
        r"failed market (buy|sell) ([\d.]+) \S+.*?\[([^\]]+)\]",
        text,
        re.I,
    )
    if failed:
        side, volume, reason = failed.groups()
        word = "Buy" if side.lower() == "buy" else "Sell"
        if reason.lower() == "trade disabled":
            return "reject", "Order rejected. Trading was switched off on the old login."
        why = reason[:1].upper() + reason[1:] + "."
        return "reject", f"{word} of {lot_words(volume)} was rejected. {why}"
    moved = re.search(r"-> sl: ([\d.]+), tp: ([\d.]+) done", text, re.I)
    if moved:
        stop, target = moved.groups()
        return "move", f"Stop moved to {float(stop):.2f} (target {float(target):.2f})"
    return None, None


def journal_lines():
    if not JOURNAL.exists():
        return []
    files = sorted(JOURNAL.glob("*.log"))
    if not files:
        return []
    rows = []
    seen = set()
    for raw in decode_log(files[-1]).splitlines()[-400:]:
        parts = raw.split("\t")
        if len(parts) < 5:
            continue
        when = parts[2].split(".")[0]
        source = parts[3]
        text = parts[4].strip()
        kind = ""
        line = None
        if source.startswith("Trades"):
            kind, line = plain_trade(text)
            if kind == "reject" and "old login" in line:
                if "old_login" in seen:
                    continue
                seen.add("old_login")
        elif "authorized on" in text.lower():
            line = "Connected to FTMO server."
        if line:
            rows.append({"time": when[:5], "kind": kind, "text": line})
    return list(reversed(rows[-14:]))


def us_dst(day):
    march = datetime(day.year, 3, 1)
    second_sunday = 8 + (6 - march.weekday()) % 7
    november = datetime(day.year, 11, 1)
    first_sunday = 1 + (6 - november.weekday()) % 7
    start = datetime(day.year, 3, second_sunday, 7)
    end = datetime(day.year, 11, first_sunday, 6)
    return start <= day < end


def uk_dst(day):
    march31 = datetime(day.year, 3, 31)
    last_sun_mar = 31 - (march31.weekday() + 1) % 7
    oct31 = datetime(day.year, 10, 31)
    last_sun_oct = 31 - (oct31.weekday() + 1) % 7
    start = datetime(day.year, 3, last_sun_mar, 1)
    end = datetime(day.year, 10, last_sun_oct, 1)
    return start <= day < end


def ny_now():
    utc = datetime.now(timezone.utc).replace(tzinfo=None)
    offset = -4 if us_dst(utc) else -5
    return utc + timedelta(hours=offset)


def uk_now():
    utc = datetime.now(timezone.utc).replace(tzinfo=None)
    offset = 1 if uk_dst(utc) else 0
    return utc + timedelta(hours=offset)


def bar_ny(bar_time, offset_hours):
    real_utc = datetime.fromtimestamp(int(bar_time) - offset_hours * 3600, timezone.utc)
    naive = real_utc.replace(tzinfo=None)
    ny_offset = -4 if us_dst(naive) else -5
    return naive + timedelta(hours=ny_offset)


def server_offset_hours(tick_time):
    now_utc = datetime.now(timezone.utc).timestamp()
    delta = float(tick_time) - now_utc
    return int(round(delta / 3600.0))


def chart_bars(symbol, timeframe, count, offset):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None:
        return []
    bars = []
    for rate in rates:
        when = bar_ny(rate["time"], offset)
        bars.append({
            "t": when.strftime("%H:%M"),
            "o": float(rate["open"]),
            "h": float(rate["high"]),
            "l": float(rate["low"]),
            "c": float(rate["close"]),
        })
    return bars


def level(price, color, label, dash=False, name=""):
    row = {"price": float(price), "color": color, "label": label, "dash": dash}
    if name:
        row["name"] = name
    return row


def position_levels(position):
    levels = [level(position.price_open, "#ffffff", f"{float(position.price_open):.2f}", name="Entry")]
    if position.sl:
        levels.append(level(position.sl, "#f85149", f"{float(position.sl):.2f}", name="Stop"))
    if position.tp:
        levels.append(level(position.tp, "#3fb950", f"{float(position.tp):.2f}", name="Target"))
    return levels


def trade_row(position):
    buy = position.type == mt5.POSITION_TYPE_BUY
    current = float(position.price_current)
    profit = float(position.profit)
    return {
        "ticket": int(position.ticket),
        "symbol": position.symbol,
        "side": "buy" if buy else "sell",
        "volume": f"{float(position.volume):.2f}",
        "price": f"{float(position.price_open):.2f}",
        "current": f"{current:.2f}",
        "sl": f"{float(position.sl):.2f}" if position.sl else "—",
        "tp": f"{float(position.tp):.2f}" if position.tp else "—",
        "profit": profit,
        "profit_text": f"{profit:+,.2f}",
    }


def ohlc_line(bar):
    if not bar:
        return ""
    return f"O {bar['o']:.2f}   H {bar['h']:.2f}   L {bar['l']:.2f}   C {bar['c']:.2f}"


def day_name(now):
    return ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[now.weekday()]


def shot_day(now):
    return now.weekday() in (0, 2, 3, 4)


def fade10_day(now):
    return now.weekday() == 3


def mod_fade_day(now):
    return now.weekday() in (0, 1, 2)


def pm_drive_day(now):
    return now.weekday() in (2, 3, 4)


def clock_left(now, target_minute):
    now_s = now.hour * 3600 + now.minute * 60 + now.second
    left = target_minute * 60 - now_s
    if left <= 0:
        return "now"
    minutes, seconds = divmod(left, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def bar_closes_in(now, start_minute):
    now_s = now.hour * 3600 + now.minute * 60 + now.second
    start_s = start_minute * 60
    if now_s < start_s or now_s >= start_s + 300:
        return None
    return f"{start_s + 300 - now_s}s"


def price_text(value):
    return f"{value:,.2f}"


def open_at(bars, hhmm):
    for bar in bars:
        if bar["t"] == hhmm:
            return bar["o"]
    return None


def comment_of(position):
    return (position.comment or "").lower() if position is not None else ""


def idea(id_name, name, subtitle, state, side, lead, facts, lines):
    tone = {
        "Watching": "watching",
        "Getting close": "close",
        "Ready": "ready",
        "In a trade": "in",
        "Passed": "passed",
        "Standing aside": "aside",
    }[state]
    return {
        "id": id_name,
        "name": name,
        "subtitle": subtitle,
        "state": state,
        "tone": tone,
        "side": side or "",
        "lead": lead,
        "facts": facts,
        "lines": lines,
    }


def trade_facts(position, bid):
    side = "buy" if position.type == mt5.POSITION_TYPE_BUY else "sell"
    word = "BUY" if side == "buy" else "SELL"
    return side, word, [
        {"label": "Entry", "value": price_text(float(position.price_open))},
        {"label": "Current", "value": price_text(bid)},
        {"label": "Stop / TP", "value": f"{float(position.sl):.0f} / {float(position.tp):.0f}"},
        {"label": "Open P&L", "value": f"${float(position.profit):+,.2f}"},
    ]


def london_card(now, minutes, bid, bars, position):
    sub = "08:30 UK (03:30 NY) · Mon–Fri · $660 Risk"
    op3 = open_at(bars, "03:00")
    mv = None if op3 is None else (bid - op3)
    mv_txt = "—" if mv is None else f"{mv:+.1f} pts"

    if position is not None and "london" in comment_of(position):
        side, word, facts = trade_facts(position, bid)
        return idea("london", "1. London Range-Fade", sub, "In a trade", side,
                    f"{word} {float(position.volume):.2f} lots open.", facts,
                    ["Stop 15 pts, target 90 pts. Flattens by 14:20 UK (09:20 NY)."])
    if now.weekday() >= 5:
        return idea("london", "1. London Range-Fade", sub, "Standing aside", "",
                    "Weekend — resumes Monday at 08:30 UK.",
                    [{"label": "Band", "value": "5..30 pts"}, {"label": "Stop / TP", "value": "15 / 90"},
                     {"label": "Risk", "value": "$660"}, {"label": "Full TP", "value": "+$2,640"}],
                    ["Fades a 5..30 pt drift from 08:00 to 08:30 UK back toward the London open."])
    if minutes >= 3 * 60 + 35:
        return idea("london", "1. London Range-Fade", sub, "Passed", "",
                    "08:30 UK London window has completed for today.",
                    [{"label": "08:00 Open", "value": "—" if op3 is None else price_text(op3)},
                     {"label": "Since 08:00", "value": mv_txt},
                     {"label": "Band", "value": "5..30 pts"},
                     {"label": "Status", "value": "Done today"}],
                    ["Any open London trade closes automatically at 14:20 UK before New York opens."])
    closes = bar_closes_in(now, 3 * 60 + 30)
    in_band = mv is not None and LONDON_MIN <= abs(mv) < LONDON_MAX
    if closes and in_band and position is None:
        side = "sell" if mv > 0 else "buy"
        state, lead = "Ready", f"Ready to {side.upper()} (fade) the {mv:+.1f} pt London move."
    elif in_band and minutes >= 3 * 60:
        state, side, lead = "Getting close", "", f"Move is {mv:+.1f} pts (inside 5..30 pt fade band)."
    else:
        state, side = "Watching", ""
        lead = "Waiting for 08:00 UK open." if mv is None else f"Move since 08:00 UK: {mv:+.1f} pts (needs 5..30 pts)."
    return idea("london", "1. London Range-Fade", sub, state, side, lead,
                [{"label": "Since 08:00 UK", "value": mv_txt}, {"label": "Fade Band", "value": "5..30 pts"},
                 {"label": "Stop / TP", "value": "15 / 90 pts"},
                 {"label": "08:30 UK in", "value": closes or clock_left(now, 3 * 60 + 30)}],
                ["All 5 weekdays: fades a 5..30 pt London open drift ($660 risk, Full TP +$2,640)."])


def thu10_card(now, minutes, bid, bars, position):
    sub = "15:00 UK (10:00 NY) · Thursday Only · $1,100 Risk"
    op930 = open_at(bars, "09:30")
    mv = None if op930 is None else (bid - op930)
    mv_txt = "—" if mv is None else f"{mv:+.1f} pts"

    if position is not None and "day" in comment_of(position) and fade10_day(now) and minutes < 11 * 60:
        side, word, facts = trade_facts(position, bid)
        return idea("thu10", "2. Thu 10am Snapback", sub, "In a trade", side,
                    f"{word} {float(position.volume):.2f} lots open.", facts,
                    ["Thursday 15:00 UK snapback fade. Stop 20 pts, target 155 pts."])
    if not fade10_day(now):
        return idea("thu10", "2. Thu 10am Snapback", sub, "Standing aside", "",
                    f"Today is {day_name(now)} — this setup only fires on Thursdays.",
                    [{"label": "Day", "value": "Thursday only"}, {"label": "Trigger", "value": "60+ pts"},
                     {"label": "Stop / TP", "value": "20 / 155 pts"}, {"label": "Full TP", "value": "+$5,555"}],
                    ["Fades an exhausted 60+ pt surge in the first 30 mins of NY on Thursdays."])
    if minutes >= 10 * 60 + 5:
        return idea("thu10", "2. Thu 10am Snapback", sub, "Passed", "",
                    "15:00 UK (10:00 NY) window has passed for today.",
                    [{"label": "Since 14:30 UK", "value": mv_txt}, {"label": "Needed", "value": "60+ pts"},
                     {"label": "Stop / TP", "value": "20 / 155"}, {"label": "Status", "value": "Done today"}],
                    ["Next check today is the 16:00 UK (11:00 NY) Big Trend Shot."])
    closes = bar_closes_in(now, 10 * 60)
    met = mv is not None and abs(mv) >= SHOT_POINTS
    if closes and met and position is None:
        side = "sell" if mv > 0 else "buy"
        state, lead = "Ready", f"Ready to {side.upper()} (fade) the {mv:+.1f} pt opening spike."
    elif mv is not None and abs(mv) >= 40.0:
        state, side, lead = "Getting close", "", f"Move is {mv:+.1f} pts since 14:30 UK (needs 60 pts)."
    else:
        state, side = "Watching", ""
        lead = "Waiting for 14:30 UK NY open." if mv is None else f"Since 14:30 UK: {mv:+.1f} pts (needs 60+ pts)."
    return idea("thu10", "2. Thu 10am Snapback", sub, state, side, lead,
                [{"label": "Since 14:30 UK", "value": mv_txt}, {"label": "Needs", "value": "60+ pts"},
                 {"label": "Stop / TP", "value": "20 / 155 pts"},
                 {"label": "15:00 UK in", "value": closes or clock_left(now, 10 * 60)}],
                ["Thursdays at 15:00 UK: fades a 60+ pt 30-minute spike ($1,100 risk, Full TP +$5,555)."])


def shot11_card(now, minutes, bid, bars, position):
    sub = "16:00 UK (11:00 NY) · Mon/Wed/Thu/Fri · $1,100 Risk"
    op930 = open_at(bars, "09:30")
    mv = None if op930 is None else (bid - op930)
    mv_txt = "—" if mv is None else f"{mv:+.1f} pts"

    if position is not None and "day" in comment_of(position) and minutes >= 11 * 60:
        side, word, facts = trade_facts(position, bid)
        return idea("shot11", "3. 11am Big Trend Shot", sub, "In a trade", side,
                    f"{word} {float(position.volume):.2f} lots open.", facts,
                    ["40% banked at +1R (-0.6R cushion), +4R locks +1.5R, target 155 pts (+$5,555)."])
    if not shot_day(now):
        return idea("shot11", "3. 11am Big Trend Shot", sub, "Standing aside", "",
                    f"Today is {day_name(now)} — Trend Shots run Mon, Wed, Thu, Fri.",
                    [{"label": "Days", "value": "Mon Wed Thu Fri"}, {"label": "Trigger", "value": "60+ pts"},
                     {"label": "Stop / TP", "value": "20 / 155 pts"}, {"label": "Full TP", "value": "+$5,555"}],
                    ["On Tuesday, 16:00 UK only trades the 10..60 pt Range-Fade."])
    if minutes >= 11 * 60 + 5:
        return idea("shot11", "3. 11am Big Trend Shot", sub, "Passed", "",
                    "16:00 UK (11:00 NY) window has completed for today.",
                    [{"label": "Since 14:30 UK", "value": mv_txt}, {"label": "Needed", "value": "60+ pts"},
                     {"label": "Stop / TP", "value": "20 / 155"}, {"label": "Status", "value": "Done today"}],
                    ["Rides 60+ pt morning breakouts in the direction of the trend."])
    closes = bar_closes_in(now, 11 * 60)
    met = mv is not None and abs(mv) >= SHOT_POINTS
    if closes and met and position is None:
        side = "buy" if mv > 0 else "sell"
        state, lead = "Ready", f"Ready to {side.upper()} with the {mv:+.1f} pt breakout."
    elif mv is not None and abs(mv) >= 40.0:
        state, side, lead = "Getting close", "", f"Move is {mv:+.1f} pts since 14:30 UK (needs 60+ pts)."
    else:
        state, side = "Watching", ""
        lead = "Waiting for 14:30 UK NY open." if mv is None else f"Since 14:30 UK: {mv:+.1f} pts (needs 60+ pts)."
    return idea("shot11", "3. 11am Big Trend Shot", sub, state, side, lead,
                [{"label": "Since 14:30 UK", "value": mv_txt}, {"label": "Needs", "value": "60+ pts"},
                 {"label": "Stop / TP", "value": "20 / 155 pts"},
                 {"label": "16:00 UK in", "value": closes or clock_left(now, 11 * 60)}],
                ["Mon/Wed/Thu/Fri at 16:00 UK: rides a 60+ pt breakout ($1,100 risk, Full TP +$5,555)."])


def fade11_card(now, minutes, bid, bars, position):
    sub = "16:00 UK (11:00 NY) · Mon/Tue/Wed · $660 Risk"
    op930 = open_at(bars, "09:30")
    mv = None if op930 is None else (bid - op930)
    mv_txt = "—" if mv is None else f"{mv:+.1f} pts"

    if position is not None and "daily" in comment_of(position) and minutes < 14 * 60 + 30:
        side, word, facts = trade_facts(position, bid)
        return idea("fade11", "4. 11am Range-Fade", sub, "In a trade", side,
                    f"{word} {float(position.volume):.2f} lots open.", facts,
                    ["Mon/Tue/Wed 10..60 pt range-fade. Stop 20 pts, target 120 pts (+$2,640)."])
    if not mod_fade_day(now):
        return idea("fade11", "4. 11am Range-Fade", sub, "Standing aside", "",
                    f"Today is {day_name(now)} — 11am Range-Fade runs Mon/Tue/Wed only.",
                    [{"label": "Days", "value": "Mon Tue Wed"}, {"label": "Band", "value": "10..60 pts"},
                     {"label": "Stop / TP", "value": "20 / 120 pts"}, {"label": "Full TP", "value": "+$2,640"}],
                    ["Skipped on Thu/Fri because Thu/Fri mornings trend into the afternoon."])
    if minutes >= 11 * 60 + 5:
        return idea("fade11", "4. 11am Range-Fade", sub, "Passed", "",
                    "16:00 UK (11:00 NY) window has completed for today.",
                    [{"label": "Since 14:30 UK", "value": mv_txt}, {"label": "Band", "value": "10..60 pts"},
                     {"label": "Stop / TP", "value": "20 / 120"}, {"label": "Status", "value": "Done today"}],
                    ["Fades moderate 10..60 pt morning moves back toward the 14:30 UK open."])
    closes = bar_closes_in(now, 11 * 60)
    in_band = mv is not None and FALLBACK_MIN <= abs(mv) < SHOT_POINTS
    if closes and in_band and position is None:
        side = "sell" if mv > 0 else "buy"
        state, lead = "Ready", f"Ready to {side.upper()} (fade) the {mv:+.1f} pt range move."
    elif in_band and minutes >= 10 * 60 + 30:
        state, side, lead = "Getting close", "", f"Move is {mv:+.1f} pts (inside 10..60 pt fade band)."
    else:
        state, side = "Watching", ""
        lead = "Waiting for 14:30 UK NY open." if mv is None else f"Since 14:30 UK: {mv:+.1f} pts (band is 10..60 pts)."
    return idea("fade11", "4. 11am Range-Fade", sub, state, side, lead,
                [{"label": "Since 14:30 UK", "value": mv_txt}, {"label": "Fade Band", "value": "10..60 pts"},
                 {"label": "Stop / TP", "value": "20 / 120 pts"},
                 {"label": "16:00 UK in", "value": closes or clock_left(now, 11 * 60)}],
                ["Mon/Tue/Wed at 16:00 UK: fades a 10..60 pt morning drift ($660 risk, Full TP +$2,640)."])


def pm1430_card(now, minutes, bid, bars, position):
    sub = "19:30 UK (14:30 NY) · Wed/Thu/Fri · $660 Risk"
    op13 = open_at(bars, "13:00")
    mv = None if op13 is None else (bid - op13)
    mv_txt = "—" if mv is None else f"{mv:+.1f} pts"

    if position is not None and "daily" in comment_of(position) and minutes >= 14 * 60 + 30:
        side, word, facts = trade_facts(position, bid)
        return idea("pm1430", "5. 14:30 PM Drive", sub, "In a trade", side,
                    f"{word} {float(position.volume):.2f} lots open.", facts,
                    ["Afternoon power-hour continuation. Stop 20 pts, target 100 pts (+$2,244)."])
    if not pm_drive_day(now):
        return idea("pm1430", "5. 14:30 PM Drive", sub, "Standing aside", "",
                    f"Today is {day_name(now)} — Afternoon Drive runs Wed, Thu, Fri.",
                    [{"label": "Days", "value": "Wed Thu Fri"}, {"label": "Trigger", "value": "80+ pts"},
                     {"label": "Stop / TP", "value": "20 / 100 pts"}, {"label": "Full TP", "value": "+$2,244"}],
                    ["Rides strong 80+ pt afternoon trends from 18:00 UK into the 20:55 UK close."])
    if minutes >= 14 * 60 + 35:
        return idea("pm1430", "5. 14:30 PM Drive", sub, "Passed", "",
                    "19:30 UK (14:30 NY) window has completed for today.",
                    [{"label": "Since 18:00 UK", "value": mv_txt}, {"label": "Needed", "value": "80+ pts"},
                     {"label": "Stop / TP", "value": "20 / 100"}, {"label": "Status", "value": "Done today"}],
                    ["All open trades flatten at 20:55 UK (15:55 NY)."])
    closes = bar_closes_in(now, 14 * 60 + 30)
    met = mv is not None and abs(mv) >= PM_DRIVE_POINTS
    if closes and met and position is None:
        side = "buy" if mv > 0 else "sell"
        state, lead = "Ready", f"Ready to {side.upper()} the {mv:+.1f} pt afternoon drive."
    elif mv is not None and abs(mv) >= 55.0:
        state, side, lead = "Getting close", "", f"Move since 18:00 UK is {mv:+.1f} pts (needs 80+ pts)."
    else:
        state, side = "Watching", ""
        lead = "Waiting for 18:00 UK (13:00 NY) open." if mv is None else f"Since 18:00 UK: {mv:+.1f} pts (needs 80+ pts)."
    return idea("pm1430", "5. 14:30 PM Drive", sub, state, side, lead,
                [{"label": "Since 18:00 UK", "value": mv_txt}, {"label": "Needs", "value": "80+ pts"},
                 {"label": "Stop / TP", "value": "20 / 100 pts"},
                 {"label": "19:30 UK in", "value": closes or clock_left(now, 14 * 60 + 30)}],
                ["Wed/Thu/Fri at 19:30 UK: rides an 80+ pt drive since 18:00 UK if flat ($660 risk)."])


def board_summary(now, uk, ideas, position):
    if position is not None:
        side = "BUY" if position.type == mt5.POSITION_TYPE_BUY else "SELL"
        return f"ACTIVE TRADE: {side} {float(position.volume):.2f} lots on US100.cash at {float(position.price_open):.2f} (Open P&L: ${float(position.profit):+,.2f})"
    active = [c for c in ideas if c["state"] in ("Ready", "Getting close", "Watching")]
    if active:
        nxt = active[0]
        return f"{day_name(now)} · Next Active Setup: {nxt['name']} ({nxt['subtitle']}) — {nxt['lead']}"
    return f"{day_name(now)} · All trading windows for today have completed. Next window: Tomorrow 08:30 UK London Open Fade."


def nas_view(now, minutes, bid, ask, spread_pts, bars, position):
    open0300 = open_at(bars, "03:00")
    open930 = open_at(bars, "09:30")
    open1300 = open_at(bars, "13:00")
    levels = []
    if open0300 is not None and minutes < 9 * 60 + 30:
        levels.append(level(open0300, "#58a6ff", f"{open0300:.2f}", name="08:00 UK London Open"))
    if open930 is not None:
        levels.append(level(open930, "#e3b341", f"{open930:.2f}", name="14:30 UK (09:30 NY) Open"))
        levels.append(level(open930 + SHOT_POINTS, "#8b949e", f"{open930 + SHOT_POINTS:.2f}", True, "+60 Shot"))
        levels.append(level(open930 - SHOT_POINTS, "#8b949e", f"{open930 - SHOT_POINTS:.2f}", True, "-60 Shot"))
    if open1300 is not None and minutes >= 13 * 60:
        levels.append(level(open1300, "#a371f7", f"{open1300:.2f}", True, "18:00 UK (13:00 NY) Open"))
    if position is not None:
        levels = position_levels(position) + levels
    last = bars[-1] if bars else None
    return {
        "id": "nas",
        "title": "US100.cash · M5 Live Chart",
        "bid": f"{bid:,.2f}",
        "ask": f"{ask:,.2f}",
        "spread": f"{spread_pts:.1f} pts",
        "bars": bars[-84:],
        "levels": levels,
        "note": "US100.cash, M5\n" + ohlc_line(last),
    }


def blank_snapshot(message):
    return {
        "uk_clock": "--:--:--",
        "ny_clock": "--:--:--",
        "metrics": [],
        "charts": [{"id": "nas", "title": "US100.cash · M5", "bars": [], "levels": [], "bid": "-", "ask": "-", "spread": "-", "note": message}],
        "board": message,
        "thinking": [],
        "trades": [],
        "journal": journal_lines(),
    }


def snapshot_now():
    if mt5.terminal_info() is None and not mt5.initialize(timeout=1500):
        return blank_snapshot("MetaTrader 5 is waiting for connection...")
    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.account_info()
    if tick is None:
        return blank_snapshot("Waiting for US100.cash quotes...")
    offset = server_offset_hours(tick.time)
    now = ny_now()
    uk = uk_now()
    minutes = now.hour * 60 + now.minute
    bid = float(tick.bid)
    ask = float(tick.ask)
    spread_pts = ask - bid
    bars = chart_bars(SYMBOL, mt5.TIMEFRAME_M5, 180, offset)
    nas_positions = [p for p in (mt5.positions_get(symbol=SYMBOL) or []) if p.magic == MAGIC]
    trading = bool(info.trade_allowed) if info is not None else False
    nas_position = nas_positions[0] if nas_positions else None

    nas = nas_view(now, minutes, bid, ask, spread_pts, bars, nas_position)
    ideas = [
        london_card(now, minutes, bid, bars, nas_position),
        thu10_card(now, minutes, bid, bars, nas_position),
        shot11_card(now, minutes, bid, bars, nas_position),
        fade11_card(now, minutes, bid, bars, nas_position),
        pm1430_card(now, minutes, bid, bars, nas_position),
    ]

    balance = float(info.balance) if info is not None else 100000.0
    equity = float(info.equity) if info is not None else balance
    open_pnl = equity - balance
    floor_room = equity - 90000.0
    target_room = 110000.0 - equity

    metrics = [
        {"label": "Account Balance", "value": f"${balance:,.2f}", "sub": info.name if info else "FTMO $100k", "cls": ""},
        {"label": "Live Equity", "value": f"${equity:,.2f}", "sub": f"Open P&L: ${open_pnl:+,.2f}", "cls": "good" if open_pnl >= 0 else "bad"},
        {"label": "FTMO $90k Floor Cushion", "value": f"${floor_room:,.2f}", "sub": "Hard floor: $90,000 (Bot stops at $91k)", "cls": "good" if floor_room >= 5000 else "warn"},
        {"label": "Daily Loss Limit", "value": "$4,200 Cap", "sub": "FTMO Max Daily Loss: $5,000", "cls": ""},
        {"label": "2-Stage Smart Runner", "value": "40% @ +1R", "sub": "Stop -> -0.60R (+$44/$26 min) · +4R -> +1.5R", "cls": "good"},
        {"label": "Execution Status", "value": "TRADING LIVE" if trading else "DISABLED", "sub": f"Magic {MAGIC} · US100.cash Only", "cls": "good" if trading else "bad"},
    ]

    return {
        "uk_clock": f"{uk.strftime('%a %H:%M:%S')} UK",
        "ny_clock": f"{now.strftime('%H:%M:%S')} NY",
        "metrics": metrics,
        "board": board_summary(now, uk, ideas, nas_position),
        "charts": [nas],
        "thinking": ideas,
        "trades": [trade_row(p) for p in nas_positions],
        "journal": journal_lines(),
    }


_snapshot_lock = threading.Lock()
_snapshot_busy = False
_last_snapshot = None


def snapshot():
    global _snapshot_busy, _last_snapshot
    with _snapshot_lock:
        if _snapshot_busy:
            return _last_snapshot or blank_snapshot("MetaTrader is refreshing...")
        _snapshot_busy = True
    box = {}

    def run():
        global _snapshot_busy
        try:
            box["value"] = snapshot_now()
        except Exception:
            box["error"] = True
        finally:
            with _snapshot_lock:
                _snapshot_busy = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join(2.0)
    if thread.is_alive():
        return _last_snapshot or blank_snapshot("MetaTrader is refreshing...")
    if box.get("error"):
        return blank_snapshot("MetaTrader is not connected")
    value = box.get("value") or blank_snapshot("MetaTrader is not connected")
    charts = value.get("charts") or []
    if charts and charts[0].get("bars"):
        _last_snapshot = value
    return value


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api"):
            body = json.dumps(snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        payload = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        return


def main():
    servers = [ThreadingHTTPServer((HOST, port), Handler) for port in PORTS]
    for server in servers:
        print(f"http://{server.server_address[0]}:{server.server_address[1]}/", flush=True)
    for server in servers[1:]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    servers[0].serve_forever()


if __name__ == "__main__":
    main()
