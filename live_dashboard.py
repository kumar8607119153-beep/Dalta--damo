# ============================================================
# live_dashboard.py
# SANJAY RANA - REAL TRADING DASHBOARD
# PART 1/4
# ============================================================

import os
import time
import json
import hmac
import hashlib
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

SYMBOL = os.getenv("DELTA_SYMBOL", "BTCUSD")
PRODUCT_ID = int(os.getenv("DELTA_PRODUCT_ID", "27"))

TIMEFRAME = "5m"
CANDLE_SECONDS = 300

ATR_PERIOD = 10
MULTIPLIER = 3.0

TP1_POINTS = 300
TP2_POINTS = 600
TP3_POINTS = 900

ORDER_SIZE = int(
    os.getenv("DELTA_ORDER_SIZE", "1")
)

REFRESH_SECONDS = 5


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Sanjay Rana Real Trading",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SANJAY RANA — REAL TRADING")

st.caption(
    "Delta Exchange India | BTCUSD | 5 Minute | "
    "ATR 10 | Multiplier 3.0 | HL2"
)


# ============================================================
# MEMBER API CONNECTION
# ============================================================

st.header("👤 MEMBER API CONNECTION")

member_name = st.text_input(
    "Member Name",
    value="Member 1"
)

api_key = st.text_input(
    "Delta API Key",
    type="password"
)

api_secret = st.text_input(
    "Delta API Secret",
    type="password"
)

connect_button = st.button(
    "🔌 CONNECT MEMBER ACCOUNT",
    use_container_width=True
)


# ============================================================
# SESSION STORAGE
# ============================================================

if connect_button:

    if not member_name.strip():
        st.error("Member name required.")

    elif not api_key.strip():
        st.error("API Key required.")

    elif not api_secret.strip():
        st.error("API Secret required.")

    else:

        st.session_state["member_name"] = member_name.strip()
        st.session_state["api_key"] = api_key.strip()
        st.session_state["api_secret"] = api_secret.strip()

        st.session_state["member_connected"] = True

        st.success(
            f"🟢 {member_name} API credentials saved for this session."
        )


# ============================================================
# CONNECTION STATUS
# ============================================================

if st.session_state.get("member_connected", False):

    st.success(
        "🟢 MEMBER ACCOUNT CONNECTED"
    )

    st.write(
        "Member:",
        st.session_state.get(
            "member_name",
            "-"
        )
    )

else:

    st.warning(
        "🔴 MEMBER ACCOUNT NOT CONNECTED"
    )


# ============================================================
# ACTIVE CREDENTIALS
# ============================================================

API_KEY = st.session_state.get(
    "api_key",
    ""
)

