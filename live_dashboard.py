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

REFRESH_SECONDS = 5

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
# DISPLAY HELPERS
# ============================================================

def number(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def show_price(value):
    value = number(value)

    if value is None:
        return "-"

    return f"{value:,.2f}"


# ============================================================
# DELTA API
# ============================================================

class DeltaAPI:

    def __init__(self):

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
# API CREDENTIALS
# ============================================================

API_KEY = os.getenv(
    "DELTA_API_KEY",
    ""
)

API_SECRET = os.getenv(
    "DELTA_API_SECRET",
    ""
)


api = DeltaAPI()


# ============================================================
# BASIC STATUS
# ============================================================

if REMOTE_TRADING:

    st.warning(
        "🔴 REAL TRADING MODE ENABLED"
    )

else:

    st.info(
        "🟡 SIGNAL / TEST MODE — "
        "REAL ORDERS DISABLED"
      # ============================================================
# PART 2/4
# CANDLE DATA + EXACT SUPERTREND ENGINE
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
                "volume": float(
                    candle.get("volume", 0)
                )
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
# FETCH CANDLES
# ============================================================

candle_response = api.candles()

df = make_dataframe(candle_response)


if df.empty:

    st.error(
        "❌ Delta se candle data nahi mila."
    )

    st.stop()


# ============================================================
# ONLY COMPLETED 5-MINUTE CANDLES
# ============================================================

current_candle_start = (
    int(time.time())
    // CANDLE_SECONDS
) * CANDLE_SECONDS


df = df[
    df["time"] < current_candle_start
].copy()


df = (
    df
    .reset_index(drop=True)
)


if len(df) < ATR_PERIOD + 5:

    st.error(
        "❌ SuperTrend calculate karne ke liye "
        "enough candles nahi hain."
    )

    st.stop()


# ============================================================
# TRUE RANGE
# ============================================================

prev_close = df["close"].shift(1)

tr1 = (
    df["high"]
    - df["low"]
)

tr2 = (
    df["high"]
    - prev_close
).abs()

tr3 = (
    df["low"]
    - prev_close
).abs()


df["TR"] = pd.concat(
    [
        tr1,
        tr2,
        tr3
    ],
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
        previous_atr
        * (ATR_PERIOD - 1)
        + current_tr
    ) / ATR_PERIOD


# ============================================================
# HL2
# ============================================================

df["HL2"] = (
    df["high"]
    + df["low"]
) / 2.0


# ============================================================
# SUPERTREND DATA
# ============================================================

df["UP"] = float("nan")
df["DN"] = float("nan")

df["TREND"] = float("nan")

df["SUPERTREND"] = float("nan")

df["SIGNAL"] = ""


# ============================================================
# SUPERTREND CALCULATION
#
# BUY / BULLISH  = TREND -1
# SELL / BEARISH = TREND  1
#
# ATR 10
# MULTIPLIER 3.0
# SOURCE HL2
# ============================================================

for i in range(
    len(df)
):

    atr = df.loc[i, "ATR"]


    if pd.isna(atr):

        continue


    src = df.loc[i, "HL2"]


    upper_basic = (
        src
        + MULTIPLIER * atr
    )

    lower_basic = (
        src
        - MULTIPLIER * atr
    )


    # --------------------------------------------------------
    # FIRST VALID BAR
    # --------------------------------------------------------

    if i == ATR_PERIOD - 1:

        df.loc[i, "UP"] = (
            upper_basic
        )

        df.loc[i, "DN"] = (
            lower_basic
        )

        # TradingView direction
        df.loc[i, "TREND"] = 1

        df.loc[i, "SUPERTREND"] = (
            upper_basic
        )

        continue


    # --------------------------------------------------------
    # PREVIOUS VALUES
    # --------------------------------------------------------

    previous_up = (
        df.loc[i - 1, "UP"]
    )

    previous_dn = (
        df.loc[i - 1, "DN"]
    )

    previous_trend = (
        df.loc[i - 1, "TREND"]
    )

    previous_close = (
        df.loc[i - 1, "close"]
    )


    if pd.isna(previous_up):

        previous_up = upper_basic


    if pd.isna(previous_dn):

        previous_dn = lower_basic


    if pd.isna(previous_trend):

        previous_trend = 1


    # ========================================================
    # FINAL LOWER BAND
    # ========================================================

    if (
        lower_basic > previous_dn
        or previous_close < previous_dn
    ):

        lower_band = lower_basic

    else:

        lower_band = previous_dn


    # ========================================================
    # FINAL UPPER BAND
    # ========================================================

    if (
        upper_basic < previous_up
        or previous_close > previous_up
    ):

        upper_band = upper_basic

    else:

        upper_band = previous_up


    # ========================================================
    # TREND DIRECTION
    # ========================================================

    trend = previous_trend

    close = df.loc[i, "close"]


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
    # SAVE BANDS
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
    # CONFIRMED SIGNAL
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
# CURRENT COMPLETED CANDLE
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

    current_direction = (
        "BUY / BULLISH 🟢"
    )

else:

    current_direction = (
        "SELL / BEARISH 🔴"
    )


# ============================================================
# LAST CONFIRMED ENTRY
# ============================================================

if len(signal_rows) >= 1:

    current_entry_row = (
        signal_rows.iloc[-1]
    )

    signal_direction = (
        current_entry_row["SIGNAL"]
    )

    signal_entry_price = float(
        current_entry_row["close"]
    )

    signal_supertrend = float(
        current_entry_row["SUPERTREND"]
    )

    signal_time = indian_time(
        current_entry_row["time"]
    )

else:

    signal_direction = ""

    signal_entry_price = current_close

    signal_supertrend = (
        current_supertrend
    )

    signal_time = indian_time(
        last_candle["time"]
    )


# ============================================================
# PREVIOUS ENTRY
# ============================================================

if len(signal_rows) >= 2:

    previous_entry_row = (
        signal_rows.iloc[-2]
    )

    previous_entry_signal = (
        previous_entry_row["SIGNAL"]
    )

    previous_entry_price = float(
        previous_entry_row["close"]
    )

    previous_entry_st = float(
        previous_entry_row["SUPERTREND"]
    )

    previous_entry_time = indian_time(
        previous_entry_row["time"]
    )

else:

    previous_entry_signal = ""

    previous_entry_price = None

    previous_entry_st = None

    previous_entry_time = "-"


# ============================================================
# DISPLAY SUPERTREND
# ============================================================

st.divider()

st.header(
    "📈 SUPERTREND — 5 MINUTE"
)


a1, a2, a3 = st.columns(3)


with a1:

    st.metric(
        "CURRENT DIRECTION",
        current_direction
    )


with a2:

    st.metric(
        "CURRENT CLOSE",
        show_price(current_close)
    )


with a3:

    st.metric(
        "SUPERTREND",
        show_price(current_supertrend)
    )


# ============================================================
# CURRENT ENTRY
# ============================================================

st.subheader(
    "🎯 CURRENT ENTRY"
)


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

st.subheader(
    "📜 PREVIOUS ENTRY"
)


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
)
