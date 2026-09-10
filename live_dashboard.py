# ============================================================
# SANJAY RANA - DELTA REAL TRADING DASHBOARD
# PART 1/4
# ============================================================

import os
import time
import json
import hmac
import hashlib
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# SETTINGS
# ============================================================

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://api.india.delta.exchange"
).rstrip("/")

SYMBOL = os.getenv("DELTA_SYMBOL", "BTCUSD")
PRODUCT_ID = int(os.getenv("DELTA_PRODUCT_ID", "27"))

TIMEFRAME = "5m"
CANDLE_SECONDS = 300

ATR_PERIOD = 10
MULTIPLIER = 3.0

REFRESH_SECONDS = 1
# ============================================================
# INDIAN TIME FUNCTION (इसे सबसे ऊपर रखें)
# ============================================================

IST = timezone(timedelta(hours=5, minutes=30))

def indian_time(timestamp):
    try:
        ts = int(float(timestamp))
        if ts > 10_000_000_000:
            ts = ts // 1000
        return datetime.fromtimestamp(
            ts,
            tz=timezone.utc
        ).astimezone(IST).strftime(
            "%Y-%m-%d %H:%M:%S IST"
        )
    except Exception:
        return "-"


def show_price(val):
    try:
        if val is None or pd.isna(val):
            return "-"
        return f"${float(val):,.2f}"
    except Exception:
        return str(val)

def number(val, default=0.0):
    try:
        if val is None or pd.isna(val):
            return default
        return float(val)
    except Exception:
        return default
        

# ============================================================
# REAL TRADING MASTER SWITCH
# ============================================================

REMOTE_TRADING = (
    os.getenv("REMOTE_TRADING", "false").lower() == "true"
)

# ============================================================
# DEFAULT REMOTE CONTROL SETTINGS
# ============================================================

DEFAULT_BUY_OFFSET = int(
    os.getenv("BUY_OFFSET", "-50")
)

DEFAULT_SELL_OFFSET = int(
    os.getenv("SELL_OFFSET", "50")
)

DEFAULT_ORDER_SIZE = int(
    os.getenv("ORDER_SIZE", "1")
)

# LIMIT pending रहने के बाद कितने seconds में MARKET करना है.
# 0 = automatic MARKET conversion बंद.
DEFAULT_LIMIT_TIMEOUT = int(
    os.getenv("LIMIT_TIMEOUT", "60")
)

TARGET_1 = int(os.getenv("TARGET_1", "300"))
TARGET_2 = int(os.getenv("TARGET_2", "600"))
TARGET_3 = int(os.getenv("TARGET_3", "900"))


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Sanjay Rana Real Trading",
    page_icon="📈",
    layout="wide"
)


# ============================================================
# MAIN TABS — WATCHLIST / TRADINGVIEW FULL SCREEN / DASHBOARD
# ============================================================
selected_tab = st.radio(
    "SELECT VIEW",
    ["Watchlist", "Demo Account", "TradingView Chart", "Trading Dashboard"],
    horizontal=True,
    key="main_view_tab"
)

if selected_tab == "Watchlist":
    st.title("📋 WATCHLIST (LIVE TICK & LOGOS)")

    st.markdown("""
    <style>
    .watch-card {
        border: 1px solid rgba(128,128,128,.30);
        border-radius: 12px;
        padding: 10px;
        margin-bottom: 10px;
        background: rgba(128,128,128,.08);
    }
    </style>
    """, unsafe_allow_html=True)

    components.html("""
    <div style="display:flex; flex-direction:column; gap:8px; width:100%;">
      <div class="watch-card">
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-single-quote.js" async>
        {"symbol":"BINANCE:BTCUSDT","width":"100%","colorTheme":"dark","isTransparent":true,"locale":"en"}
        </script>
      </div>
      <div class="watch-card">
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-single-quote.js" async>
        {"symbol":"BINANCE:ETHUSDT","width":"100%","colorTheme":"dark","isTransparent":true,"locale":"en"}
        </script>
      </div>
      <div class="watch-card">
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-single-quote.js" async>
        {"symbol":"BINANCE:TAOUSDT","width":"100%","colorTheme":"dark","isTransparent":true,"locale":"en"}
        </script>
      </div>
      <div class="watch-card">
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-single-quote.js" async>
        {"symbol":"OANDA:XAUUSD","width":"100%","colorTheme":"dark","isTransparent":true,"locale":"en"}
        </script>
      </div>
    </div>
    """, height=520, scrolling=False)

    st.stop()
    

# ============================================================
# DEMO ACCOUNT — COMPLETELY SEPARATE SYSTEM
# Based on the same 5-minute SuperTrend logic as the real system.
# REAL DELTA ORDERS ARE NEVER USED HERE.
# ============================================================

def demo_get_candles():
    try:
        end = int(time.time())
        start = end - (500 * CANDLE_SECONDS)
        response = requests.get(
            BASE_URL + "/v2/history/candles",
            params={
                "symbol": SYMBOL,
                "resolution": TIMEFRAME,
                "start": start,
                "end": end
            },
            timeout=10
        )
        return response.json()
    except Exception:
        return None


def demo_make_dataframe(data):
    if not isinstance(data, dict) or not data.get("success"):
        return pd.DataFrame()
    result = data.get("result")
    if not isinstance(result, list):
        return pd.DataFrame()
    rows = []
    for candle in result:
        try:
            rows.append({
                "time": int(candle["time"]),
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
            })
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .drop_duplicates("time")
        .sort_values("time")
        .reset_index(drop=True)
    )


def demo_supertrend(df_in):
    df = df_in.copy()
    prev_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    df["ATR"] = float("nan")

    first_atr = df["TR"].iloc[:ATR_PERIOD].mean()
    df.loc[ATR_PERIOD - 1, "ATR"] = first_atr

    for i in range(ATR_PERIOD, len(df)):
        df.loc[i, "ATR"] = (
            df.loc[i - 1, "ATR"] * (ATR_PERIOD - 1)
            + df.loc[i, "TR"]
        ) / ATR_PERIOD

    df["HL2"] = (df["high"] + df["low"]) / 2.0
    df["UP"] = float("nan")
    df["DN"] = float("nan")
    df["TREND"] = float("nan")
    df["SUPERTREND"] = float("nan")
    df["SIGNAL"] = ""

    for i in range(len(df)):
        atr = df.loc[i, "ATR"]
        if pd.isna(atr):
            continue
        src = df.loc[i, "HL2"]
        upper_basic = src + MULTIPLIER * atr
        lower_basic = src - MULTIPLIER * atr

        if i == ATR_PERIOD - 1:
            df.loc[i, "UP"] = upper_basic
            df.loc[i, "DN"] = lower_basic
            df.loc[i, "TREND"] = 1
            df.loc[i, "SUPERTREND"] = upper_basic
            continue

        previous_up = df.loc[i - 1, "UP"]
        previous_dn = df.loc[i - 1, "DN"]
        previous_trend = df.loc[i - 1, "TREND"]
        previous_close = df.loc[i - 1, "close"]

        if pd.isna(previous_up):
            previous_up = upper_basic
        if pd.isna(previous_dn):
            previous_dn = lower_basic
        if pd.isna(previous_trend):
            previous_trend = 1

        lower_band = (
            lower_basic if lower_basic > previous_dn or previous_close < previous_dn
            else previous_dn
        )
        upper_band = (
            upper_basic if upper_basic < previous_up or previous_close > previous_up
            else previous_up
        )

        close = df.loc[i, "close"]
        trend = previous_trend
        if previous_trend == 1:
            trend = -1 if close > upper_band else 1
        else:
            trend = 1 if close < lower_band else -1

        df.loc[i, "UP"] = upper_band
        df.loc[i, "DN"] = lower_band
        df.loc[i, "TREND"] = trend
        df.loc[i, "SUPERTREND"] = lower_band if trend == -1 else upper_band

        if trend == -1 and previous_trend == 1:
            df.loc[i, "SIGNAL"] = "BUY"
        elif trend == 1 and previous_trend == -1:
            df.loc[i, "SIGNAL"] = "SELL"

    return df