API_SECRET = st.session_state.get(
    "api_secret",
    ""
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def show_price(value):

    try:

        return f"{float(value):,.2f}"

    except Exception:

        return "DATA UNAVAILABLE"


def show_time(timestamp):

    try:

        timestamp = int(float(timestamp))

        if timestamp > 10_000_000_000:
            timestamp //= 1000

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    except Exception:

        return "-"


def number(value, default=0.0):

    try:

        return float(value)

    except Exception:

        return default


# ============================================================
# DELTA REAL API CLIENT
# ============================================================

class DeltaAPI:

    def __init__(self):

        self.session = requests.Session()


    # --------------------------------------------------------
    # SIGNATURE
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

        body_string = ""

        if body:

            body_string = json.dumps(
                body,
                separators=(",", ":")
            )


        query_string = ""

        if params:

            query_string = "?" + "&".join(
                f"{k}={params[k]}"
                for k in params
            )


        headers = {
            "Accept": "application/json",
            "User-Agent": "Sanjay-Rana-Real-Trading-Bot"
        }


        if private:

            if not API_KEY or not API_SECRET:

                return {
                    "success": False,
                    "error": "Member API credentials missing"
                }


            timestamp = str(
                int(time.time())
            )


            signature = self.make_signature(
                method,
                timestamp,
                path,
                query_string,
                body_string
            )


            headers.update({

                "api-key": API_KEY,

                "timestamp": timestamp,

                "signature": signature,

                "Content-Type":
                    "application/json"

            })


        try:

            response = self.session.request(

                method.upper(),

                BASE_URL + path,

                params=params,

                data=body_string
                if body_string
                else None,

                headers=headers,

                timeout=15
            )


            try:

                return response.json()

            except Exception:

                return {
                    "success": False,
                    "error": response.text
                }


        except Exception as e:

            return {
                "success": False,
                "error": str(e)
            }


api = DeltaAPI()
# ============================================================
# PART 2/4
# CANDLE DATA + SUPERTREND
# ============================================================


def get_candles():

    end = int(time.time())

    start = end - (
        500 * CANDLE_SECONDS
    )

    return api.request(
        "GET",
        "/v2/history/candles",
        params={
            "symbol": SYMBOL,
            "resolution": TIMEFRAME,
            "start": start,
            "end": end
        },
        private=False
    )


def make_dataframe(data):

    if not data:
        return pd.DataFrame()

    if not data.get("success"):
        return pd.DataFrame()

    result = data.get(
        "result",
        []
    )

    rows = []

    for candle in result:

        try:

            rows.append({

                "time":
                    int(candle["time"]),

                "open":
                    float(candle["open"]),

                "high":
                    float(candle["high"]),

                "low":
                    float(candle["low"]),

                "close":
                    float(candle["close"])

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
# SUPERTREND ENGINE
# ============================================================

def calculate_supertrend(df):

    if len(df) < ATR_PERIOD + 5:

        return pd.DataFrame()


    high = df["high"]
    low = df["low"]
    close = df["close"]


    # ========================================================
    # TRUE RANGE
    # ========================================================

    previous_close = close.shift(1)

    tr1 = high - low

    tr2 = (
        high - previous_close
    ).abs()

    tr3 = (
        low - previous_close
    ).abs()


    tr = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)


    # ========================================================
    # ATR 10 — WILDER RMA
    # ========================================================

    atr = pd.Series(
        index=df.index,
        dtype=float
    )


    atr.iloc[
        ATR_PERIOD - 1
    ] = tr.iloc[
        :ATR_PERIOD
    ].mean()


    for i in range(
        ATR_PERIOD,
        len(df)
    ):

        atr.iloc[i] = (

            atr.iloc[i - 1]
            * (ATR_PERIOD - 1)
            + tr.iloc[i]

        ) / ATR_PERIOD


    # ========================================================
    # HL2
    # ========================================================

    hl2 = (
        high + low
    ) / 2.0


    upper_basic = (
        hl2
        + MULTIPLIER * atr
    )

    lower_basic = (
        hl2
        - MULTIPLIER * atr
    )


    upper_band = pd.Series(
        index=df.index,
        dtype=float
    )

    lower_band = pd.Series(
        index=df.index,
        dtype=float
    )

    trend = pd.Series(
        index=df.index,
        dtype=int
    )

    supertrend = pd.Series(
        index=df.index,
        dtype=float
    )


    # ========================================================
    # ENGINE
    # ========================================================

    for i in range(len(df)):

        if i < ATR_PERIOD - 1:

            continue


        if i == ATR_PERIOD - 1:

            upper_band.iloc[i] = (
                upper_basic.iloc[i]
            )

            lower_band.iloc[i] = (
                lower_basic.iloc[i]
            )

            trend.iloc[i] = 1

            supertrend.iloc[i] = (
                lower_band.iloc[i]
            )

            continue


        # ----------------------------------------------------
        # LOWER BAND
        # ----------------------------------------------------

        if (
            lower_basic.iloc[i]
            > lower_band.iloc[i - 1]

            or

            close.iloc[i - 1]
            < lower_band.iloc[i - 1]
        ):

            lower_band.iloc[i] = (
                lower_basic.iloc[i]
            )

        else:

            lower_band.iloc[i] = (
                lower_band.iloc[i - 1]
            )


        # ----------------------------------------------------
        # UPPER BAND
        # ----------------------------------------------------

        if (
            upper_basic.iloc[i]
            < upper_band.iloc[i - 1]

            or

            close.iloc[i - 1]
            > upper_band.iloc[i - 1]
        ):

            upper_band.iloc[i] = (
                upper_basic.iloc[i]
            )

        else:

            upper_band.iloc[i] = (
                upper_band.iloc[i - 1]
            )


        # ----------------------------------------------------
        # TREND
        # ----------------------------------------------------

        previous_trend = (
            trend.iloc[i - 1]
        )


        if previous_trend == 1:

            if (
                close.iloc[i]
                > upper_band.iloc[i]
            ):

                trend.iloc[i] = -1

            else:

                trend.iloc[i] = 1

        else:

            if (
                close.iloc[i]
                < lower_band.iloc[i]
            ):

                trend.iloc[i] = 1

            else:

                trend.iloc[i] = -1


        # ----------------------------------------------------
        # SUPERTREND
        # ----------------------------------------------------

        if trend.iloc[i] == -1:

            supertrend.iloc[i] = (
                lower_band.iloc[i]
            )

        else:

            supertrend.iloc[i] = (
                upper_band.iloc[i]
            )


    result = df.copy()

    result["ATR"] = atr

    result["Trend"] = trend

    result["SuperTrend"] = supertrend

    result["SIGNAL"] = ""


    # ========================================================
    # BUY / SELL SIGNAL
    # ========================================================

    for i in range(1, len(result)):

        previous = result.iloc[i - 1]

        current = result.iloc[i]


        if (
            previous["Trend"] == 1
            and current["Trend"] == -1
        ):

            result.loc[
                result.index[i],
                "SIGNAL"
            ] = "BUY"


        elif (
            previous["Trend"] == -1
            and current["Trend"] == 1
        ):

            result.loc[
                result.index[i],
                "SIGNAL"
            ] = "SELL"


    return result


# ============================================================
# GET MARKET DATA
# ============================================================

candle_data = get_candles()

df = make_dataframe(
    candle_data
)


# ============================================================
# ONLY COMPLETED 5-MINUTE CANDLES
# ============================================================

if not df.empty:

    current_candle_start = (
        int(time.time())
        // CANDLE_SECONDS
    ) * CANDLE_SECONDS


    df = df[
        df["time"]
        < current_candle_start
    ].copy()


    df = df.reset_index(
        drop=True
    )


# ============================================================
# SUPERTREND CALCULATION
# ============================================================

if not df.empty:

    df = calculate_supertrend(df)


# ============================================================
# SIGNAL DATA
# ============================================================

signal_rows = pd.DataFrame()

if not df.empty:

    signal_rows = df[
        df["SIGNAL"].isin(
            ["BUY", "SELL"]
        )
    ].copy()
  # ============================================================
# PART 3/4
# CURRENT ENTRY + TARGETS + REAL BUY/SELL
# ============================================================


st.divider()

st.header(
    "🎯 SUPERTREND ENTRY"
)


# ============================================================
# CURRENT SIGNAL
# ============================================================

current_signal = None
current_entry = None
current_st = None
current_signal_time = None


if not signal_rows.empty:

    current = signal_rows.iloc[-1]

    current_signal = str(
        current["SIGNAL"]
    )

    current_entry = float(
        current["close"]
    )

    current_st = float(
        current["SuperTrend"]
    )

    current_signal_time = (
        show_time(
            current["time"]
        )
    )


# ============================================================
# CURRENT ENTRY DISPLAY
# ============================================================

if current_signal == "BUY":

    st.success(
        f"🟢 BUY | "
        f"ENTRY: {show_price(current_entry)} | "
        f"SUPERTREND: {show_price(current_st)}"
    )


elif current_signal == "SELL":

    st.error(
        f"🔴 SELL | "
        f"ENTRY: {show_price(current_entry)} | "
        f"SUPERTREND: {show_price(current_st)}"
    )


else:

    st.info(
        "No new SuperTrend entry."
    )


if current_signal:

    st.write(
        f"Signal Candle: "
        f"**{current_signal_time}**"
    )


# ============================================================
# TARGET CALCULATION
# ============================================================

if current_signal == "BUY":

    target1 = (
        current_entry
        + TP1_POINTS
    )

    target2 = (
        current_entry
        + TP2_POINTS
    )

    target3 = (
        current_entry
        + TP3_POINTS
    )


elif current_signal == "SELL":

    target1 = (
        current_entry
        - TP1_POINTS
    )

    target2 = (
        current_entry
        - TP2_POINTS
    )

    target3 = (
        current_entry
        - TP3_POINTS
    )


else:

    target1 = None
    target2 = None
    target3 = None


# ============================================================
# TARGET DISPLAY
# ============================================================

st.subheader(
    "🎯 TARGETS"
)


t1, t2, t3 = st.columns(3)


with t1:

    st.metric(
        "TARGET 1",
        show_price(target1)
        if target1
        else "-"
    )


with t2:

    st.metric(
        "TARGET 2",
        show_price(target2)
        if target2
        else "-"
    )


with t3:

    st.metric(
        "TARGET 3",
        show_price(target3)
        if target3
        else "-"
    )


# ============================================================
# ORDER SIZE
# ============================================================

st.subheader(
    "⚙️ REAL ORDER SETTINGS"
)


order_size = st.number_input(
    "Order Size",
    min_value=1,
    value=ORDER_SIZE,
    step=1
)


# ============================================================
# REAL ORDER FUNCTION
# ============================================================

def place_real_order(
    side,
    size,
    entry,
    tp
):

    if not API_KEY or not API_SECRET:

        return {
            "success": False,
            "error":
                "Member API credentials missing"
        }


    path = "/v2/orders"

    timestamp = str(
        int(time.time())
    )


    # --------------------------------------------------------
    # Real market order
    # --------------------------------------------------------

    body = {

        "product_id":
            PRODUCT_ID,

        "product_symbol":
            SYMBOL,

        "size":
            int(size),

        "side":
            side,

        "order_type":
            "market_order",

        "time_in_force":
            "ioc",

        "reduce_only":
            False,

        "client_order_id":
            (
                "sanjay_"
                + side
                + "_"
                + str(int(time.time()))
            )

    }


    body_string = json.dumps(
        body,
        separators=(",", ":")
    )


    signature = api.make_signature(

        "POST",

        timestamp,

        path,

        "",

        body_string

    )


    headers = {

        "api-key":
            API_KEY,

        "timestamp":
            timestamp,

        "signature":
            signature,

        "User-Agent":
            "Sanjay-Rana-Real-Trading",

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"

    }


    try:

        response = requests.post(

            BASE_URL + path,

            data=body_string,

            headers=headers,

            timeout=15

        )


        try:

            result = response.json()

        except Exception:

            result = {
                "success": False,
                "error": response.text
            }


        return result


    except Exception as e:

        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# REAL BUY / SELL BUTTON
# ============================================================

st.divider()

st.subheader(
    "🚨 REAL ORDER PLACEMENT"
)


st.warning(
    "यह button Delta Exchange पर वास्तविक order भेजेगा।"
)


buy_col, sell_col = st.columns(2)


with buy_col:

    buy_button = st.button(
        "🟢 REAL BUY",
        use_container_width=True
    )


with sell_col:

    sell_button = st.button(
        "🔴 REAL SELL",
        use_container_width=True
    )


# ============================================================
# BUY
# ============================================================

if buy_button:

    if current_signal != "BUY":

        st.error(
            "Current SuperTrend signal BUY नहीं है."
        )

    else:

        result = place_real_order(

            "buy",

            order_size,

            current_entry,

            target1

        )


        if result.get("success"):

            st.success(
                "🟢 REAL BUY ORDER SENT"
            )

            st.json(result)

        else:

            st.error(
                "BUY ORDER FAILED"
            )

            st.json(result)


# ============================================================
# SELL
# ============================================================

if sell_button:

    if current_signal != "SELL":

        st.error(
            "Current SuperTrend signal SELL नहीं है."
        )

    else:

        result = place_real_order(

            "sell",

            order_size,

            current_entry,

            target1

        )


        if result.get("success"):

            st.success(
                "🔴 REAL SELL ORDER SENT"
            )

            st.json(result)

        else:

            st.error(
                "SELL ORDER FAILED"
            )

            st.json(result)
          # ============================================================
# PART 4/4
# REAL POSITION + ORDERS + PREVIOUS ENTRY
# ============================================================


# ============================================================
# PREVIOUS ENTRY
# ============================================================

st.divider()

st.header(
    "📜 PREVIOUS ENTRY"
)


if len(signal_rows) >= 2:

    previous = signal_rows.iloc[-2]

    previous_signal = str(
        previous["SIGNAL"]
    )

    previous_price = float(
        previous["close"]
    )

    previous_st = float(
        previous["SuperTrend"]
    )

    previous_time = show_time(
        previous["time"]
    )


    if previous_signal == "BUY":

        st.success(
            f"🟢 BUY | "
            f"ENTRY: {show_price(previous_price)} | "
            f"SUPERTREND: {show_price(previous_st)}"
        )

    else:

        st.error(
            f"🔴 SELL | "
            f"ENTRY: {show_price(previous_price)} | "
            f"SUPERTREND: {show_price(previous_st)}"
        )


    st.write(
        f"Signal Candle: "
        f"**{previous_time}**"
    )


else:

    st.info(
        "Previous entry available नहीं है."
    )


# ============================================================
# CURRENT TREND
# ============================================================

st.divider()

st.header(
    "📊 CURRENT SUPERTREND"
)


if not df.empty:

    last = df.iloc[-1]

    last_trend = int(
        last["Trend"]
    )

    last_close = float(
        last["close"]
    )

    last_st = float(
        last["SuperTrend"]
    )


    if last_trend == -1:

        st.success(
            "BUY / BULLISH 🟢"
        )

    else:

        st.error(
            "SELL / BEARISH 🔴"
        )


    c1, c2 = st.columns(2)


    with c1:

        st.metric(
            "CURRENT CLOSE",
            show_price(last_close)
        )


    with c2:

        st.metric(
            "SUPERTREND",
            show_price(last_st)
        )


# ============================================================
# REAL POSITION
# ============================================================

st.divider()

st.header(
    "📍 REAL MEMBER POSITION"
)


if st.session_state.get(
    "member_connected",
    False
):

    position_data = api.request(

        "GET",

        "/v2/positions",

        params={
            "product_id":
                PRODUCT_ID
        },

        private=True

    )


    if position_data.get("success"):

        result = position_data.get(
            "result",
            []
        )


        if isinstance(result, list):

            position = (
                result[0]
                if result
                else {}
            )

        elif isinstance(result, dict):

            position = result

        else:

            position = {}


        size = number(
            position.get("size"),
            0
        )

        entry_price = number(
            position.get("entry_price"),
            0
        )


        if size > 0:

            position_side = "LONG 🟢"

        elif size < 0:

            position_side = "SHORT 🔴"

        else:

            position_side = "FLAT"


        p1, p2, p3 = st.columns(3)


        with p1:

            st.metric(
                "POSITION",
                position_side
            )


        with p2:

            st.metric(
                "SIZE",
                abs(size)
            )


        with p3:

            st.metric(
                "ENTRY PRICE",
                show_price(
                    entry_price
                )
            )


    else:

        st.error(
            "Real position data unavailable."
        )


# ============================================================
# REAL OPEN ORDERS
# ============================================================

st.header(
    "📋 REAL OPEN ORDERS"
)


if st.session_state.get(
    "member_connected",
    False
):

    orders_data = api.request(

        "GET",

        "/v2/orders",

        params={
            "product_id":
                PRODUCT_ID,
            "state":
                "open"
        },

        private=True

    )


    if orders_data.get("success"):

        orders = orders_data.get(
            "result",
            []
        )


        if orders:

            rows = []


            for order in orders:

                rows.append({

                    "ID":
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
                            "-"
                        ),

                    "Size":
                        order.get(
                            "size",
                            "-"
                        ),

                    "Price":
                        order.get(
                            "limit_price",
                            "-"
                        ),

                    "TP":
                        order.get(
                            "bracket_take_profit_price",
                            "-"
                        ),

                    "SL":
                        order.get(
                            "bracket_stop_loss_price",
                            "-"
                        ),

                    "State":
                        order.get(
                            "state",
                            "-"
                        )

                })


            st.dataframe(

                pd.DataFrame(rows),

                use_container_width=True,

                hide_index=True

            )

        else:

            st.info(
                "No real open orders."
            )


    else:

        st.error(
            "Unable to fetch real orders."
        )


# ============================================================
# MEMBER INFO
# ============================================================

st.divider()

st.header(
    "👤 CONNECTED MEMBER"
)


if st.session_state.get(
    "member_connected",
    False
):

    st.success(
        "🟢 Connected"
    )

    st.write(
        "Member:",
        st.session_state.get(
            "member_name",
            "-"
        )
    )

else:

    st.info(
        "No member connected."
    )


# ============================================================
# REFRESH
# ============================================================

time.sleep(
    REFRESH_SECONDS
)

st.rerun()
