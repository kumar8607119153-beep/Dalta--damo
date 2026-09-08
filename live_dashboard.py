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
# ============================================================
# PART 2/4
# SANJAY RANA - ENTRY + TARGET ENGINE
# ============================================================

# ============================================================
# TARGET SETTINGS
# ============================================================

TARGET_1_POINTS = 300
TARGET_2_POINTS = 600
TARGET_3_POINTS = 900


# ============================================================
# CURRENT SIGNAL
# ============================================================

if len(signal_rows) >= 1:

    current = signal_rows.iloc[-1]

    current_signal = str(
        current["SIGNAL"]
    ).upper()

    entry_price = float(
        current["close"]
    )

    supertrend_price = float(
        current["SUPERTREND"]
    )

    signal_timestamp = int(
        current["time"]
    )


    # ========================================================
    # TARGET CALCULATION
    # ========================================================

    if current_signal == "BUY":

        target_1 = (
            entry_price +
            TARGET_1_POINTS
        )

        target_2 = (
            entry_price +
            TARGET_2_POINTS
        )

        target_3 = (
            entry_price +
            TARGET_3_POINTS
        )


    elif current_signal == "SELL":

        target_1 = (
            entry_price -
            TARGET_1_POINTS
        )

        target_2 = (
            entry_price -
            TARGET_2_POINTS
        )

        target_3 = (
            entry_price -
            TARGET_3_POINTS
        )


    else:

        target_1 = entry_price
        target_2 = entry_price
        target_3 = entry_price


    # ========================================================
    # ENTRY
    # ========================================================

    st.header("🎯 CURRENT ENTRY")


    if current_signal == "BUY":

        st.success(
            f"🟢 BUY  |  "
            f"ENTRY: {entry_price:,.2f}  |  "
            f"SUPERTREND: {supertrend_price:,.2f}"
        )

    elif current_signal == "SELL":

        st.error(
            f"🔴 SELL  |  "
            f"ENTRY: {entry_price:,.2f}  |  "
            f"SUPERTREND: {supertrend_price:,.2f}"
        )


    signal_time = datetime.fromtimestamp(
        signal_timestamp,
        tz=timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


    st.write(
        f"Signal Candle: **{signal_time}**"
    )


    # ========================================================
    # TARGETS
    # ========================================================

    st.header("🎯 TARGETS")


    t1, t2, t3 = st.columns(3)


    with t1:

        st.metric(
            "TARGET 1",
            f"{target_1:,.2f}"
        )

        st.caption(
            f"{TARGET_1_POINTS} points"
        )


    with t2:

        st.metric(
            "TARGET 2",
            f"{target_2:,.2f}"
        )

        st.caption(
            f"{TARGET_2_POINTS} points"
        )


    with t3:

        st.metric(
            "TARGET 3",
            f"{target_3:,.2f}"
        )

        st.caption(
            f"{TARGET_3_POINTS} points"
        )


    # ========================================================
    # TARGET STATUS
    # ========================================================

    if real_price is not None:

        if current_signal == "BUY":

            if real_price >= target_3:

                target_status = "🎯 TARGET 3 HIT"

            elif real_price >= target_2:

                target_status = "🎯 TARGET 2 HIT"

            elif real_price >= target_1:

                target_status = "🎯 TARGET 1 HIT"

            else:

                target_status = "⏳ TARGET 1 WAITING"


        elif current_signal == "SELL":

            if real_price <= target_3:

                target_status = "🎯 TARGET 3 HIT"

            elif real_price <= target_2:

                target_status = "🎯 TARGET 2 HIT"

            elif real_price <= target_1:

                target_status = "🎯 TARGET 1 HIT"

            else:

                target_status = "⏳ TARGET 1 WAITING"


        else:

            target_status = "WAITING"


        st.info(
            f"Target Status: **{target_status}**"
        )


else:

    st.info(
        "No confirmed SuperTrend entry available."
    )


# ============================================================
# PREVIOUS ENTRY
# ============================================================

st.header("📜 PREVIOUS ENTRY")


if len(signal_rows) >= 2:

    previous = signal_rows.iloc[-2]

    previous_signal = str(
        previous["SIGNAL"]
    ).upper()

    previous_entry = float(
        previous["close"]
    )

    previous_st = float(
        previous["SUPERTREND"]
    )

    previous_time = datetime.fromtimestamp(
        int(previous["time"]),
        tz=timezone.utc
    ).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


    if previous_signal == "BUY":

        previous_t1 = (
            previous_entry +
            TARGET_1_POINTS
        )

        previous_t2 = (
            previous_entry +
            TARGET_2_POINTS
        )

        previous_t3 = (
            previous_entry +
            TARGET_3_POINTS
        )


        st.success(
            f"🟢 BUY  |  "
            f"ENTRY: {previous_entry:,.2f}  |  "
            f"SUPERTREND: {previous_st:,.2f}"
        )


    else:

        previous_t1 = (
            previous_entry -
            TARGET_1_POINTS
        )

        previous_t2 = (
            previous_entry -
            TARGET_2_POINTS
        )

        previous_t3 = (
            previous_entry -
            TARGET_3_POINTS
        )


        st.error(
            f"🔴 SELL  |  "
            f"ENTRY: {previous_entry:,.2f}  |  "
            f"SUPERTREND: {previous_st:,.2f}"
        )


    st.write(
        f"Signal Candle: **{previous_time}**"
    )


    p1, p2, p3 = st.columns(3)


    with p1:

        st.metric(
            "PREVIOUS T1",
            f"{previous_t1:,.2f}"
        )


    with p2:

        st.metric(
            "PREVIOUS T2",
            f"{previous_t2:,.2f}"
        )


    with p3:

        st.metric(
            "PREVIOUS T3",
            f"{previous_t3:,.2f}"
        )


else:

    st.info(
        "Previous entry available nahi hai."
        # ============================================================
# PART 3/4
# SANJAY RANA - MEMBER + API + AUTO BOT
# ============================================================

import hmac
import hashlib
import json


# ============================================================
# MEMBER SETTINGS
# ============================================================

MEMBER_NAME = os.getenv(
    "MEMBER_NAME",
    "Member 1"
)

API_KEY = os.getenv(
    "DELTA_API_KEY",
    ""
)

API_SECRET = os.getenv(
    "DELTA_API_SECRET",
    ""
)

PRODUCT_ID = int(
    os.getenv(
        "DELTA_PRODUCT_ID",
        "27"
    )
)

ORDER_SIZE = int(
    os.getenv(
        "DELTA_ORDER_SIZE",
        "1"
    )
)

# IMPORTANT:
# false = signal only
# true  = automatic real order
AUTO_TRADE = os.getenv(
    "AUTO_TRADE",
    "false"
).lower() == "true"


# ============================================================
# MEMBER CONNECTION
# ============================================================

st.divider()

st.header("👤 MEMBER API CONNECTION")

mc1, mc2 = st.columns(2)

with mc1:

    st.write(
        f"**Member:** {MEMBER_NAME}"
    )

with mc2:

    if API_KEY and API_SECRET:

        st.success(
            "🟢 API credentials loaded"
        )

    else:

        st.warning(
            "🟡 API credentials not added"
        )


# ============================================================
# AUTO BOT STATUS
# ============================================================

st.header("🤖 AUTO TRADING BOT")


if AUTO_TRADE:

    st.success(
        "🟢 AUTO TRADE ENABLED"
    )

else:

    st.warning(
        "🟡 AUTO TRADE DISABLED"
    )


st.write(
    "Manual BUY/SELL button: ❌"
)


# ============================================================
# DELTA PRIVATE API
# ============================================================

def delta_signature(
    method,
    timestamp,
    path,
    query_string="",
    body=""
):

    message = (
        method.upper()
        +
        timestamp
        +
        path
        +
        query_string
        +
        body
    )

    return hmac.new(
        API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def delta_private_request(
    method,
    path,
    params=None,
    body=None
):

    if not API_KEY or not API_SECRET:

        return {
            "success": False,
            "error": "API credentials missing"
        }


    params = params or {}

    body = body or {}

    body_string = json.dumps(
        body,
        separators=(",", ":")
    ) if body else ""


    query_string = ""

    if params:

        query_string = "?" + "&".join(
            f"{key}={value}"
            for key, value in params.items()
        )


    timestamp = str(
        int(time.time())
    )


    signature = delta_signature(
        method,
        timestamp,
        path,
        query_string,
        body_string
    )


    headers = {

        "Accept":
            "application/json",

        "Content-Type":
            "application/json",

        "api-key":
            API_KEY,

        "timestamp":
            timestamp,

        "signature":
            signature

    }


    try:

        response = requests.request(

            method.upper(),

            BASE_URL + path,

            params=params,

            data=body_string,

            headers=headers,

            timeout=15

        )


        try:

            return response.json()

        except Exception:

            return {

                "success": False,

                "error":
                    "Invalid API response"

            }


    except requests.RequestException as e:

        return {

            "success": False,

            "error": str(e)

        }


# ============================================================
# REAL ORDER FUNCTION
# ============================================================

def place_real_order(
    side,
    size
):

    if not AUTO_TRADE:

        return {

            "success": False,

            "error":
                "AUTO_TRADE is disabled"

        }


    if not API_KEY or not API_SECRET:

        return {

            "success": False,

            "error":
                "API credentials missing"

        }


    order_body = {

        "product_id":
            PRODUCT_ID,

        "size":
            int(size),

        "side":
            side,

        "order_type":
            "market"

    }


    return delta_private_request(

        "POST",

        "/v2/orders",

        body=order_body

    )


# ============================================================
# SIGNAL ID
# ============================================================

def signal_id(row):

    return (
        f"{int(row['time'])}_"
        f"{row['SIGNAL']}"
    )


# ============================================================
# PREVENT DUPLICATE ORDERS
# ============================================================

if "last_processed_signal" not in st.session_state:

    st.session_state[
        "last_processed_signal"
    ] = ""


# ============================================================
# AUTO SIGNAL PROCESSOR
# ============================================================

if len(signal_rows) >= 1:

    bot_signal = signal_rows.iloc[-1]

    bot_signal_type = str(
        bot_signal["SIGNAL"]
    ).upper()

    bot_signal_id = signal_id(
        bot_signal
    )


    st.subheader(
        "📡 BOT SIGNAL"
    )


    if bot_signal_type == "BUY":

        st.success(
            f"🟢 NEW SIGNAL: BUY"
        )

    elif bot_signal_type == "SELL":

        st.error(
            f"🔴 NEW SIGNAL: SELL"
        )


    st.write(
        f"Signal Entry: "
        f"**{float(bot_signal['close']):,.2f}**"
    )


    st.write(
        f"Signal Candle: "
        f"**{datetime.fromtimestamp("
        f"int(bot_signal['time']),"
        f"tz=timezone.utc)"
        f".strftime('%Y-%m-%d %H:%M:%S UTC')}**"
    )


    # ========================================================
    # ONLY PROCESS NEW SIGNAL ONCE
    # ========================================================

    if (
        bot_signal_id
        !=
        st.session_state[
            "last_processed_signal"
        ]
    ):


        # ----------------------------------------------------
        # MARK SIGNAL AS PROCESSED
        # ----------------------------------------------------

        st.session_state[
            "last_processed_signal"
        ] = bot_signal_id


        # ----------------------------------------------------
        # REAL AUTO ORDER
        # ----------------------------------------------------

        if AUTO_TRADE:

            if bot_signal_type == "BUY":

                order_result = place_real_order(
                    "buy",
                    ORDER_SIZE
                )

            elif bot_signal_type == "SELL":

                order_result = place_real_order(
                    "sell",
                    ORDER_SIZE
                )

            else:

                order_result = {
                    "success":
                        False,

                    "error":
                        "Unknown signal"
                }


            # ------------------------------------------------
            # ORDER RESULT
            # ------------------------------------------------

            if order_result.get(
                "success"
            ):

                st.success(
                    "✅ REAL ORDER SENT"
                )

                st.json(
                    order_result
                )

            else:

                st.error(
                    "❌ REAL ORDER FAILED"
                )

                st.json(
                    order_result
                )


        else:

            st.info(
                "Signal detected. "
                "AUTO_TRADE=false, "
                "so no real order was sent."
            )


else:

    st.info(
        "No SuperTrend signal available."
    )


# ============================================================
# BOT CONFIGURATION
# ============================================================

st.divider()

st.header("⚙️ BOT CONFIGURATION")

config_rows = [

    {
        "Setting":
            "Member",

        "Value":
            MEMBER_NAME
    },

    {
        "Setting":
            "Symbol",

        "Value":
            SYMBOL
    },

    {
        "Setting":
            "Timeframe",

        "Value":
            "5 Minute"
    },

    {
        "Setting":
            "ATR",

        "Value":
            ATR_PERIOD
    },

    {
        "Setting":
            "Multiplier",

        "Value":
            MULTIPLIER
    },

    {
        "Setting":
            "Order Size",

        "Value":
            ORDER_SIZE
    },

    {
        "Setting":
            "Auto Trade",

        "Value":
            "ON"
            if AUTO_TRADE
            else
            "OFF"
    }

]


st.dataframe(
    pd.DataFrame(config_rows),
    use_container_width=True,
    hide_index=True
)
