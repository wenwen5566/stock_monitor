import csv
import html
import os
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_FILE = os.path.join(APP_DIR, "watchlist.csv")
REFRESH_SECONDS = 30
ET = ZoneInfo("America/New_York")

BG = "#080808"
PANEL = "#111111"
FG = "#F4F4F4"
MUTED = "#A7A7A7"
GRID = "#292929"
FAR = "#46390D"
NEAR = "#79770E"
ENTRY_TRIGGERED = "#E02828"
BREAKOUT_TRIGGERED = "#098105"

st.set_page_config(page_title="US Stock Target Monitor", page_icon="📈", layout="wide")


def to_float(value):
    value = (value or "").strip()
    return None if not value else float(value)


def load_watchlist():
    rows = []
    with open(WATCHLIST_FILE, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"symbol", "name", "entry_price", "breakout_price"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must contain: symbol,name,entry_price,breakout_price")
        for row in reader:
            symbol = (row.get("symbol") or "").strip().upper()
            if symbol:
                rows.append({
                    "symbol": symbol,
                    "name": (row.get("name") or symbol).strip(),
                    "entry_price": to_float(row.get("entry_price")),
                    "breakout_price": to_float(row.get("breakout_price")),
                })
    return rows


def fetch_quotes(symbols):
    quotes = {}
    if not symbols:
        return quotes
    data = yf.download(
        tickers=symbols,
        period="1d",
        interval="1m",
        group_by="ticker",
        auto_adjust=False,
        progress=False,
        threads=True,
        prepost=True,
    )

    def save(sym, frame):
        try:
            close = frame["Close"].dropna()
            if close.empty:
                return
            ts = close.index[-1]
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.tz_localize("UTC")
            quotes[sym] = {
                "price": float(close.iloc[-1]),
                "quote_time": ts.tz_convert(ET).to_pydatetime(),
            }
        except Exception:
            pass

    if len(symbols) == 1:
        if data is not None and not data.empty:
            save(symbols[0], data)
    else:
        for sym in symbols:
            try:
                save(sym, data[sym])
            except Exception:
                pass

    for sym in [s for s in symbols if s not in quotes]:
        try:
            hist = yf.Ticker(sym).history(period="1d", interval="1m", prepost=True)
            save(sym, hist)
        except Exception:
            pass
    return quotes


def market_session(now):
    if now.weekday() >= 5:
        return "CLOSED"
    t = now.time()
    if dtime(4, 0) <= t < dtime(9, 30):
        return "PRE"
    if dtime(9, 30) <= t < dtime(16, 0):
        return "RTH"
    if dtime(16, 0) <= t < dtime(20, 0):
        return "POST"
    return "CLOSED"


def build_rows(watchlist, quotes, target_key, mode):
    rows = []
    for row in watchlist:
        q = quotes.get(row["symbol"])
        target = row[target_key]
        if not q or target is None:
            continue
        price = q["price"]
        dist = (price - target) / target * 100.0
        rows.append({
            "symbol": row["symbol"],
            "name": row["name"],
            "price": price,
            "target": target,
            "dollar": price - target,
            "distance": dist,
            "quote_time": q.get("quote_time"),
        })
    return sorted(rows, key=lambda x: x["distance"], reverse=(mode == "exit"))


def row_color(distance, mode):
    if mode == "entry":
        if distance < 0:
            return ENTRY_TRIGGERED
        if distance <= 0.75:
            return NEAR
        if distance <= 1.50:
            return FAR
    else:
        if distance > 0:
            return BREAKOUT_TRIGGERED
        if distance >= -0.75:
            return NEAR
        if distance >= -1.50:
            return FAR
    return PANEL


def render_table(rows, target_label, mode):
    if not rows:
        st.info("No quotes available for this panel.")
        return
    parts = [f"""
    <div class="table-wrap"><table class="monitor-table">
      <thead><tr><th>Symbol</th><th>Last</th><th>{html.escape(target_label)}</th><th>$ Diff</th><th>Distance</th></tr></thead><tbody>
    """]
    for r in rows:
        color = row_color(r["distance"], mode)
        parts.append(
            f'<tr style="background:{color}">'
            f'<td><b>{html.escape(r["symbol"])}</b></td>'
            f'<td>${r["price"]:,.2f}</td>'
            f'<td>${r["target"]:,.2f}</td>'
            f'<td>{r["dollar"]:+,.2f}</td>'
            f'<td><b>{r["distance"]:+.2f}%</b></td>'
            '</tr>'
        )
    parts.append("</tbody></table></div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


def update_alert_log(entry_rows, exit_rows):
    if "prev_dist" not in st.session_state:
        st.session_state.prev_dist = {}
    if "entry_logs" not in st.session_state:
        st.session_state.entry_logs = []
    if "exit_logs" not in st.session_state:
        st.session_state.exit_logs = []
    now = datetime.now(ET).strftime("%H:%M:%S")
    for mode, rows, logs in (("ENTRY", entry_rows, st.session_state.entry_logs), ("EXIT", exit_rows, st.session_state.exit_logs)):
        for r in rows:
            key = (r["symbol"], mode)
            prev = st.session_state.prev_dist.get(key)
            cur = r["distance"]
            crossed = (mode == "ENTRY" and cur <= 0 and prev is not None and prev > 0) or (mode == "EXIT" and cur >= 0 and prev is not None and prev < 0)
            if crossed:
                logs.insert(0, f'{now}  {r["symbol"]:<6}  TARGET CROSSED  ${r["price"]:,.2f}  {cur:+.2f}%')
                del logs[30:]
            st.session_state.prev_dist[key] = cur


def render_log(lines):
    shown = lines[:3]
    if not shown:
        shown = ["No alerts in this browser session."]
    text = "\n".join(html.escape(x) for x in shown)
    st.markdown(f'<div class="log-box"><pre>{text}</pre></div>', unsafe_allow_html=True)


st.markdown(f"""
<style>
.stApp {{ background: {BG}; color: {FG}; }}
[data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
.block-container {{ max-width: 1600px; padding-top: 0.8rem; padding-bottom: 1rem; }}
.statusbar {{ color:{MUTED}; font-size:0.95rem; margin:0 0 .55rem 0; }}
.panel-title {{ font-size:1.35rem; font-weight:800; color:{FG}; margin:.2rem 0 .45rem; }}
.table-wrap {{ border:1px solid {GRID}; border-radius:8px; overflow:auto; background:{PANEL}; }}
.monitor-table {{ width:100%; border-collapse:collapse; font-size:1.02rem; color:{FG}; }}
.monitor-table th {{ background:#1B1B1B; position:sticky; top:0; padding:10px 8px; border-bottom:1px solid {GRID}; text-align:center; }}
.monitor-table td {{ padding:10px 8px; border-bottom:1px solid {GRID}; text-align:center; white-space:nowrap; }}
.log-title {{ font-size:1.18rem; font-weight:800; margin:.65rem 0 .25rem; }}
.log-box {{ height:88px; overflow:auto; border:1px solid {GRID}; border-radius:8px; background:{PANEL}; padding:8px 10px; }}
.log-box pre {{ margin:0; color:{FG}; font-size:.92rem; line-height:1.45; white-space:pre-wrap; }}
@media (max-width: 800px) {{
  .block-container {{ padding-left:.55rem; padding-right:.55rem; }}
  .monitor-table {{ font-size:.90rem; }}
  .monitor-table th,.monitor-table td {{ padding:8px 5px; }}
  .panel-title {{ font-size:1.18rem; }}
}}
</style>
""", unsafe_allow_html=True)

# Auto refresh using a tiny browser-side reload; no extra dependency is required.
st.markdown(f'<script>setTimeout(function(){{window.location.reload();}}, {REFRESH_SECONDS * 1000});</script>', unsafe_allow_html=True)

try:
    watchlist = load_watchlist()
    symbols = list(dict.fromkeys(r["symbol"] for r in watchlist))
    with st.spinner("Updating Yahoo Finance quotes..."):
        quotes = fetch_quotes(symbols)
except Exception as exc:
    st.error(f"Update failed: {exc}")
    st.stop()

now = datetime.now(ET)
qtimes = [q["quote_time"] for q in quotes.values() if q.get("quote_time")]
if qtimes:
    newest = max(qtimes)
    age = max(0, int((now - newest).total_seconds()))
    quote_text = f"Newest quote {newest:%H:%M:%S} ET · {age}s ago"
else:
    quote_text = "Newest quote --"

st.markdown(
    f'<div class="statusbar">SESSION: <b>{market_session(now)}</b> &nbsp; · &nbsp; Updated: <b>{len(quotes)}/{len(symbols)}</b> &nbsp; · &nbsp; App update {now:%H:%M:%S} ET &nbsp; · &nbsp; {quote_text} &nbsp; · &nbsp; Auto refresh {REFRESH_SECONDS}s</div>',
    unsafe_allow_html=True,
)

entry_rows = build_rows(watchlist, quotes, "entry_price", "entry")
exit_rows = build_rows(watchlist, quotes, "breakout_price", "exit")
update_alert_log(entry_rows, exit_rows)

left, right = st.columns(2, gap="medium")
with left:
    st.markdown('<div class="panel-title">ENTRY &nbsp; | &nbsp; LOW TO HIGH</div>', unsafe_allow_html=True)
    render_table(entry_rows, "Entry", "entry")
    st.markdown('<div class="log-title">ENTRY ALERT LOG</div>', unsafe_allow_html=True)
    render_log(st.session_state.entry_logs)
with right:
    st.markdown('<div class="panel-title">BREAKOUT / EXIT &nbsp; | &nbsp; HIGH TO LOW</div>', unsafe_allow_html=True)
    render_table(exit_rows, "Exit", "exit")
    st.markdown('<div class="log-title">BREAKOUT / EXIT ALERT LOG</div>', unsafe_allow_html=True)
    render_log(st.session_state.exit_logs)

st.caption("Yahoo Finance/yfinance is used for convenience and may not be exchange-grade real-time data. Alert logs in this first cloud version exist only for the active browser session.")
