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
SHOT_RISK = 2400.0
FALLBACK_STOP = 30.0
FALLBACK_TARGET = 120.0
FALLBACK_RISK = 250.0
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
  .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: #000; height: 48vh; min-height: 280px; }
  .chartbox { display: flex; flex-direction: column; min-width: 0; background: #000; }
  .charthead { display: flex; justify-content: space-between; gap: 8px; padding: 4px 8px; background: #2a2e32; color: #fff; }
  .charthead .px { color: #fff; }
  .charthead .px b { font-weight: 600; }
  .chartwrap { position: relative; flex: 1; min-height: 0; background: #000; }
  svg { width: 100%; height: 100%; display: block; background: #000; }
  .corner { position: absolute; left: 8px; top: 6px; color: #fff; white-space: pre; line-height: 1.35; text-shadow: 1px 1px 0 #000; pointer-events: none; }
  .desk { display: grid; grid-template-columns: 1.35fr 0.65fr; gap: 1px; background: #000; }
  .panel { background: #000; min-width: 0; }
  h2 { margin: 0; padding: 6px 10px; background: #2a2e32; color: #fff; font: 600 12px Tahoma, sans-serif; }
  .think { display: grid; grid-template-columns: 1fr 1fr; }
  .card { padding: 10px 12px 12px; border-right: 1px solid #222; }
  .card h3 { margin: 0 0 8px; color: #fff; font: 600 13px Tahoma, sans-serif; display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
  .pill { font: 600 12px Tahoma, sans-serif; }
  .pill.wait { color: #d0d0d0; }
  .pill.ready.buy, .side.buy { color: #1e88e5; }
  .pill.ready.sell, .side.sell { color: #e53935; }
  .pill.in { color: #fff; }
  .pill.aside { color: #ffb300; }
  .pill.off { color: #8a8a8a; }
  .pill.block { color: #ff5252; }
  .card p { margin: 0 0 4px; color: #d0d0d0; line-height: 1.45; }
  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; color: #9a9a9a; font-weight: 400; padding: 6px 8px; background: #141414; }
  td { padding: 7px 8px; border-top: 1px solid #222; color: #e0e0e0; }
  td.up { color: #00c000; }
  td.down { color: #ff5252; }
  .empty { padding: 12px; color: #9a9a9a; }
  #journal { background: #000; border-top: 1px solid #222; max-height: 132px; overflow: auto; }
  #lines { padding: 4px 10px 8px; }
  .jrow { display: flex; gap: 14px; padding: 3px 0; }
  .jrow span { color: #8a8a8a; min-width: 52px; }
  .jrow b { font-weight: 400; color: #d0d0d0; }
  .jrow.buy b { color: #00c000; }
  .jrow.reject b { color: #ff5252; }
  @media (max-width: 980px) {
    .charts, .think, .desk { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>
<header>
  <div id="symbol">Pass bot</div>
  <div id="account"></div>
</header>
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
<section class="desk">
  <section class="panel">
    <h2>Thinking</h2>
    <div class="think" id="think"></div>
  </section>
  <section class="panel">
    <h2>Trades</h2>
    <div id="trades"></div>
  </section>
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
  });
  svg.innerHTML = parts.join("");
}
function head(id, chart) {
  const el = document.getElementById(id);
  if (!chart) { el.innerHTML = ""; return; }
  el.innerHTML = "<span>" + esc(chart.title) + "</span><span class='px'>Bid <b>" + esc(chart.bid) + "</b>  Ask <b>" + esc(chart.ask) + "</b></span>";
}
function render(data) {
  document.getElementById("symbol").textContent = "Pass bot   " + (data.symbol_line || "");
  document.getElementById("account").innerHTML = data.account_html || "";
  const charts = {};
  (data.charts || []).forEach(chart => { charts[chart.id] = chart; });
  head("head-nas", charts.nas);
  head("head-gold", charts.gold);
  document.getElementById("note-nas").textContent = charts.nas ? (charts.nas.note || "") : "";
  document.getElementById("note-gold").textContent = charts.gold ? (charts.gold.note || "") : "";
  draw("chart-nas", charts.nas);
  draw("chart-gold", charts.gold);
  document.getElementById("think").innerHTML = (data.thinking || []).map(card => {
    const lines = (card.lines || []).map(line => "<p>" + esc(line) + "</p>").join("");
    const side = card.side ? " " + esc(card.side) : "";
    return "<div class='card'><h3>" + esc(card.market) + "<span class='pill " + esc(card.tone || "off") + side + "'>" + esc(card.state) + "</span></h3>" + lines + "</div>";
  }).join("");
  const trades = data.trades || [];
  const box = document.getElementById("trades");
  if (!trades.length) {
    box.innerHTML = "<div class='empty'>No open trade.</div>";
  } else {
    const rows = trades.map(row => {
      const cls = row.profit > 0 ? "up" : (row.profit < 0 ? "down" : "");
      return "<tr class='" + esc(row.side) + "'><td>" + esc(row.symbol) + "</td><td class='side " + esc(row.side) + "'>" + esc(row.side === "buy" ? "buy" : "sell") + "</td><td>" + esc(row.volume) + "</td><td>" + esc(row.price) + "</td><td>" + esc(row.sl) + "</td><td>" + esc(row.tp) + "</td><td class='" + cls + "'>" + esc(row.profit_text) + "</td></tr>";
    }).join("");
    box.innerHTML = "<table><tr><th>Symbol</th><th>Type</th><th>Volume</th><th>Price</th><th>S / L</th><th>T / P</th><th>Profit</th></tr>" + rows + "</table>";
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
setInterval(tick, 2000);
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


def wanted_order(move, minutes, bars, bid, ask, shot_day):
    if move is None:
        if shot_day:
            return None, "Waiting for the 09:30 New York open."
        return None, "Waiting for the 09:30 open. Today is the one 11:00 trade."
    if shot_day and minutes < 10 * 60:
        if abs(move) < SHOT_POINTS:
            return None, f"10:00 fade. The open has moved {move:+.1f}. It needs 60."
        side = "sell" if move > 0 else "buy"
        word = "Sell" if side == "sell" else "Buy"
        return order_from(side, bid, ask, SHOT_STOP, SHOT_TARGET, SHOT_RISK, "ORB am"), f"{word} the 10:00 fade."
    if minutes < 11 * 60:
        if shot_day and abs(move) >= SHOT_POINTS:
            side = "buy" if move > 0 else "sell"
            word = "Buy" if side == "buy" else "Sell"
            return order_from(side, bid, ask, SHOT_STOP, SHOT_TARGET, SHOT_RISK, "ORB day"), f"{word} the 11:00 shot, with the move."
        if abs(move) >= 0.5:
            side = "buy" if move > 0 else "sell"
            word = "Buy" if side == "buy" else "Sell"
            return order_from(side, bid, ask, FALLBACK_STOP, FALLBACK_TARGET, FALLBACK_RISK, "ORB daily"), f"{word} the 11:00 trade. Stop 30, target 120, $250."
        return None, "11:00 trade is off. The morning is flat."
    return None, "That was the trade for today. The hop after 11:00 is off."


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


def level(price, color, label, dash=False):
    return {"price": float(price), "color": color, "label": label, "dash": dash}


def position_levels(position):
    levels = [level(position.price_open, "#ffffff", f"{float(position.price_open):.2f}")]
    if position.sl:
        levels.append(level(position.sl, "#ff3b30", f"{float(position.sl):.2f}"))
    if position.tp:
        levels.append(level(position.tp, "#00c000", f"{float(position.tp):.2f}"))
    return levels


def trade_row(position):
    return {
        "symbol": position.symbol,
        "side": "buy" if position.type == mt5.POSITION_TYPE_BUY else "sell",
        "volume": f"{float(position.volume):.2f}",
        "price": f"{float(position.price_open):.2f}",
        "sl": f"{float(position.sl):.2f}" if position.sl else "",
        "tp": f"{float(position.tp):.2f}" if position.tp else "",
        "profit": float(position.profit),
        "profit_text": f"{float(position.profit):,.2f}",
    }


def ohlc_line(bar):
    if not bar:
        return ""
    return f"O {bar['o']:.2f}  H {bar['h']:.2f}  L {bar['l']:.2f}  C {bar['c']:.2f}"


def nas_view(now, minutes, bid, ask, bars, trading, position):
    open930 = None
    for bar in bars:
        hour, minute = bar["t"].split(":")
        if hour == "09" and minute == "30":
            open930 = bar["o"]
    move = None if open930 is None else bid - open930
    shot_day = now.weekday() in (0, 3, 4)
    order, why = wanted_order(move, minutes, bars, bid, ask, shot_day)
    levels = []
    if open930 is not None:
        levels.append(level(open930, "#ffd700", f"{open930:.2f}"))
        levels.append(level(open930 + SHOT_POINTS, "#8a8a8a", f"{open930 + SHOT_POINTS:.2f}", True))
        levels.append(level(open930 - SHOT_POINTS, "#8a8a8a", f"{open930 - SHOT_POINTS:.2f}", True))
    lines = []
    if shot_day:
        lines.append("Shot day. 10:00 fades the move. 11:00 goes with it.")
    else:
        lines.append("Not a shot day. One Nasdaq trade at 11:00 New York.")
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
        elif nasdaq_open:
            state, tone = "Aside", "aside"
            lines.append("Nasdaq has the account. Gold waits until that trade is flat.")
        elif now.weekday() >= 5:
            lines.append("Gold is off for the weekend.")
        elif minutes < 3 * 60 or minutes >= 16 * 60:
            state, tone = "Off", "off"
            lines.append("Gold trades from 03:00 to 16:00 New York.")
        elif (now.weekday() in (0, 3, 4) and 9 * 60 + 50 <= minutes <= 11 * 60):
            state, tone = "Aside", "aside"
            lines.append("Standing aside so the Nasdaq shots go first.")
        elif now.weekday() not in (0, 3, 4) and 10 * 60 + 50 <= minutes <= 11 * 60:
            state, tone = "Aside", "aside"
            lines.append("Standing aside for the 11:00 Nasdaq trade.")
        elif tick is None or closed is None or len(closed) < 3:
            state, tone = "Waiting", "wait"
            lines.append("Gold prices are not in yet.")
        else:
            net = float(closed[-1]["close"]) - float(closed[0]["open"])
            spread = ask - bid
            lines.append(f"Last 3 minutes {net:+.2f}. It needs {GOLD_MIN:.2f}. Spread {spread:.2f}.")
            if spread > 0.60:
                state, tone = "Blocked", "block"
                lines.append("The spread is too wide to take the bite.")
            elif abs(net) < GOLD_MIN:
                state, tone = "Watching", "wait"
            else:
                buy = net > 0
                window = list(closed)
                if buy:
                    pullback = max(float(bar["high"]) for bar in window) - float(window[-1]["close"])
                else:
                    pullback = float(window[-1]["close"]) - min(float(bar["low"]) for bar in window)
                if pullback > abs(net) * 0.5:
                    state, tone = "Watching", "wait"
                    lines.append("The move gave back half. Waiting for the next push.")
                else:
                    side = "buy" if buy else "sell"
                    state = "Ready" if trading else "Blocked"
                    tone = "ready" if trading else "block"
                    entry = ask if buy else bid
                    bite = min(2.50, max(0.90, abs(net) * 0.50))
                    stop = min(1.60, max(0.80, pullback + 0.30))
                    sl = entry - stop if buy else entry + stop
                    tp = entry + bite if buy else entry - bite
                    lines.append(f"Wants to {side}. Risk ${GOLD_RISK:.0f}.")
                    levels = [
                        level(entry, "#ffffff", f"{entry:.2f}"),
                        level(sl, "#ff3b30", f"{sl:.2f}"),
                        level(tp, "#00c000", f"{tp:.2f}"),
                    ]
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
        "thinking": {"market": "Gold", "state": state, "tone": tone, "side": side, "lines": lines},
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
        "thinking": [
            {"market": "Nasdaq", "state": "Off", "tone": "off", "side": "", "lines": [message]},
            {"market": "Gold", "state": "Off", "tone": "off", "side": "", "lines": [message]},
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
    nas = nas_view(now, minutes, bid, ask, bars, trading, nas_positions[0] if nas_positions else None)
    gold = gold_view(now, minutes, trading, bool(nas_positions), gold_positions[0] if gold_positions else None)
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
        "charts": [
            {key: nas[key] for key in ("id", "title", "bid", "ask", "bars", "levels", "note")},
            {key: gold[key] for key in ("id", "title", "bid", "ask", "bars", "levels", "note")},
        ],
        "thinking": [nas["thinking"], gold["thinking"]],
        "trades": trades,
        "journal": journal_lines(),
    }


_snapshot_lock = threading.Lock()
_snapshot_busy = False


def snapshot():
    global _snapshot_busy
    with _snapshot_lock:
        if _snapshot_busy:
            return blank_snapshot("MetaTrader is waiting for the login")
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
        return blank_snapshot("MetaTrader is waiting for the login")
    if box.get("error"):
        return blank_snapshot("MetaTrader is not connected")
    return box.get("value") or blank_snapshot("MetaTrader is not connected")


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
