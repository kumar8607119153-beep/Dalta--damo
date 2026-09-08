# ============================================================
# live_dashboard.py
# SANJAY RANA - AUTO TRADING BOT
# PART 1/4
#
# IMPORTANT:
# - 5 Minute
# - ATR 10
# - Multiplier 3.0
# - Source HL2
# - OLD MATCHED SUPERTREND LOGIC
# - ONLY COMPLETED CANDLES
# - NO MANUAL BUY/SELL BUTTON
# ============================================================

import os
import time
from datetime import datetime, timezone

import requests
import pandas as pd
import streamlit as st


# ============================================================
# SETTINGS
# ============================================================

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://api.india.delta.exchange"
).rstrip("/")

SYMBOL = os.getenv(
    "DELTA_SYMBOL",
    "BTCUSD"
)

TIMEFRAME = "5m"
CANDLE_SECONDS = 300

ATR_PERIOD = 10
MULTIPLIER = 3.0

REFRESH_SECONDS = 5


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Sanjay Rana Auto Bot",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SANJAY RANA — AUTO TRADING BOT")

st.caption(
    "5 Minute | ATR 10 | Multiplier 3.0 | Source HL2"
)


# ============================================================
# DELTA CANDLE API
# ============================================================

def get_candles():

    end = int(time.time())

    start = end - (500 * CANDLE_SECONDS)

    try:

        response = requests.get(
            BASE_URL + "/v2/history/candles",
            params={
                "symbol": SYMBOL,
                "resolution": TIMEFRAME,
                "start": start,
                "end": end
            },
            timeout=15
        )

        data = response.json()

        if not response.ok:

            st.error(
                f"Delta candle API error: {data}"
            )

            st.stop()

        if not data.get("success"):

            st.error(
                f"Delta candle data unavailable: {data}"
            )

            st.stop()

        return data.get("result", [])

    except Exception as e:

        st.error(
            f"API Error: {e}"
        )

        st.stop()


# ============================================================
# CANDLE DATA
# ============================================================

raw_candles = get_candles()

rows = []

for candle in raw_candles:

    try:

        rows.append({

            "time": int(candle["time"]),

            "open": float(candle["open"]),

            "high": float(candle["high"]),

            "low": float(candle["low"]),

            "close": float(candle["close"])

        })

    except Exception:

        continue


if not rows:

    st.error("No candle data found.")

    st.stop()


df = pd.DataFrame(rows)


df = (
    df
    .drop_duplicates("time")
    .sort_values("time")
    .reset_index(drop=True)
)


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

    st.error(
        "Not enough completed candles."
    )

    st.stop()


# ============================================================
# TRUE RANGE
# ============================================================

prev_close = df["close"].shift(1)

tr1 = (
    df["high"] -
    df["low"]
)

tr2 = (
    df["high"] -
    prev_close
).abs()

