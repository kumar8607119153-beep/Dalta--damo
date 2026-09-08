# ============================================================
# live_dashboard.py
# SANJAY RANA - SUPERTREND DEMO DASHBOARD
# ============================================================

import os
import time
from datetime import datetime, timezone

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


# ============================================================
# 1. SETTINGS + SUPERTREND ENGINE
# ============================================================

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://api.india.delta.exchange"
).rstrip("/")

SYMBOL = os.getenv("DELTA_SYMBOL", "BTCUSD")

TIMEFRAME = "5m"
CANDLE_SECONDS = 300

ATR_PERIOD = 10
MULTIPLIER = 3.0

TP1_POINTS = 300
TP2_POINTS = 600
TP3_POINTS = 900

REFRESH_SECONDS = 5


st.set_page_config(
    page_title="Sanjay Rana SuperTrend",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SANJAY RANA — SUPERTREND DEMO DASHBOARD")
st.caption("5 Minute | ATR 10 | Multiplier 3.0 | HL2")


# ============================================================
# DELTA CANDLES
# ============================================================

def get_candles():

    end = int(time.time())
    start = end - (500 * CANDLE_SECONDS)

    try:
        r = requests.get(
            BASE_URL + "/v2/history/candles",
            params={
                "symbol": SYMBOL,
                "resolution": TIMEFRAME,
                "start": start,
                "end": end
            },
            timeout=15
        )

        data = r.json()

        if not r.ok or not data.get("success"):
            st.error("Delta candle data unavailable.")
            st.stop()

        return data.get("result", [])

    except Exception as e:
        st.error(f"API Error: {e}")
        st.stop()


raw = get_candles()

rows = []

for c in raw:
    try:
        rows.append({
            "time": int(c["time"]),
            "open": float(c["open"]),
            "high": float(c["high"]),
            "low": float(c["low"]),
            "close": float(c["close"])
        })
    except Exception:
        pass


if not rows:
    st.error("No candle data.")
    st.stop()


df = pd.DataFrame(rows)

df = (
    df.drop_duplicates("time")
      .sort_values("time")
      .reset_index(drop=True)
)


# ============================================================
# ONLY COMPLETED 5-MINUTE CANDLES
# ============================================================

current_start = (
    int(time.time()) // CANDLE_SECONDS
) * CANDLE_SECONDS

df = df[df["time"] < current_start].reset_index(drop=True)

if len(df) < ATR_PERIOD + 5:
    st.error("Not enough completed candles.")
    st.stop()


# ============================================================
# ATR 10 - WILDER RMA
# ============================================================

prev_close = df["close"].shift(1)

tr = pd.concat([
    df["high"] - df["low"],
    (df["high"] - prev_close).abs(),
    (df["low"] - prev_close).abs()
], axis=1).max(axis=1)

atr = pd.Series(float("nan"), index=df.index)

atr.iloc[ATR_PERIOD - 1] = tr.iloc[:ATR_PERIOD].mean()

for i in range(ATR_PERIOD, len(df)):
    atr.iloc[i] = (
        atr.iloc[i - 1] * (ATR_PERIOD - 1)
        + tr.iloc[i]
    ) / ATR_PERIOD


# ============================================================
# SUPERTREND
# ============================================================

hl2 = (df["high"] + df["low"]) / 2

basic_upper = hl2 + MULTIPLIER * atr
basic_lower = hl2 - MULTIPLIER * atr

upper = pd.Series(float("nan"), index=df.index)
lower = pd.Series(float("nan"), index=df.index)

trend = pd.Series(float("nan"), index=df.index)
supertrend = pd.Series(float("nan"), index=df.index)

signal = pd.Series("", index=df.index)


for i in range(len(df)):

    if pd.isna(atr.iloc[i]):
        continue

    if i == ATR_PERIOD - 1:

        upper.iloc[i] = basic_upper.iloc[i]
        lower.iloc[i] = basic_lower.iloc[i]

        trend.iloc[i] = 1
        supertrend.iloc[i] = lower.iloc[i]

        continue


    # Final lower band
    if (
        basic_lower.iloc[i] > lower.iloc[i - 1]
        or df["close"].iloc[i - 1] < lower.iloc[i - 1]
    ):
        lower.iloc[i] = basic_lower.iloc[i]
    else:
        lower.iloc[i] = lower.iloc[i - 1]


    # Final upper band
    if (
        basic_upper.iloc[i] < upper.iloc[i - 1]
        or df["close"].iloc[i - 1] > upper.iloc[i - 1]
    ):
        upper.iloc[i] = basic_upper.iloc[i]
    else:
        upper.iloc[i] = upper.iloc[i - 1]


    previous_trend = trend.iloc[i - 1]

    if previous_trend == 1:

        if df["close"].iloc[i] > upper.iloc[i]:
            trend.iloc[i] = -1
        else:
            trend.iloc[i] = 1

    else:

        if df["close"].iloc[i] < lower.iloc[i]:
            trend.iloc[i] = 1
        else:
            trend.iloc[i] = -1


    if trend.iloc[i] == -1:
        supertrend.iloc[i] = lower.iloc[i]
    else:
        supertrend.iloc[i] = upper.iloc[i]


    # Signal
    if trend.iloc[i] == -1 and previous_trend == 1:
        signal.iloc[i] = "BUY"

    elif trend.iloc[i] == 1 and previous_trend == -1:
        signal.iloc[i] = "SELL"


df["ATR"] = atr
df["Trend"] = trend
df["SuperTrend"] = supertrend
df["SIGNAL"] = signal


# ============================================================
# 2. CURRENT + PREVIOUS ENTRY
# ============================================================

signals = df[df["SIGNAL"].isin(["BUY", "SELL"])].copy()


def indian_time(ts):

    return (
        datetime.fromtimestamp(
            int(ts),
            tz=timezone.utc
        )
        .astimezone(
            __import__("datetime").timezone(
                __import__("datetime").timedelta(hours=5, minutes=30)
            )
        )
        .strftime("%d-%m-%Y %I:%M:%S %p")
    )


st.divider()
st.header("🎯 CURRENT ENTRY")


if len(signals) > 0:

    current = signals.iloc[-1]

    current_signal = current["SIGNAL"]
    current_entry = float(current["close"])
    current_st = float(current["SuperTrend"])

    if current_signal == "BUY":
        st.success(
            f"🟢 BUY | ENTRY: {current_entry:,.2f} | "
            f"SUPERTREND: {current_st:,.2f}"
        )
    else:
        st.error(
            f"🔴 SELL | ENTRY: {current_entry:,.2f} | "
            f"SUPERTREND: {current_st:,.2f}"
        )

    st.write(
        f"Signal Candle: **{indian_time(current['time'])} IST**"
    )

else:

    st.info("No SuperTrend entry found.")


st.header("📜 PREVIOUS ENTRY")


if len(signals) >= 2:

    previous = signals.iloc[-2]

    previous_signal = previous["SIGNAL"]
    previous_entry = float(previous["close"])
    previous_st = float(previous["SuperTrend"])

    if previous_signal == "BUY":
        st.success(
            f"🟢 BUY | ENTRY: {previous_entry:,.2f} | "
            f"SUPERTREND: {previous_st:,.2f}"
        )
    else:
        st.error(
            f"🔴 SELL | ENTRY: {previous_entry:,.2f} | "
            f"SUPERTREND: {previous_st:,.2f}"
        )

    st.write(
        f"Signal Candle: **{indian_time(previous['time'])} IST**"
    )

else:

    st.info("Previous entry available nahi hai.")


# ============================================================
# 3. TARGET ENGINE
# ============================================================

st.divider()
st.header("🎯 CURRENT ENTRY + TARGETS")


if len(signals) > 0:

    entry = float(signals.iloc[-1]["close"])
    side = signals.iloc[-1]["SIGNAL"]

    if side == "BUY":

        tp1 = entry + TP1_POINTS
        tp2 = entry + TP2_POINTS
        tp3 = entry + TP3_POINTS

    else:

        tp1 = entry - TP1_POINTS
        tp2 = entry - TP2_POINTS
        tp3 = entry - TP3_POINTS


    a, b, c, d = st.columns(4)

    with a:
        st.metric("ENTRY", f"{entry:,.2f}")

    with b:
        st.metric("TP1", f"{tp1:,.2f}")

    with c:
        st.metric("TP2", f"{tp2:,.2f}")

    with d:
        st.metric("TP3", f"{tp3:,.2f}")


# ============================================================
# 4. DEMO TRADE HISTORY
# ============================================================

st.divider()
st.header("🧪 DEMO TRADE HISTORY")

demo_rows = []

for _, row in signals.iterrows():

    entry = float(row["close"])
    side = row["SIGNAL"]

    if side == "BUY":

        t1 = entry + TP1_POINTS
        t2 = entry + TP2_POINTS
        t3 = entry + TP3_POINTS

    else:

        t1 = entry - TP1_POINTS
        t2 = entry - TP2_POINTS
        t3 = entry - TP3_POINTS


    demo_rows.append({
        "Time (IST)": indian_time(row["time"]),
        "Side": side,
        "Entry": entry,
        "TP1": t1,
        "TP2": t2,
        "TP3": t3,
        "SuperTrend": float(row["SuperTrend"])
    })


if demo_rows:

    history = pd.DataFrame(demo_rows)

    history = history.sort_values(
        "Time (IST)",
        ascending=False
    )

    st.dataframe(
        history.head(20),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info("Abhi koi demo trade history nahi hai.")


# ============================================================
# CURRENT TREND
# ============================================================

st.divider()
st.header("📈 CURRENT SUPERTREND")

last = df.iloc[-1]

if int(last["Trend"]) == -1:

    st.success("BUY / BULLISH 🟢")

else:

    st.error("SELL / BEARISH 🔴")


st.write(
    f"Current Close: **{float(last['close']):,.2f}**"
)

st.write(
    f"Current SuperTrend: **{float(last['SuperTrend']):,.2f}**"
)


# ============================================================
# TRADINGVIEW ORIGINAL CHART
# ============================================================

st.divider()
st.header("📊 TRADINGVIEW ORIGINAL CHART")

tradingview = """
<div style="height:600px;width:100%">
<script src="https://s3.tradingview.com/tv.js"></script>

<div id="tv_chart" style="height:100%;width:100%"></div>

<script>
new TradingView.widget({
    "autosize": true,
    "symbol": "BINANCE:BTCUSDT",
    "interval": "5",
    "timezone": "Asia/Kolkata",
    "theme": "dark",
    "style": "1",
    "locale": "en",
    "enable_publishing": false,
    "allow_symbol_change": true,
    "hide_side_toolbar": false,
    "container_id": "tv_chart"
});
</script>
</div>
"""

components.html(
    tradingview,
    height=620
)


# ============================================================
# REFRESH
# ============================================================

st.divider()

st.caption(
    "DEMO MODE — No real order is placed."
)

time.sleep(REFRESH_SECONDS)
st.rerun()
