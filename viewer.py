"""Live view of the pass bot on US100.cash. Read only. Sends no orders.

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
<title>US100.cash,M5</title>
<style>
  html, body { margin: 0; height: 100%; background: #1c1f22; color: #d7d7d7; font: 12px Tahoma, "Segoe UI", sans-serif; }
  body { display: flex; flex-direction: column; min-height: 100vh; }
  header { display: flex; justify-content: space-between; gap: 16px; padding: 6px 10px; background: #2a2e32; border-bottom: 1px solid #111; }
  header b { color: #fff; font-weight: 600; }
  .bad { color: #ff5a5a; }
  .good { color: #4cd07a; }
  #orderbar { background: #23272b; border-bottom: 1px solid #111; }
  #ticket { display: flex; flex-wrap: wrap; align-items: center; gap: 14px; padding: 8px 10px; }
  main { flex: 1; min-height: 0; }
  #chartwrap { position: relative; background: #000; height: 100%; min-height: 420px; }
  svg { width: 100%; height: 100%; display: block; }
  #comment { position: absolute; left: 8px; top: 6px; color: #f2f2f2; white-space: pre; line-height: 1.35; text-shadow: 0 1px 2px #000; pointer-events: none; }
  aside { background: #23272b; border-left: 1px solid #111; display: flex; flex-direction: column; }
  h2 { margin: 0; padding: 8px 10px; background: #2f3439; color: #fff; font-size: 12px; font-weight: 600; }
  .ticket { padding: 10px; }
  .sym { font-size: 16px; color: #fff; margin-bottom: 2px; }
  .kind { color: #9a9a9a; margin-bottom: 10px; }
  .buttons { display: grid; grid-template-columns: 110px 110px; gap: 8px; }
  .btn { border: 1px solid #111; padding: 8px 6px 6px; text-align: center; background: #3a3f44; color: #8d8d8d; }
  .btn.on-sell { background: #c44747; color: #fff; }
  .btn.on-buy { background: #3d7ec4; color: #fff; }
  .btn .px { display: block; font-size: 16px; font-weight: 700; }
  .btn small { color: inherit; opacity: 0.85; }
  .field { display: flex; flex-direction: column; gap: 2px; min-width: 90px; }
  .field span { color: #9a9a9a; }
  .field b { color: #fff; font-weight: 600; }
  .status { flex-basis: 100%; line-height: 1.4; }
  #journal { background: #0d0d0d; border-top: 1px solid #111; padding: 6px 10px 8px; min-height: 92px; }
  #journal h2 { margin: 0 -10px 6px; }
  #lines { font: 13px Tahoma, "Segoe UI", sans-serif; }
  .jrow { display: flex; gap: 14px; padding: 3px 0; }
  .jrow span { color: #8a8a8a; min-width: 108px; }
  .jrow b { font-weight: 600; color: #e7e1d4; }
  .jrow.buy b { color: #8fce7a; }
  .jrow.reject b { color: #ff5a5a; }
</style>
</head>
<body>
<header>
  <div id="symbol">US100.cash, M5</div>
  <div id="account"></div>
</header>
<section id="orderbar">
  <div class="ticket" id="ticket"></div>
</section>
<main>
  <div id="chartwrap">
    <svg id="chart" viewBox="0 0 900 520" preserveAspectRatio="none"></svg>
    <div id="comment"></div>
  </div>
</main>
<section id="journal">
  <h2>Journal</h2>
  <div id="lines"></div>
</section>
<script>
function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;");
}
function field(label, value) {
  return '<div class="field"><span>' + esc(label) + '</span><b>' + esc(value) + '</b></div>';
}
function ticket(data) {
  const t = data.ticket;
  const sellOn = t.side === "sell" ? " on-sell" : "";
  const buyOn = t.side === "buy" ? " on-buy" : "";
  let html = '<div class="sym">' + esc(t.symbol || "US100.cash") + '</div><div class="kind">' + esc(t.execution) + '</div>';
  html += '<div class="buttons">';
  html += '<div class="btn' + sellOn + '"><span>Sell</span><span class="px">' + esc(t.bid) + '</span><small>by market</small></div>';
  html += '<div class="btn' + buyOn + '"><span>Buy</span><span class="px">' + esc(t.ask) + '</span><small>by market</small></div>';
  html += '</div>';
  html += field("Volume", t.volume);
  html += field("Stop Loss", t.sl);
  html += field("Take Profit", t.tp);
  html += field("Comment", t.comment);
  html += '<div class="status ' + (t.ok ? "good" : "bad") + '">' + esc(t.status) + '</div>';
  document.getElementById("ticket").innerHTML = html;
}
function htag(parts, y, price, color, text, x0, x1) {
  parts.push('<line x1="'+x0+'" x2="'+x1+'" y1="'+y(price)+'" y2="'+y(price)+'" stroke="'+color+'" stroke-width="1"/>');
  const yy = y(price);
  parts.push('<rect x="'+(x1+2)+'" y="'+(yy-8)+'" width="70" height="16" fill="'+color+'"/>');
  parts.push('<text x="'+(x1+37)+'" y="'+(yy+4)+'" fill="#000" font-size="11" text-anchor="middle" font-family="Tahoma">'+text+'</text>');
}
function draw(data) {
  const bars = data.bars || [];
  const svg = document.getElementById("chart");
  if (!bars.length) { svg.innerHTML = ""; return; }
  const left = 8, right = 820, top = 16, bottom = 492;
  let lo = Math.min(...bars.map(b => b.l));
  let hi = Math.max(...bars.map(b => b.h));
  (data.levels || []).forEach(level => {
    if (level.price) { lo = Math.min(lo, level.price); hi = Math.max(hi, level.price); }
  });
  const span0 = Math.max(hi - lo, 1);
  lo -= span0 * 0.08;
  hi += span0 * 0.08;
  const span = hi - lo;
  const y = p => top + (hi - p) / span * (bottom - top);
  const cw = (right - left) / bars.length;
  const parts = [];
  for (let i = 0; i <= 6; i++) {
    const p = lo + span * i / 6;
    const yy = y(p);
    parts.push('<line x1="'+left+'" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" stroke="#2a2a2a"/>');
    parts.push('<text x="828" y="'+(yy+4)+'" fill="#8a8a8a" font-size="11" font-family="Tahoma">'+p.toFixed(2)+'</text>');
  }
  for (let i = 0; i < bars.length; i += 12) {
    const x = left + i * cw;
    parts.push('<line x1="'+x+'" x2="'+x+'" y1="'+top+'" y2="'+bottom+'" stroke="#2a2a2a"/>');
    parts.push('<text x="'+x+'" y="508" fill="#8a8a8a" font-size="11" font-family="Tahoma">'+bars[i].t+'</text>');
  }
  bars.forEach((b, i) => {
    const x = left + i * cw + cw * 0.5;
    const up = b.c >= b.o;
    const color = "#f2f2f2";
    parts.push('<line x1="'+x+'" x2="'+x+'" y1="'+y(b.h)+'" y2="'+y(b.l)+'" stroke="'+color+'" stroke-width="1"/>');
    const topY = y(Math.max(b.o, b.c));
    const botY = y(Math.min(b.o, b.c));
    const fill = up ? "#000" : "#f2f2f2";
    parts.push('<rect x="'+(x-cw*0.32)+'" y="'+topY+'" width="'+(cw*0.64)+'" height="'+Math.max(1, botY-topY)+'" fill="'+fill+'" stroke="'+color+'"/>');
  });
  (data.levels || []).forEach(level => {
    if (!level.price) return;
    htag(parts, y, level.price, level.color, level.label, left, right);
  });
  svg.innerHTML = parts.join("");
}
async function tick() {
  const data = await (await fetch("/api")).json();
  document.getElementById("symbol").textContent = data.symbol_line;
  document.getElementById("account").innerHTML = data.account_html;
  document.getElementById("comment").textContent = data.comment;
  ticket(data);
  const lines = document.getElementById("lines");
  lines.innerHTML = (data.journal || []).map(row => {
    return '<div class="jrow ' + esc(row.kind || "") + '"><span>' + esc(row.time || "") + '</span><b>' + esc(row.text || "") + '</b></div>';
  }).join("");
  draw(data);
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


def gold_note():
    if not mt5.symbol_select(GOLD, True):
        return "Gold is not on this account."
    tick = mt5.symbol_info_tick(GOLD)
    rates = mt5.copy_rates_from_pos(GOLD, mt5.TIMEFRAME_M1, 1, 3)
    positions = [p for p in (mt5.positions_get(symbol=GOLD) or []) if p.magic == MAGIC]
    if positions:
        position = positions[0]
        side = "Buy" if position.type == mt5.POSITION_TYPE_BUY else "Sell"
        return (
            f"Gold {side} {float(position.volume):.2f} at {float(position.price_open):.2f}. "
            f"Stop {float(position.sl):.2f}. Target {float(position.tp):.2f}."
        )
    nasdaq = [p for p in (mt5.positions_get(symbol=SYMBOL) or []) if p.magic == MAGIC]
    if nasdaq:
        return "Gold is waiting. Nasdaq has the account."
    now = ny_now()
    minutes = now.hour * 60 + now.minute
    if now.weekday() >= 5:
        return "Gold is off for the weekend."
    if minutes < 3 * 60 or minutes >= 16 * 60:
        return "Gold watches from 03:00 to 16:00 New York."
    shot_day = now.weekday() in (0, 3, 4)
    if shot_day and 9 * 60 + 50 <= minutes <= 11 * 60:
        return "Gold is standing aside so the Nasdaq shots go first."
    if not shot_day and 10 * 60 + 50 <= minutes <= 11 * 60:
        return "Gold is standing aside for the 11:00 Nasdaq trade."
    if tick is None or rates is None or len(rates) < 3:
        return "Gold prices are not in yet."
    net = float(rates[-1]["close"]) - float(rates[0]["open"])
    spread = float(tick.ask) - float(tick.bid)
    if spread > 0.60:
        return f"Gold spread is {spread:.2f}. That is too wide."
    if abs(net) < GOLD_MIN:
        return f"Gold is watching. The last 3 minutes moved {net:+.2f}. It needs {GOLD_MIN:.2f}."
    buy = net > 0
    window = list(rates)
    if buy:
        pullback = max(float(bar["high"]) for bar in window) - float(window[-1]["close"])
    else:
        pullback = float(window[-1]["close"]) - min(float(bar["low"]) for bar in window)
    if pullback > abs(net) * 0.5:
        return f"Gold moved {net:+.2f}, then gave back half. Waiting for the next push."
    word = "buy" if buy else "sell"
    return f"Gold wants to {word}. The last 3 minutes moved {net:+.2f}. Risk ${GOLD_RISK:.0f}."


def snapshot():
    blank = {
        "symbol_line": "US100.cash, M5",
        "account_html": "MetaTrader is not connected",
        "comment": "MetaTrader is not connected",
        "ticket": empty_ticket(0, 0),
        "journal": journal_lines(),
        "bars": [],
        "levels": [],
    }
    if mt5.terminal_info() is None and not mt5.initialize():
        return blank
    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.account_info()
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 80)
    if tick is None or rates is None:
        blank["comment"] = "No US100.cash prices yet."
        return blank

    offset = server_offset_hours(tick.time)
    now = ny_now()
    bid = float(tick.bid)
    ask = float(tick.ask)
    bars = []
    open930 = None
    for rate in rates:
        when = bar_ny(rate["time"], offset)
        bars.append({"t": when.strftime("%H:%M"), "o": float(rate["open"]), "h": float(rate["high"]),
                     "l": float(rate["low"]), "c": float(rate["close"])})
        if when.hour == 9 and when.minute == 30 and when.date() == now.date():
            open930 = float(rate["open"])
    move = None if open930 is None else bid - open930
    minutes = now.hour * 60 + now.minute
    last = bars[-1]
    positions = [p for p in (mt5.positions_get(symbol=SYMBOL) or []) if p.magic == MAGIC]
    gold_positions = [p for p in (mt5.positions_get(symbol=GOLD) or []) if p.magic == MAGIC]
    trading = bool(info.trade_allowed) if info is not None else False
    balance = float(info.balance) if info is not None else 0.0

    levels = []
    if open930:
        levels.append({"price": open930, "color": "#c8b56a", "label": f"{open930:.2f}"})
    if positions:
        ticket = position_ticket(positions[0], bid, ask)
        ticket["execution"] = "Position"
        ticket["ok"] = True
        money = ticket.pop("profit")
        ticket["status"] = f"In the trade. Profit ${money:,.0f}."
        if ticket["entry_price"]:
            levels.append({"price": ticket["entry_price"], "color": "#d0d0d0", "label": f"{ticket['entry_price']:.2f}"})
        if ticket["sl_price"]:
            levels.append({"price": ticket["sl_price"], "color": "#e24b4b", "label": ticket["sl"]})
        if ticket["tp_price"]:
            levels.append({"price": ticket["tp_price"], "color": "#3dbb6a", "label": ticket["tp"]})
        why = "The position is open. S/L is the red line. T/P is the green line."
    elif gold_positions:
        gold_tick = mt5.symbol_info_tick(GOLD)
        gold_bid = float(gold_tick.bid) if gold_tick else 0.0
        gold_ask = float(gold_tick.ask) if gold_tick else 0.0
        ticket = position_ticket(gold_positions[0], gold_bid, gold_ask)
        ticket["execution"] = "Position"
        ticket["ok"] = True
        money = ticket.pop("profit")
        ticket["status"] = f"Gold is open. Profit ${money:,.0f}."
        why = "Gold hop is open. The Nasdaq chart stays up. Gold prices are on the ticket."
    else:
        shot_day = now.weekday() in (0, 3, 4)
        order, why = wanted_order(move, minutes, bars, bid, ask, shot_day)
        if order is None:
            ticket = empty_ticket(bid, ask)
            ticket["status"] = why
            ticket["ok"] = True
        else:
            ticket = order
            ticket["bid"] = f"{bid:.2f}"
            ticket["ask"] = f"{ask:.2f}"
            ticket["execution"] = "Market Execution"
            levels.append({"price": ticket["entry_price"], "color": "#d0d0d0", "label": f"{ticket['entry_price']:.2f}"})
            levels.append({"price": ticket["sl_price"], "color": "#e24b4b", "label": ticket["sl"]})
            levels.append({"price": ticket["tp_price"], "color": "#3dbb6a", "label": ticket["tp"]})
            if not trading:
                ticket["ok"] = False
                ticket["status"] = "Trade disabled. This order will be rejected."
            else:
                ticket["ok"] = True
                ticket["status"] = "This is the order the bot will send."

    if not trading:
        why = why + "\nTrading is off on this login. A new order will be rejected until it is turned back on."

    comment = "\n".join([
        f"US100.cash,M5",
        f"O {last['o']:.2f}  H {last['h']:.2f}  L {last['l']:.2f}  C {last['c']:.2f}",
        "",
        "PASS BOT",
        why,
        "",
        gold_note(),
    ])
    account = ""
    if info is not None:
        flag = "trading disabled" if not trading else "trading enabled"
        account = f"Balance <b>{balance:,.2f}</b> USD  {esc_text(info.name)}  <span class=\"{'bad' if not trading else 'good'}\">{flag}</span>"
    return {
        "symbol_line": f"US100.cash, M5   New York {now.strftime('%H:%M:%S')}",
        "account_html": account,
        "comment": comment,
        "ticket": ticket,
        "journal": journal_lines(),
        "bars": bars[-48:],
        "levels": levels,
    }


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
