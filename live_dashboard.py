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

owner_col1, owner_col2 = st.columns(2)

with owner_col1:

    owner_api_key_input = st.text_input(
        "🔑 Owner API Key",
        type="password",
        key="owner_api_key_input"
    )

with owner_col2:

    owner_api_secret_input = st.text_input(
        "🔐 Owner API Secret",
        type="password",
        key="owner_api_secret_input"
    )


if st.button(
    "🔗 TEST OWNER API",
    key="test_owner_api_button"
):

    if (
        not owner_api_key_input
        or not owner_api_secret_input
    ):

        st.error(
            "❌ Owner API Key और API Secret दोनों डालें।"
        )

    else:

        try:

            owner_client = DeltaAPI(
                owner_api_key_input,
                owner_api_secret_input
            )

            owner_result = owner_client.position()

            if owner_result.get("success"):

                st.success(
                    "🟢 OWNER API CONNECTED"
                )

                st.session_state[
                    "owner_api_connected"
                ] = True

                st.session_state[
                    "owner_api_key"
                ] = owner_api_key_input

                st.session_state[
                    "owner_api_secret"
                ] = owner_api_secret_input

            else:

                st.error(
                    "🔴 OWNER API CONNECTION FAILED"
                )

                st.session_state[
                    "owner_api_connected"
                ] = False

                st.write(
                    owner_result.get(
                        "error"
                    )
                )

        except Exception as e:

            st.error(
                f"❌ Owner API Error: {e}"
            )


# ============================================================
# OWNER STATUS
# ============================================================

if st.session_state.get(
    "owner_api_connected",
    False
):

    st.success(
        "👑 Owner Status: CONNECTED"
    )

else:

    st.warning(
        "👑 Owner Status: NOT CONNECTED"
    )


# ============================================================
# MEMBER SYSTEM
# ============================================================

st.divider()

st.header(
    "👥 MEMBER API CONTROL"
)

st.caption(
    "जितने चाहें Members जोड़ सकते हैं। "
    "हर Member की अलग API होगी।"
)


# ============================================================
# MEMBER STORAGE
# ============================================================

if "members" not in st.session_state:

    st.session_state["members"] = []


# ============================================================
# ADD MEMBER
# ============================================================

if st.button(
    "➕ ADD MEMBER",
    key="add_member_button"
):

    member_number = (
        len(
            st.session_state["members"]
        ) + 1
    )

    st.session_state[
        "members"
    ].append({

        "name":
            f"Member {member_number}",

        "api_key":
            "",

        "api_secret":
            "",

        "connected":
            False,

        "active":
            False
    })


# ============================================================
# MEMBER COUNT
# ============================================================

st.info(
    f"👥 Total Members: "
    f"{len(st.session_state['members'])}"
)


# ============================================================
# MEMBER CARDS
# ============================================================

for index, member in enumerate(
    st.session_state["members"]
):

    st.markdown("---")

    st.subheader(
        f"👤 {member['name']}"
    )


    # --------------------------------------------------------
    # MEMBER NAME
    # --------------------------------------------------------

    member["name"] = st.text_input(

        "Member Name",

        value=member["name"],

        key=f"member_name_{index}"
    )


    # --------------------------------------------------------
    # MEMBER API KEY
    # --------------------------------------------------------

    api_col1, api_col2 = st.columns(2)


    with api_col1:

        member["api_key"] = st.text_input(

            "🔑 Member API Key",

            value=member["api_key"],

            type="password",

            key=f"member_api_key_{index}"
        )


    with api_col2:

        member["api_secret"] = st.text_input(

            "🔐 Member API Secret",

            value=member["api_secret"],

            type="password",

            key=f"member_api_secret_{index}"
        )


    # --------------------------------------------------------
    # TEST MEMBER API
    # --------------------------------------------------------

    if st.button(

        "🔗 TEST MEMBER API",

        key=f"test_member_api_{index}"
    ):

        if not member["api_key"]:

            member["connected"] = False

            st.error(
                "❌ Member API Key खाली है।"
            )

        elif not member["api_secret"]:

            member["connected"] = False

            st.error(
                "❌ Member API Secret खाली है।"
            )

        else:

            try:

                member_client = DeltaAPI(

                    member["api_key"],

                    member["api_secret"]
                )


                result = member_client.position()


                if result.get("success"):

                    member["connected"] = True

                    st.success(
                        "🟢 MEMBER API CONNECTED"
                    )

                else:

                    member["connected"] = False

                    st.error(
                        "🔴 MEMBER API CONNECTION FAILED"
                    )

                    st.write(
                        result.get(
                            "error"
                        )
                    )


            except Exception as e:

                member["connected"] = False

                st.error(
                    f"❌ Member API Error: {e}"
                )


    # --------------------------------------------------------
    # MEMBER CONNECTION STATUS
    # --------------------------------------------------------

    if member["connected"]:

        st.success(
            "🟢 API CONNECTED"
        )

    else:

        st.warning(
            "🟡 API NOT CONNECTED"
        )


    # --------------------------------------------------------
    # MEMBER ACTIVE CONTROL
    # --------------------------------------------------------

    member_active = st.toggle(

        "🎛️ MEMBER ACTIVE / REAL TRADING",

        value=member["active"],

        key=f"member_active_{index}"
    )


    if member_active:

        if member["connected"]:

            member["active"] = True

            st.error(
                f"🔴 {member['name']} "
                "REAL TRADING ACTIVE"
            )

        else:

            member["active"] = False

            st.warning(
                "⚠️ पहले API CONNECT करें। "
                "फिर Member Active करें।"
            )

    else:

        member["active"] = False

        st.success(
            f"🟢 {member['name']} — TRADING OFF"
        )


    # --------------------------------------------------------
    # REMOVE MEMBER
    # --------------------------------------------------------

    if st.button(

        "🗑️ REMOVE MEMBER",

        key=f"remove_member_{index}"
    ):

        st.session_state[
            "members"
        ].pop(index)

        st.rerun()


