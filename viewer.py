"""Live view of the pass bot. Nasdaq and gold, side by side. Read only. Sends no orders.

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
RIDE_RISK = 400.0
GOLD = "XAUUSD"
GOLD_MIN = 1.20
GOLD_RISK = 250.0
HOST = "0.0.0.0"
PORTS = (8765, 18765)
JOURNAL = Path(r"C:\Users\user\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\logs")

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pass bot</title>
<style>
  html, body { margin: 0; height: 100%; background: #1c2024; color: #c0c0c0; font: 12px Tahoma, sans-serif; }
  body { display: flex; flex-direction: column; min-height: 100vh; }
  header { display: flex; justify-content: space-between; gap: 16px; align-items: center; padding: 5px 10px; background: #2a2e32; border-bottom: 1px solid #000; color: #fff; }
  header b { color: #fff; font-weight: 600; }
  .bad { color: #ff5252; }
  .good { color: #00c000; }
  .board { background: #000; border-bottom: 1px solid #000; }
  .board h2 { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
  .board h2 .when { font-weight: 400; color: #fff; }
  .board h2 .clock { font-weight: 400; color: #fff; }
  .pulse { width: 7px; height: 7px; border-radius: 50%; background: #00c000; display: inline-block; margin-left: 8px; vertical-align: middle; animation: pulse 1.6s ease-in-out infinite; }
  @keyframes pulse { 50% { opacity: 0.25; } }
  .boardline { margin: 0; padding: 8px 12px; color: #fff; background: #000; border-bottom: 1px solid #222; line-height: 1.45; }
  .ideas { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; }
  .idea { min-width: 0; padding: 10px 12px 12px; background: #000; border-right: 1px solid #222; border-top: 2px solid #2a2e32; }
  .idea.weighing { border-top-color: #fff; }
  .idea.ready.buy { border-top-color: #1e88e5; }
  .idea.ready.sell { border-top-color: #e53935; }
  .idea.in { border-top-color: #fff; }
  .idea-top { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; padding-bottom: 6px; border-bottom: 1px solid #222; }
  .idea h3 { margin: 0; color: #fff; font: 600 13px Tahoma, sans-serif; }
  .state { color: #b0b0b0; font: 600 12px Tahoma, sans-serif; white-space: nowrap; }
  .state.close { color: #ffd700; }
  .state.ready.buy { color: #1e88e5; }
  .state.ready.sell { color: #e53935; }
  .state.in { color: #fff; }
  .lead { margin: 8px 0; color: #fff; line-height: 1.4; }
  .facts { display: grid; grid-template-columns: 1fr 1fr; gap: 7px 12px; margin: 0 0 8px; }
  .fact span { display: block; color: #808080; }
  .fact b { display: block; margin-top: 1px; color: #fff; font-weight: 600; font-size: 13px; }
  .fact b.tick, .clock.tick { animation: settle 0.9s ease; }
  @keyframes settle { from { color: #ffd700; } to { color: #fff; } }
  .idea p { margin: 0 0 4px; color: #c0c0c0; line-height: 1.45; }
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: #000; height: 34vh; min-height: 220px; }
  .chartbox { display: flex; flex-direction: column; min-width: 0; background: #000; }
  .charthead { display: flex; justify-content: space-between; gap: 8px; padding: 4px 8px; background: #2a2e32; color: #fff; }
  .charthead .px { color: #fff; }
  .charthead .px b { font-weight: 600; }
  .chartwrap { position: relative; flex: 1; min-height: 0; background: #000; }
  svg { width: 100%; height: 100%; display: block; background: #000; }
  .corner { position: absolute; left: 8px; top: 6px; color: #fff; white-space: pre; line-height: 1.35; text-shadow: 1px 1px 0 #000; pointer-events: none; }
  .desk { display: grid; grid-template-columns: 1fr; gap: 1px; background: #000; }
  .panel { background: #000; min-width: 0; }
  h2 { margin: 0; padding: 6px 10px; background: #2a2e32; color: #fff; font: 600 12px Tahoma, sans-serif; }
  .side.buy { color: #1e88e5; }
  .side.sell { color: #e53935; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; color: #9a9a9a; font-weight: 400; padding: 6px 8px; background: #141414; }
  td { padding: 7px 8px; border-top: 1px solid #222; color: #e0e0e0; }
  td.up { color: #1e88e5; }
  td.down { color: #e53935; }
  td.pnl { font-weight: 600; font-size: 13px; }
  td.pnl.tick { animation: pnlflash 0.9s ease; }
  @keyframes pnlflash { from { background: #2a2e32; } to { background: transparent; } }
  #tradebox { border-bottom: 1px solid #000; }
  .empty { padding: 12px; color: #9a9a9a; }
  #journal { background: #000; border-top: 1px solid #222; max-height: 132px; overflow: auto; }
  #lines { padding: 4px 10px 8px; }
  .jrow { display: flex; gap: 14px; padding: 3px 0; }
  .jrow span { color: #8a8a8a; min-width: 52px; }
  .jrow b { font-weight: 400; color: #d0d0d0; }
  .jrow.buy b { color: #00c000; }
  .jrow.reject b { color: #ff5252; }
  @media (max-width: 980px) {
    .charts, .ideas, .facts { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<header>
  <div id="symbol">Pass bot</div>
  <div id="account"></div>
</header>
<section class="board">
  <h2><span>Thinking</span><span class="when"><span class="clock" id="clock"></span><i class="pulse"></i></span></h2>
  <p class="boardline" id="board">Reading the terminal.</p>
  <div class="ideas" id="think"></div>
</section>
<section class="desk" id="tradebox">
  <section class="panel">
    <h2>Trade</h2>
    <div id="trades"><div class="empty">No open trade.</div></div>
  </section>
</section>
<section class="charts">
  <div class="chartbox">
    <div class="charthead" id="head-nas"><span>US100.cash, M5</span></div>
    <div class="chartwrap">
      <svg id="chart-nas" viewBox="0 0 640 420" preserveAspectRatio="none"></svg>
      <div class="corner" id="note-nas"></div>
    </div>
  </div>
  <div class="chartbox">
    <div class="charthead" id="head-gold"><span>XAUUSD, M1</span></div>
    <div class="chartwrap">
      <svg id="chart-gold" viewBox="0 0 640 420" preserveAspectRatio="none"></svg>
      <div class="corner" id="note-gold"></div>
    </div>
  </div>
</section>
<section id="journal">
  <h2>Journal</h2>
  <div id="lines"></div>
</section>
<script>
function esc(s) {
  return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;");
}
function htag(parts, y, price, color, text, x0, x1, dash) {
  const yy = y(price);
  const dashAttr = dash ? ' stroke-dasharray="3 3"' : "";
  parts.push('<line x1="'+x0+'" x2="'+x1+'" y1="'+yy+'" y2="'+yy+'" stroke="'+color+'" stroke-width="1"'+dashAttr+'/>');
  const w = Math.max(46, text.length * 7);
  parts.push('<rect x="'+(x1+2)+'" y="'+(yy-8)+'" width="'+w+'" height="16" fill="'+color+'"/>');
  parts.push('<text x="'+(x1+2+w/2)+'" y="'+(yy+4)+'" fill="#000" font-size="11" text-anchor="middle" font-family="Tahoma">'+text+'</text>');
}
function draw(id, chart) {
  const svg = document.getElementById(id);
  const bars = (chart && chart.bars) || [];
  if (!bars.length) { svg.innerHTML = ""; return; }
  const levels = chart.levels || [];
  const left = 6, right = 560, top = 14, bottom = 392;
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
    parts.push('<line x1="'+left+'" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" stroke="#292929"/>');
    parts.push('<text x="568" y="'+(yy+4)+'" fill="#808080" font-size="11" font-family="Tahoma">'+p.toFixed(2)+'</text>');
  }
  const step = Math.max(8, Math.round(bars.length / 5));
  for (let i = 0; i < bars.length; i += step) {
    const x = left + i * cw;
    parts.push('<line x1="'+x+'" x2="'+x+'" y1="'+top+'" y2="'+bottom+'" stroke="#292929"/>');
    parts.push('<text x="'+(x+2)+'" y="412" fill="#808080" font-size="11" font-family="Tahoma">'+bars[i].t+'</text>');
  }
  bars.forEach((b, i) => {
    const x = left + i * cw + cw * 0.5;
    const up = b.c >= b.o;
    const color = "#ffffff";
    parts.push('<line x1="'+x+'" x2="'+x+'" y1="'+y(b.h)+'" y2="'+y(b.l)+'" stroke="'+color+'" stroke-width="1"/>');
    const topY = y(Math.max(b.o, b.c));
    const botY = y(Math.min(b.o, b.c));
    const fill = up ? "#000000" : "#ffffff";
    parts.push('<rect x="'+(x-Math.max(1, cw*0.32))+'" y="'+topY+'" width="'+Math.max(1, cw*0.64)+'" height="'+Math.max(1, botY-topY)+'" fill="'+fill+'" stroke="'+color+'"/>');
  });
  levels.forEach(level => {
    if (!level.price) return;
    htag(parts, y, level.price, level.color, esc(level.label), left, right, level.dash);
    if (level.name) {
      const yy = y(level.price);
      parts.push('<text x="'+(left+4)+'" y="'+(yy-4)+'" fill="'+level.color+'" font-size="11" font-family="Tahoma">'+esc(level.name)+'</text>');
    }
  });
  svg.innerHTML = parts.join("");
}
function head(id, chart) {
  const el = document.getElementById(id);
  if (!chart) { el.innerHTML = ""; return; }
  el.innerHTML = "<span>" + esc(chart.title) + "</span><span class='px'>Bid <b>" + esc(chart.bid) + "</b>  Ask <b>" + esc(chart.ask) + "</b></span>";
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
  document.getElementById("symbol").textContent = "Pass bot   " + (data.symbol_line || "");
  document.getElementById("account").innerHTML = data.account_html || "";
  const clock = document.getElementById("clock");
  const clockText = data.symbol_line || "";
  if (clock.textContent !== clockText) {
    clock.textContent = clockText;
    clock.classList.remove("tick");
    void clock.offsetWidth;
    clock.classList.add("tick");
  }
  document.getElementById("board").textContent = data.board || "";
  const charts = {};
  (data.charts || []).forEach(chart => { charts[chart.id] = chart; });
  head("head-nas", charts.nas);
  head("head-gold", charts.gold);
  document.getElementById("note-nas").textContent = charts.nas ? (charts.nas.note || "") : "";
  document.getElementById("note-gold").textContent = charts.gold ? (charts.gold.note || "") : "";
  draw("chart-nas", charts.nas);
  draw("chart-gold", charts.gold);
  const root = document.getElementById("think");
  root.innerHTML = (data.thinking || []).map(card => {
    const side = card.side ? " " + esc(card.side) : "";
    const weighing = (card.state === "Watching" || card.state === "Getting close" || card.state === "Ready" || card.state === "In a trade") ? " weighing" : "";
    const facts = (card.facts || []).map(fact => {
      return "<div class='fact'><span>" + esc(fact.label) + "</span><b class='live' data-k='" + esc(card.id) + ":" + esc(fact.label) + "'>" + esc(fact.value) + "</b></div>";
    }).join("");
    const lines = (card.lines || []).map(line => "<p>" + esc(line) + "</p>").join("");
    return "<article class='idea" + weighing + " " + esc(card.tone || "") + side + "' id='idea-" + esc(card.id) + "'><div class='idea-top'><h3>" + esc(card.name) + "</h3><span class='state " + esc(card.tone || "") + side + "'>" + esc(card.state) + "</span></div><p class='lead'>" + esc(card.lead || "") + "</p><div class='facts'>" + facts + "</div>" + lines + "</article>";
  }).join("");
  markTicks(root);
  const trades = data.trades || [];
  const box = document.getElementById("trades");
  if (!trades.length) {
    box.innerHTML = "<div class='empty'>No open trade.</div>";
  } else {
    const rows = trades.map(row => {
      const cls = row.profit > 0 ? "up" : (row.profit < 0 ? "down" : "");
      const word = row.side === "buy" ? "buy" : "sell";
      const key = esc(row.ticket || row.symbol);
      return "<tr><td>" + esc(row.symbol) + "</td><td class='side " + esc(row.side) + "'>" + word + "</td><td>" + esc(row.volume) + "</td><td>" + esc(row.price) + "</td><td data-k='" + key + ":current'>" + esc(row.current) + "</td><td>" + esc(row.sl) + "</td><td>" + esc(row.tp) + "</td><td class='pnl " + cls + "' data-k='" + key + ":profit'>" + esc(row.profit_text) + "</td></tr>";
    }).join("");
    box.innerHTML = "<table><tr><th>Symbol</th><th>Type</th><th>Volume</th><th>Open</th><th>Current</th><th>S / L</th><th>T / P</th><th>Profit</th></tr>" + rows + "</table>";
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
    document.getElementById("symbol").textContent = "Pass bot";
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
        return word, f"{word} {lot_words(volume)} at {float(price):.2f}"
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
        return "change", f"Stop moved to {float(stop):.2f}. Target left at {float(target):.2f}."
    return None


def journal_lines():
    day = datetime.now().strftime("%Y%m%d")
    path = JOURNAL / f"{day}.log"
    if not path.exists():
        return [{"time": "", "text": "No journal for today.", "kind": ""}]
    events = []
    for line in decode_log(path).splitlines():
        if "\tTrades\t" not in line:
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        clock = parts[2].split(".")[0][:-3]
        parsed = plain_trade(parts[-1].split(": ", 1)[-1])
        if parsed is None:
            continue
        kind, text = parsed
        events.append({"time": clock, "text": text, "kind": "buy" if kind == "Bought" else "sell" if kind == "Sold" else kind})
    if not events:
        return [{"time": "", "text": "No orders yet today.", "kind": ""}]
    folded = []
    for event in events:
        if (
            folded
            and event["kind"] == "reject"
            and folded[-1]["kind"] == "reject"
            and folded[-1]["text"] == event["text"]
        ):
            folded[-1]["count"] += 1
            folded[-1]["end"] = event["time"]
            continue
        event["count"] = 1
        event["end"] = event["time"]
        folded.append(event)
    rows = []
    for event in folded[-8:]:
        when = event["time"] if event["count"] == 1 else f"{event['time']}–{event['end']}"
        text = event["text"]
        if event["count"] > 1 and event["kind"] == "reject":
            text = f"{event['count']} orders rejected. Trading was switched off on the old login."
        rows.append({"time": when, "text": text, "kind": event["kind"]})
    return rows


def lots(risk, distance):
    if distance <= 0:
        return 0.0
    step = 0.01
    return math.floor((risk / distance) / step + 1e-8) * step


def ny_now():
    return datetime.now(timezone.utc) + timedelta(hours=-4)


def bar_ny(bar_time, offset_hours):
    real_utc = datetime.fromtimestamp(int(bar_time) - offset_hours * 3600, timezone.utc)
    return real_utc + timedelta(hours=-4)


def server_offset_hours(tick_time):
    delta = int(tick_time) - datetime.now(timezone.utc).timestamp()
    return int(round(delta / 3600.0))


def order_from(side, bid, ask, stop, target, risk, comment):
    price = ask if side == "buy" else bid
    if side == "buy":
        sl = price - stop
        tp = price + target
    else:
        sl = price + stop
        tp = price - target
    return {
        "symbol": "US100.cash",
        "side": side,
        "volume": f"{lots(risk, stop):.2f}",
        "sl": f"{sl:.2f}",
        "tp": f"{tp:.2f}",
        "comment": comment,
        "sl_price": sl,
        "tp_price": tp,
        "entry_price": price,
    }


def ride_order(bars, bid, ask):
    closed = bars[:-1]
    if len(closed) < 6:
        return None, "Ride is waiting for a half hour of bars."
    window = closed[-6:]
    net = window[-1]["c"] - window[0]["o"]
    if abs(net) < 12:
        return None, f"Ride is off. The last half hour moved {net:+.1f}. It needs 12."
    buy = net > 0
    if buy:
        pullback = max(bar["h"] for bar in window) - window[-1]["c"]
    else:
        pullback = window[-1]["c"] - min(bar["l"] for bar in window)
    if pullback > abs(net) * 0.5:
        return None, "Ride is off. The move has given back half."
    bite = min(25.0, max(8.0, abs(net) * 0.40))
    stop = min(20.0, max(8.0, pullback + 2.0))
    if bite < stop:
        return None, "Ride is off. The bite is smaller than the stop."
    side = "buy" if buy else "sell"
    word = "Buy" if buy else "Sell"
    ticket = order_from(side, bid, ask, stop, bite, RIDE_RISK, "ORB ride")
    return ticket, f"{word} the ride. The last half hour already moved {net:+.1f}."


def wanted_order(move, minutes, bars, bid, ask, shot_day, now=None):
    wd = now.weekday() if now is not None else 0
    if 3 * 60 <= minutes < 3 * 60 + 35:
        op3 = open_0300(bars)
        if op3 is not None:
            mv_lon = bid - op3
            if LONDON_MIN <= abs(mv_lon) < LONDON_MAX:
                side = "sell" if mv_lon > 0 else "buy"
                word = "Buy" if side == "buy" else "Sell"
                return order_from(side, bid, ask, LONDON_STOP, LONDON_TARGET, LONDON_RISK, "ORB london"), f"{word} the 08:30 UK (03:30 NY) London range-fade ({mv_lon:+.1f} pts, $600)."
            return None, f"Watching 08:30 UK (03:30 NY) London open: {mv_lon:+.1f} pts (fades 5..30 pt move)."
    if move is None:
        if shot_day:
            return None, "Waiting for the 09:30 New York open (after 08:30 UK London setup)."
        return None, "Waiting for the 09:30 open. Today has the 11:00 range-fade ($600)."
    if wd == 3 and minutes < 10 * 60:
        if abs(move) < SHOT_POINTS:
            return None, f"Thursday 10:00 fade. The open has moved {move:+.1f}. It needs 60."
        side = "sell" if move > 0 else "buy"
        word = "Sell" if side == "sell" else "Buy"
        return order_from(side, bid, ask, SHOT_STOP, SHOT_TARGET, SHOT_RISK, "ORB day"), f"{word} the Thursday 10:00 fade ($1,000)."
    if minutes < 11 * 60:
        if shot_day and abs(move) >= SHOT_POINTS:
            side = "buy" if move > 0 else "sell"
            word = "Buy" if side == "buy" else "Sell"
            return order_from(side, bid, ask, SHOT_STOP, SHOT_TARGET, SHOT_RISK, "ORB day"), f"{word} the 11:00 trend shot ($1,100)."
        if wd in (0, 1, 2) and FALLBACK_MIN <= abs(move) < SHOT_POINTS:
            side = "sell" if move > 0 else "buy"
            word = "Buy" if side == "buy" else "Sell"
            return order_from(side, bid, ask, FALLBACK_STOP, FALLBACK_TARGET, FALLBACK_RISK, "ORB daily"), f"{word} the 11:00 range-fade (Mon/Tue/Wed). Stop 20, target 120, $660."
        return None, "11:00 trade is waiting for a 60-pt trend shot (or Mon/Tue/Wed 10..60 pt fade)."
    if wd in (2, 3, 4) and 13 * 60 <= minutes < 14 * 60 + 35:
        op13 = open_1300(bars)
        if op13 is not None:
            mv_pm = bid - op13
            if abs(mv_pm) >= PM_DRIVE_POINTS:
                side = "buy" if mv_pm > 0 else "sell"
                word = "Buy" if side == "buy" else "Sell"
                return order_from(side, bid, ask, PM_DRIVE_STOP, PM_DRIVE_TARGET, PM_DRIVE_RISK, "ORB daily"), f"{word} the 14:30 afternoon drive ({mv_pm:+.1f} from 13:00, $600)."
            return None, f"Watching 14:30 afternoon drive: {mv_pm:+.1f} from 13:00 (needs 80 pts)."
    return None, "Morning window complete. Watching 14:30 afternoon drive (Wed/Thu/Fri) if flat."


def position_ticket(position, bid, ask):
    buy = position.type == mt5.POSITION_TYPE_BUY
    comment = (position.comment or "").strip() or "open trade"
    return {
        "symbol": position.symbol,
        "side": "buy" if buy else "sell",
        "volume": f"{float(position.volume):.2f}",
        "sl": f"{float(position.sl):.2f}" if position.sl else "-",
        "tp": f"{float(position.tp):.2f}" if position.tp else "-",
        "comment": comment,
        "sl_price": float(position.sl) or None,
        "tp_price": float(position.tp) or None,
        "entry_price": float(position.price_open),
        "profit": float(position.profit),
        "bid": f"{bid:.2f}",
        "ask": f"{ask:.2f}",
    }


def empty_ticket(bid, ask):
    return {
        "symbol": "US100.cash",
        "side": "",
        "volume": "-",
        "sl": "-",
        "tp": "-",
        "comment": "-",
        "bid": f"{bid:.2f}" if bid else "-",
        "ask": f"{ask:.2f}" if ask else "-",
        "execution": "Market Execution",
        "ok": True,
        "status": "No order. The bot is flat.",
    }


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
    levels = [level(position.price_open, "#ffffff", f"{float(position.price_open):.2f}", name="entry")]
    if position.sl:
        levels.append(level(position.sl, "#ff3b30", f"{float(position.sl):.2f}", name="stop"))
    if position.tp:
        levels.append(level(position.tp, "#00c000", f"{float(position.tp):.2f}", name="target"))
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
        "sl": f"{float(position.sl):.2f}" if position.sl else "",
        "tp": f"{float(position.tp):.2f}" if position.tp else "",
        "profit": profit,
        "profit_text": f"{profit:,.2f}",
    }


def ohlc_line(bar):
    if not bar:
        return ""
    return f"O {bar['o']:.2f}  H {bar['h']:.2f}  L {bar['l']:.2f}  C {bar['c']:.2f}"


def day_name(now):
    return ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")[now.weekday()]


def next_shot_day(now):
    ahead = {1: "Wednesday", 5: "Monday", 6: "Monday"}
    return ahead.get(now.weekday(), "Monday")


def shot_day(now):
    return now.weekday() in (0, 2, 3, 4)


def fade10_day(now):
    return now.weekday() == 3


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
        return f"{hours} h {minutes} min {seconds} sec"
    if minutes:
        return f"{minutes} min {seconds} sec"
    return f"{seconds} sec"


def bar_closes_in(now, start_minute):
    now_s = now.hour * 3600 + now.minute * 60 + now.second
    start_s = start_minute * 60
    if now_s < start_s or now_s >= start_s + 300:
        return None
    return f"{start_s + 300 - now_s} sec"


def price_text(value):
    return f"{value:,.2f}"


def open_930(bars):
    for bar in bars:
        if bar["t"] == "09:30":
            return bar["o"]
    return None


def open_0300(bars):
    for bar in bars:
        if bar["t"] == "03:00":
            return bar["o"]
    return None


def open_1300(bars):
    for bar in bars:
        if bar["t"] == "13:00":
            return bar["o"]
    return None


def half_hour_move(bars):
    closed = bars[:-1]
    if len(closed) < 6:
        return None
    window = closed[-6:]
    return window[-1]["c"] - window[0]["o"]


def comment_of(position):
    return (position.comment or "").lower() if position is not None else ""


def nasdaq_role(position, now):
    if position is None:
        return None
    if owns(position, "hop"):
        return "hop"
    if owns(position, "fallback"):
        return "fallback"
    if owns(position, "shots"):
        return "shots"
    return "shots" if shot_day(now) else "fallback"


def owns(position, key):
    text = comment_of(position)
    if position is None:
        return False
    if key == "fallback":
        return "daily" in text
    if key == "hop":
        return "ride" in text
    if key == "shots":
        return "orb am" in text or "orb day" in text
    if key == "gold":
        return "gold" in text
    return False


def idea(id_name, name, state, side, lead, facts, lines):
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
        "state": state,
        "tone": tone,
        "side": side or "",
        "lead": lead,
        "facts": facts,
        "lines": lines,
    }


def trade_facts(position, bid):
    side = "buy" if position.type == mt5.POSITION_TYPE_BUY else "sell"
    word = "Buy" if side == "buy" else "Sell"
    return side, word, [
        {"label": "Bid", "value": price_text(bid)},
        {"label": "Entry", "value": price_text(float(position.price_open))},
        {"label": "Stop", "value": price_text(float(position.sl)) if position.sl else "—"},
        {"label": "Target", "value": price_text(float(position.tp)) if position.tp else "—"},
        {"label": "Open result", "value": f"{float(position.profit):+,.2f}"},
        {"label": "Volume", "value": f"{float(position.volume):.2f}"},
    ]


def move_words(move, need):
    if move is None:
        return "The 09:30 open is not on the chart yet."
    gone = abs(move)
    way = "above" if move > 0 else "below" if move < 0 else "on"
    short = need - gone
    if move == 0:
        return f"Price is on the 09:30 open. It needs {need:.1f} points."
    if short > 0:
        return f"Price is {gone:.1f} points {way} the open, {short:.1f} short of {need:.0f}."
    return f"Price is {gone:.1f} points {way} the open. That clears {need:.0f}."


def near_level(move, need):
    if move is None:
        return "Watching"
    if abs(move) >= need:
        return "met"
    if abs(move) >= need * 0.67:
        return "Getting close"
    return "Watching"


def board_line(now, ideas):
    verbs = {
        "Watching": ("is watching", "are watching"),
        "Getting close": ("is getting close", "are getting close"),
        "Ready": ("is ready", "are ready"),
        "In a trade": ("is in a trade", "are in a trade"),
        "Passed": ("has passed", "have passed"),
        "Standing aside": ("is standing aside", "are standing aside"),
    }
    parts = []
    for item in ideas:
        plural = item["name"] == "Nasdaq shots"
        parts.append(f"{item['name']} {verbs[item['state']][1 if plural else 0]}")
    return f"{day_name(now)}. " + ". ".join(parts) + "."


def shots_idea(now, minutes, bid, bars, position, trading):
    move = None if open_930(bars) is None else bid - open_930(bars)
    if nasdaq_role(position, now) == "shots":
        side, word, facts = trade_facts(position, bid)
        return idea(
            "shots", "Nasdaq shots", "In a trade", side,
            f"{word} {float(position.volume):.2f} lots from {price_text(float(position.price_open))}.",
            facts,
            ["Red line is the stop. Green line is the target. 40% off at +1R & -0.60R cushion (+4R locks +1.5R, $1,100 risk)."],
        )
    if not shot_day(now):
        return idea(
            "shots", "Nasdaq shots", "Standing aside", "",
            f"Today is {day_name(now)}. Trend shots run on Mon, Wed, Thu, and Fri.",
            [
                {"label": "Bid", "value": price_text(bid)},
                {"label": "Needs", "value": "60 points"},
                {"label": "Next", "value": next_shot_day(now)},
                {"label": "From the open", "value": "—" if move is None else f"{move:+.1f}"},
            ],
            ["Thu 10:00 fades a 60+ pt move. Mon/Wed/Thu/Fri 11:00 rides a 60+ pt move."],
        )
    if minutes >= 11 * 60 + 5:
        return idea(
            "shots", "Nasdaq shots", "Passed", "",
            move_words(move, SHOT_POINTS),
            [
                {"label": "Bid", "value": price_text(bid)},
                {"label": "From the open", "value": "—" if move is None else f"{move:+.1f}"},
                {"label": "Needed", "value": "60 points"},
                {"label": "Window", "value": "closed"},
            ],
            ["The morning shot window has closed for today."],
        )
    weighing_11 = (not fade10_day(now)) or (minutes >= 10 * 60 + 5)
    start = 11 * 60 if weighing_11 else 10 * 60
    closes = bar_closes_in(now, start)
    level = near_level(move, SHOT_POINTS)
    if closes and level == "met":
        state = "Ready"
        side = ("buy" if move > 0 else "sell") if weighing_11 else ("sell" if move > 0 else "buy")
        word = "Buy" if side == "buy" else "Sell"
        action = "with the move" if weighing_11 else "the Thursday fade"
        lead = f"Ready to {word.lower()} {action}."
    elif level == "met":
        state, side = "Getting close", ""
        lead = move_words(move, SHOT_POINTS) + " Waiting for the bar to close."
    elif level == "Getting close":
        state, side = "Getting close", ""
        lead = move_words(move, SHOT_POINTS)
    else:
        state, side = "Watching", ""
        lead = move_words(move, SHOT_POINTS)
    when = "11:00 goes with a 60+ pt move" if weighing_11 else "Thursday 10:00 fades a 60+ pt move"
    facts = [
        {"label": "Bid", "value": price_text(bid)},
        {"label": "From the open", "value": "—" if move is None else f"{move:+.1f}"},
        {"label": "Short of 60", "value": "—" if move is None else f"{max(0.0, SHOT_POINTS - abs(move)):.1f}"},
        {"label": "Bar closes" if closes else f"{'11:00' if weighing_11 else '10:00'} in", "value": closes or clock_left(now, start)},
    ]
    lines = [f"{when}. Stop {SHOT_STOP:.0f}, target {SHOT_TARGET:.0f}, risk ${SHOT_RISK:.0f}."]
    if weighing_11 and fade10_day(now) and minutes >= 10 * 60 + 5:
        lines.append("The Thursday 10:00 fade has passed.")
    if state == "Ready" and not trading:
        lines.append("Trading is off on this login, so no order will be sent.")
    return idea("shots", "Nasdaq shots", state, side, lead, facts, lines)


def morning_pullback(bars, move, price):
    seen = False
    extreme = None
    buy = move > 0
    for bar in bars:
        if bar["t"] == "09:30":
            seen = True
        if not seen:
            continue
        if extreme is None:
            extreme = bar["h"] if buy else bar["l"]
        else:
            extreme = max(extreme, bar["h"]) if buy else min(extreme, bar["l"])
    if extreme is None:
        return None
    if buy:
        return max(extreme, price) - price
    return price - min(extreme, price)


def fallback_idea(now, minutes, bid, bars, position, trading):
    opened = open_930(bars)
    move = None if opened is None else bid - opened
    role = nasdaq_role(position, now)
    if role == "fallback":
        side, word, facts = trade_facts(position, bid)
        return idea(
            "fallback", "11:00 range-fade", "In a trade", side,
            f"{word} {float(position.volume):.2f} lots from {price_text(float(position.price_open))}.",
            facts,
            ["Half-shot ($660 risk). Stop 20, target 120 (or 100 on 14:30 afternoon drive)."],
        )
    if now.weekday() >= 5 or now.weekday() in (3, 4):
        return idea(
            "fallback", "11:00 range-fade", "Standing aside", "",
            "The Nasdaq session is closed for the weekend." if now.weekday() >= 5 else "11:00 range-fade is Mon/Tue/Wed only (Thu/Fri reserved for 60+ pt shots).",
            [{"label": "Bid", "value": price_text(bid)}, {"label": "Band", "value": "10..60 pts"}, {"label": "Stop", "value": "20"}, {"label": "Target", "value": "120"}],
            ["Fades a 10..60 point morning range back toward the 09:30 open at 11:00 NY on Mon/Tue/Wed ($660 risk)."],
        )
    if role == "shots":
        return idea(
            "fallback", "11:00 range-fade", "Standing aside", "",
            "A $1,000 Nasdaq shot has the account.",
            [
                {"label": "Bid", "value": price_text(bid)},
                {"label": "From the open", "value": "—" if move is None else f"{move:+.1f}"},
                {"label": "Band", "value": "10..60 pts"},
                {"label": "11:00 in", "value": clock_left(now, 11 * 60)},
            ],
            ["The $600 range-fade waits unless the account is flat."],
        )
    if shot_day(now) and move is not None and abs(move) >= SHOT_POINTS and minutes <= 11 * 60 + 4:
        return idea(
            "fallback", "11:00 range-fade", "Standing aside", "",
            "Morning move is 60+ points — that belongs to the $1,000 trend shot.",
            [
                {"label": "Bid", "value": price_text(bid)},
                {"label": "From the open", "value": f"{move:+.1f}"},
                {"label": "Band", "value": "10..60 pts"},
                {"label": "Regime", "value": "Breakout (>=60)"},
            ],
            ["When 09:30->11:00 clears 60 points, we ride the breakout ($1,000). When it stays in 10..60 pts, we fade the range ($600)."],
        )
    if minutes >= 11 * 60 + 5:
        return idea(
            "fallback", "11:00 range-fade", "Passed", "",
            move_words(move, FALLBACK_MIN) if move is not None else "The 11:00 bar has closed.",
            [
                {"label": "Bid", "value": price_text(bid)},
                {"label": "From the open", "value": "—" if move is None else f"{move:+.1f}"},
                {"label": "Band", "value": "10..60 pts"},
                {"label": "Window", "value": "closed"},
            ],
            ["The 11:00 decision has passed for today."],
        )
    in_band = move is not None and FALLBACK_MIN <= abs(move) < SHOT_POINTS
    closes = bar_closes_in(now, 11 * 60)
    if closes and in_band:
        side = "sell" if move > 0 else "buy"
        word = "buy" if side == "buy" else "sell"
        state, lead = "Ready", f"Ready to {word} (fade) the 11:00 range move ($600)."
    elif in_band and minutes >= 10 * 60 + 30:
        state, side = "Getting close", ""
        lead = f"Price is {move:+.1f} pts from the 09:30 open (inside the 10..60 pt fade band)."
    else:
        state, side = "Watching", ""
        lead = "Waiting for the 09:30 New York open." if move is None else f"Price is {move:+.1f} pts from 09:30 (fade band is 10..60 pts)."
    lines = ["When 09:30->11:00 stays between 10 and 60 points, fade it back toward the open. Stop 20, target 120, risk $600."]
    if state == "Ready" and not trading:
        lines.append("Trading is off on this login, so no order will be sent.")
    return idea(
        "fallback", "11:00 range-fade", state, side, lead,
        [
            {"label": "Bid", "value": price_text(bid)},
            {"label": "From the open", "value": "—" if move is None else f"{move:+.1f}"},
            {"label": "Band", "value": "10..60 pts"},
            {"label": "11:00 in" if not closes else "Bar closes", "value": closes or clock_left(now, 11 * 60)},
        ],
        lines,
    )


def hop_idea(now, bid, bars, position):
    op13 = open_1300(bars)
    mv_pm = None if op13 is None else bid - op13
    move_text = "—" if mv_pm is None else f"{mv_pm:+.1f}"
    minutes = now.hour * 60 + now.minute
    if owns(position, "hop"):
        side, word, facts = trade_facts(position, bid)
        return idea(
            "hop", "14:30 afternoon drive", "In a trade", side,
            f"{word} {float(position.volume):.2f} lots from {price_text(float(position.price_open))}.",
            facts,
            ["Afternoon continuation ($600 risk, stop 20, target 100)."],
        )
    if not pm_drive_day(now):
        return idea(
            "hop", "14:30 afternoon drive", "Standing aside", "",
            f"Today is {day_name(now)}. The 14:30 drive runs Wed, Thu, and Fri.",
            [
                {"label": "Bid", "value": price_text(bid)},
                {"label": "Since 13:00", "value": move_text},
                {"label": "Needs", "value": "80 points"},
                {"label": "Days", "value": "Wed Thu Fri"},
            ],
            ["On Wed/Thu/Fri, if flat at 14:30 and price has moved 80+ pts from 13:00, ride it ($600 risk)."],
        )
    if minutes >= 14 * 60 + 35:
        return idea(
            "hop", "14:30 afternoon drive", "Passed", "",
            "The 14:30 afternoon checkpoint has passed.",
            [
                {"label": "Bid", "value": price_text(bid)},
                {"label": "Since 13:00", "value": move_text},
                {"label": "Needed", "value": "80 points"},
                {"label": "Window", "value": "closed"},
            ],
            ["Positions flatten at 15:55 New York."],
        )
    closes = bar_closes_in(now, 14 * 60 + 30)
    level = near_level(mv_pm, PM_DRIVE_POINTS)
    if closes and level == "met" and position is None:
        side = "buy" if mv_pm > 0 else "sell"
        state = "Ready"
        lead = f"Ready to {side} the 14:30 afternoon drive ({mv_pm:+.1f} pts since 13:00)."
    elif level in ("met", "Getting close"):
        state, side = "Getting close", ""
        lead = move_words(mv_pm, PM_DRIVE_POINTS)
    else:
        state, side = "Watching", ""
        lead = "Waiting for the 13:00 afternoon open." if mv_pm is None else f"Since 13:00: {mv_pm:+.1f} pts (needs 80 pts at 14:30)."
    return idea(
        "hop", "14:30 afternoon drive", state, side, lead,
        [
            {"label": "Bid", "value": price_text(bid)},
            {"label": "Since 13:00", "value": move_text},
            {"label": "Needs", "value": "80 points"},
            {"label": "14:30 in" if not closes else "Bar closes", "value": closes or clock_left(now, 14 * 60 + 30)},
        ],
        ["Wed/Thu/Fri at 14:30 NY: if flat and 13:00->14:30 moved 80+ pts, go with it. Stop 20, target 100, risk $600."],
    )


def gold_used(now):
    """Gold trades taken today, on the New York day, from deal history.

    The bot keeps its own count in a terminal global variable, but the
    Python library has no way to read those, and the old code quietly
    reported 0 forever. Opening gold deals can be read, so count those.
    Deal times come back on the broker clock, like the bars.
    """
    try:
        tick = mt5.symbol_info_tick(GOLD)
        if tick is None:
            return 0
        offset = server_offset_hours(tick.time)
        start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=1)
        deals = mt5.history_deals_get(start, start + timedelta(days=3))
        if not deals:
            return 0
        used = 0
        for deal in deals:
            if deal.symbol != GOLD or int(deal.magic) != MAGIC:
                continue
            if int(deal.entry) != int(mt5.DEAL_ENTRY_IN):
                continue
            real_utc = datetime.fromtimestamp(int(deal.time) - offset * 3600, timezone.utc)
            opened_ny = (real_utc + timedelta(hours=-4)).replace(tzinfo=None)
            if opened_ny.date() == now.date():
                used += 1
        return used
    except Exception:
        return 0


def gold_idea(now, minutes, trading, nasdaq_open, position, bid, ask, closed, nas_bars=None, nas_bid=None, nas_pos=None):
    op3 = open_0300(nas_bars or [])
    mv_lon = None if (op3 is None or nas_bid is None) else (nas_bid - op3)
    move_text = "—" if mv_lon is None else f"{mv_lon:+.1f}"
    if nas_pos is not None and "london" in comment_of(nas_pos):
        side, word, facts = trade_facts(nas_pos, nas_bid if nas_bid is not None else float(nas_pos.price_open))
        return idea(
            "gold", "08:30 UK London fade", "In a trade", side,
            f"{word} {float(nas_pos.volume):.2f} lots from {price_text(float(nas_pos.price_open))}.",
            facts,
            ["US100.cash London Open fade ($600 risk, stop 15, target 90). Closes by 14:20 UK (09:20 NY)."],
        )
    if now.weekday() >= 5:
        return idea(
            "gold", "08:30 UK London fade", "Standing aside", "",
            "London session is closed for the weekend.",
            [{"label": "US100 Bid", "value": "—" if nas_bid is None else price_text(nas_bid)}, {"label": "Band", "value": "5..30 pts"}, {"label": "Stop / Target", "value": "15 / 90"}, {"label": "Risk", "value": "$660"}],
            ["Fades a 5..30 pt drift between 08:00 and 08:30 UK (03:00->03:30 NY) on US100.cash."],
        )
    if minutes >= 3 * 60 + 35:
        return idea(
            "gold", "08:30 UK London fade", "Passed", "",
            "The 08:30 UK (03:30 NY) London Open trade has been judged for today.",
            [
                {"label": "US100 Bid", "value": "—" if nas_bid is None else price_text(nas_bid)},
                {"label": "Since 08:00 UK", "value": move_text},
                {"label": "Band", "value": "5..30 pts"},
                {"label": "Window", "value": "closed"},
            ],
            ["Any open London trade flattens at 14:20 UK (09:20 NY) before Wall Street opens."],
        )
    closes = bar_closes_in(now, 3 * 60 + 30)
    in_band = mv_lon is not None and LONDON_MIN <= abs(mv_lon) < LONDON_MAX
    if closes and in_band and nas_pos is None:
        side = "sell" if mv_lon > 0 else "buy"
        state = "Ready"
        lead = f"Ready to {side} (fade) the 08:30 UK London drift ({mv_lon:+.1f} pts)."
    elif in_band and minutes >= 3 * 60:
        state, side = "Getting close", ""
        lead = f"US100 is {mv_lon:+.1f} pts from 08:00 UK open (inside the 5..30 pt fade band)."
    else:
        state, side = "Watching", ""
        lead = "Waiting for 08:00 UK (03:00 NY) London open." if mv_lon is None else f"Since 08:00 UK: {mv_lon:+.1f} pts (fade band is 5..30 pts at 08:30 UK)."
    return idea(
        "gold", "08:30 UK London fade", state, side, lead,
        [
            {"label": "US100 Bid", "value": "—" if nas_bid is None else price_text(nas_bid)},
            {"label": "Since 08:00 UK", "value": move_text},
            {"label": "Band", "value": "5..30 pts"},
            {"label": "08:30 UK in" if not closes else "Bar closes", "value": closes or clock_left(now, 3 * 60 + 30)},
        ],
        ["All 5 weekdays at 08:30 UK (03:30 NY): fade a 5..30 pt London drift on US100.cash. Stop 15, target 90, risk $600."],
    )


def nas_view(now, minutes, bid, ask, bars, trading, position):
    open930 = None
    for bar in bars:
        hour, minute = bar["t"].split(":")
        if hour == "09" and minute == "30":
            open930 = bar["o"]
    move = None if open930 is None else bid - open930
    is_shot_day = shot_day(now)
    order, why = wanted_order(move, minutes, bars, bid, ask, is_shot_day, now=now)
    levels = []
    if open930 is not None:
        levels.append(level(open930, "#ffd700", f"{open930:.2f}"))
        levels.append(level(open930 + SHOT_POINTS, "#8a8a8a", f"{open930 + SHOT_POINTS:.2f}", True))
        levels.append(level(open930 - SHOT_POINTS, "#8a8a8a", f"{open930 - SHOT_POINTS:.2f}", True))
    lines = []
    if fade10_day(now):
        lines.append("Thursday: 10:00 fades 60+ pt move ($2.4k). 11:00 rides 60+ pt ($2.4k) or fades 10..60 pt ($1.4k). 14:30 rides 80+ pt PM drive ($1.4k).")
    elif is_shot_day:
        lines.append("Shot day: 11:00 rides 60+ pt ($2.4k) or fades 10..60 pt ($1.4k).")
    else:
        lines.append("Tuesday: 11:00 fades a 10..60 pt range move ($600).")
    if position is not None:
        state, tone, side = "In trade", "in", "buy" if position.type == mt5.POSITION_TYPE_BUY else "sell"
        lines.append(f"{side.title()} {float(position.volume):.2f} at {float(position.price_open):.2f}.")
        lines.append("Red line is the stop. Green line is the target.")
        levels = position_levels(position) + [lv for lv in levels if lv["color"] == "#ffd700" or lv["dash"]]
    elif order is not None:
        side = order["side"]
        state = "Ready" if trading else "Blocked"
        tone = "ready" if trading else "block"
        lines.append(why)
        lines.append(f"Stop {order['sl']}  Target {order['tp']}  Risk ${SHOT_RISK if 'am' in order['comment'] or order['comment']=='ORB day' else FALLBACK_RISK:.0f}.")
        levels.append(level(order["entry_price"], "#ffffff", f"{order['entry_price']:.2f}"))
        levels.append(level(order["sl_price"], "#ff3b30", order["sl"]))
        levels.append(level(order["tp_price"], "#00c000", order["tp"]))
    else:
        side = ""
        if minutes > 11 * 60:
            state, tone = "Done", "off"
        else:
            state, tone = "Waiting", "wait"
        lines.append(why)
    if move is not None:
        lines.append(f"Since 09:30: {move:+.1f} points. The shot lines are 60 either side.")
    else:
        lines.append("The 09:30 open is not on the chart yet.")
    if not trading:
        lines.append("Trading is off on this login. No new order will be sent.")
    last = bars[-1] if bars else None
    return {
        "id": "nas",
        "title": "US100.cash, M5",
        "bid": f"{bid:.2f}",
        "ask": f"{ask:.2f}",
        "bars": bars[-60:],
        "levels": levels,
        "note": "US100.cash,M5\n" + ohlc_line(last),
        "thinking": {"market": "Nasdaq", "state": state, "tone": tone, "side": side, "lines": lines},
    }


def gold_view(now, minutes, trading, nasdaq_open, position):
    lines = []
    levels = []
    side = ""
    state, tone = "Off", "off"
    bid = ask = None
    bars = []
    closed = None
    if not mt5.symbol_select(GOLD, True):
        lines.append("XAUUSD is not on this account.")
    else:
        tick = mt5.symbol_info_tick(GOLD)
        if tick is not None:
            bid = float(tick.bid)
            ask = float(tick.ask)
            offset = server_offset_hours(tick.time)
            bars = chart_bars(GOLD, mt5.TIMEFRAME_M1, 80, offset)
        closed = mt5.copy_rates_from_pos(GOLD, mt5.TIMEFRAME_M1, 1, 3)
        if position is not None:
            state, tone = "In trade", "in"
            side = "buy" if position.type == mt5.POSITION_TYPE_BUY else "sell"
            lines.append(f"{side.title()} {float(position.volume):.2f} from {float(position.price_open):.2f}.")
            lines.append("It stands down at 16:00 New York, or sooner if a Nasdaq shot needs the account.")
            levels = position_levels(position)
        elif position is None:
            state, tone = "Off", "off"
            lines.append("Gold scalping is turned off.")
    if not trading and state not in ("In trade",):
        lines.append("Trading is off on this login.")
        if state == "Ready":
            state, tone = "Blocked", "block"
    last = bars[-1] if bars else None
    return {
        "id": "gold",
        "title": "XAUUSD, M1",
        "bid": f"{bid:.2f}" if bid is not None else "-",
        "ask": f"{ask:.2f}" if ask is not None else "-",
        "bars": bars[-70:],
        "levels": levels,
        "note": "XAUUSD,M1\n" + ohlc_line(last),
        "thinking": gold_idea(now, minutes, trading, nasdaq_open, position, bid, ask, closed),
    }


def blank_snapshot(message):
    empty = {
        "bars": [],
        "levels": [],
        "bid": "-",
        "ask": "-",
        "note": message,
    }
    return {
        "symbol_line": "",
        "account_html": esc_text(message),
        "charts": [
            {"id": "nas", "title": "US100.cash, M5", **empty},
            {"id": "gold", "title": "XAUUSD, M1", **empty},
        ],
        "board": message,
        "thinking": [
            idea("shots", "Nasdaq shots", "Watching", "", message, [], [message]),
            idea("fallback", "11:00 fallback", "Watching", "", message, [], [message]),
            idea("hop", "The hop", "Watching", "", message, [], [message]),
            idea("gold", "Gold scalp", "Watching", "", message, [], [message]),
        ],
        "trades": [],
        "journal": journal_lines(),
    }


def snapshot_now():
    if mt5.terminal_info() is None and not mt5.initialize(timeout=1500):
        return blank_snapshot("MetaTrader is waiting for the login")
    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.account_info()
    if tick is None:
        return blank_snapshot("No US100.cash prices yet")
    offset = server_offset_hours(tick.time)
    now = ny_now()
    minutes = now.hour * 60 + now.minute
    bid = float(tick.bid)
    ask = float(tick.ask)
    bars = chart_bars(SYMBOL, mt5.TIMEFRAME_M5, 160, offset)
    nas_positions = [p for p in (mt5.positions_get(symbol=SYMBOL) or []) if p.magic == MAGIC]
    gold_positions = [p for p in (mt5.positions_get(symbol=GOLD) or []) if p.magic == MAGIC]
    trading = bool(info.trade_allowed) if info is not None else False
    nas_position = nas_positions[0] if nas_positions else None
    nas = nas_view(now, minutes, bid, ask, bars, trading, nas_position)
    gold = gold_view(now, minutes, trading, bool(nas_positions), gold_positions[0] if gold_positions else None)
    london_card = gold_idea(now, minutes, trading, bool(nas_positions), gold_positions[0] if gold_positions else None, None, None, None, nas_bars=bars, nas_bid=bid, nas_pos=nas_position)
    ideas = [
        london_card,
        shots_idea(now, minutes, bid, bars, nas_position, trading),
        fallback_idea(now, minutes, bid, bars, nas_position, trading),
        hop_idea(now, bid, bars, nas_position),
    ]
    balance = float(info.balance) if info is not None else 0.0
    if info is None:
        account = "MetaTrader is not connected"
    else:
        flag = "trading disabled" if not trading else "trading enabled"
        account = (
            f"Balance <b>{balance:,.2f}</b> USD  {esc_text(info.name)}  "
            f"<span class=\"{'bad' if not trading else 'good'}\">{flag}</span>"
        )
    trades = [trade_row(p) for p in nas_positions + gold_positions]
    return {
        "symbol_line": f"New York {now.strftime('%H:%M:%S')}",
        "account_html": account,
        "board": board_line(now, ideas),
        "charts": [
            {key: nas[key] for key in ("id", "title", "bid", "ask", "bars", "levels", "note")},
            {key: gold[key] for key in ("id", "title", "bid", "ask", "bars", "levels", "note")},
        ],
        "thinking": ideas,
        "trades": trades,
        "journal": journal_lines(),
    }


_snapshot_lock = threading.Lock()
_snapshot_busy = False
_last_snapshot = None


def snapshot():
    global _snapshot_busy, _last_snapshot
    with _snapshot_lock:
        if _snapshot_busy:
            return _last_snapshot or blank_snapshot("MetaTrader is waiting for the login")
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
        return _last_snapshot or blank_snapshot("MetaTrader is waiting for the login")
    if box.get("error"):
        return blank_snapshot("MetaTrader is not connected")
    value = box.get("value") or blank_snapshot("MetaTrader is not connected")
    charts = value.get("charts") or []
    if charts and charts[0].get("bars"):
        _last_snapshot = value
    return value


def esc_text(value):
    return (value or "").replace("&", "&amp;").replace("<", "&lt;")


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
