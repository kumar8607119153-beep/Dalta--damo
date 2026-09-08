# ============================================================
# live_dashboard.py
# SANJAY RANA
# DELTA EXCHANGE INDIA
# TRADINGVIEW SUPERTREND ENTRY ENGINE
# ============================================================

import os
import time
import hmac
import hashlib
from datetime import datetime, timezone

import requests
import pandas as pd
import numpy as np
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://api.india.delta.exchange"
).rstrip("/")

SYMBOL = os.getenv("DELTA_SYMBOL", "BTCUSD")

TIMEFRAME = "5m"
CANDLE_SECONDS = 300

# TradingView Pine settings
ATR_PERIOD = 10
MULTIPLIER = 3.0

REFRESH_SECONDS = max(
    3,
    int(os.getenv("DASHBOARD_REFRESH", "5"))
)


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Sanjay Rana SuperTrend",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SANJAY RANA — TRADINGVIEW SUPERTREND")
st.caption(
    "Delta Exchange India REAL DATA • 5 Minute • "
    "ATR 10 • Multiplier 3.0 • HL2"
)


# ============================================================
# DELTA PUBLIC API
# ============================================================

class DeltaAPI:

    def __init__(self):
        self.session = requests.Session()

    def get(self, path, params=None):

        try:
            response = self.session.get(
                BASE_URL + path,
                params=params or {},
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Sanjay-Rana-SuperTrend"
                },
                timeout=15
            )

            try:
                data = response.json()
            except Exception:
                return {
                    "success": False,
                    "error": "Invalid API response"
                }

            if not response.ok:
                return {
                    "success": False,
                    "error": data
                }

            return data

        except requests.RequestException as e:

            return {
                "success": False,
                "error": str(e)
            }

    def ticker(self):

        return self.get(
            f"/v2/tickers/{SYMBOL}"
        )

    def candles(self):

        end = int(time.time())

        # Enough history for ATR + SuperTrend
        start = end - (500 * CANDLE_SECONDS)

        return self.get(
            "/v2/history/candles",
            {
                "symbol": SYMBOL,
                "resolution": TIMEFRAME,
                "start": start,
                "end": end
            }
        )


api = DeltaAPI()


# ============================================================
# DATA HELPERS
# ============================================================

def number(value, default=None):

    try:

        if value is None:
            return default

        return float(value)

    except Exception:

        return default


def get_result(data):

    if not data:
        return None

    if not data.get("success"):
        return None

    return data.get("result")


# ============================================================
# CANDLE DATAFRAME
# ============================================================