# ============================================================
# ACTIVE MEMBER SUMMARY
# ============================================================

st.divider()

st.subheader(
    "📊 MEMBER SUMMARY"
)


if st.session_state["members"]:

    summary = []

    for member in st.session_state["members"]:

        summary.append({

            "Member":
                member["name"],

            "API":
                (
                    "CONNECTED"
                    if member["connected"]
                    else "NOT CONNECTED"
                ),

            "Trading":
                (
                    "ACTIVE"
                    if member["active"]
                    else "OFF"
                )
        })


    st.dataframe(

        pd.DataFrame(summary),

        use_container_width=True,

        hide_index=True
    )

else:

    st.info(
        "अभी कोई Member नहीं जोड़ा गया है।"
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
# SESSION STATE
# ============================================================

if "remote_enabled" not in st.session_state:
    st.session_state["remote_enabled"] = False

if "last_order_signal" not in st.session_state:
    st.session_state["last_order_signal"] = ""

if "pending_order_id" not in st.session_state:
    st.session_state["pending_order_id"] = None

if "pending_order_side" not in st.session_state:
    st.session_state["pending_order_side"] = ""

if "pending_order_time" not in st.session_state:
    st.session_state["pending_order_time"] = 0


# ============================================================
# REMOTE ON / OFF
# ============================================================

remote_enabled = st.toggle(
    "REAL TRADING REMOTE CONTROL",
    value=st.session_state["remote_enabled"]
)

st.session_state["remote_enabled"] = remote_enabled


if remote_enabled:
    st.error("🔴 REAL ORDER CONTROL: ON")
else:
    st.success("🟢 REAL ORDER CONTROL: OFF")


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


            if st.button(
                "PLACE REAL LIMIT ORDER",
                type="primary"
            ):

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
                        f"LIMIT ORDER SENT"
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
# PART 1/5
# SANJAY RANA — REAL TRADING DASHBOARD
# OWNER API + MEMBER SYSTEM + BASIC CONFIG
# ============================================================

import os
import time
import hmac
import hashlib
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd
import streamlit as st


# ============================================================
# BASIC SETTINGS
# ============================================================

OWNER_NAME = "Sanjay Rana"

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://api.india.delta.exchange"
).rstrip("/")

SYMBOL = os.getenv(
    "DELTA_SYMBOL",
    "BTCUSD"
)

PRODUCT_ID = int(
    os.getenv(
        "DELTA_PRODUCT_ID",
        "27"
    )
)

TIMEFRAME = "5m"

CANDLE_SECONDS = 300

ATR_PERIOD = 10

SUPERTREND_MULTIPLIER = 3.0

REFRESH_SECONDS = max(
    3,
    int(
        os.getenv(
            "DASHBOARD_REFRESH",
            "5"
        )
    )
)


# ============================================================
# ORDER SETTINGS
# ============================================================

DEFAULT_ORDER_SIZE = int(
    os.getenv(
        "ORDER_SIZE",
        "1"
    )
)

DEFAULT_BUY_OFFSET = float(
    os.getenv(
        "BUY_OFFSET",
        "-50"
    )
)

DEFAULT_SELL_OFFSET = float(
    os.getenv(
        "SELL_OFFSET",
        "50"
    )
)

DEFAULT_LIMIT_TIMEOUT = int(
    os.getenv(
        "LIMIT_TIMEOUT",
        "60"
    )
)


# ============================================================
# TARGET SETTINGS
# ============================================================