def run_demo_account():
    if "demo_position" not in st.session_state:
        st.session_state.demo_position = None
    if "demo_pending" not in st.session_state:
        st.session_state.demo_pending = None
    if "demo_history" not in st.session_state:
        st.session_state.demo_history = []
    if "demo_last_processed_bar" not in st.session_state:
        st.session_state.demo_last_processed_bar = 0

    st.title("🟢 DEMO ACCOUNT (AUTO-TRADING)")
    st.caption("Automatic SuperTrend Virtual Trading & History Tracker")

    data = demo_get_candles()
    df_demo = demo_make_dataframe(data)

    current_start = (int(time.time()) // CANDLE_SECONDS) * CANDLE_SECONDS
    if not df_demo.empty:
        df_demo = df_demo[df_demo["time"] < current_start].reset_index(drop=True)

    if len(df_demo) < ATR_PERIOD + 5:
        st.error("Demo SuperTrend ke liye enough candles nahi hain.")
        return

    df_demo = demo_supertrend(df_demo)
    last = df_demo.iloc[-1]
    last_bar_time = int(last["time"])
    last_close = float(last["close"])
    last_high = float(last["high"])
    last_low = float(last["low"])
    last_signal = str(last["SIGNAL"])
    last_st = float(last["SUPERTREND"])

    # --------------------------------------------------------
    # AUTO ORDER GENERATION ON SIGNAL FLIP
    # --------------------------------------------------------
    if st.session_state.demo_last_processed_bar != last_bar_time:
        st.session_state.demo_last_processed_bar = last_bar_time

        if last_signal in ["BUY", "SELL"]:
            if st.session_state.demo_pending:
                if st.session_state.demo_pending["side"] != last_signal:
                    st.session_state.demo_pending = None

            if not st.session_state.demo_position and not st.session_state.demo_pending:
                limit_price = last_close - 50 if last_signal == "BUY" else last_close + 50
                st.session_state.demo_pending = {
                    "side": last_signal,
                    "price": limit_price,
                    "signal_time": last_bar_time,
                }

    # --------------------------------------------------------
    # FILL PENDING LIMIT ORDER
    # --------------------------------------------------------
    pending = st.session_state.demo_pending
    if pending and pending["signal_time"] != last_bar_time:
        fill_price = pending["price"]
        if last_low <= fill_price <= last_high:
            st.session_state.demo_position = {
                "side": pending["side"],
                "entry": fill_price,
                "qty": 30,
                "entry_time": last_bar_time,
                "t1_hit": False,
                "t2_hit": False,
                "t3_hit": False,
            }
            st.session_state.demo_pending = None

    # --------------------------------------------------------
    # TARGET TRACKING & HISTORY RECORDING
    # --------------------------------------------------------
    pos = st.session_state.demo_position
    if pos:
        entry = pos["entry"]
        side = pos["side"]
        t1 = entry + TARGET_1 if side == "BUY" else entry - TARGET_1
        t2 = entry + TARGET_2 if side == "BUY" else entry - TARGET_2
        t3 = entry + TARGET_3 if side == "BUY" else entry - TARGET_3

        if not pos["t1_hit"] and ((side == "BUY" and last_high >= t1) or (side == "SELL" and last_low <= t1)):
            qty = 10
            pnl = TARGET_1 * qty if side == "BUY" else -TARGET_1 * qty
            pos["t1_hit"] = True
            pos["qty"] -= qty
            st.session_state.demo_history.insert(0, {"Time": indian_time(last_bar_time), "Side": side, "Entry": round(entry,2), "Exit": round(t1,2), "Qty": qty, "Reason": "TP1", "P&L": round(pnl,2)})

        if not pos["t2_hit"] and ((side == "BUY" and last_high >= t2) or (side == "SELL" and last_low <= t2)):
            qty = min(10, pos["qty"])
            pnl = TARGET_2 * qty if side == "BUY" else -TARGET_2 * qty
            pos["t2_hit"] = True
            pos["qty"] -= qty
            st.session_state.demo_history.insert(0, {"Time": indian_time(last_bar_time), "Side": side, "Entry": round(entry,2), "Exit": round(t2,2), "Qty": qty, "Reason": "TP2", "P&L": round(pnl,2)})

        if not pos["t3_hit"] and ((side == "BUY" and last_high >= t3) or (side == "SELL" and last_low <= t3)):
            qty = min(10, pos["qty"])
            pnl = TARGET_3 * qty if side == "BUY" else -TARGET_3 * qty
            pos["t3_hit"] = True
            pos["qty"] -= qty
            st.session_state.demo_history.insert(0, {"Time": indian_time(last_bar_time), "Side": side, "Entry": round(entry,2), "Exit": round(t3,2), "Qty": qty, "Reason": "TP3", "P&L": round(pnl,2)})

        if pos["qty"] <= 0:
            st.session_state.demo_position = None

    # --------------------------------------------------------
    # SCREEN METRICS (WITHOUT BALANCE)
    # --------------------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("SUPERTrend", "BUY 🟢" if int(last["TREND"]) == -1 else "SELL 🔴")
    c2.metric("LAST CLOSED PRICE", show_price(last_close))
    c3.metric("ACTIVE TRADES / STATUS", "Running" if pos else "Waiting")

    st.write(f"**Confirmed 5-minute signal:** {last_signal or 'NO NEW FLIP'}")
    st.write(f"**SuperTrend Line:** {show_price(last_st)}")

    if st.session_state.demo_pending:
        p = st.session_state.demo_pending
        st.warning(f"⏳ DEMO LIMIT PENDING — {p['side']} @ {show_price(p['price'])}")

    if pos:
        st.success(f"OPEN DEMO {pos['side']} — Entry {show_price(pos['entry'])} — Qty {pos['qty']}")

    # --------------------------------------------------------
    # PERMANENT HISTORY TABLE
    # --------------------------------------------------------
    st.subheader("📜 DEMO TRADE HISTORY")
    if st.session_state.demo_history:
        st.dataframe(pd.DataFrame(st.session_state.demo_history), use_container_width=True, hide_index=True)
    else:
        st.info("No demo trades yet. Waiting for targets to hit...")

    # TradingView Live Widget (Bitcoin Only)
    st.subheader("📡 TRADINGVIEW LIVE MARKET")
    components.html("""
    <div style="display:flex;width:100%;">
      <div class="tradingview-widget-container" style="width:100%;"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-single-quote.js" async>{"symbol":"BINANCE:BTCUSDT","width":"100%","colorTheme":"dark","isTransparent":true,"locale":"en"}</script></div>
    </div>
    """, height=145, scrolling=False)
    

    data = demo_get_candles()
    df_demo = demo_make_dataframe(data)

    current_start = (int(time.time()) // CANDLE_SECONDS) * CANDLE_SECONDS
    if not df_demo.empty:
        df_demo = df_demo[df_demo["time"] < current_start].reset_index(drop=True)

    if len(df_demo) < ATR_PERIOD + 5:
        st.error("Demo SuperTrend ke liye enough 5-minute candles nahi hain.")
        return

    df_demo = demo_supertrend(df_demo)
    last = df_demo.iloc[-1]
    last_bar_time = int(last["time"])
    last_close = float(last["close"])
    last_high = float(last["high"])
    last_low = float(last["low"])
    last_signal = str(last["SIGNAL"])
    last_st = float(last["SUPERTREND"])

    # --------------------------------------------------------
    # ONE ORDER ONLY ON A CONFIRMED SUPERTREND FLIP
    # --------------------------------------------------------
    if st.session_state.demo_last_processed_bar != last_bar_time:
        st.session_state.demo_last_processed_bar = last_bar_time

        if last_signal in ["BUY", "SELL"]:
            st.session_state.demo_last_signal_time = last_bar_time

            # New flip cancels an unfilled opposite pending demo order.
            if st.session_state.demo_pending:
                if st.session_state.demo_pending["side"] != last_signal:
                    st.session_state.demo_pending = None

            # Do not create another order while a position/pending order exists.
            if not st.session_state.demo_position and not st.session_state.demo_pending:
                if last_signal == "BUY":
                    limit_price = last_close - 50
                else:
                    limit_price = last_close + 50

                st.session_state.demo_pending = {
                    "side": last_signal,
                    "price": limit_price,
                    "signal_time": last_bar_time,
                }

    # --------------------------------------------------------
    # FILL PENDING LIMIT ONLY ON A LATER CONFIRMED CANDLE
    # --------------------------------------------------------
    pending = st.session_state.demo_pending
    if pending and pending["signal_time"] != last_bar_time:
        fill_price = pending["price"]
        if last_low <= fill_price <= last_high:
            st.session_state.demo_position = {
                "side": pending["side"],
                "entry": fill_price,
                "qty": 30,
                "entry_time": last_bar_time,
                "t1_hit": False,
                "t2_hit": False,
                "t3_hit": False,
            }
            st.session_state.demo_pending = None

    # --------------------------------------------------------
    # POSITION TARGETS — 300 / 600 / 900 POINTS
    # --------------------------------------------------------
    pos = st.session_state.demo_position
    if pos:
        entry = pos["entry"]
        side = pos["side"]
        if side == "BUY":
            t1, t2, t3 = entry + TARGET_1, entry + TARGET_2, entry + TARGET_3
        else:
            t1, t2, t3 = entry - TARGET_1, entry - TARGET_2, entry - TARGET_3

        # Demo TP1/TP2/TP3 are tracked in history as partial exits.
        if not pos["t1_hit"] and ((side == "BUY" and last_high >= t1) or (side == "SELL" and last_low <= t1)):
            qty = 10
            pnl = TARGET_1 * qty
            if side == "SELL": pnl = -pnl
            st.session_state.demo_balance += pnl
            st.session_state.demo_realized_pnl += pnl
            pos["t1_hit"] = True
            pos["qty"] -= qty
            st.session_state.demo_history.insert(0, {"Time": indian_time(last_bar_time), "Side": side, "Entry": round(entry,2), "Exit": round(t1,2), "Qty": qty, "Reason": "TP1", "P&L": round(pnl,2)})

        if not pos["t2_hit"] and ((side == "BUY" and last_high >= t2) or (side == "SELL" and last_low <= t2)):
            qty = min(10, pos["qty"])
            pnl = TARGET_2 * qty
            if side == "SELL": pnl = -pnl
            st.session_state.demo_balance += pnl
            st.session_state.demo_realized_pnl += pnl
            pos["t2_hit"] = True
            pos["qty"] -= qty
            st.session_state.demo_history.insert(0, {"Time": indian_time(last_bar_time), "Side": side, "Entry": round(entry,2), "Exit": round(t2,2), "Qty": qty, "Reason": "TP2", "P&L": round(pnl,2)})

        if not pos["t3_hit"] and ((side == "BUY" and last_high >= t3) or (side == "SELL" and last_low <= t3)):
            qty = min(10, pos["qty"])
            pnl = TARGET_3 * qty
            if side == "SELL": pnl = -pnl
            st.session_state.demo_balance += pnl
            st.session_state.demo_realized_pnl += pnl
            pos["t3_hit"] = True
            pos["qty"] -= qty
            st.session_state.demo_history.insert(0, {"Time": indian_time(last_bar_time), "Side": side, "Entry": round(entry,2), "Exit": round(t3,2), "Qty": qty, "Reason": "TP3", "P&L": round(pnl,2)})

        if pos["qty"] <= 0:
            st.session_state.demo_position = None

    # --------------------------------------------------------
    # LIVE VIEW
    # --------------------------------------------------------
    # --------------------------------------------------------
    # SCREEN METRICS (WITHOUT BALANCE)
    # --------------------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("SUPERTrend", "BUY 🟢" if int(last["TREND"]) == -1 else "SELL 🔴")
    c2.metric("LAST CLOSED PRICE", show_price(last_close))
    c3.metric("ACTIVE TRADES / STATUS", "Running" if pos else "Waiting")

    st.write(f"**Confirmed 5-minute signal:** {last_signal or 'NO NEW FLIP'}")
    st.write(f"**SuperTrend Line:** {show_price(last_st)}")

    if st.session_state.demo_pending:
        p = st.session_state.demo_pending
        st.warning(f"⏳ DEMO LIMIT PENDING — {p['side']} @ {show_price(p['price'])}")

    if pos:
        st.success(f"OPEN DEMO {pos['side']} — Entry {show_price(pos['entry'])} — Qty {pos['qty']}")
        
    c3.metric("SUPERTrend", "BUY 🟢" if int(last["TREND"]) == -1 else "SELL 🔴")
    c4.metric("LAST CLOSED PRICE", show_price(last_close))
    last_close = float(last["close"])

    st.write(f"**Confirmed 5-minute signal:** {last_signal or 'NO NEW FLIP'}")
    st.write(f"**SuperTrend:** {show_price(last_st)}")

    if st.session_state.demo_pending:
        p = st.session_state.demo_pending
        st.warning(f"⏳ DEMO LIMIT PENDING — {p['side']} @ {show_price(p['price'])}")

    pos = st.session_state.demo_position
    if pos:
        entry = pos["entry"]
        side = pos["side"]
        if side == "BUY":
            t1, t2, t3 = entry + TARGET_1, entry + TARGET_2, entry + TARGET_3
        else:
            t1, t2, t3 = entry - TARGET_1, entry - TARGET_2, entry - TARGET_3
        st.success(f"OPEN DEMO {side} — Entry {show_price(entry)} — Qty {pos['qty']}")
        st.write(f"TP1: **{show_price(t1)}** | TP2: **{show_price(t2)}** | TP3: **{show_price(t3)}**")

    st.subheader("📜 DEMO TRADE HISTORY")
    if st.session_state.demo_history:
        st.dataframe(pd.DataFrame(st.session_state.demo_history), use_container_width=True, hide_index=True)
    else:
        st.info("No demo trades yet.")

    # TradingView live quote widgets. These are view-only and do not place orders.
    st.subheader("📡 TRADINGVIEW LIVE MARKET")
    components.html("""
    <div style="display:flex;width:100%;">
      <div class="tradingview-widget-container" style="width:100%;"><div class="tradingview-widget-container__widget"></div><script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-single-quote.js" async>{"symbol":"BINANCE:BTCUSDT","width":"100%","colorTheme":"dark","isTransparent":true,"locale":"en"}</script></div>
    </div>
    """, height=145, scrolling=False)
                                  
                 


# ------------------------------------------------------------
# DEMO ACCOUNT TAB — REAL SYSTEM SEPARATE
# ------------------------------------------------------------
if selected_tab == "Demo Account":
    run_demo_account()
    st.stop()

# ------------------------------------------------------------
# TRADINGVIEW CHART — FULL AVAILABLE SCREEN
# Early Exit: नीचे का पूरा trading dashboard execute नहीं होगा.
# ------------------------------------------------------------
if selected_tab == "TradingView Chart":
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 0rem !important;
            padding-bottom: 0rem !important;
            padding-left: 0rem !important;
            padding-right: 0rem !important;
            max-width: 100% !important;
        }
        header[data-testid="stHeader"] {
            display: none;
        }
        [data-testid="stAppViewContainer"] > .main {
            padding: 0 !important;
        }
        iframe {
            width: 100% !important;
            border: 0 !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    components.html(
        """
        <div
            class="tradingview-widget-container"
            style="height:100vh;width:100%;margin:0;padding:0;">

            <div
                class="tradingview-widget-container__widget"
                style="height:100vh;width:100%;">
            </div>

            <script
                type="text/javascript"
                src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
                async>
            {
                "autosize": true,
                "symbol": "BINANCE:BTCUSDT",
                "interval": "5",
                "timezone": "Asia/Kolkata",
                "theme": "dark",
                "style": "1",
                "locale": "en",
                "enable_publishing": false,
                "allow_symbol_change": true,
                "hide_top_toolbar": false,
                "hide_legend": false,
                "save_image": false,
                "hide_volume": false,
                "support_host": "https://www.tradingview.com"
            }
            </script>
        </div>
        """,
        height=900,
        scrolling=False
    )

    st.stop()

st.title("📈 SANJAY RANA — REAL TRADING DASHBOARD")

st.caption(
    "5 Minute | ATR 10 | Multiplier 3.0 | HL2 | "
    "Confirmed Candle Close"
)


# ============================================================
# INDIAN TIME
# ============================================================

IST = timezone(timedelta(hours=5, minutes=30))


def indian_time(timestamp):
    try:
        ts = int(float(timestamp))

        if ts > 10_000_000_000:
            ts = ts // 1000

        return datetime.fromtimestamp(
            ts,
            tz=timezone.utc
        ).astimezone(IST).strftime(
            "%Y-%m-%d %H:%M:%S IST"
        )

    except Exception:
        return "-"

# ============================================================
# DELTA API
# ============================================================

class DeltaAPI:

    def __init__(self, api_key=None, api_secret=None):
        global API_KEY, API_SECRET
        
        if api_key:
            API_KEY = api_key
        if api_secret:
            API_SECRET = api_secret

        self.session = requests.Session()

        self.session.headers.update({
            "User-Agent": "Sanjay-Rana-Real-Trading-Bot",
            "Accept": "application/json"
        })
        



    # --------------------------------------------------------
    # HMAC SIGNATURE
    # --------------------------------------------------------

    def make_signature(
        self,
        method,
        timestamp,
        path,
        query_string="",
        body=""
    ):

        message = (
            method.upper()
            + timestamp
            + path
            + query_string
            + body
        )

        return hmac.new(
            API_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()


    # --------------------------------------------------------
    # REQUEST
    # --------------------------------------------------------

    def request(
        self,
        method,
        path,
        params=None,
        body=None,
        private=False
    ):

        params = params or {}

        body = body or {}

        payload = ""

        if body:
            payload = json.dumps(
                body,
                separators=(",", ":")
            )

        query_string = ""

        if params:

            parts = []

            for key, value in params.items():

                parts.append(
                    f"{key}={value}"
                )

            query_string = "?" + "&".join(parts)


        headers = {
            "Accept": "application/json",
            "User-Agent": "Sanjay-Rana-Real-Trading-Bot"
        }


        if private:

            if not API_KEY or not API_SECRET:

                return {
                    "success": False,
                    "error": "API key/secret missing"
                }


            timestamp = str(
                int(time.time())
            )


            signature = self.make_signature(
                method,
                timestamp,
                path,
                query_string,
                payload
            )


            headers.update({
                "api-key": API_KEY,
                "timestamp": timestamp,
                "signature": signature,
                "Content-Type": "application/json"
            })


        try:

            response = self.session.request(
                method.upper(),
                BASE_URL + path,
                params=params,
                data=payload if payload else None,
                headers=headers,
                timeout=15
            )


            try:
                data = response.json()

            except Exception:

                return {
                    "success": False,
                    "error": response.text
                }


            return data


        except Exception as e:

            return {
                "success": False,
                "error": str(e)
            }


    # --------------------------------------------------------
    # PUBLIC
    # --------------------------------------------------------

    def candles(self):

        end = int(time.time())

        start = (
            end
            - (500 * CANDLE_SECONDS)
        )

        return self.request(
            "GET",
            "/v2/history/candles",
            params={
                "symbol": SYMBOL,
                "resolution": TIMEFRAME,
                "start": start,
                "end": end
            }
        )


    def ticker(self):

        return self.request(
            "GET",
            f"/v2/tickers/{SYMBOL}"
        )


    # --------------------------------------------------------
    # PRIVATE
    # --------------------------------------------------------

    def open_orders(self):

        return self.request(
            "GET",
            "/v2/orders",
            params={
                "product_id": PRODUCT_ID,
                "state": "open"
            },
            private=True
        )


    def position(self):

        return self.request(
            "GET",
            "/v2/positions",
            params={
                "product_id": PRODUCT_ID
            },
            private=True
        )


    # --------------------------------------------------------
    # PLACE LIMIT ORDER
    # --------------------------------------------------------

    def place_limit_order(
        self,
        side,
        size,
        limit_price
    ):

        body = {

            "product_id": PRODUCT_ID,

            "product_symbol": SYMBOL,

            "limit_price": str(
                limit_price
            ),

            "size": int(size),

            "side": side,

            "order_type": "limit_order"
        }


        return self.request(
            "POST",
            "/v2/orders",
            body=body,
            private=True
        )


    # --------------------------------------------------------
    # CANCEL ORDER
    # --------------------------------------------------------

    def cancel_order(self, order_id):

        return self.request(
            "DELETE",
            f"/v2/orders/{order_id}",
            private=True
        )


# ============================================================
# API CREDENTIALS (OWNER & MEMBERS FROM GITHUB SECRETS)
# ============================================================
# यह कोड GitHub Secrets से कीज़ खुद ले लेता है
OWNER_KEY = st.secrets.get("OWNER_API_KEY", "")
OWNER_SECRET = st.secrets.get("OWNER_API_SECRET", "")

MEMBER1_KEY = st.secrets.get("MEMBER1_API_KEY", "")
MEMBER1_SECRET = st.secrets.get("MEMBER1_API_SECRET", "")



API_KEY = OWNER_KEY
API_SECRET = OWNER_SECRET

api = DeltaAPI()



# ============================================================
# BASIC STATUS (PERMANENTLY LIVE)
# ============================================================

st.info(
    "⚡ LIVE TRADING MODE: PERMANENTLY ACTIVE"
)

    # ============================================================
# OWNER API + MEMBER API CONTROL
# PLACE THIS DIRECTLY BELOW PART 1
# ============================================================

st.divider()

# ============================================================
# OWNER API
# ============================================================

st.header("👑 OWNER API")

# Credentials are loaded automatically from environment / GitHub Secrets
# ============================================================
# OWNER API CREDENTIALS (SECURE FETCH)
# ============================================================
try:
    OWNER_API_KEY = st.secrets.get("OWNER_API_KEY", os.getenv("OWNER_API_KEY", ""))
    OWNER_API_SECRET = st.secrets.get("OWNER_API_SECRET", os.getenv("OWNER_API_SECRET", ""))
except Exception:
    OWNER_API_KEY = os.getenv("OWNER_API_KEY", "")
    OWNER_API_SECRET = os.getenv("OWNER_API_SECRET", "")
    

# ============================================================
# OWNER STATUS (AUTOMATIC HEALTH CHECK)
# ============================================================

if not OWNER_API_KEY or not OWNER_API_SECRET:
    st.error("❌ OWNER_API_KEY / OWNER_API_SECRET GitHub Secrets में नहीं मिले।")
    st.session_state["owner_api_connected"] = False
else:
    try:
        owner_client = DeltaAPI(OWNER_API_KEY, OWNER_API_SECRET)
        owner_result = owner_client.position()
        
        if owner_result.get("success"):
            st.success("👑 Owner Status: CONNECTED & LIVE 🟢")
            st.session_state["owner_api_connected"] = True
            st.session_state["owner_api_key"] = OWNER_API_KEY
            st.session_state["owner_api_secret"] = OWNER_API_SECRET
        else:
            st.session_state["owner_api_connected"] = False
            err_text = str(owner_result.get("error", ""))
            
            if "ip" in err_text.lower() or "whitelist" in err_text.lower():
                st.error(f"🌐 IP WHITELIST ERROR: Streamlit Cloud का IP Delta Exchange पर जोड़ा नहीं है! | Details: {err_text}")
            else:
                st.error(f"🔴 Owner Status: NOT CONNECTED | Reason: {err_text}")
                
    except Exception as e:
        st.session_state["owner_api_connected"] = False
        st.error(f"❌ Owner API Connection Error: {e}")



# ============================================================
# FIXED 5 MEMBERS PRE-CONFIGURED (AUTOMATIC HEALTH CHECK)
# ============================================================

st.divider()
st.header("👥 MEMBER API CONTROL (5 MEMBERS)")

# 5 फिक्स मेंबर्स सीधे GitHub Secrets से लोड होंगे
st.session_state["members"] = [
    {
        "name": "Member 1",
        "api_key": st.secrets.get("MEMBER1_API_KEY", os.getenv("MEMBER1_API_KEY", "")),
        "api_secret": st.secrets.get("MEMBER1_API_SECRET", os.getenv("MEMBER1_API_SECRET", "")),
        "connected": False,
        "active": True
    },
    {
        "name": "Member 2",
        "api_key": st.secrets.get("MEMBER2_API_KEY", os.getenv("MEMBER2_API_KEY", "")),
        "api_secret": st.secrets.get("MEMBER2_API_SECRET", os.getenv("MEMBER2_API_SECRET", "")),
        "connected": False,
        "active": True
    },
    {
        "name": "Member 3",
        "api_key": st.secrets.get("MEMBER3_API_KEY", os.getenv("MEMBER3_API_KEY", "")),
        "api_secret": st.secrets.get("MEMBER3_API_SECRET", os.getenv("MEMBER3_API_SECRET", "")),
        "connected": False,
        "active": True
    },
    {
        "name": "Member 4",
        "api_key": st.secrets.get("MEMBER4_API_KEY", os.getenv("MEMBER4_API_KEY", "")),
        "api_secret": st.secrets.get("MEMBER4_API_SECRET", os.getenv("MEMBER4_API_SECRET", "")),
        "connected": False,
        "active": True
    },
    {
        "name": "Member 5",
        "api_key": st.secrets.get("MEMBER5_API_KEY", os.getenv("MEMBER5_API_KEY", "")),
        "api_secret": st.secrets.get("MEMBER5_API_SECRET", os.getenv("MEMBER5_API_SECRET", "")),
        "connected": False,
        "active": True
    }
]

st.info("👥 Total Pre-configured Members: 5 (Automatic Live Sync Enabled)")

# पांचों मेंबर्स का ऑटोमैटिक हेल्थ चेक लूप (बिना किसी बटन के)
for index, member in enumerate(st.session_state["members"]):
    st.markdown("---")
    st.subheader(f"👤 {member['name']}")

    if not member["api_key"] or not member["api_secret"]:
        member["connected"] = False
        st.error(f"❌ {member['name']}: GitHub Secrets में API Key या Secret गायब है (`MEMBER{index+1}_API_KEY`).")
    else:
        try:
            member_client = DeltaAPI(member["api_key"], member["api_secret"])
            member_result = member_client.position()
            
            if member_result.get("success"):
                member["connected"] = True
                st.success(f"🟢 {member['name']} — API CONNECTED & LIVE")
            else:
                member["connected"] = False
                err_text = str(member_result.get("error", ""))
                
                if "ip" in err_text.lower() or "whitelist" in err_text.lower():
                    st.error(f"🌐 IP WHITELIST ERROR ({member['name']}): Streamlit IP Delta पर जोड़ी नहीं है! | {err_text}")
                else:
                    st.error(f"🔴 {member['name']} — NOT CONNECTED | Reason: {err_text}")
                    
        except Exception as e:
        #   member["connected"] = False
            st.error(f"❌ {member['name']} API Error: {e}")

    if member["connected"]:
        st.write(f"Status: **REAL TRADING ACTIVE (AUTO)** 🚀")
    else:
        st.write(f"Status: **TRADING PAUSED (Check Secrets / IP)** ⚠️")


# ============================================================
# ACTIVE MEMBER SUMMARY TABLE
# ============================================================

st.divider()
st.subheader("📊 MEMBER SUMMARY")

summary = []
for member in st.session_state["members"]:
    summary.append({
        "Member": member["name"],
        "API": "CONNECTED" if member["connected"] else "NOT CONNECTED",
        "Trading": "ACTIVE" if member["active"] else "OFF"
    })

st.dataframe(
    pd.DataFrame(summary),
    use_container_width=True,
    hide_index=True
)



# ============================================================
# END — OWNER + MEMBER API BLOCK
#
# PART 2 इसके नीचे आएगा।
# PART 3 इसके बाद।
# PART 4 सबसे बाद।
#
# FINAL st.rerun() पूरी file के बिल्कुल अंत में रहेगा।
# ============================================================
# ============================================================
# PART 2/4
# CANDLE DATA + SUPERTREND ENGINE
# ============================================================

def get_result(data):

    if not data:
        return None

    if not data.get("success"):
        return None

    return data.get("result")


def make_dataframe(data):

    result = get_result(data)

    if not isinstance(result, list):
        return pd.DataFrame()

    rows = []

    for candle in result:
        try:
            rows.append({
                "time": int(candle["time"]),
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle.get("volume", 0))
            })
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    df = (
        df
        .drop_duplicates("time")
        .sort_values("time")
        .reset_index(drop=True)
    )

    return df


# ============================================================
# GET CANDLES
# ============================================================

candle_response = api.candles()

df = make_dataframe(candle_response)

if df.empty:
    st.error("Delta se candle data nahi mila.")
    st.stop()


# ============================================================
# ONLY COMPLETED 5-MINUTE CANDLES
# ============================================================

current_candle_start = (
    int(time.time()) // CANDLE_SECONDS
) * CANDLE_SECONDS

df = df[
    df["time"] < current_candle_start
].copy()

df = df.reset_index(drop=True)

if len(df) < ATR_PERIOD + 5:
    st.error("SuperTrend ke liye enough candles nahi hain.")
    st.stop()


# ============================================================
# TRUE RANGE
# ============================================================

prev_close = df["close"].shift(1)

tr1 = df["high"] - df["low"]

tr2 = (
    df["high"] - prev_close
).abs()

tr3 = (
    df["low"] - prev_close
).abs()

df["TR"] = pd.concat(
    [tr1, tr2, tr3],
    axis=1
).max(axis=1)


# ============================================================
# ATR 10 — WILDER RMA
# ============================================================

df["ATR"] = float("nan")

first_atr = (
    df["TR"]
    .iloc[:ATR_PERIOD]
    .mean()
)

df.loc[
    ATR_PERIOD - 1,
    "ATR"
] = first_atr


for i in range(
    ATR_PERIOD,
    len(df)
):

    previous_atr = df.loc[
        i - 1,
        "ATR"
    ]

    current_tr = df.loc[
        i,
        "TR"
    ]

    df.loc[
        i,
        "ATR"
    ] = (
        previous_atr * (ATR_PERIOD - 1)
        + current_tr
    ) / ATR_PERIOD


# ============================================================
# HL2
# ============================================================

df["HL2"] = (
    df["high"] + df["low"]
) / 2.0


# ============================================================
# SUPERTREND COLUMNS
# ============================================================

df["UP"] = float("nan")
df["DN"] = float("nan")
df["TREND"] = float("nan")
df["SUPERTREND"] = float("nan")
df["SIGNAL"] = ""


# ============================================================
# SUPERTREND CALCULATION
#
# ATR = 10
# MULTIPLIER = 3.0
# SOURCE = HL2
#
# TradingView direction:
# -1 = BULLISH / BUY
#  1 = BEARISH / SELL
# ============================================================

for i in range(len(df)):

    atr = df.loc[i, "ATR"]

    if pd.isna(atr):
        continue

    src = df.loc[i, "HL2"]

    upper_basic = (
        src + MULTIPLIER * atr
    )

    lower_basic = (
        src - MULTIPLIER * atr
    )


    # ========================================================
    # FIRST VALID BAR
    # ========================================================

    if i == ATR_PERIOD - 1:

        df.loc[i, "UP"] = upper_basic
        df.loc[i, "DN"] = lower_basic
        df.loc[i, "TREND"] = 1
        df.loc[i, "SUPERTREND"] = upper_basic

        continue


    # ========================================================
    # PREVIOUS VALUES
    # ========================================================

    previous_up = df.loc[
        i - 1,
        "UP"
    ]

    previous_dn = df.loc[
        i - 1,
        "DN"
    ]

    previous_trend = df.loc[
        i - 1,
        "TREND"
    ]

    previous_close = df.loc[
        i - 1,
        "close"
    ]


    if pd.isna(previous_up):
        previous_up = upper_basic

    if pd.isna(previous_dn):
        previous_dn = lower_basic

    if pd.isna(previous_trend):
        previous_trend = 1


    # ========================================================
    # LOWER BAND
    # ========================================================

    if (
        lower_basic > previous_dn
        or previous_close < previous_dn
    ):

        lower_band = lower_basic

    else:

        lower_band = previous_dn


    # ========================================================
    # UPPER BAND
    # ========================================================

    if (
        upper_basic < previous_up
        or previous_close > previous_up
    ):

        upper_band = upper_basic

    else:

        upper_band = previous_up


    # ========================================================
    # TREND
    # ========================================================

    trend = previous_trend

    close = df.loc[
        i,
        "close"
    ]


    if previous_trend == 1:

        if close > upper_band:
            trend = -1
        else:
            trend = 1

    else:

        if close < lower_band:
            trend = 1
        else:
            trend = -1


    # ========================================================
    # SAVE
    # ========================================================

    df.loc[i, "UP"] = upper_band

    df.loc[i, "DN"] = lower_band

    df.loc[i, "TREND"] = trend


    # ========================================================
    # SUPERTREND LINE
    # ========================================================

    if trend == -1:

        df.loc[
            i,
            "SUPERTREND"
        ] = lower_band

    else:

        df.loc[
            i,
            "SUPERTREND"
        ] = upper_band


    # ========================================================
    # SIGNAL
    # ========================================================

    if (
        trend == -1
        and previous_trend == 1
    ):

        df.loc[
            i,
            "SIGNAL"
        ] = "BUY"


    elif (
        trend == 1
        and previous_trend == -1
    ):

        df.loc[
            i,
            "SIGNAL"
        ] = "SELL"


# ============================================================
# SIGNAL HISTORY
# ============================================================

signal_rows = df[
    df["SIGNAL"].isin(
        ["BUY", "SELL"]
    )
].copy()


# ============================================================
# CURRENT CANDLE
# ============================================================

last_candle = df.iloc[-1]

current_trend = int(
    last_candle["TREND"]
)

current_close = float(
    last_candle["close"]
)

current_supertrend = float(
    last_candle["SUPERTREND"]
)

current_signal = str(
    last_candle["SIGNAL"]
)


# ============================================================
# CURRENT DIRECTION
# ============================================================

if current_trend == -1:

    current_direction = "BUY / BULLISH 🟢"

else:

    current_direction = "SELL / BEARISH 🔴"


# ============================================================
# CURRENT ENTRY
# ============================================================

if len(signal_rows) >= 1:

    current_entry = signal_rows.iloc[-1]

    signal_direction = str(
        current_entry["SIGNAL"]
    )

    signal_entry_price = float(
        current_entry["close"]
    )

    signal_supertrend = float(
        current_entry["SUPERTREND"]
    )

    signal_time = indian_time(
        current_entry["time"]
    )

else:

    signal_direction = ""

    signal_entry_price = current_close

    signal_supertrend = current_supertrend

    signal_time = indian_time(
        last_candle["time"]
    )


# ============================================================
# PREVIOUS ENTRY
# ============================================================

if len(signal_rows) >= 2:

    previous_entry = signal_rows.iloc[-2]

    previous_entry_signal = str(
        previous_entry["SIGNAL"]
    )

    previous_entry_price = float(
        previous_entry["close"]
    )

    previous_entry_st = float(
        previous_entry["SUPERTREND"]
    )

    previous_entry_time = indian_time(
        previous_entry["time"]
    )

else:

    previous_entry_signal = ""

    previous_entry_price = None

    previous_entry_st = None

    previous_entry_time = "-"


# ============================================================
# DISPLAY
# ============================================================

st.divider()

st.header("📈 SUPERTREND — 5 MINUTE")

c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "CURRENT DIRECTION",
        current_direction
    )

with c2:

    st.metric(
        "CURRENT CLOSE",
        show_price(current_close)
    )

with c3:

    st.metric(
        "SUPERTREND",
        show_price(current_supertrend)
    )


# ============================================================
# CURRENT ENTRY
# ============================================================

st.subheader("🎯 CURRENT ENTRY")

if signal_direction == "BUY":

    st.success(
        f"🟢 BUY | "
        f"ENTRY: {show_price(signal_entry_price)} | "
        f"SUPERTREND: {show_price(signal_supertrend)}"
    )

elif signal_direction == "SELL":

    st.error(
        f"🔴 SELL | "
        f"ENTRY: {show_price(signal_entry_price)} | "
        f"SUPERTREND: {show_price(signal_supertrend)}"
    )

else:

    st.info(
        "No confirmed SuperTrend entry."
    )


st.write(
    f"Signal Candle: **{signal_time}**"
)


# ============================================================
# PREVIOUS ENTRY
# ============================================================

st.subheader("📜 PREVIOUS ENTRY")

if previous_entry_signal == "BUY":

    st.success(
        f"🟢 BUY | "
        f"ENTRY: {show_price(previous_entry_price)} | "
        f"SUPERTREND: {show_price(previous_entry_st)}"
    )

elif previous_entry_signal == "SELL":

    st.error(
        f"🔴 SELL | "
        f"ENTRY: {show_price(previous_entry_price)} | "
        f"SUPERTREND: {show_price(previous_entry_st)}"
    )

else:

    st.info(
        "Previous entry available nahi hai."
    )


st.write(
    f"Signal Candle: **{previous_entry_time}**"
                                          )
# ============================================================
# PART 3/4
# REMOTE CONTROL + TARGETS + REAL LIMIT ORDER CONTROL
# ============================================================

st.divider()

st.header("🎛️ REMOTE CONTROL")


# ============================================================
# REAL TRADING PERMANENTLY ON (ALWAYS ACTIVE)
# ============================================================

if "remote_enabled" not in st.session_state:
    st.session_state["remote_enabled"] = True

if "last_order_signal" not in st.session_state:
    st.session_state["last_order_signal"] = ""

if "pending_order_id" not in st.session_state:
    st.session_state["pending_order_id"] = None

if "pending_order_side" not in st.session_state:
    st.session_state["pending_order_side"] = ""

if "pending_order_time" not in st.session_state:
    st.session_state["pending_order_time"] = 0

remote_enabled = True
st.session_state["remote_enabled"] = True

# प्रोफेशनल और मार्केट जैसा ब्लू स्टेटस बॉक्स
st.info("⚡ LIVE TRADING ENGINE: ACTIVE & PERMANENTLY ON")




# ============================================================
# ORDER SETTINGS
# ============================================================

r1, r2 = st.columns(2)


with r1:

    buy_offset = st.number_input(
        "BUY LIMIT OFFSET",
        value=DEFAULT_BUY_OFFSET,
        step=10,
        help="Example: -50 means signal price se 50 points neeche."
    )


with r2:

    sell_offset = st.number_input(
        "SELL LIMIT OFFSET",
        value=DEFAULT_SELL_OFFSET,
        step=10,
        help="Example: +50 means signal price se 50 points upar."
    )


r3, r4 = st.columns(2)


with r3:

    order_size = st.number_input(
        "ORDER SIZE",
        min_value=1,
        value=DEFAULT_ORDER_SIZE,
        step=1
    )


with r4:

    limit_timeout = st.number_input(
        "LIMIT TIMEOUT (SECONDS)",
        min_value=0,
        value=DEFAULT_LIMIT_TIMEOUT,
        step=5,
        help="0 = MARKET conversion disabled."
    )


# ============================================================
# TARGET SETTINGS
# ============================================================

st.subheader("🎯 TARGET SETTINGS")


t1_points = st.number_input(
    "TARGET 1 POINTS",
    min_value=1,
    value=TARGET_1,
    step=50
)


t2_points = st.number_input(
    "TARGET 2 POINTS",
    min_value=1,
    value=TARGET_2,
    step=50
)


t3_points = st.number_input(
    "TARGET 3 POINTS",
    min_value=1,
    value=TARGET_3,
    step=50
)


# ============================================================
# ENTRY PRICE WITH REMOTE OFFSET
# ============================================================

if signal_direction == "BUY":

    limit_entry_price = (
        signal_entry_price
        + float(buy_offset)
    )

elif signal_direction == "SELL":

    limit_entry_price = (
        signal_entry_price
        + float(sell_offset)
    )

else:

    limit_entry_price = (
        signal_entry_price
    )


# ============================================================
# TARGET CALCULATION
# ============================================================

if signal_direction == "BUY":

    target1 = (
        limit_entry_price
        + t1_points
    )

    target2 = (
        limit_entry_price
        + t2_points
    )

    target3 = (
        limit_entry_price
        + t3_points
    )

elif signal_direction == "SELL":

    target1 = (
        limit_entry_price
        - t1_points
    )

    target2 = (
        limit_entry_price
        - t2_points
    )

    target3 = (
        limit_entry_price
        - t3_points
    )

else:

    target1 = limit_entry_price + t1_points
    target2 = limit_entry_price + t2_points
    target3 = limit_entry_price + t3_points


# ============================================================
# DISPLAY ENTRY + TARGETS
# ============================================================

st.subheader("📌 ORDER ENTRY + TARGETS")


ec1, ec2, ec3, ec4 = st.columns(4)


with ec1:

    st.metric(
        "LIMIT ENTRY",
        show_price(limit_entry_price)
    )


with ec2:

    st.metric(
        "TARGET 1",
        show_price(target1)
    )


with ec3:

    st.metric(
        "TARGET 2",
        show_price(target2)
    )


with ec4:

    st.metric(
        "TARGET 3",
        show_price(target3)
    )


# ============================================================
# DIRECTION CHANGE
# ============================================================

st.subheader(
    "🔄 PENDING ORDER AUTO-CANCEL"
)

st.info(
    "SuperTrend direction change hote hi "
    "opposite pending LIMIT order automatically cancel hoga."
)


# ============================================================
# GET OPEN ORDERS
# ============================================================

open_orders_response = api.open_orders()

open_orders = get_result(
    open_orders_response
)

if not isinstance(open_orders, list):
    open_orders = []


# ============================================================
# FIND OUR PENDING ORDER
# ============================================================

pending_orders = []

for order in open_orders:

    try:

        order_product_id = int(
            order.get(
                "product_id",
                PRODUCT_ID
            )
        )

    except Exception:

        order_product_id = PRODUCT_ID


    if order_product_id != PRODUCT_ID:
        continue


    order_type = str(
        order.get(
            "order_type",
            order.get("type", "")
        )
    ).lower()


    state = str(
        order.get(
            "state",
            ""
        )
    ).lower()


    if (
        "limit" in order_type
        and state not in [
            "cancelled",
            "filled",
            "rejected"
        ]
    ):

        pending_orders.append(order)


# ============================================================
# CANCEL PENDING ORDER ON DIRECTION CHANGE
# ============================================================

if pending_orders:

    for order in pending_orders:

        order_id = order.get("id")

        order_side = str(
            order.get(
                "side",
                ""
            )
        ).lower()


        should_cancel = False


        # ----------------------------------------------------
        # BUY PENDING + CURRENT SELL
        # ----------------------------------------------------

        if (
            order_side == "buy"
            and current_trend == 1
        ):

            should_cancel = True


        # ----------------------------------------------------
        # SELL PENDING + CURRENT BUY
        # ----------------------------------------------------

        elif (
            order_side == "sell"
            and current_trend == -1
        ):

            should_cancel = True


        # ----------------------------------------------------
        # CANCEL
        # ----------------------------------------------------

        if (
            should_cancel
            and remote_enabled
            and order_id is not None
        ):

            cancel_result = api.cancel_order(
                order_id
            )


            if cancel_result.get("success"):

                st.warning(
                    f"🔄 Pending {order_side.upper()} "
                    f"order CANCELLED — "
                    f"SuperTrend direction changed."
                )

                st.session_state[
                    "pending_order_id"
                ] = None


            else:

                st.error(
                    "Pending order cancel failed: "
                    + str(
                        cancel_result.get(
                            "error",
                            "Unknown error"
                        )
                    )
                )


# ============================================================
# SHOW PENDING ORDERS
# ============================================================

if pending_orders:

    pending_rows = []

    for order in pending_orders:

        pending_rows.append({

            "Order ID":
                order.get("id", "-"),

            "Side":
                str(
                    order.get(
                        "side",
                        ""
                    )
                ).upper(),

            "Price":
                show_price(
                    order.get(
                        "limit_price"
                    )
                ),

            "Size":
                order.get(
                    "size",
                    "-"
                ),

            "Status":
                order.get(
                    "state",
                    "-"
                )
        })


    st.dataframe(
        pd.DataFrame(
            pending_rows
        ),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No pending LIMIT order."
    )


# ============================================================
# PLACE NEW REAL LIMIT ORDER
# ============================================================

st.subheader(
    "🚀 REAL LIMIT ORDER"
)


if not remote_enabled:

    st.warning(
        "Remote Control OFF — "
        "real order place nahi hoga."
    )

else:

    if not API_KEY or not API_SECRET:

        st.error(
            "API Key / API Secret missing."
        )

    elif signal_direction not in [
        "BUY",
        "SELL"
    ]:

        st.info(
            "Naya confirmed BUY/SELL signal ka wait hai."
        )

    else:

        current_signal_time = (
            signal_time
        )


        # ----------------------------------------------------
        # PREVENT DUPLICATE ORDER
        # ----------------------------------------------------

        already_processed = (
            st.session_state[
                "last_order_signal"
            ]
            == current_signal_time
        )


        if already_processed:

            st.success(
                f"Signal already processed: "
                f"{signal_direction}"
            )

        else:

            order_side = (
                "buy"
                if signal_direction == "BUY"
                else "sell"
            )


            st.write(
                f"Signal: **{signal_direction}**"
            )

            st.write(
                f"LIMIT PRICE: "
                f"**{show_price(limit_entry_price)}**"
            )

            st.write(
                f"SIZE: **{order_size}**"
            )


            # ====================================================
            # BINA BUTTON KE DIRECT AUTOMATIC ORDER EXECUTION
            # ====================================================

            result = api.place_limit_order(
                side=order_side,
                size=int(order_size),
                limit_price=limit_entry_price
            )


            if result.get("success"):

                result_data = result.get(
                    "result",
                    {}
                )


                new_order_id = (
                    result_data.get("id")
                    if isinstance(
                        result_data,
                        dict
                    )
                    else None
                )


                st.session_state[
                    "pending_order_id"
                ] = new_order_id


                st.session_state[
                    "pending_order_side"
                ] = order_side


                st.session_state[
                    "pending_order_time"
                ] = time.time()


                st.session_state[
                    "last_order_signal"
                ] = current_signal_time


                st.success(
                    f"✅ REAL {signal_direction} "
                    f"LIMIT ORDER SENT AUTOMATICALLY"
                )


                st.write(
                    f"Order ID: "
                    f"**{new_order_id}**"
                )


            else:

                st.error(
                    "❌ REAL ORDER FAILED: "
                    + str(
                        result.get(
                            "error",
                            "Unknown error"
                        )
                    )
        )
                

# ============================================================
# CURRENT SIGNAL INFORMATION
# ============================================================

st.divider()

st.subheader(
    "📡 SIGNAL INFORMATION"
)

s1, s2, s3 = st.columns(3)


with s1:

    st.write(
        f"Direction: **{current_direction}**"
    )


with s2:

    st.write(
        f"Signal Entry: "
        f"**{show_price(signal_entry_price)}**"
    )


with s3:

    st.write(
        f"Signal Time: **{signal_time}**"
)
    # ============================================================
# PART 4/4
# REAL POSITION + ORDER STATUS + TARGET STATUS + REFRESH
# ============================================================

st.divider()

st.header("📍 REAL POSITION")


# ============================================================
# GET REAL POSITION
# ============================================================

position_response = api.position()

position_data = get_result(position_response)

if isinstance(position_data, list):

    if position_data:
        position = position_data[0]
    else:
        position = {}

elif isinstance(position_data, dict):

    position = position_data

else:

    position = {}


position_size = number(
    position.get("size"),
    0
)

position_entry = number(
    position.get("entry_price")
)

position_pnl = number(
    position.get("unrealized_pnl"),
    0
)


# ============================================================
# POSITION SIDE
# ============================================================

if position_size > 0:

    position_side = "LONG 🟢"

elif position_size < 0:

    position_side = "SHORT 🔴"

else:

    position_side = "FLAT ⚪"


p1, p2, p3, p4 = st.columns(4)


with p1:

    st.metric(
        "POSITION",
        position_side
    )


with p2:

    st.metric(
        "SIZE",
        str(abs(position_size))
    )


with p3:

    st.metric(
        "ENTRY PRICE",
        show_price(position_entry)
    )


with p4:

    st.metric(
        "UNREALIZED P&L",
        f"₹{position_pnl:,.2f}"
    )


# ============================================================
# ORDER STATUS
# ============================================================

st.header("📋 REAL ORDER STATUS")


orders_response = api.open_orders()

orders_result = get_result(
    orders_response
)


if isinstance(orders_result, list):

    open_orders = orders_result

else:

    open_orders = []


if open_orders:

    order_rows = []


    for order in open_orders:

        order_rows.append({

            "Order ID":
                order.get(
                    "id",
                    "-"
                ),

            "Side":
                str(
                    order.get(
                        "side",
                        ""
                    )
                ).upper(),

            "Type":
                order.get(
                    "order_type",
                    order.get(
                        "type",
                        "-"
                    )
                ),

            "Price":
                show_price(
                    order.get(
                        "limit_price"
                    )
                ),

            "Size":
                order.get(
                    "size",
                    "-"
                ),

            "State":
                order.get(
                    "state",
                    "-"
                )
        })


    st.dataframe(
        pd.DataFrame(
            order_rows
        ),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No open orders."
    )


# ============================================================
# TARGET STATUS
# ============================================================

st.header("🎯 TARGET STATUS")


if signal_direction == "BUY":

    target_direction = "LONG"

elif signal_direction == "SELL":

    target_direction = "SHORT"

else:

    target_direction = "NONE"


tc1, tc2, tc3, tc4 = st.columns(4)


with tc1:

    st.metric(
        "DIRECTION",
        target_direction
    )


with tc2:

    st.metric(
        "TARGET 1",
        show_price(target1)
    )


with tc3:

    st.metric(
        "TARGET 2",
        show_price(target2)
    )


with tc4:

    st.metric(
        "TARGET 3",
        show_price(target3)
    )


# ============================================================
# TARGET DISTANCE
# ============================================================

if signal_direction in ["BUY", "SELL"]:

    st.write(
        f"Entry: **{show_price(limit_entry_price)}**"
    )

    st.write(
        f"T1: **{show_price(target1)}**"
    )

    st.write(
        f"T2: **{show_price(target2)}**"
    )

    st.write(
        f"T3: **{show_price(target3)}**"
    )


# ============================================================
# LIVE MARKET PRICE
# ============================================================

st.header("💰 LIVE MARKET PRICE")


ticker_response = api.ticker()

ticker_result = get_result(
    ticker_response
)


if isinstance(ticker_result, dict):

    live_price = None


    for key in [
        "close",
        "last_price",
        "mark_price",
        "spot_price"
    ]:

        value = number(
            ticker_result.get(key)
        )


        if value is not None:

            live_price = value

            break


else:

    live_price = None


st.metric(
    "BTCUSD",
    show_price(live_price)
)


# ============================================================
# SIGNAL / ORDER SUMMARY
# ============================================================

st.header("📊 TRADING SUMMARY")


summary_rows = [

    {
        "Item": "SuperTrend Direction",
        "Value": current_direction
    },

    {
        "Item": "Signal Entry",
        "Value": show_price(
            signal_entry_price
        )
    },

    {
        "Item": "Limit Entry",
        "Value": show_price(
            limit_entry_price
        )
    },

    {
        "Item": "Target 1",
        "Value": show_price(
            target1
        )
    },

    {
        "Item": "Target 2",
        "Value": show_price(
            target2
        )
    },

    {
        "Item": "Target 3",
        "Value": show_price(
            target3
        )
    },

    {
        "Item": "Signal Time",
        "Value": signal_time
    },

    {
        "Item": "Remote Trading",
        "Value": (
            "ON 🔴"
            if remote_enabled
            else "OFF 🟢"
        )
    }
]


st.dataframe(
    pd.DataFrame(
        summary_rows
    ),
    use_container_width=True,
    hide_index=True
)


# ============================================================
# SAFETY INFORMATION
# ============================================================

st.divider()

st.subheader(
    "⚠️ REAL TRADING SAFETY"
)

if remote_enabled:

    st.error(
        "REAL TRADING ACTIVE — "
        "Dashboard se exchange orders bheje ja sakte hain."
    )

else:

    st.success(
        "REAL TRADING OFF — "
        "Dashboard order place nahi karega."
    )


st.write(
    "Pending LIMIT order ka direction "
    "SuperTrend se opposite hone par "
    "automatic cancellation Part 3 mein enabled hai."
)


# ============================================================
# INDIAN TIME
# ============================================================

now_ist = datetime.now(
    timezone.utc
).astimezone(IST)


st.write(
    "Dashboard Time: "
    f"**{now_ist.strftime('%Y-%m-%d %H:%M:%S IST')}**"
)


# ============================================================
# AUTO REFRESH
# ============================================================

# ============================================================
# ORIGINAL TRADINGVIEW CHART — VIEW ONLY
# ============================================================

components.html(
    """
    <div
        class="tradingview-widget-container"
        style="height:100vh;width:100%;">

        <div
            class="tradingview-widget-container__widget"
            style="height:100%;width:100%;">
        </div>

        <script
            type="text/javascript"
            src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
            async>

        {
            "autosize": true,
            "symbol": "BINANCE:BTCUSDT",
            "interval": "5",
            "timezone": "Asia/Kolkata",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "enable_publishing": false,
            "allow_symbol_change": true,
            "hide_top_toolbar": false,
            "hide_legend": false,
            "save_image": false,
            "hide_volume": false,
            "support_host": "https://www.tradingview.com"
        }

        </script>
    </div>
    """,
    height=1200,
    scrolling=False
)

# ============================================================
# END OF PART 1
# PART 2 = CANDLE + SUPERTREND ENGINE
# ============================================================
time.sleep(REFRESH_SECONDS)
st.rerun()
