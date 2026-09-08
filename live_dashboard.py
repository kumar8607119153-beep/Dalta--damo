# ============================================================
# live_dashboard.py
# SANJAY RANA - DELTA EXCHANGE LIVE DASHBOARD
#
# SEPARATE FILE - does NOT modify delta_futures_bot.py
# READ ONLY - dashboard itself does not place/cancel orders
# ============================================================

import os
import time
import hmac
import hashlib
from datetime import datetime, timezone

import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go


# ============================================================
# CONFIG
# ============================================================

OWNER_NAME = "Sanjay Rana"
OWNER_MOBILE = "8930814389"

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://api.india.delta.exchange"
).rstrip("/")

API_KEY = os.getenv("DELTA_API_KEY", "")
API_SECRET = os.getenv("DELTA_API_SECRET", "")

SYMBOL = os.getenv("DELTA_SYMBOL", "BTCUSD")
PRODUCT_ID = int(os.getenv("DELTA_PRODUCT_ID", "27"))

TIMEFRAME = "5m"
CANDLE_SECONDS = 300

ATR_PERIOD = int(
    os.getenv("ST_ATR_PERIOD", "14")
)

SUPERTREND_MULTIPLIER = float(
    os.getenv("ST_MULTIPLIER", "3.0")
)

REFRESH_SECONDS = max(
    3,
    int(os.getenv("DASHBOARD_REFRESH", "5"))
)


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="Sanjay Rana Live Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 SANJAY RANA — LIVE TRADING DASHBOARD")

st.caption(
    "REAL Delta Exchange India data • "
    "Read-only dashboard • No dummy price"
)


# ============================================================
# HELPERS
# ============================================================