TARGET_1 = float(
    os.getenv(
        "TARGET_1",
        "300"
    )
)

TARGET_2 = float(
    os.getenv(
        "TARGET_2",
        "600"
    )
)

TARGET_3 = float(
    os.getenv(
        "TARGET_3",
        "900"
    )
)


# ============================================================
# OWNER API
#
# OWNER API environment variables se li jayegi.
# Code ke andar secret hard-code nahi karna.
# ============================================================

OWNER_API_KEY = os.getenv(
    "DELTA_API_KEY",
    ""
)

OWNER_API_SECRET = os.getenv(
    "DELTA_API_SECRET",
    "")


# ============================================================
# INDIAN TIME
# ============================================================

IST = timezone(
    timedelta(
        hours=5,
        minutes=30
    )
)


def indian_time(timestamp=None):

    try:

        if timestamp is None:

            dt = datetime.now(
                timezone.utc
            )

        else:

            ts = int(
                float(timestamp)
            )

            if ts > 10_000_000_000:
                ts = ts // 1000

            dt = datetime.fromtimestamp(
                ts,
                tz=timezone.utc
            )

        return dt.astimezone(
            IST
        ).strftime(
            "%Y-%m-%d %H:%M:%S IST"
        )

    except Exception:

        return "-"


# ============================================================
# NUMBER HELPERS
# ============================================================

def number(
    value,
    default=None
):

    try:

        if value is None:
            return default

        return float(value)

    except Exception:

        return default


def integer(
    value,
    default=0
):

    try:

        return int(
            float(value)
        )

    except Exception:

        return default


def show_price(value):

    value = number(
        value
    )

    if value is None:
        return "DATA UNAVAILABLE"

    return f"{value:,.2f}"


def show_pnl(value):

    value = number(
        value,
        0
    )

    if value > 0:

        return f"+₹{value:,.2f}"

    if value < 0:

        return f"-₹{abs(value):,.2f}"

    return "₹0.00"


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Sanjay Rana Real Trading",
    page_icon="📈",
    layout="wide"
)


st.title(
    "📈 SANJAY RANA — REAL TRADING DASHBOARD"
)


st.caption(
    "Delta Exchange India | "
    "5 Minute | ATR 10 | Multiplier 3.0 | HL2"
)


# ============================================================
# DELTA API CLIENT
# ============================================================

