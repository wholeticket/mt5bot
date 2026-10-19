"""Live view of the pass bot weighing US100.cash. Read only. Sends no orders.

The page listens on this PC, ports 8765 and 18765.
127.0.0.1 only works in a browser on this PC. From the laptop, open the
PC's own address on the same network, or the tunnel URL printed at startup.
"""

import json
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import MetaTrader5 as mt5

SYMBOL = "US100.cash"
MAGIC = 26101201
SPREAD_MAX = 250
SHOT_POINTS = 60.0
HOST = "0.0.0.0"
PORTS = (8765, 18765)
LOG = Path(r"C:\Users\user\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\logs")

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Pass bot viewer</title>
<style>
  body { margin: 0; background: #12140f; color: #e7e1d4; font: 15px/1.4 Georgia, serif; }
  header { padding: 16px 22px 8px; display: flex; justify-content: space-between; gap: 16px; }
  h1 { font-size: 22px; font-weight: 600; margin: 0; }
  .muted { color: #9a927f; font-size: 13px; }
  main { display: grid; grid-template-columns: 1.4fr 0.8fr; gap: 16px; padding: 8px 22px 22px; }
  section { background: #1b1e16; border: 1px solid #2e3326; padding: 12px 14px; }
  h2 { font-size: 14px; letter-spacing: 0.04em; text-transform: uppercase; margin: 0 0 8px; color: #c8b56a; }
  svg { width: 100%; height: 340px; background: #10130d; }
  .row { display: flex; justify-content: space-between; gap: 12px; padding: 7px 0; border-bottom: 1px solid #2a2e23; }
  .row b { font-weight: 600; }
  .buy { color: #8fce7a; }
  .sell { color: #e07a72; }
  .wait { color: #c8b56a; }
  .pass { color: #9a927f; }
  #verdict { font-size: 20px; margin: 0 0 10px; }
</style>
</head>
<body>
<header>
  <div>
    <h1>Pass bot, watching US100.cash</h1>
    <div class="muted" id="clock">Connecting to MetaTrader…</div>
  </div>
  <div class="muted" id="account"></div>
</header>
<main>
  <section>
    <h2>Chart the bot is reading</h2>
    <svg id="chart" viewBox="0 0 800 340"></svg>
    <div class="muted">M5 candles. The gold line is the 09:30 New York open. The dashed lines are 60 points either side, the size the 10:00 and 11:00 shots need.</div>
  </section>
  <section>
    <h2>Weighing</h2>
    <p id="verdict" class="wait">…</p>
    <div id="rows"></div>
    <p class="muted" id="ea"></p>
  </section>
</main>
<script>
function cls(kind) {
  if (kind === "buy") return "buy";
  if (kind === "sell") return "sell";
  if (kind === "pass") return "pass";
  return "wait";
}
function row(label, text, kind) {
  return '<div class="row"><span>' + label + '</span><b class="' + cls(kind) + '">' + text + '</b></div>';
}
function draw(bars, openPx) {
  const svg = document.getElementById("chart");
  if (!bars.length) { svg.innerHTML = ""; return; }
  const pad = 16;
  const w = 800, h = 340;
  let lo = Math.min(...bars.map(b => b.l));
  let hi = Math.max(...bars.map(b => b.h));
  if (openPx) { lo = Math.min(lo, openPx - 60); hi = Math.max(hi, openPx + 60); }
  const span = Math.max(hi - lo, 1);
  const y = p => pad + (hi - p) / span * (h - pad * 2);
  const cw = (w - pad * 2) / bars.length;
  let d = "";
  bars.forEach((b, i) => {
    const x = pad + i * cw + cw * 0.5;
    const up = b.c >= b.o;
    const color = up ? "#8fce7a" : "#e07a72";
    d += '<line x1="'+x+'" x2="'+x+'" y1="'+y(b.h)+'" y2="'+y(b.l)+'" stroke="'+color+'" stroke-width="1"/>';
    const top = y(Math.max(b.o, b.c));
    const bot = y(Math.min(b.o, b.c));
    d += '<rect x="'+(x-cw*0.28)+'" y="'+top+'" width="'+(cw*0.56)+'" height="'+Math.max(1, bot-top)+'" fill="'+color+'"/>';
  });
  if (openPx) {
    [openPx, openPx+60, openPx-60].forEach((p, n) => {
      const dash = n ? ' stroke-dasharray="4 4"' : "";
      d += '<line x1="'+pad+'" x2="'+(w-pad)+'" y1="'+y(p)+'" y2="'+y(p)+'" stroke="#c8b56a" stroke-width="1"'+dash+'/>';
    });
  }
  svg.innerHTML = d;
}
async function tick() {
  const data = await (await fetch("/api")).json();
  document.getElementById("clock").textContent = data.clock;
  document.getElementById("account").textContent = data.account;
  const v = document.getElementById("verdict");
  v.textContent = data.verdict;
  v.className = cls(data.verdict_kind);
  document.getElementById("rows").innerHTML = data.rows.map(r => row(r.label, r.text, r.kind)).join("");
  document.getElementById("ea").textContent = data.ea;
  draw(data.bars, data.open930);
}
tick();
setInterval(tick, 2000);
</script>
</body>
</html>
"""


def read_log_tail():
    day = datetime.now().strftime("%Y%m%d")
    path = LOG / f"{day}.log"
    if not path.exists():
        return "The EA has not written a log today."
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        raw = raw[2:]
    text = raw.decode("utf-16-le", errors="replace")
    interesting = []
    for line in text.splitlines():
        if any(token in line for token in ("SIGNAL|", "FILTER|", "event=structure", "event=book", "event=initialized")):
            interesting.append(line.split("\t")[-1].strip())
    if not interesting:
        return "The EA is loaded. It has not logged a buy or a sell yet."
    return "Latest from the EA: " + interesting[-1]


def ny_now(offset_hours):
    real_utc = datetime.now(timezone.utc)
    return real_utc + timedelta(hours=-4)


def bar_ny(bar_time, offset_hours):
    real_utc = datetime.fromtimestamp(int(bar_time) - offset_hours * 3600, timezone.utc)
    return real_utc + timedelta(hours=-4)


def server_offset_hours(tick_time):
    delta = int(tick_time) - datetime.now(timezone.utc).timestamp()
    return int(round(delta / 3600.0))


def ride_view(bars, minutes):
    if minutes <= 11 * 60:
        return "wait", "Waits until the 11:00 shot bar is done"
    closed = bars[:-1]
    if len(closed) < 6:
        return "wait", "Waiting for a half hour of bars"
    window = closed[-6:]
    net = window[-1]["c"] - window[0]["o"]
    if abs(net) < 12:
        return "pass", f"Last half hour moved {net:+.1f}, needs 12"
    buy = net > 0
    if buy:
        pullback = max(bar["h"] for bar in window) - window[-1]["c"]
    else:
        pullback = window[-1]["c"] - min(bar["l"] for bar in window)
    if pullback > abs(net) * 0.5:
        return "pass", "The move has given back half"
    bite = min(25.0, max(8.0, abs(net) * 0.40))
    word = "Buy" if buy else "Sell"
    return ("buy" if buy else "sell"), f"{word} the move, take about {bite:.0f} points"


def side_for(move, fade):
    if abs(move) < SHOT_POINTS:
        return "pass", f"{abs(move):.1f} points, needs {SHOT_POINTS:.0f}"
    if fade:
        kind = "sell" if move > 0 else "buy"
    else:
        kind = "buy" if move > 0 else "sell"
    word = "Buy" if kind == "buy" else "Sell"
    return kind, f"{word} if this is the close ({abs(move):.1f} points)"


def snapshot():
    if mt5.terminal_info() is None and not mt5.initialize():
        return {"clock": "MetaTrader is not connected.", "account": "", "verdict": "Cannot see the chart",
                "verdict_kind": "wait", "rows": [], "ea": "", "bars": [], "open930": None}
    tick = mt5.symbol_info_tick(SYMBOL)
    info = mt5.account_info()
    rates = mt5.copy_rates_from_pos(SYMBOL, mt5.TIMEFRAME_M5, 0, 80)
    if tick is None or rates is None:
        return {"clock": "No US100.cash prices yet.", "account": "", "verdict": "Waiting for prices",
                "verdict_kind": "wait", "rows": [], "ea": read_log_tail(), "bars": [], "open930": None}

    offset = server_offset_hours(tick.time)
    now = ny_now(offset)
    spread = (tick.ask - tick.bid) / 0.01
    bars = []
    open930 = None
    for rate in rates:
        when = bar_ny(rate["time"], offset)
        bars.append({"t": when.strftime("%H:%M"), "o": float(rate["open"]), "h": float(rate["high"]),
                     "l": float(rate["low"]), "c": float(rate["close"])})
        if when.hour == 9 and when.minute == 30 and when.date() == now.date():
            open930 = float(rate["open"])

    price = float(tick.bid)
    move = None if open930 is None else price - open930
    minutes = now.hour * 60 + now.minute
    spread_ok = spread <= SPREAD_MAX
    positions = mt5.positions_get(symbol=SYMBOL) or []
    managed = [p for p in positions if p.magic == MAGIC]

    if managed:
        position = managed[0]
        kind = "buy" if position.type == mt5.POSITION_TYPE_BUY else "sell"
        verdict = "In a trade"
        verdict_kind = kind
        pos_text = f"{'Buy' if kind == 'buy' else 'Sell'} {position.volume:.2f} at {position.price_open:.2f}"
    else:
        pos_text = "No open trade"
        if open930 is None:
            verdict = "Watching for the 09:30 New York open"
            verdict_kind = "wait"
        elif minutes < 10 * 60:
            kind, _ = side_for(move, fade=True)
            if kind == "pass":
                verdict = "10:00 shot would pass on this price"
                verdict_kind = "pass"
            else:
                verdict = "10:00 shot is lining up a " + ("buy" if kind == "buy" else "sell")
                verdict_kind = kind
        elif minutes < 11 * 60:
            kind, _ = side_for(move, fade=False)
            if kind == "pass":
                verdict = "11:00 shot would pass, fallback can still go with the move"
                verdict_kind = "wait"
            else:
                verdict = "11:00 shot is lining up a " + ("buy" if kind == "buy" else "sell")
                verdict_kind = kind
        else:
            verdict = "Shots have had their bar. A ride can hop on a move already going."
            verdict_kind = "wait"

    ten_kind, ten_text = ("wait", "Waiting for the 09:30 open") if move is None else side_for(move, True)
    eleven_kind, eleven_text = ("wait", "Waiting for the 09:30 open") if move is None else side_for(move, False)
    if move is None:
        fall_kind, fall_text = "wait", "Waiting for the 09:30 open"
    elif abs(move) >= SHOT_POINTS:
        fall_kind, fall_text = "pass", "Not used if the 60-point shot is taken"
    elif abs(move) >= 0.5:
        fall_kind = "buy" if move > 0 else "sell"
        fall_text = f"{'Buy' if fall_kind == 'buy' else 'Sell'} the smaller 11:00 trade, stop 30, target 120"
    else:
        fall_kind, fall_text = "pass", "Morning is flat"

    if minutes <= 11 * 60:
        structure = "Held back until the 11:00 shot bar is done"
    else:
        structure = "Allowed to look. It still needs a clean fair-value gap."

    ride_kind, ride_text = ride_view(bars, minutes)
    if not managed and minutes > 11 * 60 and ride_kind in ("buy", "sell"):
        verdict = ride_text
        verdict_kind = ride_kind

    if not spread_ok:
        verdict = "Spread is too wide to send an order"
        verdict_kind = "pass"

    rows = [
        {"label": "New York", "text": now.strftime("%H:%M"), "kind": "wait"},
        {"label": "Spread", "text": f"{spread:.0f} points, max {SPREAD_MAX}", "kind": "wait" if spread_ok else "pass"},
        {"label": "Move from 09:30", "text": "not printed yet" if move is None else f"{move:+.1f} points", "kind": "wait"},
        {"label": "10:00 fade", "text": ten_text, "kind": ten_kind},
        {"label": "11:00 with the move", "text": eleven_text, "kind": eleven_kind},
        {"label": "11:00 fallback", "text": fall_text, "kind": fall_kind},
        {"label": "Structure long or short", "text": structure, "kind": "wait"},
        {"label": "Ride", "text": ride_text, "kind": ride_kind},
        {"label": "Position", "text": pos_text, "kind": "buy" if managed and managed[0].type == mt5.POSITION_TYPE_BUY else ("sell" if managed else "pass")},
    ]
    account = ""
    if info is not None:
        account = f"Demo {info.login}  Balance ${info.balance:,.0f}"
    return {
        "clock": f"New York {now.strftime('%H:%M:%S')}  ·  this PC {datetime.now().strftime('%H:%M:%S')}",
        "account": account,
        "verdict": verdict,
        "verdict_kind": verdict_kind,
        "rows": rows,
        "ea": read_log_tail(),
        "bars": bars[-60:],
        "open930": open930,
    }


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
    mt5.initialize()
    servers = [ThreadingHTTPServer((HOST, port), Handler) for port in PORTS]
    for server in servers:
        print(f"http://{server.server_address[0]}:{server.server_address[1]}/", flush=True)
    for server in servers[1:]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    servers[0].serve_forever()


if __name__ == "__main__":
    main()
