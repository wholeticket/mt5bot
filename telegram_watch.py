"""Tell a private Telegram chat what the pass bot is doing.

The token stays in %LOCALAPPDATA%\\mt5bot\\telegram.env, never in this repo.
Message the bot /start once, from the phone you want alerts on.
"""

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import MetaTrader5 as mt5

DATA = Path(r"C:\Users\user\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075")
ENV_PATH = Path.home() / "AppData" / "Local" / "mt5bot" / "telegram.env"
SYMBOL = "US100.cash"
MAGIC = 26101201
POLL_SECONDS = 20

REASONS = {
    "spread": "spread too wide",
    "cost_too_high": "target too close for the spread",
    "daily_loss_money_lock": "today's loss limit is reached",
    "equity_floor": "equity floor is too close",
    "opex": "opex day, standing aside",
    "am_setup_already_formed": "the morning setup had already formed",
    "session_already_traded": "that session was already traded",
    "am_flat": "closed at 16:30 UK",
    "session_flat": "closed at the end of the session",
    "time_exit": "closed on the time exit",
    "thesis_spent": "the level was already gone",
    "reward_too_small": "the target was too close",
}


def load_env():
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not ENV_PATH.exists():
        ENV_PATH.write_text("BOT_TOKEN=\nCHAT_ID=\n", encoding="utf-8")
    values = {}
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def save_chat(chat_id):
    text = ENV_PATH.read_text(encoding="utf-8")
    lines = []
    found = False
    for line in text.splitlines():
        if line.startswith("CHAT_ID="):
            lines.append(f"CHAT_ID={chat_id}")
            found = True
        else:
            lines.append(line)
    if not found:
        lines.append(f"CHAT_ID={chat_id}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def api(token, method, payload=None, timeout=30):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def send(token, chat_id, text):
    if not chat_id:
        print(text)
        return
    api(token, "sendMessage", {"chat_id": int(chat_id), "text": text})


def money(value):
    return f"${value:,.0f}" if abs(value) >= 100 else f"${value:,.2f}"


def side_name(position_type):
    return "BUY" if position_type == mt5.POSITION_TYPE_BUY else "SELL"


def lots_text(volume):
    return f"{volume:.0f}" if volume >= 10 else f"{volume:.2f}"


def connect():
    if mt5.terminal_info() is not None:
        return True
    return mt5.initialize()


def account_text():
    if not connect():
        return "MetaTrader is closed on this PC."
    info = mt5.account_info()
    terminal = mt5.terminal_info()
    if info is None or terminal is None or not terminal.connected:
        return "MetaTrader is open, but the FTMO login is disconnected."
    lines = [
        "PASS BOT",
        f"Login {info.login}",
        f"Balance {money(info.balance)}",
        f"Equity {money(info.equity)}",
        "Trading is on" if info.trade_allowed and terminal.trade_allowed else "Trading is off, so no order can be sent",
    ]
    positions = mt5.positions_get() or []
    managed = [p for p in positions if p.magic == MAGIC]
    if not managed:
        lines.append("No open trade")
    for position in managed:
        lines.append(
            f"{side_name(position.type)} {position.symbol} {lots_text(position.volume)} lots @ {position.price_open:.2f}"
        )
        lines.append(f"Stop {position.sl:.2f}  Target {position.tp:.2f}")
        lines.append(f"Open profit {money(position.profit)}")
    return "\n".join(lines)


def deal_profit(ticket):
    # Deal times follow the broker clock, which is ahead of this PC.
    deals = mt5.history_deals_get(datetime.now() - timedelta(days=2), datetime.now() + timedelta(days=1))
    if not deals:
        return None
    total = 0.0
    found = False
    for deal in deals:
        if deal.position_id == ticket and deal.entry in (mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT):
            total += deal.profit + deal.commission + deal.swap
            found = True
    return total if found else None


def close_text(result):
    if result > 0.005:
        return f"Trade closed\nProfit {money(result)}"
    if result < -0.005:
        return f"Trade closed\nLoss {money(abs(result))}"
    return "Trade closed\nFlat $0.00"


def position_map():
    if not connect():
        return None
    positions = mt5.positions_get() or []
    return {
        p.ticket: (p.symbol, p.type, p.volume, p.price_open, p.sl, p.tp, p.profit)
        for p in positions
        if p.magic == MAGIC
    }


def describe_position_changes(previous, current, pending):
    notes = []
    if previous is None or current is None:
        return notes
    for ticket, row in current.items():
        symbol, kind, volume, price, stop, target, profit = row
        if ticket not in previous:
            notes.append(
                "New signal\n"
                f"{side_name(kind)} {symbol} NOW AT {price:.2f}\n"
                f"TAKE PROFIT AT {target:.2f}\n"
                f"STOP LOSS AT {stop:.2f}"
            )
            continue
        _old_symbol, old_kind, old_volume, old_price, old_stop, old_target, _old_profit = previous[ticket]
        if volume < old_volume - 0.01:
            notes.append(
                f"Partial close\n"
                f"{lots_text(old_volume - volume)} lots closed, {lots_text(volume)} still open\n"
                f"Open profit {money(profit)}"
            )
        if abs(stop - old_stop) > 0.05:
            if abs(stop - price) < 1.0:
                notes.append(f"Stop moved to the entry, {stop:.2f}")
            else:
                notes.append(f"Stop moved to {stop:.2f}")
    now = time.time()
    for ticket in previous:
        if ticket not in current:
            pending[ticket] = now
    for ticket, seen in list(pending.items()):
        if ticket in current:
            pending.pop(ticket, None)
            continue
        result = deal_profit(ticket)
        if result is None and now - seen < 90:
            continue
        notes.append(close_text(result) if result is not None else "Trade closed")
        pending.pop(ticket, None)
    return notes


def expert_log_path(day):
    return DATA / "MQL5" / "Logs" / f"{day.strftime('%Y%m%d')}.log"


def fresh_log(day, offset):
    path = expert_log_path(day)
    if not path.exists():
        return offset, []
    raw = path.read_bytes()
    if raw.startswith(b"\xff\xfe"):
        raw = raw[2:]
    text = raw.decode("utf-16-le", errors="replace")
    if offset > len(text):
        offset = 0
    chunk = text[offset:]
    return len(text), [line for line in chunk.splitlines() if line.strip()]


def translate_log(line):
    parts = line.split("\t")
    message = parts[-1] if parts else ""
    if "|" not in message or "RobustForexEA" not in line:
        return None
    fields = {}
    for piece in message.split("|"):
        if "=" in piece:
            key, value = piece.split("=", 1)
            fields[key] = value
    event = fields.get("event", "")
    if message.startswith("EA|") and event == "deinitialized":
        return "The bot was removed from the chart. This PC will not take the next trade until it is put back."
    if message.startswith("TRADE|") and event == "open_failed":
        return f"The order was rejected. {fields.get('description', '')}".strip()
    if message.startswith("TRADE|") and event == "open_blocked":
        return f"No trade. {REASONS.get(fields.get('reason', ''), fields.get('reason', 'blocked'))}"
    if message.startswith("FILTER|") and event == "entry_blocked":
        return f"No trade. {REASONS.get(fields.get('reason', ''), fields.get('reason', 'blocked'))}"
    if message.startswith("RISK|") and event == "entry_blocked":
        return f"No trade. {REASONS.get(fields.get('reason', ''), fields.get('reason', 'blocked'))}"
    if message.startswith("FILTER|") and event == "calendar_unavailable":
        return None
    return None


def handle_updates(token, chat_id, offset):
    try:
        result = api(token, "getUpdates", {"timeout": 1, "offset": offset}, timeout=10)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return chat_id, offset
    for update in result.get("result", []):
        offset = update["update_id"] + 1
        message = update.get("message") or {}
        text = (message.get("text") or "").strip()
        incoming = str(message.get("chat", {}).get("id", ""))
        if not incoming:
            continue
        if not chat_id and text.startswith("/start"):
            chat_id = incoming
            save_chat(chat_id)
            send(token, chat_id, "This chat will get the pass bot updates.\n\n" + account_text())
            continue
        if incoming != str(chat_id):
            continue
        if text.startswith("/start") or text.startswith("/status"):
            send(token, chat_id, account_text())
    return chat_id, offset


def main():
    env = load_env()
    token = env.get("BOT_TOKEN", "")
    chat_id = env.get("CHAT_ID", "")
    if not token:
        print(f"Add the BotFather token to {ENV_PATH}")
        return
    connect()
    offset = 0
    try:
        existing = api(token, "getUpdates", {"timeout": 0, "offset": -1}, timeout=15)
        if existing.get("result"):
            offset = existing["result"][-1]["update_id"] + 1
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        pass
    day = datetime.now()
    offset_log, _lines = fresh_log(day, 0)
    previous = position_map()
    pending_closes = {}
    was_connected = previous is not None
    print("watching", flush=True)
    if chat_id:
        send(token, chat_id, "Watcher is on.\n\n" + account_text())
    while True:
        now = datetime.now()
        if now.date() != day.date():
            day = now
            offset_log = 0
        chat_id, offset = handle_updates(token, chat_id, offset)
        try:
            offset_log, lines = fresh_log(day, offset_log)
            for line in lines:
                note = translate_log(line)
                if note and chat_id:
                    send(token, chat_id, note)
            current = position_map()
            connected = current is not None and mt5.terminal_info() is not None and mt5.terminal_info().connected
            if was_connected and not connected and chat_id:
                send(token, chat_id, "MetaTrader lost the FTMO connection. No new trade can be taken until it is back.")
            if connected and not was_connected and chat_id and previous is not None:
                send(token, chat_id, "FTMO connection is back.\n\n" + account_text())
            was_connected = connected
            if connected:
                for note in describe_position_changes(previous, current, pending_closes):
                    print(note.replace("\n", " | "), flush=True)
                    if chat_id:
                        send(token, chat_id, note)
                previous = current
        except Exception as error:
            print(f"{now:%H:%M:%S} {error}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
