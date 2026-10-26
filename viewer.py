"""Live view of the US100.cash pass bot. Read only. Sends no orders.

The page listens on this PC, ports 8765 and 18765.
"""

import json
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
SHOT_POINTS = 60.0
FALLBACK_MIN = 10.0
PM_DRIVE_POINTS = 80.0
LONDON_MIN = 5.0
LONDON_MAX = 30.0
SPREAD_CAP = 2.50
HOST = "0.0.0.0"
PORTS = (8765, 18765)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>US100</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #090b10;
    --card: #10141d;
    --card-2: #131824;
    --line: rgba(255,255,255,0.07);
    --text: #e8edf5;
    --muted: #7d8590;
    --green: #10b981;
    --red: #f43f5e;
    --gold: #e3b341;
    --sans: Inter, "SF Pro Text", "SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --mono: "JetBrains Mono", "SFMono-Regular", "SF Mono", ui-monospace, Consolas, monospace;
    --lift: inset 0 1px 0 rgba(255,255,255,0.06);
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; min-height: 100%; }
  body {
    color: var(--text);
    font: 14px/1.4 var(--sans);
    font-variant-numeric: tabular-nums;
    color-scheme: dark;
    background:
      radial-gradient(900px 420px at 0% -10%, rgba(16,185,129,0.07), transparent 55%),
      var(--bg);
    padding: 20px 22px 48px;
  }
  .shell { width: 100%; max-width: 1120px; margin: 0 auto; display: flex; flex-direction: column; gap: 12px; min-width: 0; }
  .card {
    background: linear-gradient(180deg, rgba(255,255,255,0.035), transparent 42px), var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    box-shadow: var(--lift);
  }
  .top {
    position: sticky; top: 10px; z-index: 3;
    display: flex; align-items: center; gap: 0;
    padding: 12px 14px 12px 18px;
    backdrop-filter: blur(16px);
  }
  .metrics { display: flex; flex-wrap: wrap; align-items: center; min-width: 0; flex: 1; }
  .metric { padding: 2px 16px; min-width: 0; }
  .metric + .metric { box-shadow: inset 1px 0 0 var(--line); }
  .metric span, .kicker, .panel h2, .fact span {
    display: block;
    color: var(--muted);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  th {
    color: var(--muted);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .num {
    font-family: var(--mono);
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    font-size: 16px;
    letter-spacing: -0.03em;
    color: #f4f7fb;
  }
  .pill {
    display: inline-flex; align-items: center; gap: 8px;
    margin-left: 8px; flex: none;
    padding: 7px 12px; border-radius: 999px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em;
  }
  .pill.live { color: #6ee7b7; background: rgba(16,185,129,0.12); border: 1px solid rgba(16,185,129,0.38); }
  .pill.locked { color: #fda4af; background: rgba(244,63,94,0.12); border: 1px solid rgba(244,63,94,0.35); }
  .pill i {
    width: 7px; height: 7px; border-radius: 50%; background: currentColor; display: block;
  }
  .pill.live i { background: var(--green); box-shadow: 0 0 0 0 rgba(16,185,129,0.65); animation: pulse 1.8s ease-out infinite; }
  @keyframes pulse {
    70% { box-shadow: 0 0 0 7px rgba(16,185,129,0); }
    100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); }
  }
  .trade { padding: 12px 16px; color: var(--muted); font-size: 13px; }
  .trade.live {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px 18px;
    color: var(--text);
    border-color: rgba(16,185,129,0.32);
    background:
      linear-gradient(180deg, rgba(16,185,129,0.10), transparent 48px),
      var(--card);
    box-shadow: var(--lift), 0 10px 32px rgba(16,185,129,0.06);
  }
  .trade.live.sell {
    border-color: rgba(244,63,94,0.32);
    background:
      linear-gradient(180deg, rgba(244,63,94,0.10), transparent 48px),
      var(--card);
    box-shadow: var(--lift), 0 10px 32px rgba(244,63,94,0.06);
  }
  .kv { display: flex; flex-direction: column; gap: 1px; }
  .kv span { color: var(--muted); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; font-weight: 600; }
  .kv b { font-family: var(--mono); font-variant-numeric: tabular-nums; font-weight: 600; font-size: 14px; }
  .side { font-weight: 700; letter-spacing: 0.06em; font-size: 13px; }
  .side.buy { color: var(--green); }
  .side.sell { color: var(--red); }
  .pnl { margin-left: auto; font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 28px; font-weight: 700; letter-spacing: -0.04em; }
  .up { color: var(--green); }
  .down { color: var(--red); }
  .hero { padding: 18px 18px 16px; display: grid; grid-template-columns: 1fr auto; gap: 6px 18px; align-items: end; }
  .hero.next {
    border-color: rgba(227,179,65,0.34);
    background:
      linear-gradient(180deg, rgba(227,179,65,0.09), transparent 70px),
      var(--card);
    box-shadow: var(--lift), 0 14px 40px rgba(227,179,65,0.05);
  }
  .hero h1 { margin: 2px 0 0; font-family: var(--mono); font-weight: 700; font-size: 30px; letter-spacing: -0.045em; }
  .hero h1 em { font-style: normal; color: var(--muted); font-size: 15px; font-weight: 500; margin-left: 10px; }
  .count { font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 28px; font-weight: 700; color: var(--gold); letter-spacing: -0.04em; }
  .line { grid-column: 1 / -1; color: #c5ceda; font-size: 15px; margin-top: 2px; }
  .facts { grid-column: 1 / -1; display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
  .fact {
    flex: 1 1 190px;
    background: var(--card-2);
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 9px 12px;
    box-shadow: var(--lift);
  }
  .fact b { display: block; margin-top: 3px; font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 13px; font-weight: 600; letter-spacing: -0.02em; line-height: 1.35; }
  .verdict { grid-column: 1 / -1; margin-top: 4px; font-family: var(--mono); font-size: 15px; font-weight: 600; letter-spacing: -0.02em; }
  .panel { padding: 14px 14px 12px; }
  .panel h2 { margin: 0 0 10px; font-weight: 600; }
  .head-row { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; min-width: 0; }
  .head-row h2 { margin: 0; }
  .px { min-width: 0; color: var(--muted); font-family: var(--mono); font-variant-numeric: tabular-nums; font-size: 12px; }
  .px b { color: var(--text); font-weight: 600; }
  .px b.wide { color: var(--red); }
  td.read { color: #c5ceda; font-family: var(--sans); font-size: 13.5px; }
  tbody tr.next { background: rgba(16,185,129,0.045); }
  tbody tr.next:hover { background: rgba(16,185,129,0.08); }
  tbody tr.later { background: rgba(227,179,65,0.035); }
  .wide { color: var(--red); }
  .chart-frame { width: 100%; border-radius: 12px; overflow: hidden; border: 1px solid var(--line); background: #0c1018; }
  canvas { display: block; width: 100%; max-width: 100%; }
  table { width: 100%; border-collapse: collapse; table-layout: fixed; }
  th:nth-child(1), td:nth-child(1) { width: 16%; }
  th:nth-child(2), td:nth-child(2) { width: 28%; }
  th:nth-child(3), td:nth-child(3) { width: 24%; }
  th:nth-child(4), td:nth-child(4) { width: 32%; }
  th { text-align: left; font-weight: 600; padding: 0 12px 8px 12px; }
  td {
    padding: 11px 12px;
    border-top: 1px solid var(--line);
    font-family: var(--mono);
    font-variant-numeric: tabular-nums;
    font-size: 13px;
    vertical-align: middle;
  }
  td.name { font-family: var(--sans); font-size: 14px; }
  tbody tr { transition: background .15s ease; }
  tbody tr:hover { background: rgba(255,255,255,0.03); }
  .badge {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 84px; border-radius: 999px; padding: 3px 10px;
    font-family: var(--sans); font-size: 11px; font-weight: 700; letter-spacing: 0.04em;
    border: 1px solid transparent;
  }
  .badge.done { color: #9aa3af; background: rgba(255,255,255,0.04); }
  .badge.next { color: #6ee7b7; background: rgba(16,185,129,0.12); border-color: rgba(16,185,129,0.32); }
  .badge.off { color: #6e7681; background: transparent; border-color: var(--line); }
  .badge.later { color: #f0d78c; background: rgba(227,179,65,0.10); border-color: rgba(227,179,65,0.28); }
  #fills.hide { display: none; }
  @media (max-width: 760px) {
    body { padding: 12px 12px 32px; }
    .top { flex-wrap: wrap; padding: 10px 12px; align-items: flex-start; }
    .metrics { flex: 1 1 100%; gap: 8px 0; }
    .metric { flex: 1 1 46%; padding: 6px 10px; }
    .metric + .metric { box-shadow: none; }
    .pill { margin: 8px 0 2px 10px; }
    .hero { grid-template-columns: 1fr; }
    .hero h1 { font-size: 24px; }
    .hero h1 em { display: inline-block; margin: 4px 0 0; }
    .count { font-size: 22px; justify-self: start; }
    .head-row { flex-direction: column; align-items: flex-start; gap: 4px; }
    .badge { min-width: 0; padding: 3px 8px; }
    td, th { padding-left: 8px; padding-right: 8px; }
    .pnl { margin-left: 0; width: 100%; font-size: 26px; }
    .fact { flex-basis: 100%; }
  }
</style>
</head>
<body>
<div class="shell">
<header class="top card" id="top"></header>
<div class="trade card flat" id="trade">Flat</div>
<section class="hero card" id="hero"></section>
<section class="panel card">
  <div class="head-row" id="chart-head"><h2>US100.cash · M5</h2></div>
  <div class="chart-frame"><canvas id="chart"></canvas></div>
</section>
<section class="panel card">
  <h2>Today's windows</h2>
  <table>
    <thead><tr><th>London</th><th>Setup</th><th>Status</th><th>Readout</th></tr></thead>
    <tbody id="windows"></tbody>
  </table>
</section>
<section class="panel card hide" id="fills">
  <h2>Today's fills</h2>
  <table>
    <thead><tr><th>London</th><th>Side</th><th>Lots</th><th>Price</th><th>Result</th></tr></thead>
    <tbody id="fill-rows"></tbody>
  </table>
</section>
</div>
<script>
function esc(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;");
}
function money(n) {
  if (n == null || Number.isNaN(n)) return "—";
  const sign = n > 0 ? "+" : "";
  return sign + "$" + Number(n).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
function plainMoney(n) {
  if (n == null || Number.isNaN(n)) return "—";
  return "$" + Number(n).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
function cls(n) { return n > 0 ? "up" : (n < 0 ? "down" : ""); }
function metric(label, value, extra) {
  return '<div class="metric"><span>'+label+'</span><b class="num'+(extra ? " "+extra : "")+'">'+value+'</b></div>';
}
function parsePx(text) {
  const n = Number(String(text == null ? "" : text).replace(/,/g, ""));
  return Number.isFinite(n) ? n : null;
}
function roundRect(ctx, x, y, w, h, r) {
  const rr = Math.min(r, w / 2, h / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}
let lastChart = null;
function draw(chart, retry) {
  lastChart = chart;
  const canvas = document.getElementById("chart");
  const frame = canvas.parentElement;
  canvas.style.width = "100%";
  const cssW = frame.clientWidth;
  if (cssW < 20) {
    if (!retry) requestAnimationFrame(() => { if (lastChart) draw(lastChart, true); });
    return;
  }
  const cssH = cssW < 640 ? 260 : 380;
  const dpr = Math.min(window.devicePixelRatio || 1, 3);
  const bw = Math.round(cssW * dpr);
  const bh = Math.round(cssH * dpr);
  if (canvas.width !== bw || canvas.height !== bh) {
    canvas.width = bw;
    canvas.height = bh;
  }
  canvas.style.width = "100%";
  canvas.style.height = cssH + "px";
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.fillStyle = "#0c1018";
  ctx.fillRect(0, 0, cssW, cssH);
  const bars = (chart && chart.bars) || [];
  if (!bars.length) {
    ctx.fillStyle = "#7d8590";
    ctx.font = "500 13px Inter, sans-serif";
    ctx.fillText("Waiting for bars", 16, 28);
    return;
  }
  const compact = cssW < 560;
  const tags = [];
  (chart.levels || []).forEach(level => {
    const price = Number(level.price);
    if (!Number.isFinite(price)) return;
    const priceText = price.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
    const label = String(level.label || "");
    const text = (!compact && /^[+-]/.test(label)) ? (label + "  " + priceText) : priceText;
    tags.push({price: price, color: level.color || "#e8edf5", dash: !!level.dash, text: text, kind: "level"});
  });
  const bid = parsePx(chart.bid);
  if (bid != null) {
    tags.push({
      price: bid,
      color: "#f4f7fb",
      dash: false,
      text: bid.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}),
      kind: "bid"
    });
  }
  ctx.font = '600 11px "JetBrains Mono", Consolas, monospace';
  let gutter = 72;
  tags.forEach(tag => { gutter = Math.max(gutter, ctx.measureText(tag.text).width + 20); });
  gutter = Math.min(gutter, Math.max(88, cssW * 0.38));
  const left = 10, right = Math.max(left + 40, cssW - gutter - 6), top = 16, bottom = cssH - 14;
  let lo = Math.min.apply(null, bars.map(b => b.l));
  let hi = Math.max.apply(null, bars.map(b => b.h));
  tags.forEach(tag => { lo = Math.min(lo, tag.price); hi = Math.max(hi, tag.price); });
  const pad = Math.max(hi - lo, 1) * 0.1;
  lo -= pad; hi += pad;
  const span = hi - lo || 1;
  const yOf = p => top + (hi - p) / span * (bottom - top);
  ctx.strokeStyle = "rgba(255,255,255,0.04)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i++) {
    const yy = Math.round(yOf(lo + span * i / 4)) + 0.5;
    ctx.beginPath();
    ctx.moveTo(left, yy);
    ctx.lineTo(right, yy);
    ctx.stroke();
  }
  const slot = (right - left) / bars.length;
  bars.forEach((b, i) => {
    const x = left + i * slot + slot * 0.5;
    const up = b.c >= b.o;
    const color = up ? "#10b981" : "#f43f5e";
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(Math.round(x) + 0.5, yOf(b.h));
    ctx.lineTo(Math.round(x) + 0.5, yOf(b.l));
    ctx.stroke();
    const bodyW = Math.max(1.6, slot * 0.66);
    const y1 = yOf(Math.max(b.o, b.c));
    const y2 = yOf(Math.min(b.o, b.c));
    ctx.fillStyle = color;
    ctx.fillRect(x - bodyW / 2, y1, bodyW, Math.max(1, y2 - y1));
  });
  tags.forEach(tag => {
    if (tag.kind === "bid") return;
    const yy = Math.round(yOf(tag.price)) + 0.5;
    ctx.save();
    ctx.strokeStyle = tag.color;
    ctx.globalAlpha = tag.dash ? 0.55 : 0.9;
    ctx.lineWidth = 1;
    ctx.setLineDash(tag.dash ? [3, 4] : []);
    ctx.beginPath();
    ctx.moveTo(left, yy);
    ctx.lineTo(right, yy);
    ctx.stroke();
    ctx.restore();
  });
  if (bid != null) {
    const yy = Math.round(yOf(bid)) + 0.5;
    ctx.save();
    ctx.strokeStyle = "rgba(244,247,251,0.7)";
    ctx.setLineDash([2, 3]);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(left, yy);
    ctx.lineTo(right, yy);
    ctx.stroke();
    ctx.restore();
  }
  const placed = tags.map(tag => ({tag: tag, y: yOf(tag.price)}));
  placed.sort((a, b) => a.y - b.y);
  const pillH = 18;
  for (let i = 1; i < placed.length; i++) {
    const minY = placed[i - 1].y + pillH + 3;
    if (placed[i].y < minY) placed[i].y = minY;
  }
  if (placed.length && placed[placed.length - 1].y > bottom - 2) {
    const shift = placed[placed.length - 1].y - (bottom - 2);
    placed.forEach(item => { item.y -= shift; });
  }
  if (placed.length && placed[0].y < top + 8) {
    const shift = top + 8 - placed[0].y;
    placed.forEach(item => { item.y += shift; });
  }
  ctx.font = '600 11px "JetBrains Mono", Consolas, monospace';
  ctx.textBaseline = "middle";
  placed.forEach(item => {
    const tag = item.tag;
    const tw = ctx.measureText(tag.text).width;
    const w = Math.min(tw + 14, cssW - right - 10);
    const x = right + 8;
    const y = item.y - pillH / 2;
    ctx.fillStyle = tag.color;
    roundRect(ctx, x, y, w, pillH, 6);
    ctx.fill();
    ctx.fillStyle = "#0b0e14";
    ctx.fillText(tag.text, x + 7, item.y + 0.5);
  });
}
window.addEventListener("resize", () => { if (lastChart) draw(lastChart); });
function render(data) {
  const day = data.day_pnl;
  document.getElementById("top").innerHTML =
    '<div class="metrics">' +
      metric("London", esc(data.london)) +
      metric("New York", esc(data.ny)) +
      metric("Balance", plainMoney(data.balance)) +
      metric("Equity", plainMoney(data.equity)) +
      metric("Today", money(day), cls(day)) +
    '</div>' +
    '<div class="pill '+(data.trading === "LIVE" ? "live" : "locked")+'"><i></i>'+esc(data.trading || "LOCKED")+'</div>';

  const trade = document.getElementById("trade");
  const pos = data.position;
  if (!pos) {
    trade.className = "trade card flat";
    trade.innerHTML = "Flat";
  } else {
    const side = String(pos.side || "");
    trade.className = "trade card live " + side;
    trade.innerHTML =
      '<div class="kv"><span>Symbol</span><b>'+esc(pos.symbol)+'</b></div>' +
      '<div class="kv"><span>Side</span><b class="side '+esc(side)+'">'+esc(side.toUpperCase())+'</b></div>' +
      '<div class="kv"><span>Lots</span><b>'+esc(pos.volume)+'</b></div>' +
      '<div class="kv"><span>Entry</span><b>'+esc(pos.entry)+'</b></div>' +
      '<div class="kv"><span>SL</span><b>'+esc(pos.sl)+'</b></div>' +
      '<div class="kv"><span>TP</span><b>'+esc(pos.tp)+'</b></div>' +
      '<div class="pnl '+cls(pos.pnl)+'">'+money(pos.pnl)+'</div>';
  }

  const hero = data.hero || {};
  const heroEl = document.getElementById("hero");
  const hot = hero.kicker === "Next trade check" || hero.kicker === "Checking now";
  heroEl.className = "hero card" + (hot ? " next" : "");
  const facts = (hero.facts || []).map(f =>
    '<div class="fact"><span>'+esc(f.k)+'</span><b>'+esc(f.v)+'</b></div>').join("");
  heroEl.innerHTML =
    '<div><div class="kicker">'+esc(hero.kicker || "")+'</div><h1>'+esc(hero.title || "")+'<em>'+esc(hero.ny || "")+'</em></h1></div>' +
    '<div class="count">'+esc(hero.countdown || "")+'</div>' +
    (hero.line ? '<div class="line">'+esc(hero.line)+'</div>' : '') +
    (facts ? '<div class="facts">'+facts+'</div>' : '') +
    (hero.verdict ? '<div class="verdict">'+esc(hero.verdict)+'</div>' : '');

  const chart = data.chart || {};
  document.getElementById("chart-head").innerHTML =
    '<h2>US100.cash · M5</h2>' +
    '<div class="px">Bid <b>'+esc(chart.bid || "—")+'</b> · Ask <b>'+esc(chart.ask || "—")+'</b> · Spread <b class="'+(chart.spread_wide ? "wide" : "")+'">'+esc(chart.spread || "—")+'</b></div>';
  draw(chart);

  document.getElementById("windows").innerHTML = (data.windows || []).map(row =>
    '<tr class="'+esc(row.status)+'"><td><b>'+esc(row.time)+'</b></td><td class="name">'+esc(row.name)+'</td><td><span class="badge '+esc(row.status)+'">'+esc(row.badge)+'</span></td><td class="read">'+esc(row.readout)+'</td></tr>'
  ).join("");

  const fills = data.fills || [];
  const box = document.getElementById("fills");
  box.classList.toggle("hide", !fills.length);
  document.getElementById("fill-rows").innerHTML = fills.map(row =>
    '<tr><td>'+esc(row.time)+'</td><td class="side '+esc(row.side)+'">'+esc(row.side.toUpperCase())+'</td><td>'+esc(row.lots)+'</td><td>'+esc(row.price)+'</td><td class="'+cls(row.pnl)+'">'+esc(row.result)+'</td></tr>'
  ).join("");
}
async function tick() {
  try {
    render(await (await fetch("/api")).json());
  } catch (err) {
    const heroEl = document.getElementById("hero");
    heroEl.className = "hero card";
    heroEl.innerHTML = '<div><div class="kicker">Waiting</div><h1>Viewer offline</h1></div>';
  }
}
tick();
setInterval(tick, 1000);
</script>
</body>
</html>
"""


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
    return utc + timedelta(hours=(-4 if us_dst(utc) else -5))


def uk_now():
    utc = datetime.now(timezone.utc).replace(tzinfo=None)
    return utc + timedelta(hours=(1 if uk_dst(utc) else 0))


def london_hhmm(hour, minute, on=None):
    when = on or ny_now()
    local = datetime(when.year, when.month, when.day, hour, minute)
    for ny_offset in (-4, -5):
        utc = local - timedelta(hours=ny_offset)
        if us_dst(utc) == (ny_offset == -4):
            uk_offset = 1 if uk_dst(utc) else 0
            london = utc + timedelta(hours=uk_offset)
            return f"{london.hour:02d}:{london.minute:02d}"
    return f"{(hour + 4) % 24:02d}:{minute:02d}"


def london_from_ny(when):
    return london_hhmm(when.hour, when.minute, when)


def bar_ny(bar_time, offset_hours):
    real_utc = datetime.fromtimestamp(int(bar_time) - offset_hours * 3600, timezone.utc).replace(tzinfo=None)
    return real_utc + timedelta(hours=(-4 if us_dst(real_utc) else -5))


def server_offset_hours(tick_time):
    return int(round((float(tick_time) - datetime.now(timezone.utc).timestamp()) / 3600.0))


def clock_left(now, target_minute):
    left = target_minute * 60 - (now.hour * 3600 + now.minute * 60 + now.second)
    if left <= 0:
        return "now"
    minutes, seconds = divmod(left, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h {minutes:02d}m"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def px(value):
    return f"{value:,.2f}"


def pts(value):
    return f"{value:+.1f} pts"


def chart_bars(symbol, timeframe, count, offset):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None:
        return []
    bars = []
    for rate in rates:
        when = bar_ny(rate["time"], offset)
        bars.append({
            "t": when.strftime("%H:%M"),
            "day": when.strftime("%Y-%m-%d"),
            "o": float(rate["open"]),
            "h": float(rate["high"]),
            "l": float(rate["low"]),
            "c": float(rate["close"]),
        })
    return bars


def bar_at(bars, hhmm, day):
    for bar in bars:
        if bar["t"] == hhmm and bar["day"] == day:
            return bar
    return None


def level(price, color, label, dash=False):
    return {"price": float(price), "color": color, "label": label, "dash": dash}


def shot_day(weekday):
    return weekday in (0, 2, 3, 4)


def fade_day(weekday):
    return weekday in (0, 1, 2)


def windows_for(now):
    return (
        {"id": "london", "ny": 3 * 60 + 30, "open": 3 * 60, "name": "London fade", "days": set(range(5)), "when": "Mon–Fri"},
        {"id": "thu", "ny": 10 * 60, "open": 9 * 60 + 30, "name": "Thu snapback", "days": {3}, "when": "Thursday"},
        {"id": "eleven", "ny": 11 * 60, "open": 9 * 60 + 30, "name": "11:00 check", "days": set(range(5)), "when": "Mon–Fri"},
        {"id": "pm", "ny": 14 * 60 + 30, "open": 13 * 60, "name": "Afternoon drive", "days": {2, 3, 4}, "when": "Wed–Fri"},
    )


def hhmm(minute):
    return f"{minute // 60:02d}:{minute % 60:02d}"


def burst_of(bars, day, prev_minute, price, move):
    prev = bar_at(bars, hhmm(prev_minute), day)
    if prev is None or move == 0:
        return None
    return (price - prev["o"]) * (1 if move > 0 else -1)


def eleven_verdict(move, burst, weekday, burst_known):
    side = "BUY" if move > 0 else "SELL"
    fade_side = "SELL" if move > 0 else "BUY"
    if abs(move) >= SHOT_POINTS:
        if not shot_day(weekday):
            return f"No trade · trend is off today"
        if not burst_known:
            return f"{side} trend · 10m not in yet"
        if burst is not None and burst > 55:
            return f"No trade · 10m {burst:+.0f} blocks the trend"
        return f"{side} trend · $1,100"
    if FALLBACK_MIN <= abs(move) < SHOT_POINTS:
        if not fade_day(weekday):
            return "No trade · 10–60 fade is off today"
        return f"{fade_side} fade · $660"
    return "No trade · inside 10 pts"


def window_rows(now, minutes, bid, bars):
    day = now.strftime("%Y-%m-%d")
    weekday = now.weekday()
    specs = windows_for(now)
    coming = [s for s in specs if weekday in s["days"] and minutes < s["ny"] + 5]
    nxt = coming[0]["id"] if coming else None
    rows = []
    for spec in specs:
        london = london_hhmm(spec["ny"] // 60, spec["ny"] % 60, now)
        on = weekday in spec["days"] and weekday < 5
        if not on:
            status, badge, readout = "off", "Off today", spec["when"]
        elif minutes >= spec["ny"] + 5:
            status, badge = "done", "Done"
            readout = done_readout(spec, bars, day, weekday)
        elif spec["id"] == nxt:
            status, badge = "next", "Next"
            readout = next_readout(spec, minutes, bid, bars, day)
        else:
            status, badge = "later", "Later"
            readout = next_readout(spec, minutes, bid, bars, day)
        rows.append({"time": london, "name": spec["name"], "status": status, "badge": badge, "readout": readout})
    return rows


def move_at(bars, day, open_minute, check_minute, live_price=None):
    opened = bar_at(bars, hhmm(open_minute), day)
    if opened is None:
        return None, None
    if live_price is None:
        checked = bar_at(bars, hhmm(check_minute), day)
        if checked is None:
            return opened["o"], None
        return opened["o"], checked["c"] - opened["o"]
    return opened["o"], live_price - opened["o"]


def done_readout(spec, bars, day, weekday):
    if spec["id"] == "london":
        _, move = move_at(bars, day, 3 * 60, 3 * 60 + 30)
        if move is None:
            return "passed"
        if LONDON_MIN <= abs(move) < LONDON_MAX:
            return f"{pts(move)} · fade"
        return f"{pts(move)} · no trade"
    if spec["id"] == "thu":
        _, move = move_at(bars, day, 9 * 60 + 30, 10 * 60)
        if move is None:
            return "passed"
        return f"{pts(move)} · fade" if abs(move) >= SHOT_POINTS else f"{pts(move)} · no trade"
    if spec["id"] == "eleven":
        opened, move = move_at(bars, day, 9 * 60 + 30, 11 * 60)
        if move is None:
            return "passed"
        checked = bar_at(bars, "11:00", day)
        burst = None
        known = bar_at(bars, "10:55", day) is not None and checked is not None
        if known:
            burst = burst_of(bars, day, 10 * 60 + 55, checked["c"], move)
        return eleven_verdict(move, burst, weekday, known).replace(" · $1,100", "").replace(" · $660", "")
    _, move = move_at(bars, day, 13 * 60, 14 * 60 + 30)
    if move is None:
        return "passed"
    return f"{pts(move)} · with trend" if abs(move) >= PM_DRIVE_POINTS else f"{pts(move)} · no trade"


def next_readout(spec, minutes, bid, bars, day):
    if minutes < spec["open"]:
        return f"waits for {london_hhmm(spec['open'] // 60, spec['open'] % 60)} open"
    opened, move = move_at(bars, day, spec["open"], spec["ny"], bid)
    if opened is None or move is None:
        return "waiting for the open bar"
    return pts(move)


def hero_block(now, minutes, bid, bars):
    weekday = now.weekday()
    if weekday >= 5:
        return {
            "kicker": "Closed",
            "title": "No checks",
            "ny": "",
            "line": "Next is Monday 07:30 London fade",
            "countdown": "",
            "facts": [],
            "verdict": "",
        }
    specs = [s for s in windows_for(now) if weekday in s["days"]]
    nxt = next((s for s in specs if minutes < s["ny"] + 5), None)
    if nxt is None:
        tomorrow = now + timedelta(days=1)
        while tomorrow.weekday() >= 5:
            tomorrow += timedelta(days=1)
        first = windows_for(tomorrow)[0]
        when = london_hhmm(first["ny"] // 60, first["ny"] % 60, tomorrow)
        return {
            "kicker": "Done today",
            "title": "No more checks",
            "ny": "",
            "line": f"Next is {tomorrow.strftime('%a')} {when} London {first['name'].lower()}",
            "countdown": "",
            "facts": [],
            "verdict": "",
        }
    london = london_hhmm(nxt["ny"] // 60, nxt["ny"] % 60, now)
    ny = hhmm(nxt["ny"])
    block = {
        "kicker": "Checking now" if nxt["ny"] <= minutes < nxt["ny"] + 5 else "Next trade check",
        "title": f"{london} London",
        "ny": f"{ny} NY",
        "line": "",
        "countdown": clock_left(now, nxt["ny"] if minutes < nxt["ny"] else nxt["ny"] + 5),
        "facts": [],
        "verdict": "",
    }
    if minutes < nxt["open"]:
        open_london = london_hhmm(nxt["open"] // 60, nxt["open"] % 60, now)
        block["line"] = f"Waiting for {open_london} London open to set levels"
        return block
    day = now.strftime("%Y-%m-%d")
    opened, move = move_at(bars, day, nxt["open"], nxt["ny"], bid)
    if opened is None or move is None:
        block["line"] = "Waiting for the open bar"
        return block
    if nxt["id"] == "eleven":
        block["facts"] = eleven_facts(now, minutes, bid, bars, day, opened, move)
        known = minutes >= 10 * 60 + 55
        burst = burst_of(bars, day, 10 * 60 + 55, bid, move) if known else None
        block["verdict"] = f"If {london} hit now: " + eleven_verdict(move, burst, weekday, known)
        return block
    open_london = london_hhmm(nxt["open"] // 60, nxt["open"] % 60, now)
    block["facts"] = [
        {"k": f"{open_london} open", "v": px(opened)},
        {"k": "Price", "v": f"{px(bid)}   {pts(move)}"},
    ]
    if nxt["id"] == "london":
        block["facts"].append({"k": "Fade 5–30", "v": f"BUY ≤ {px(opened - LONDON_MIN)} · SELL ≥ {px(opened + LONDON_MIN)}"})
        fired = LONDON_MIN <= abs(move) < LONDON_MAX
        side = "BUY fade" if move < 0 else "SELL fade"
        block["verdict"] = f"If {london} hit now: {side if fired else 'no trade'}"
    elif nxt["id"] == "thu":
        block["facts"].append({"k": "Fade 60+", "v": f"BUY ≤ {px(opened - SHOT_POINTS)} · SELL ≥ {px(opened + SHOT_POINTS)}"})
        side = "BUY fade" if move < 0 else "SELL fade"
        block["verdict"] = f"If {london} hit now: {side if abs(move) >= SHOT_POINTS else 'no trade'}"
    else:
        block["facts"].append({"k": "Drive 80+", "v": f"BUY ≥ {px(opened + PM_DRIVE_POINTS)} · SELL ≤ {px(opened - PM_DRIVE_POINTS)}"})
        side = "BUY drive" if move > 0 else "SELL drive"
        block["verdict"] = f"If {london} hit now: {side if abs(move) >= PM_DRIVE_POINTS else 'no trade'}"
    return block


def eleven_facts(now, minutes, bid, bars, day, opened, move):
    fade_hi = opened + SHOT_POINTS
    fade_lo = opened + FALLBACK_MIN
    buy_hi = opened - FALLBACK_MIN
    buy_lo = opened - SHOT_POINTS
    if minutes < 10 * 60 + 55:
        burst = f"starts {london_hhmm(10, 55, now)} · max 55"
    else:
        value = burst_of(bars, day, 10 * 60 + 55, bid, move)
        burst = "—" if value is None else f"{value:+.1f} · max 55 for the trend"
    return [
        {"k": f"{london_hhmm(9, 30, now)} open", "v": px(opened)},
        {"k": "Price", "v": f"{px(bid)}   {pts(move)}"},
        {"k": "Fade 10–60", "v": f"SELL ≥ {px(fade_lo)} and < {px(fade_hi)} · BUY ≤ {px(buy_hi)} and > {px(buy_lo)}"},
        {"k": "Trend 60+", "v": f"BUY ≥ {px(fade_hi)} · SELL ≤ {px(buy_lo)}"},
        {"k": "10m", "v": burst},
    ]


def chart_levels(now, minutes, bars, bid, position):
    day = now.strftime("%Y-%m-%d")
    levels = []
    if position is not None:
        levels.append(level(position.price_open, "#ffffff", px(position.price_open)))
        if position.sl:
            levels.append(level(position.sl, "#f85149", px(position.sl)))
        if position.tp:
            levels.append(level(position.tp, "#3fb950", px(position.tp)))
    if minutes < 9 * 60 + 30:
        opened = bar_at(bars, "03:00", day)
        if opened:
            price = opened["o"]
            levels += [
                level(price, "#e3b341", px(price)),
                level(price + LONDON_MIN, "#8b949e", f"+{LONDON_MIN:.0f}", True),
                level(price - LONDON_MIN, "#8b949e", f"-{LONDON_MIN:.0f}", True),
                level(price + LONDON_MAX, "#58a6ff", f"+{LONDON_MAX:.0f}", True),
                level(price - LONDON_MAX, "#58a6ff", f"-{LONDON_MAX:.0f}", True),
            ]
        return levels
    opened = bar_at(bars, "09:30", day)
    if opened:
        price = opened["o"]
        levels += [
            level(price, "#e3b341", px(price)),
            level(price + FALLBACK_MIN, "#8b949e", "+10", True),
            level(price - FALLBACK_MIN, "#8b949e", "-10", True),
            level(price + SHOT_POINTS, "#58a6ff", "+60", True),
            level(price - SHOT_POINTS, "#58a6ff", "-60", True),
        ]
    pm_open = bar_at(bars, "13:00", day) if minutes >= 13 * 60 else None
    if pm_open and now.weekday() in (2, 3, 4):
        price = pm_open["o"]
        levels += [
            level(price, "#d2a8ff", px(price)),
            level(price + PM_DRIVE_POINTS, "#d2a8ff", "+80", True),
            level(price - PM_DRIVE_POINTS, "#d2a8ff", "-80", True),
        ]
    return levels


def position_view(position):
    if position is None:
        return None
    buy = position.type == mt5.POSITION_TYPE_BUY
    return {
        "symbol": position.symbol,
        "side": "buy" if buy else "sell",
        "volume": f"{float(position.volume):.2f}",
        "entry": px(position.price_open),
        "sl": px(position.sl) if position.sl else "—",
        "tp": px(position.tp) if position.tp else "—",
        "pnl": float(position.profit),
    }


def todays_fills(now, offset, tick_time):
    server_now = datetime.fromtimestamp(int(tick_time), timezone.utc).replace(tzinfo=None)
    deals = mt5.history_deals_get(server_now - timedelta(days=3), server_now + timedelta(hours=1)) or []
    rows = []
    closed = 0.0
    for deal in deals:
        if deal.symbol != SYMBOL or deal.type not in (0, 1):
            continue
        when = bar_ny(deal.time, offset)
        if when.date() != now.date():
            continue
        profit = float(deal.profit) + float(deal.commission) + float(deal.swap)
        closed += profit
        result = "in" if deal.entry == 0 else money_text(profit)
        rows.append({
            "time": london_from_ny(when),
            "side": "buy" if deal.type == 0 else "sell",
            "lots": f"{float(deal.volume):.2f}",
            "price": px(deal.price),
            "pnl": profit,
            "result": result,
            "sort": int(deal.time),
        })
    rows.sort(key=lambda row: row["sort"])
    for row in rows:
        row.pop("sort", None)
    return rows, closed


def money_text(value):
    sign = "+" if value > 0 else ""
    return f"{sign}${value:,.2f}"


def blank_snapshot(message):
    return {
        "london": "--:--:--",
        "ny": "--:--:--",
        "balance": None,
        "equity": None,
        "day_pnl": None,
        "trading": "LOCKED",
        "position": None,
        "hero": {"kicker": "Waiting", "title": message, "ny": "", "line": "", "countdown": "", "facts": [], "verdict": ""},
        "chart": {"bars": [], "levels": [], "bid": "—", "ask": "—", "spread": "—", "spread_wide": False},
        "windows": [],
        "fills": [],
    }


def snapshot_now():
    if mt5.terminal_info() is None and not mt5.initialize(timeout=1500):
        return blank_snapshot("MetaTrader is not connected")
    term = mt5.terminal_info()
    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.account_info()
    if tick is None:
        return blank_snapshot("Waiting for US100.cash")
    offset = server_offset_hours(tick.time)
    now = ny_now()
    uk = uk_now()
    minutes = now.hour * 60 + now.minute
    bid = float(tick.bid)
    ask = float(tick.ask)
    spread = ask - bid
    bars = chart_bars(SYMBOL, mt5.TIMEFRAME_M5, 220, offset)
    positions = [p for p in (mt5.positions_get(symbol=SYMBOL) or []) if p.magic == MAGIC]
    position = positions[0] if positions else None
    live = bool(term and term.connected and term.trade_allowed and info and info.trade_allowed and info.trade_expert)
    balance = float(info.balance) if info is not None else None
    equity = float(info.equity) if info is not None else None
    fills, closed = todays_fills(now, offset, tick.time)
    floating = sum(float(p.profit) for p in positions)
    today = bars[-1]["day"] if bars else ""
    session = [b for b in bars if b["day"] == today]
    return {
        "london": uk.strftime("%H:%M:%S"),
        "ny": now.strftime("%H:%M:%S"),
        "balance": balance,
        "equity": equity,
        "day_pnl": None if balance is None else closed + floating,
        "trading": "LIVE" if live else "LOCKED",
        "position": position_view(position),
        "hero": hero_block(now, minutes, bid, bars),
        "chart": {
            "bars": session[-96:] or bars[-96:],
            "levels": chart_levels(now, minutes, bars, bid, position),
            "bid": px(bid),
            "ask": px(ask),
            "spread": f"{spread:.2f}",
            "spread_wide": spread > SPREAD_CAP,
        },
        "windows": window_rows(now, minutes, bid, bars),
        "fills": fills,
    }


_snapshot_lock = threading.Lock()
_snapshot_busy = False
_last_snapshot = None


def snapshot():
    global _snapshot_busy, _last_snapshot
    with _snapshot_lock:
        if _snapshot_busy:
            return _last_snapshot or blank_snapshot("MetaTrader is refreshing")
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
        return _last_snapshot or blank_snapshot("MetaTrader is refreshing")
    if box.get("error"):
        return blank_snapshot("MetaTrader is not connected")
    value = box.get("value") or blank_snapshot("MetaTrader is not connected")
    if value.get("chart", {}).get("bars"):
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
        if self.path.startswith("/report.pdf"):
            pdf_path = Path(__file__).with_name("US100_2026_Backtest_Report.pdf")
            if pdf_path.exists():
                body = pdf_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Disposition", 'inline; filename="US100_2026_Backtest_Report.pdf"')
                self.end_headers()
                self.wfile.write(body)
                return
        if self.path.startswith("/report"):
            html_path = Path(__file__).with_name("US100_2026_Backtest_Report.html")
            if html_path.exists():
                body = html_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
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