class DeltaAPI:

    def __init__(
        self,
        api_key="",
        api_secret=""
    ):

        self.api_key = api_key

        self.api_secret = api_secret

        self.session = requests.Session()


    # ========================================================
    # SIGNATURE
    # ========================================================

    def signature(
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

            self.api_secret.encode(
                "utf-8"
            ),

            message.encode(
                "utf-8"
            ),

            hashlib.sha256

        ).hexdigest()


    # ========================================================
    # REQUEST
    # ========================================================

    def request(
        self,
        method,
        path,
        params=None,
        body="",
        private=False
    ):

        params = params or {}

        headers = {

            "Accept":
                "application/json",

            "User-Agent":
                "Sanjay-Rana-Real-Trading"
        }


        if private:

            if (
                not self.api_key
                or not self.api_secret
            ):

                return {

                    "success": False,

                    "error":
                        "API credentials missing"
                }


            query_string = ""

            if params:

                query_parts = []

                for key, value in params.items():

                    query_parts.append(
                        f"{key}={value}"
                    )

                query_string = (
                    "?"
                    + "&".join(
                        query_parts
                    )
                )


            timestamp = str(
                int(
                    time.time()
                )
            )


            signature = self.signature(

                method,

                timestamp,

                path,

                query_string,

                body
            )


            headers.update({

                "api-key":
                    self.api_key,

                "timestamp":
                    timestamp,

                "signature":
                    signature,

                "Content-Type":
                    "application/json"
            })


        try:

            response = self.session.request(

                method.upper(),

                BASE_URL + path,

                params=params,

                data=body
                if body
                else None,

                headers=headers,

                timeout=15
            )


            try:

                data = response.json()

            except Exception:

                return {

                    "success": False,

                    "error":
                        "Invalid API response"
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


    # ========================================================
    # PUBLIC TICKER
    # ========================================================

    def ticker(self):

        return self.request(

            "GET",

            f"/v2/tickers/{SYMBOL}"
        )


    # ========================================================
    # CANDLES
    # ========================================================

    def candles(self):

        end = int(
            time.time()
        )

        start = (
            end
            - (
                500
                * CANDLE_SECONDS
            )
        )


        return self.request(

            "GET",

            "/v2/history/candles",

            {

                "symbol":
                    SYMBOL,

                "resolution":
                    TIMEFRAME,

                "start":
                    start,

                "end":
                    end
            }
        )


    # ========================================================
    # POSITION
    # ========================================================

    def position(self):

        return self.request(

            "GET",

            "/v2/positions",

            {
                "product_id":
                    PRODUCT_ID
            },

            private=True
        )


    # ========================================================
    # OPEN ORDERS
    # ========================================================

    def open_orders(self):

        return self.request(

            "GET",

            "/v2/orders",

            {

                "product_ids":
                    str(PRODUCT_ID),

                "states":
                    "open,pending"
            },

            private=True
        )


    # ========================================================
    # FILLS
    # ========================================================

    def fills(self):

        return self.request(

            "GET",

            "/v2/fills",

            {

                "product_ids":
                    str(PRODUCT_ID),

                "page_size":
                    100
            },

            private=True
        )


    # ========================================================
    # ORDER HISTORY
    # ========================================================

    def order_history(self):

        return self.request(

            "GET",

            "/v2/orders/history",

            {

                "product_ids":
                    str(PRODUCT_ID),

                "page_size":
                    100
            },

            private=True
        )


# ============================================================
# OWNER API CLIENT
# ============================================================

owner_api = DeltaAPI(

    OWNER_API_KEY,

    OWNER_API_SECRET
)


# ============================================================
# SESSION STATE
#
# Unlimited members ke liye list.
# 5 ki koi fixed limit nahi.
# ============================================================

if "members" not in st.session_state:

    st.session_state["members"] = []


if "remote_trading" not in st.session_state:

    st.session_state["remote_trading"] = False


if "last_signal_time" not in st.session_state:

    st.session_state["last_signal_time"] = ""


if "last_signal_direction" not in st.session_state:

    st.session_state[
        "last_signal_direction"
    ] = ""


# ============================================================
# OWNER CONNECTION
# ============================================================

st.divider()

st.header(
    "👑 OWNER / ADMIN CONNECTION"
)


if OWNER_API_KEY and OWNER_API_SECRET:

    st.success(
        "🟢 Owner API credentials available"
    )

else:

    st.warning(
        "🟡 Owner API अभी configure नहीं है."
    )


# ============================================================
# OWNER API TEST
# ============================================================

if st.button(
    "🔗 TEST OWNER API",
    key="owner_api_test"
):

    if (
        not OWNER_API_KEY
        or not OWNER_API_SECRET
    ):

        st.error(
            "Owner API Key और API Secret missing हैं."
        )

    else:

        owner_test = owner_api.ticker()


        if owner_test.get(
            "success"
        ):

            st.success(
                "🟢 OWNER API CONNECTED"
            )

        else:

            st.error(
                "🔴 OWNER API CONNECTION FAILED"
            )

            st.write(
                owner_test.get(
                    "error"
                )
            )


# ============================================================
# GLOBAL REMOTE CONTROL
# ============================================================

st.divider()

st.header(
    "🎛️ MASTER REMOTE CONTROL"
)


master_remote = st.toggle(

    "REAL TRADING MASTER ON/OFF",

    value=st.session_state[
        "remote_trading"
    ],

    key="master_remote_control"
)


st.session_state[
    "remote_trading"
] = master_remote


if master_remote:

    st.error(
        "🔴 MASTER REAL TRADING = ON"
    )

else:

    st.success(
        "🟢 MASTER REAL TRADING = OFF"
    )


# ============================================================
# BASIC SETTINGS DISPLAY
# ============================================================

st.divider()

st.header(
    "⚙️ TRADING SETTINGS"
)


s1, s2, s3, s4 = st.columns(4)


with s1:

    st.metric(
        "SYMBOL",
        SYMBOL
    )


with s2:

    st.metric(
        "TIMEFRAME",
        TIMEFRAME
    )


with s3:

    st.metric(
        "ATR",
        str(ATR_PERIOD)
    )


with s4:

    st.metric(
        "MULTIPLIER",
        str(SUPERTREND_MULTIPLIER)
    )


# ============================================================
# TARGET SETTINGS
# ============================================================

st.subheader(
    "🎯 DEFAULT TARGETS"
)


tc1, tc2, tc3 = st.columns(3)


with tc1:

    st.metric(
        "TARGET 1",
        f"{TARGET_1:.0f} POINTS"
    )


with tc2:

    st.metric(
        "TARGET 2",
        f"{TARGET_2:.0f} POINTS"
    )


with tc3:

    st.metric(
        "TARGET 3",
        f"{TARGET_3:.0f} POINTS"
    )


# ============================================================
# CURRENT SERVER TIME
# ============================================================

st.divider()

st.caption(
    "Dashboard Time: "
    + indian_time()
)

# ============================================================
# END OF PART 1
# PART 2 = CANDLE + SUPERTREND ENGINE
# ============================================================
time.sleep(REFRESH_SECONDS)
st.rerun()