def number(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def integer(value, default=0):
    try:
        return int(float(value))
    except Exception:
        return default


def show_price(value):
    value = number(value)

    if value is None:
        return "DATA UNAVAILABLE"

    return f"{value:,.2f}"


def show_pnl(value):
    value = number(value)

    if value is None:
        return "DATA UNAVAILABLE"

    if value > 0:
        return f"+₹{value:,.2f}"

    if value < 0:
        return f"-₹{abs(value):,.2f}"

    return "₹0.00"


def show_time(value):
    if value is None:
        return "-"

    try:
        value = int(float(value))

        if value > 10_000_000_000:
            value //= 1000

        return datetime.fromtimestamp(
            value,
            tz=timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )

    except Exception:
        return str(value)


# ============================================================
# DELTA API READ ONLY CLIENT
# ============================================================

class DeltaAPI:

    def __init__(self):
        self.session = requests.Session()

    def signature(
        self,
        method,
        timestamp,
        path,
        query_string,
        body
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


    def request(
        self,
        method,
        path,
        params=None,
        private=False
    ):

        params = params or {}

        headers = {
            "Accept": "application/json",
            "User-Agent": "Sanjay-Rana-Live-Dashboard"
        }

        if private:

            if not API_KEY or not API_SECRET:
                return {
                    "success": False,
                    "error": "API credentials missing"
                }

            query_string = ""

            if params:
                query_string = "?" + "&".join(
                    f"{k}={params[k]}"
                    for k in params
                )

            timestamp = str(
                int(time.time())
            )

            signature = self.signature(
                method,
                timestamp,
                path,
                query_string,
                ""
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
                headers=headers,
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


    # --------------------------------------------------------
    # REAL MARKET DATA
    # --------------------------------------------------------

    def ticker(self):

        return self.request(
            "GET",
            f"/v2/tickers/{SYMBOL}"
        )


    def candles(self):

        end = int(time.time())

        start = (
            end
            - 200 * CANDLE_SECONDS
        )

        return self.request(
            "GET",
            "/v2/history/candles",
            {
                "symbol": SYMBOL,
                "resolution": TIMEFRAME,
                "start": start,
                "end": end
            }
        )


    # --------------------------------------------------------
    # REAL ACCOUNT DATA
    # --------------------------------------------------------

    def position(self):

        return self.request(
            "GET",
            "/v2/positions",
            {
                "product_id": PRODUCT_ID
            },
            private=True
        )


    def active_orders(self):

        return self.request(
            "GET",
            "/v2/orders",
            {
                "product_ids": str(PRODUCT_ID),
                "states": "open,pending"
            },
            private=True
        )


    def fills(self):

        return self.request(
            "GET",
            "/v2/fills",
            {
                "product_ids": str(PRODUCT_ID),
                "page_size": 100
            },
            private=True
        )


    def order_history(self):

        return self.request(
            "GET",
            "/v2/orders/history",
            {
                "product_ids": str(PRODUCT_ID),
                "page_size": 100
            },
            private=True
        )


api = DeltaAPI()


# ============================================================
# RESPONSE HELPERS
# ============================================================

def get_result(data):

    if not data:
        return None

    if not data.get("success"):
        return None

    return data.get("result")


def result_list(data):

    result = get_result(data)

    if isinstance(result, list):
        return result

    return []


def result_dict(data):

    result = get_result(data)

    if isinstance(result, dict):
        return result

    if isinstance(result, list) and result:
        return result[0]

    return {}


# ============================================================
# REAL CANDLES
# ============================================================

def make_dataframe(data):

    result = result_list(data)

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

    df = df.drop_duplicates(
        "time"
    )

    df = df.sort_values(
        "time"
    )

    df["datetime"] = pd.to_datetime(
        df["time"],
        unit="s",
        utc=True
    )

    return df


# ============================================================
# SUPERTREND
# SAME LOGIC AS YOUR BOT
# ATR = 14
# MULTIPLIER = 3.0
# ============================================================

def calculate_supertrend(df):

    if len(df) < ATR_PERIOD + 1:
        return pd.DataFrame()

    tr = []

    for i in range(len(df)):

        high = float(
            df.iloc[i]["high"]
        )

        low = float(
            df.iloc[i]["low"]
        )

        if i == 0:

            value = high - low

        else:

            previous_close = float(
                df.iloc[i - 1]["close"]
            )

            value = max(
                high - low,
                abs(high - previous_close),
                abs(low - previous_close)
            )

        tr.append(value)

    atr = [0.0] * len(df)

    atr[ATR_PERIOD - 1] = (
        sum(tr[:ATR_PERIOD])
        / ATR_PERIOD
    )

    for i in range(
        ATR_PERIOD,
        len(df)
    ):

        atr[i] = (
            (
                atr[i - 1]
                * (ATR_PERIOD - 1)
            )
            + tr[i]
        ) / ATR_PERIOD

    upper = [0.0] * len(df)
    lower = [0.0] * len(df)

    trend = [1] * len(df)

    supertrend = [0.0] * len(df)

    for i in range(len(df)):

        if i < ATR_PERIOD - 1:
            continue

        high = float(
            df.iloc[i]["high"]
        )

        low = float(
            df.iloc[i]["low"]
        )

        close = float(
            df.iloc[i]["close"]
        )

        hl2 = (
            high + low
        ) / 2.0

        basic_upper = (
            hl2
            + SUPERTREND_MULTIPLIER
            * atr[i]
        )

        basic_lower = (
            hl2
            - SUPERTREND_MULTIPLIER
            * atr[i]
        )

        if i == ATR_PERIOD - 1:

            upper[i] = basic_upper
            lower[i] = basic_lower
            trend[i] = 1
            supertrend[i] = lower[i]

        else:

            previous_close = float(
                df.iloc[i - 1]["close"]
            )

            previous_upper = upper[i - 1]
            previous_lower = lower[i - 1]

            upper[i] = (
                basic_upper
                if (
                    basic_upper < previous_upper
                    or previous_close > previous_upper
                )
                else previous_upper
            )

            lower[i] = (
                basic_lower
                if (
                    basic_lower > previous_lower
                    or previous_close < previous_lower
                )
                else previous_lower
            )

            previous_trend = trend[i - 1]

            if previous_trend == 1:

                if close < lower[i]:

                    trend[i] = -1
                    supertrend[i] = upper[i]

                else:

                    trend[i] = 1
                    supertrend[i] = lower[i]

            else:

                if close > upper[i]:

                    trend[i] = 1
                    supertrend[i] = lower[i]

                else:

                    trend[i] = -1
                    supertrend[i] = upper[i]

    result = df.copy()

    result["ATR"] = atr
    result["Trend"] = trend
    result["SuperTrend"] = supertrend

    return result


# ============================================================
# GET REAL DATA
# ============================================================

ticker_data = api.ticker()
candle_data = api.candles()

position_data = api.position()
active_order_data = api.active_orders()
fill_data = api.fills()
history_data = api.order_history()


ticker = result_dict(
    ticker_data
)

df = make_dataframe(
    candle_data
)

if not df.empty:
    df = calculate_supertrend(df)

position = result_dict(
    position_data
)

active_orders = result_list(
    active_order_data
)

fills = result_list(
    fill_data
)

history_orders = result_list(
    history_data
)


# ============================================================
# REAL PRICE
# ============================================================

real_price = None

for key in (
    "close",
    "mark_price",
    "spot_price",
    "last_price"
):

    if ticker.get(key) is not None:

        real_price = number(
            ticker.get(key)
        )

        if real_price is not None:
            break


# ============================================================
# OWNER
# ============================================================

st.header("👤 ADMIN / OWNER")

c1, c2, c3 = st.columns(3)

with c1:
    st.write("**Name**")
    st.write(OWNER_NAME)

with c2:
    st.write("**Mobile**")
    st.write(OWNER_MOBILE)

with c3:
    st.write("**Role**")
    st.write("Owner / Admin")


# ============================================================
# CONNECTION
# ============================================================

st.header("📡 EXCHANGE CONNECTION")

if ticker_data.get("success"):

    st.success(
        "🟢 Delta Exchange India — REAL DATA CONNECTED"
    )

else:

    st.error(
        "🔴 Delta Exchange — REAL DATA UNAVAILABLE"
    )

    st.warning(
        "Dummy price is NOT being displayed."
    )


# ============================================================
# REAL PRICE
# ============================================================

st.header("💰 LIVE BTCUSD")

st.metric(
    "REAL MARKET PRICE",
    show_price(real_price)
)


# ============================================================
# SUPERTREND
# ============================================================

st.header("🔄 SUPERTREND")

if not df.empty:

    last = df.iloc[-1]

    trend = integer(
        last["Trend"]
    )

    st_line = number(
        last["SuperTrend"]
    )

    atr = number(
        last["ATR"]
    )

    if trend == 1:
        direction = "BUY / BULLISH 🟢"
    elif trend == -1:
        direction = "SELL / BEARISH 🔴"
    else:
        direction = "UNKNOWN"

    a, b, c = st.columns(3)

    with a:
        st.metric(
            "DIRECTION",
            direction
        )

    with b:
        st.metric(
            "SUPERTREND",
            show_price(st_line)
        )

    with c:
        st.metric(
            "ATR",
            show_price(atr)
        )

else:

    st.error(
        "Real candle data unavailable."
    )


# ============================================================
# REAL CHART
# ============================================================

st.header(
    "📈 BTCUSD REAL CHART"
)

if not df.empty:

    chart = go.Figure()

    chart.add_trace(
        go.Candlestick(
            x=df["datetime"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="BTCUSD"
        )
    )

    chart.add_trace(
        go.Scatter(
            x=df["datetime"],
            y=df["SuperTrend"],
            mode="lines",
            name="SuperTrend"
        )
    )

    # --------------------------------------------------------
    # REAL ACTIVE ORDERS ONLY
    # --------------------------------------------------------

    for order in active_orders:

        limit_price = number(
            order.get("limit_price")
        )

        if limit_price is None:
            continue

        side = str(
            order.get("side", "")
        ).upper()

        reduce_only = str(
            order.get("reduce_only", "")
        ).lower() == "true"

        if reduce_only:
            label = f"TP / REDUCE {side}"
        else:
            label = f"ENTRY {side}"

        chart.add_hline(
            y=limit_price,
            annotation_text=label
        )

    # --------------------------------------------------------
    # REAL POSITION ENTRY
    # --------------------------------------------------------

    entry_price = number(
        position.get("entry_price")
    )

    size = number(
        position.get("size"),
        0
    )

    if (
        entry_price is not None
        and abs(size) > 0
    ):

        chart.add_hline(
            y=entry_price,
            annotation_text="REAL ENTRY"
        )

    chart.update_layout(
        height=650,
        xaxis_rangeslider_visible=False,
        template="plotly_dark"
    )

    st.plotly_chart(
        chart,
        use_container_width=True
    )

else:

    st.error(
        "REAL chart unavailable — "
        "Delta candles were not received."
    )


# ============================================================
# POSITION
# ============================================================

st.header("📍 REAL CURRENT POSITION")

position_size = number(
    position.get("size"),
    0
)

entry_price = number(
    position.get("entry_price")
)

if position_size > 0:
    position_side = "LONG"
elif position_size < 0:
    position_side = "SHORT"
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
        abs(position_size)
    )

with p3:
    st.metric(
        "ENTRY",
        show_price(entry_price)
    )


# ============================================================
# ACTIVE ORDERS
# ============================================================

st.header("📋 REAL ACTIVE ORDERS")

if active_orders:

    order_rows = []

    for order in active_orders:

        limit_price = number(
            order.get("limit_price")
        )

        reduce_only = str(
            order.get("reduce_only", "")
        ).lower() == "true"

        order_rows.append({
            "Order ID": order.get(
                "id",
                "-"
            ),
            "Side": str(
                order.get("side", "")
            ).upper(),
            "Type": order.get(
                "order_type",
                order.get("type", "-")
            ),
            "Price": (
                show_price(limit_price)
                if limit_price is not None
                else "MARKET / DATA UNAVAILABLE"
            ),
            "Quantity": order.get(
                "size",
                order.get("quantity", "-")
            ),
            "Reduce Only": (
                "YES"
                if reduce_only
                else "NO"
            ),
            "Status": order.get(
                "state",
                order.get("status", "-")
            )
        })

    st.dataframe(
        pd.DataFrame(order_rows),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No real active orders returned by Delta."
    )


# ============================================================
# THREE TARGETS
# ============================================================

st.header("🎯 REAL TARGET ORDERS")

targets = []

for order in active_orders:

    reduce_only = str(
        order.get("reduce_only", "")
    ).lower() == "true"

    limit_price = number(
        order.get("limit_price")
    )

    if reduce_only and limit_price is not None:

        targets.append(order)


if targets:

    target_rows = []

    for i, order in enumerate(
        targets[:3],
        start=1
    ):

        target_rows.append({
            "Target": f"TP{i}",
            "Side": str(
                order.get("side", "")
            ).upper(),
            "Price": show_price(
                order.get("limit_price")
            ),
            "Quantity": order.get(
                "size",
                "-"
            ),
            "Order ID": order.get(
                "id",
                "-"
            )
        })

    st.dataframe(
        pd.DataFrame(target_rows),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No real active reduce-only target "
        "orders are currently visible."
    )


#
============================================================
# BUY / SELL TRADE COUNT
# ============================================================

st.header("📊 BUY / SELL TRADE SUMMARY")

buy_count = 0
sell_count = 0

for fill in fills:

    side = str(
        fill.get("side", "")
    ).upper()

    if side == "BUY":
        buy_count += 1

    elif side == "SELL":
        sell_count += 1


s1, s2, s3 = st.columns(3)

with s1:
    st.metric(
        "BUY",
        buy_count
    )

with s2:
    st.metric(
        "SELL",
        sell_count
    )

with s3:
    st.metric(
        "TOTAL FILLS",
        len(fills)
    )


# ============================================================
# REAL TRADE HISTORY
# ============================================================

st.header("🧾 REAL TRADE HISTORY")

if fills:

    fill_rows = []

    for fill in fills:

        fill_price = (
            fill.get("price")
            or fill.get("fill_price")
        )

        quantity = (
            fill.get("size")
            or fill.get("quantity")
        )

        fill_rows.append({
            "Time": show_time(
                fill.get(
                    "created_at",
                    fill.get("timestamp")
                )
            ),
            "Side": str(
                fill.get("side", "")
            ).upper(),
            "Price": (
                show_price(fill_price)
                if fill_price is not None
                else "DATA UNAVAILABLE"
            ),
            "Quantity": quantity,
            "Order ID": fill.get(
                "order_id",
                "-"
            ),
            "Fee": fill.get(
                "commission",
                fill.get("fee", "-")
            ),
            "Realized P&L": (
                show_pnl(
                    fill.get(
                        "realized_pnl"
                    )
                )
                if fill.get(
                    "realized_pnl"
                ) is not None
                else "DATA UNAVAILABLE"
            )
        })

    st.dataframe(
        pd.DataFrame(fill_rows),
        use_container_width=True,
        hide_index=True
    )

else:

    st.info(
        "No real fills returned by Delta."
    )


# ============================================================
# PNL
# ============================================================

st.header("💵 REAL P&L")

realized_pnl = 0.0
has_realized_pnl = False

for fill in fills:

    pnl = number(
        fill.get("realized_pnl")
    )

    if pnl is not None:

        realized_pnl += pnl
        has_realized_pnl = True


unrealized_pnl = number(
    position.get("unrealized_pnl")
)

x1, x2 = st.columns(2)

with x1:

    if has_realized_pnl:

        st.metric(
            "REALIZED P&L",
            show_pnl(realized_pnl)
        )

    else:

        st.metric(
            "REALIZED P&L",
            "DATA UNAVAILABLE"
        )

with x2:

    if unrealized_pnl is not None:

        st.metric(
            "UNREALIZED P&L",
            show_pnl(unrealized_pnl)
        )

    else:

        st.metric(
            "UNREALIZED P&L",
            "DATA UNAVAILABLE"
        )


# ============================================================
# EXCHANGE / API
# ============================================================

st.header("🔑 API / EXCHANGE LIST")

api_status = (
    "CONNECTED"
    if ticker_data.get("success")
    else "UNAVAILABLE"
)

st.write(
    f"**Exchange:** Delta Exchange India"
)

st.write(
    f"**API Endpoint:** {BASE_URL}"
)

st.write(
    f"**Status:** {api_status}"
)

st.caption(
    "API Secret और API Key dashboard पर नहीं दिखाई जाती।"
)


# ============================================================
# MEMBER LIST
# ============================================================

st.header("👥 MEMBER LIST")

# Important:
# Delta Exchange trading API does not automatically provide
# a normal "members" management endpoint.
#
# Therefore this dashboard does NOT invent members.
# Owner is shown as the actual dashboard administrator.

members = [
    {
        "Name": OWNER_NAME,
        "Mobile": OWNER_MOBILE,
        "Role": "Owner / Admin",
        "Status": "Active"
    }
]

st.dataframe(
    pd.DataFrame(members),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Additional real members तभी दिखेंगे जब उनके लिए "
    "अलग member data source/API उपलब्ध हो।"
)


# ============================================================
# DATA SAFETY
# ============================================================

st.divider()

st.success(
    "REAL-DATA MODE: Dashboard dummy price, "
    "dummy order, dummy target या dummy P&L नहीं बनाता।"
)

st.caption(
    f"Auto refresh: {REFRESH_SECONDS} seconds"
)


# ============================================================
# AUTO REFRESH
# ============================================================

time.sleep(0.2)

st.markdown(
    f"""
    <meta http-equiv="refresh"
          content="{REFRESH_SECONDS}">
    """,
    unsafe_allow_html=True
  )