def make_dataframe(data):

    result = get_result(data)

    if not isinstance(result, list):
        return pd.DataFrame()

    rows = []

    for candle in result:

        try:

            rows.append({
                "time": int(candle["time"]),
                "open": number(candle["open"]),
                "high": number(candle["high"]),
                "low": number(candle["low"]),
                "close": number(candle["close"]),
                "volume": number(
                    candle.get("volume"),
                    0
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

    df["datetime"] = pd.to_datetime(
        df["time"],
        unit="s",
        utc=True
    )

    return df


# ============================================================
# TRADINGVIEW RMA
# ============================================================

def tradingview_rma(series, length):

    result = pd.Series(
        np.nan,
        index=series.index,
        dtype=float
    )

    if len(series) < length:
        return result

    # TradingView RMA seed
    result.iloc[length - 1] = (
        series.iloc[:length].mean()
    )

    alpha = 1.0 / length

    for i in range(length, len(series)):

        result.iloc[i] = (
            alpha * series.iloc[i]
            +
            (1.0 - alpha) * result.iloc[i - 1]
        )

    return result


# ============================================================
# TRADINGVIEW SUPERTREND
# ============================================================

def calculate_supertrend(df):

    if df.empty:
        return pd.DataFrame()

    if len(df) < ATR_PERIOD + 2:
        return pd.DataFrame()

    result = df.copy()

    high = result["high"].astype(float)
    low = result["low"].astype(float)
    close = result["close"].astype(float)

    # --------------------------------------------------------
    # TradingView SOURCE = HL2
    # --------------------------------------------------------

    src = (high + low) / 2.0

    # --------------------------------------------------------
    # TradingView True Range
    # --------------------------------------------------------

    previous_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - previous_close).abs()
    tr3 = (low - previous_close).abs()

    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    # --------------------------------------------------------
    # TradingView ta.atr(10)
    # ta.atr() = RMA(True Range)
    # --------------------------------------------------------

    atr = tradingview_rma(
        tr,
        ATR_PERIOD
    )

    # --------------------------------------------------------
    # Pine:
    #
    # up = src - Multiplier * atr
    # dn = src + Multiplier * atr
    # --------------------------------------------------------

    basic_up = (
        src - MULTIPLIER * atr
    )

    basic_dn = (
        src + MULTIPLIER * atr
    )

    final_up = pd.Series(
        np.nan,
        index=result.index,
        dtype=float
    )

    final_dn = pd.Series(
        np.nan,
        index=result.index,
        dtype=float
    )

    trend = pd.Series(
        np.nan,
        index=result.index,
        dtype=float
    )

    supertrend = pd.Series(
        np.nan,
        index=result.index,
        dtype=float
    )

    # Pine:
    # trend = 1
    current_trend = 1

    for i in range(len(result)):

        if i < ATR_PERIOD - 1:
            continue

        # ----------------------------------------------------
        # up1 = nz(up[1], up)
        # up := close[1] > up1 ? max(up, up1) : up
        # ----------------------------------------------------

        if i == ATR_PERIOD - 1:

            up1 = basic_up.iloc[i]

        else:

            up1 = final_up.iloc[i - 1]

            if pd.isna(up1):
                up1 = basic_up.iloc[i]

        if close.iloc[i - 1] > up1:

            final_up.iloc[i] = max(
                basic_up.iloc[i],
                up1
            )

        else:

            final_up.iloc[i] = basic_up.iloc[i]

        # ----------------------------------------------------
        # dn1 = nz(dn[1], dn)
        # dn := close[1] < dn1 ? min(dn, dn1) : dn
        # ----------------------------------------------------

        if i == ATR_PERIOD - 1:

            dn1 = basic_dn.iloc[i]

        else:

            dn1 = final_dn.iloc[i - 1]

            if pd.isna(dn1):
                dn1 = basic_dn.iloc[i]

        if close.iloc[i - 1] < dn1:

            final_dn.iloc[i] = min(
                basic_dn.iloc[i],
                dn1
            )

        else:

            final_dn.iloc[i] = basic_dn.iloc[i]

        # ----------------------------------------------------
        # EXACT Pine TREND LOGIC
        #
        # trend := trend == -1 and close > dn1 ? 1 :
        #          trend == 1 and close < up1 ? -1 :
        #          trend
        # ----------------------------------------------------

        if (
            current_trend == -1
            and close.iloc[i] > dn1
        ):

            current_trend = 1

        elif (
            current_trend == 1
            and close.iloc[i] < up1
        ):

            current_trend = -1

        trend.iloc[i] = current_trend

        # ----------------------------------------------------
        # TradingView plotted SuperTrend
        # ----------------------------------------------------

        if current_trend == 1:

            supertrend.iloc[i] = final_up.iloc[i]

        else:

            supertrend.iloc[i] = final_dn.iloc[i]

    # --------------------------------------------------------
    # EXACT TradingView signals
    # --------------------------------------------------------

    buy_signal = (
        (trend == 1)
        &
        (trend.shift(1) == -1)
    )

    sell_signal = (
        (trend == -1)
        &
        (trend.shift(1) == 1)
    )

    result["ATR"] = atr
    result["UP"] = final_up
    result["DN"] = final_dn
    result["Trend"] = trend
    result["SuperTrend"] = supertrend

    result["BuySignal"] = buy_signal
    result["SellSignal"] = sell_signal

    return result


# ============================================================
# FETCH REAL DATA
# ============================================================

ticker_data = api.ticker()
candle_data = api.candles()

ticker_result = get_result(ticker_data)

df = make_dataframe(candle_data)

if not df.empty:

    df = calculate_supertrend(df)


# ============================================================
# REAL MARKET PRICE
# ============================================================

real_price = None

if isinstance(ticker_result, dict):

    for key in (
        "close",
        "mark_price",
        "spot_price",
        "last_price"
    ):

        if ticker_result.get(key) is not None:

            real_price = number(
                ticker_result.get(key)
            )

            if real_price is not None:
                break


# ============================================================
# ERROR CHECK
# ============================================================

if df.empty:

    st.error(
        "🔴 Delta candle data unavailable."
    )

    st.stop()


# ============================================================
# USE CLOSED CANDLE
# ============================================================

# -1 = currently forming candle
# -2 = latest CLOSED candle

signal_index = -2

signal_candle = df.iloc[signal_index]


trend = int(
    signal_candle["Trend"]
)

st_value = number(
    signal_candle["SuperTrend"]
)

atr_value = number(
    signal_candle["ATR"]
)

buy_signal = bool(
    signal_candle["BuySignal"]
)

sell_signal = bool(
    signal_candle["SellSignal"]
)


# ============================================================
# DIRECTION
# ============================================================

if trend == 1:

    direction = "BUY / BULLISH 🟢"

elif trend == -1:

    direction = "SELL / BEARISH 🔴"

else:

    direction = "UNKNOWN"


# ============================================================
# ENTRY SIGNAL
# ============================================================

entry_price = None
signal_name = "NO NEW SIGNAL"

if buy_signal:

    signal_name = "BUY 🟢"

    entry_price = float(
        signal_candle["close"]
    )

elif sell_signal:

    signal_name = "SELL 🔴"

    entry_price = float(
        signal_candle["close"]
    )


# ============================================================
# DISPLAY
# ============================================================

st.header("📡 DELTA EXCHANGE")

if ticker_data.get("success"):

    st.success(
        "🟢 REAL DELTA DATA CONNECTED"
    )

else:

    st.error(
        "🔴 DELTA DATA UNAVAILABLE"
    )


# ============================================================
# PRICE
# ============================================================

st.header("💰 LIVE BTCUSD")

if real_price is not None:

    st.metric(
        "REAL MARKET PRICE",
        f"{real_price:,.2f}"
    )

else:

    st.metric(
        "REAL MARKET PRICE",
        "DATA UNAVAILABLE"
    )


# ============================================================
# SUPERTREND
# ============================================================

st.header(
    "🔄 TRADINGVIEW SUPERTREND ENGINE"
)

c1, c2, c3 = st.columns(3)

with c1:

    st.metric(
        "DIRECTION",
        direction
    )

with c2:

    if st_value is not None:

        st.metric(
            "SUPERTREND",
            f"{st_value:,.2f}"
        )

    else:

        st.metric(
            "SUPERTREND",
            "DATA UNAVAILABLE"
        )

with c3:

    if atr_value is not None:

        st.metric(
            "ATR (10)",
            f"{atr_value:,.2f}"
        )

    else:

        st.metric(
            "ATR (10)",
            "DATA UNAVAILABLE"
        )


# ============================================================
# ENTRY
# ============================================================

st.header("🎯 ENTRY SIGNAL")

e1, e2 = st.columns(2)

with e1:

    if buy_signal:

        st.success(
            f"🟢 BUY ENTRY : "
            f"{entry_price:,.2f}"
        )

    elif sell_signal:

        st.error(
            f"🔴 SELL ENTRY : "
            f"{entry_price:,.2f}"
        )

    else:

        st.info(
            "NO NEW BUY/SELL SIGNAL "
            "ON THE LATEST CLOSED CANDLE"
        )

with e2:

    st.metric(
        "SIGNAL CANDLE CLOSE",
        f"{float(signal_candle['close']):,.2f}"
    )


# ============================================================
# SIGNAL CANDLE TIME
# ============================================================

signal_time = signal_candle["datetime"]

st.write(
    "🕐 Signal Candle:",
    signal_time.strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )
)


# ============================================================
# DEBUG / MATCHING TABLE
# ============================================================

st.header("🔍 TRADINGVIEW MATCH CHECK")

check = pd.DataFrame([
    {
        "Setting": "Timeframe",
        "Python": "5m",
        "TradingView": "5m"
    },
    {
        "Setting": "ATR Period",
        "Python": ATR_PERIOD,
        "TradingView": 10
    },
    {
        "Setting": "Multiplier",
        "Python": MULTIPLIER,
        "TradingView": 3.0
    },
    {
        "Setting": "Source",
        "Python": "HL2",
        "TradingView": "HL2"
    },
    {
        "Setting": "ATR Method",
        "Python": "RMA / ta.atr",
        "TradingView": "ta.atr"
    },
    {
        "Setting": "BUY",
        "Python": "trend 1 after -1",
        "TradingView": "trend 1 after -1"
    },
    {
        "Setting": "SELL",
        "Python": "trend -1 after 1",
        "TradingView": "trend -1 after 1"
    }
])

st.dataframe(
    check,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# LAST CLOSED CANDLES
# ============================================================

st.header("🕯️ LAST CLOSED CANDLES")

display_df = df.tail(10).copy()

display_df["Direction"] = np.where(
    display_df["Trend"] == 1,
    "BUY / BULLISH",
    np.where(
        display_df["Trend"] == -1,
        "SELL / BEARISH",
        "UNKNOWN"
    )
)

display_df["Signal"] = np.where(
    display_df["BuySignal"],
    "BUY",
    np.where(
        display_df["SellSignal"],
        "SELL",
        ""
    )
)

display_df = display_df[
    [
        "datetime",
        "open",
        "high",
        "low",
        "close",
        "ATR",
        "SuperTrend",
        "Direction",
        "Signal"
    ]
]

st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True
)


# ============================================================
# REFRESH
# ============================================================

time.sleep(REFRESH_SECONDS)

st.rerun()
