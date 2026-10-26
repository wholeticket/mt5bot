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
<style>
  :root {
    --bg: #0b0e14;
    --panel: #121722;
    --line: #232c3d;
    --text: #e6edf3;
    --muted: #8b949e;
    --green: #3fb950;
    --red: #f85149;
    --gold: #e3b341;
    --blue: #58a6ff;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.35 ui-sans-serif, system-ui, "Segoe UI", sans-serif; }
  body { padding: 14px 16px 28px; }
  .top, .trade, .hero, .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; }
  .top {
    display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center;
    padding: 10px 14px; position: sticky; top: 0; z-index: 2;
  }
  .clock b, .stat b { font-variant-numeric: tabular-nums; font-size: 18px; font-weight: 700; }
  .clock span, .stat span { display: block; color: var(--muted); font-size: 10px; letter-spacing: .08em; text-transform: uppercase; }
  .stat { margin-left: 4px; }
  .pill { margin-left: auto; font-weight: 800; letter-spacing: .08em; font-size: 13px; padding: 6px 10px; border-radius: 999px; }
  .pill.live { color: #04210c; background: var(--green); }
  .pill.locked { color: #fff; background: var(--red); }
  .trade { margin-top: 10px; padding: 8px 14px; }
  .trade.flat { color: var(--muted); }
  .trade.live { display: flex; flex-wrap: wrap; gap: 10px 18px; align-items: center; border-color: #2d4a34; }
  .trade .side { font-weight: 800; letter-spacing: .04em; }
  .trade .side.buy { color: var(--green); }
  .trade .side.sell { color: var(--red); }
  .trade .pnl { margin-left: auto; font-size: 28px; font-weight: 800; font-variant-numeric: tabular-nums; }
  .up { color: var(--green); }
  .down { color: var(--red); }
  .hero { margin-top: 10px; padding: 14px 16px 12px; display: grid; grid-template-columns: 1fr auto; gap: 8px 16px; align-items: end; }
  .kicker { color: var(--muted); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; }
  .hero h1 { margin: 2px 0 0; font-size: 28px; letter-spacing: -0.03em; }
  .hero h1 em { font-style: normal; color: var(--muted); font-size: 16px; font-weight: 600; margin-left: 8px; }
  .count { font-size: 28px; font-weight: 800; font-variant-numeric: tabular-nums; color: var(--gold); }
  .line { grid-column: 1 / -1; font-size: 16px; }
  .facts { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; margin-top: 4px; }
  .fact { background: #0b0e14; border-radius: 8px; padding: 8px 10px; }
  .fact span { display: block; color: var(--muted); font-size: 10px; letter-spacing: .06em; text-transform: uppercase; }
  .fact b { font-variant-numeric: tabular-nums; font-size: 14px; }
  .verdict { grid-column: 1 / -1; font-size: 18px; font-weight: 750; }
  .panel { margin-top: 10px; padding: 10px 12px 12px; }
  .panel h2 { margin: 0 0 8px; color: var(--muted); font-size: 11px; letter-spacing: .08em; text-transform: uppercase; font-weight: 650; }
  .px { color: var(--muted); font-variant-numeric: tabular-nums; }
  .px b { color: var(--text); }
  .wide { color: var(--red); }
  svg { width: 100%; height: auto; display: block; background: #0b0e14; border-radius: 8px; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; color: var(--muted); font-size: 10px; letter-spacing: .06em; text-transform: uppercase; font-weight: 650; padding: 0 8px 6px 0; }
  td { padding: 7px 10px 7px 0; border-top: 1px solid var(--line); font-variant-numeric: tabular-nums; vertical-align: middle; }
  .badge { display: inline-block; min-width: 72px; text-align: center; border-radius: 999px; padding: 2px 8px; font-size: 11px; font-weight: 750; letter-spacing: .04em; }
  .badge.done { color: var(--muted); background: #1c2433; }
  .badge.next { color: #04210c; background: var(--green); }
  .badge.off { color: #6e7681; background: transparent; border: 1px solid var(--line); }
  .badge.later { color: var(--gold); background: rgba(227, 179, 65, .12); }
  #fills:empty, #fills.hide { display: none; }
  .tick { animation: tick .45s ease; }
  @keyframes tick { from { background: rgba(227, 179, 65, .35); } }
</style>
</head>
<body>
<header class="top" id="top"></header>
<div class="trade flat" id="trade">Flat</div>
<section class="hero" id="hero"></section>
<section class="panel">
  <h2 id="chart-head">US100.cash · M5</h2>
  <svg id="chart" viewBox="0 0 820 400" preserveAspectRatio="none"></svg>
</section>
<section class="panel">
  <h2>Today's windows</h2>
  <table>
    <thead><tr><th>London</th><th>Setup</th><th>Status</th><th>Readout</th></tr></thead>
    <tbody id="windows"></tbody>
  </table>
</section>
<section class="panel hide" id="fills">
  <h2>Today's fills</h2>
  <table>
    <thead><tr><th>London</th><th>Side</th><th>Lots</th><th>Price</th><th>Result</th></tr></thead>
    <tbody id="fill-rows"></tbody>
  </table>
</section>
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
function htag(parts, y, price, color, text, x0, x1, dash) {
  const yy = y(price);
  const dashAttr = dash ? ' stroke-dasharray="5 4"' : "";
  parts.push('<line x1="'+x0+'" x2="'+x1+'" y1="'+yy+'" y2="'+yy+'" stroke="'+color+'" stroke-width="1.2"'+dashAttr+'/>');
  const w = Math.max(52, text.length * 6.6);
  parts.push('<rect x="'+(x1+4)+'" y="'+(yy-8)+'" width="'+w+'" height="16" rx="3" fill="'+color+'"/>');
  parts.push('<text x="'+(x1+4+w/2)+'" y="'+(yy+4)+'" fill="#111" font-weight="700" font-size="11" text-anchor="middle">'+text+'</text>');
}
function draw(chart) {
  const svg = document.getElementById("chart");
  const bars = (chart && chart.bars) || [];
  if (!bars.length) { svg.innerHTML = ""; return; }
  const levels = chart.levels || [];
  const left = 8, right = 730, top = 14, bottom = 368;
  let lo = Math.min(...bars.map(b => b.l));
  let hi = Math.max(...bars.map(b => b.h));
  levels.forEach(level => { lo = Math.min(lo, level.price); hi = Math.max(hi, level.price); });
  const pad = Math.max(hi - lo, 1) * 0.08;
  lo -= pad; hi += pad;
  const span = hi - lo;
  const y = p => top + (hi - p) / span * (bottom - top);
  const cw = (right - left) / bars.length;
  const parts = [];
  for (let i = 0; i <= 4; i++) {
    const p = lo + span * i / 4;
    const yy = y(p);
    parts.push('<line x1="'+left+'" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" stroke="#1b2230"/>');
    parts.push('<text x="738" y="'+(yy+4)+'" fill="#8b949e" font-size="11">'+p.toFixed(1)+'</text>');
  }
  bars.forEach((b, i) => {
    const x = left + i * cw + cw * 0.5;
    const up = b.c >= b.o;
    const color = up ? "#3fb950" : "#f85149";
    parts.push('<line x1="'+x+'" x2="'+x+'" y1="'+y(b.h)+'" y2="'+y(b.l)+'" stroke="'+color+'" stroke-width="1.1"/>');
    const y1 = y(Math.max(b.o, b.c));
    const y2 = y(Math.min(b.o, b.c));
    parts.push('<rect x="'+(x-Math.max(1.1, cw*0.32))+'" y="'+y1+'" width="'+Math.max(2.2, cw*0.64)+'" height="'+Math.max(1.2, y2-y1)+'" fill="'+color+'"/>');
  });
  levels.forEach(level => {
    htag(parts, y, level.price, level.color, esc(level.label), left, right, level.dash);
  });
  svg.innerHTML = parts.join("");
}
function render(data) {
  const top = document.getElementById("top");
  const day = data.day_pnl;
  top.innerHTML =
    '<div class="clock"><span>London</span><b>'+esc(data.london)+'</b></div>' +
    '<div class="clock"><span>New York</span><b>'+esc(data.ny)+'</b></div>' +
    '<div class="stat"><span>Balance</span><b>'+plainMoney(data.balance)+'</b></div>' +
    '<div class="stat"><span>Equity</span><b>'+plainMoney(data.equity)+'</b></div>' +
    '<div class="stat"><span>Today</span><b class="'+cls(day)+'">'+money(day)+'</b></div>' +
    '<div class="pill '+(data.trading === "LIVE" ? "live" : "locked")+'">'+esc(data.trading || "LOCKED")+'</div>';

  const trade = document.getElementById("trade");
  const pos = data.position;
  if (!pos) {
    trade.className = "trade flat";
    trade.innerHTML = "Flat";
  } else {
    trade.className = "trade live";
    trade.innerHTML =
      '<b>'+esc(pos.symbol)+'</b>' +
      '<span class="side '+esc(pos.side)+'">'+esc(pos.side.toUpperCase())+'</span>' +
      '<span>'+esc(pos.volume)+' lots</span>' +
      '<span>Entry '+esc(pos.entry)+'</span>' +
      '<span>SL '+esc(pos.sl)+'</span>' +
      '<span>TP '+esc(pos.tp)+'</span>' +
      '<span class="pnl '+cls(pos.pnl)+'" data-k="pnl">'+money(pos.pnl)+'</span>';
  }

  const hero = data.hero || {};
  const facts = (hero.facts || []).map(f =>
    '<div class="fact"><span>'+esc(f.k)+'</span><b>'+esc(f.v)+'</b></div>').join("");
  document.getElementById("hero").innerHTML =
    '<div><div class="kicker">'+esc(hero.kicker || "")+'</div><h1>'+esc(hero.title || "")+'<em>'+esc(hero.ny || "")+'</em></h1></div>' +
    '<div class="count">'+esc(hero.countdown || "")+'</div>' +
    (hero.line ? '<div class="line">'+esc(hero.line)+'</div>' : '') +
    (facts ? '<div class="facts">'+facts+'</div>' : '') +
    (hero.verdict ? '<div class="verdict">'+esc(hero.verdict)+'</div>' : '');

  const chart = data.chart || {};
  const spreadCls = chart.spread_wide ? " wide" : "";
  document.getElementById("chart-head").innerHTML =
    'US100.cash · M5 <span class="px">Bid <b>'+esc(chart.bid || "—")+'</b> · Ask <b>'+esc(chart.ask || "—")+'</b> · Spread <b class="'+spreadCls.trim()+'">'+esc(chart.spread || "—")+'</b></span>';
  draw(chart);

  document.getElementById("windows").innerHTML = (data.windows || []).map(row =>
    '<tr><td><b>'+esc(row.time)+'</b></td><td>'+esc(row.name)+'</td><td><span class="badge '+esc(row.status)+'">'+esc(row.badge)+'</span></td><td>'+esc(row.readout)+'</td></tr>'
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
    document.getElementById("hero").innerHTML = '<div><div class="kicker">Waiting</div><h1>Viewer offline</h1></div>';
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