tr3 = (
    df["low"] -
    prev_close
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

    previous_atr = (
        df.loc[i - 1, "ATR"]
    )

    current_tr = (
        df.loc[i, "TR"]
    )

    df.loc[i, "ATR"] = (

        previous_atr *
        (ATR_PERIOD - 1)

        +

        current_tr

    ) / ATR_PERIOD


# ============================================================
# HL2
# ============================================================

df["HL2"] = (

    df["high"] +
    df["low"]

) / 2


# ============================================================
# OLD MATCHED SUPERTREND ENGINE
#
# THIS IS THE IMPORTANT PART
# DO NOT REPLACE WITH ta.supertrend()
#
# Same logic as the earlier working code.
# ============================================================

df["UP"] = float("nan")

df["DN"] = float("nan")

df["TREND"] = float("nan")

df["SUPERTREND"] = float("nan")

df["SIGNAL"] = ""


for i in range(len(df)):

    atr = df.loc[i, "ATR"]


    if pd.isna(atr):

        continue


    # --------------------------------------------------------
    # SOURCE = HL2
    # --------------------------------------------------------

    src = df.loc[i, "HL2"]


    # --------------------------------------------------------
    # BASIC BANDS
    # --------------------------------------------------------

    up = (
        src -
        MULTIPLIER * atr
    )

    dn = (
        src +
        MULTIPLIER * atr
    )


    # --------------------------------------------------------
    # FIRST VALID BAR
    # --------------------------------------------------------

    if i == ATR_PERIOD - 1:

        trend = 1

        df.loc[i, "UP"] = up

        df.loc[i, "DN"] = dn

        df.loc[i, "TREND"] = trend

        df.loc[i, "SUPERTREND"] = up

        continue


    # --------------------------------------------------------
    # PREVIOUS VALUES
    # --------------------------------------------------------

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

        previous_up = up


    if pd.isna(previous_dn):

        previous_dn = dn


    if pd.isna(previous_trend):

        previous_trend = 1


    # ========================================================
    # EXACT OLD BAND LOGIC
    # ========================================================

    up1 = previous_up


    if previous_close > up1:

        up = max(
            up,
            up1
        )


    dn1 = previous_dn


    if previous_close < dn1:

        dn = min(
            dn,
            dn1
        )


    # ========================================================
    # EXACT OLD TREND LOGIC
    # ========================================================

    trend = previous_trend

    close = df.loc[
        i,
        "close"
    ]


    if (
        trend == -1
        and
        close > dn1
    ):

        trend = 1


    elif (
        trend == 1
        and
        close < up1
    ):

        trend = -1


    # ========================================================
    # SAVE VALUES
    # ========================================================

    df.loc[i, "UP"] = up

    df.loc[i, "DN"] = dn

    df.loc[i, "TREND"] = trend


    if trend == 1:

        df.loc[
            i,
            "SUPERTREND"
        ] = up

    else:

        df.loc[
            i,
            "SUPERTREND"
        ] = dn


    # ========================================================
    # EXACT ENTRY SIGNAL
    # ========================================================

    if (
        trend == 1
        and
        previous_trend == -1
    ):

        df.loc[
            i,
            "SIGNAL"
        ] = "BUY"


    elif (
        trend == -1
        and
        previous_trend == 1
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
# CURRENT ENTRY
# ============================================================

st.header("🎯 CURRENT ENTRY")


if len(signal_rows) >= 1:

    current = signal_rows.iloc[-1]

    current_signal = (
        current["SIGNAL"]
    )

    current_price = float(
        current["close"]
    )

    current_st = float(
        current["SUPERTREND"]
    )

    current_time = (
        datetime.fromtimestamp(
            int(current["time"]),
            tz=timezone.utc
        )
        .strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    )


    if current_signal == "BUY":

        st.success(
            f"🟢 BUY | "
            f"ENTRY: {current_price:,.2f} | "
            f"SUPERTREND: {current_st:,.2f}"
        )

    else:

        st.error(
            f"🔴 SELL | "
            f"ENTRY: {current_price:,.2f} | "
            f"SUPERTREND: {current_st:,.2f}"
        )


    st.write(
        f"Signal Candle: **{current_time}**"
    )


else:

    st.info(
        "No SuperTrend entry found."
    )


# ============================================================
# PREVIOUS ENTRY
# ============================================================

st.header("📜 PREVIOUS ENTRY")


if len(signal_rows) >= 2:

    previous = signal_rows.iloc[-2]

    previous_signal = (
        previous["SIGNAL"]
    )

    previous_price = float(
        previous["close"]
    )

    previous_st = float(
        previous["SUPERTREND"]
    )

    previous_time = (
        datetime.fromtimestamp(
            int(previous["time"]),
            tz=timezone.utc
        )
        .strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    )


    if previous_signal == "BUY":

        st.success(
            f"🟢 BUY | "
            f"ENTRY: {previous_price:,.2f} | "
            f"SUPERTREND: {previous_st:,.2f}"
        )

    else:

        st.error(
            f"🔴 SELL | "
            f"ENTRY: {previous_price:,.2f} | "
            f"SUPERTREND: {previous_st:,.2f}"
        )


    st.write(
        f"Signal Candle: **{previous_time}**"
    )


else:

    st.info(
        "Previous entry available nahi hai."
    )


# ============================================================
# CURRENT SUPERTREND
# ============================================================

last = df.iloc[-1]

last_trend = int(
    last["TREND"]
)

last_close = float(
    last["close"]
)

last_st = float(
    last["SUPERTREND"]
)


st.divider()


if last_trend == 1:

    st.metric(
        "CURRENT SUPERTREND",
        "BUY / BULLISH 🟢"
    )

else:

    st.metric(
        "CURRENT SUPERTREND",
        "SELL / BEARISH 🔴"
    )


st.write(
    f"Current Close: "
    f"**{last_close:,.2f}**"
)


st.write(
    f"Current SuperTrend: "
    f"**{last_st:,.2f}**"
)


# ============================================================
# BOT STATUS
# ============================================================

st.divider()

st.header("🤖 BOT STATUS")

st.info(
    "AUTO BOT ENGINE READY — "
    "Manual BUY/SELL button nahi hai."
)

st.caption(
    "Real order placement Part 3/4 mein add hoga, "
    "Entry calculation ko change kiye bina."
)


# ============================================================
# REFRESH
# ============================================================

time.sleep(
    REFRESH_SECONDS
)

st.rerun()
