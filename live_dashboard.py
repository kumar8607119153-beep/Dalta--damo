# ============================================================
# live_dashboard.py
# SANJAY RANA - DELTA EXCHANGE LIVE DASHBOARD
# ============================================================

import os
import time
import hmac
import hashlib
from datetime import datetime, timezone

import requests
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
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

# ============================================================
# CONFIG (ATR 10, Multiplier 3.0, HL2 Engine)
# ============================================================

ATR_PERIOD = 10
SUPERTREND_MULTIPLIER = 3.0


REFRESH_SECONDS = max(
    3,
    int(os.getenv("DASHBOARD_REFRESH", "5"))
)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Sanjay Rana Live Dashboard",
    page_icon="📊",
    layout="wide"
)

# Admin Header Banner
st.markdown(f"""
    <div style="background-color: #161b22; padding: 12px 20px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <div>
            <span style="color: #8b949e; font-size: 13px;">Admin Owner:</span><br>
            <span style="color: #ffffff; font-size: 16px; font-weight: bold;">{OWNER_NAME}</span>
        </div>
        <div>
            <span style="color: #8b949e; font-size: 13px;">Contact Number:</span><br>
            <span style="color: #00ffcc; font-size: 16px; font-weight: bold;">{OWNER_MOBILE}</span>
        </div>
        <div>
            <span style="color: #8b949e; font-size: 13px;">PIN Number:</span><br>
            <span style="color: #00ffcc; font-size: 16px; font-weight: bold;">0000</span>
        </div>
    </div>
""", unsafe_allow_html=True)

st.title("📊 SANJAY RANA — LIVE TRADING DASHBOARD")
st.caption("REAL Delta Exchange India data • Real-time SuperTrend Engine • No dummy price")


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
        return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(value)


# ============================================================
# DELTA API READ ONLY CLIENT
# ============================================================

class DeltaAPI:
    def __init__(self):
        self.session = requests.Session()

    def signature(self, method, timestamp, path, query_string, body):
        message = method.upper() + timestamp + path + query_string + body
        return hmac.new(
            API_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def request(self, method, path, params=None, private=False):
        params = params or {}
        headers = {
            "Accept": "application/json",
            "User-Agent": "Sanjay-Rana-Live-Dashboard"
        }

        if private:
            if not API_KEY or not API_SECRET:
                return {"success": False, "error": "API credentials missing"}
            query_string = ""
            if params:
                query_string = "?" + "&".join(f"{k}={params[k]}" for k in params)
            timestamp = str(int(time.time()))
            signature = self.signature(method, timestamp, path, query_string, "")
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
                return {"success": False, "error": "Invalid API response"}

            if not response.ok:
                return {"success": False, "error": data}
            return data
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def ticker(self):
        return self.request("GET", f"/v2/tickers/{SYMBOL}")

    def candles(self):
        end = int(time.time())
        start = end - 200 * CANDLE_SECONDS
        return self.request("GET", "/v2/history/candles", {
            "symbol": SYMBOL,
            "resolution": TIMEFRAME,
            "start": start,
            "end": end
        })

    def position(self):
        return self.request("GET", "/v2/positions", {"product_id": PRODUCT_ID}, private=True)

    def active_orders(self):
        return self.request("GET", "/v2/orders", {"product_ids": str(PRODUCT_ID), "states": "open,pending"}, private=True)

    def fills(self):
        return self.request("GET", "/v2/fills", {"product_ids": str(PRODUCT_ID), "page_size": 100}, private=True)

    def order_history(self):
        return self.request("GET", "/v2/orders/history", {"product_ids": str(PRODUCT_ID), "page_size": 100}, private=True)


api = DeltaAPI()


def get_result(data):
    if not data or not data.get("success"):
        return None
    return data.get("result")


def result_list(data):
    result = get_result(data)
    return result if isinstance(result, list) else []


def result_dict(data):
    result = get_result(data)
    if isinstance(result, dict):
        return result
    if isinstance(result, list) and result:
        return result[0]
    return {}


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
                "volume": number(candle.get("volume"), 0)
            })
        except Exception:
            continue
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates("time").sort_values("time")
    df["datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df


def calculate_supertrend(df):
    if len(df) < ATR_PERIOD + 1:
        return pd.DataFrame()

    tr = []
    for i in range(len(df)):
        high = float(df.iloc[i]["high"])
        low = float(df.iloc[i]["low"])
        if i == 0:
            value = high - low
        else:
            previous_close = float(df.iloc[i - 1]["close"])
            value = max(high - low, abs(high - previous_close), abs(low - previous_close))
        tr.append(value)

    atr = [0.0] * len(df)
    atr[ATR_PERIOD - 1] = sum(tr[:ATR_PERIOD]) / ATR_PERIOD
    for i in range(ATR_PERIOD, len(df)):
        atr[i] = ((atr[i - 1] * (ATR_PERIOD - 1)) + tr[i]) / ATR_PERIOD

    upper = [0.0] * len(df)
    lower = [0.0] * len(df)
    trend = [1] * len(df)
    supertrend = [0.0] * len(df)

    for i in range(len(df)):
        if i < ATR_PERIOD - 1:
            continue
        high = float(df.iloc[i]["high"])
        low = float(df.iloc[i]["low"])
        close = float(df.iloc[i]["close"])
        hl2 = (high + low) / 2.0
        basic_upper = hl2 + SUPERTREND_MULTIPLIER * atr[i]
        basic_lower = hl2 - SUPERTREND_MULTIPLIER * atr[i]

        if i == ATR_PERIOD - 1:
            upper[i] = basic_upper
            lower[i] = basic_lower
            trend[i] = 1
            supertrend[i] = lower[i]
        else:
            previous_close = float(df.iloc[i - 1]["close"])
            previous_upper = upper[i - 1]
            previous_lower = lower[i - 1]

            upper[i] = basic_upper if (basic_upper < previous_upper or previous_close > previous_upper) else previous_upper
            lower[i] = basic_lower if (basic_lower > previous_lower or previous_close < previous_lower) else previous_lower

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


# Fetch Data
ticker_data = api.ticker()
candle_data = api.candles()
position_data = api.position()
active_order_data = api.active_orders()
fill_data = api.fills()
history_data = api.order_history()

ticker = result_dict(ticker_data)
df = make_dataframe(candle_data)
if not df.empty:
    df = calculate_supertrend(df)

position = result_dict(position_data)
active_orders = result_list(active_order_data)
fills = result_list(fill_data)
history_orders = result_list(history_data)

real_price = None
for key in ("close", "mark_price", "spot_price", "last_price"):
    if ticker.get(key) is not None:
        real_price = number(ticker.get(key))
        if real_price is not None:
            break


# ============================================================
# DASHBOARD UI SECTIONS
# ============================================================

st.header("📡 EXCHANGE CONNECTION")
if ticker_data.get("success"):
    st.success("🟢 Delta Exchange India — REAL DATA CONNECTED")
else:
    st.error("🔴 Delta Exchange — REAL DATA UNAVAILABLE")

st.header("💰 LIVE BTCUSD PRICE")
st.metric("REAL MARKET PRICE", show_price(real_price))


# Supertrend calculation check
direction = "UNKNOWN"
st_line = 0.0
atr_val = 0.0
entry_val = real_price if real_price else 0.0

if not df.empty:
    last = df.iloc[-1]
    trend = integer(last["Trend"])
    st_line = number(last["SuperTrend"])
    atr_val = number(last["ATR"])
    if trend == 1:
        direction = "BUY / BULLISH 🟢"
    elif trend == -1:
        direction = "SELL / BEARISH 🔴"

st.header("🔄 SUPERTREND & TARGETS ENGINE")
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("DIRECTION", direction)
with c2:
    st.metric("SUPERTREND", show_price(st_line))
with c3:
    st.metric("ATR (10)", show_price(atr_val))

# ============================================================
# LOCKED & STABLE TARGETS ENGINE (Session State Lock)
# ============================================================

if "locked_entry" not in st.session_state or direction != st.session_state.get("last_direction"):
    st.session_state["locked_entry"] = float(last["SuperTrend"])
    base_price = st.session_state["locked_entry"]
    
    
    
    if "BULLISH" in direction:
        st.session_state["locked_t1"] = base_price + 300
        st.session_state["locked_t2"] = base_price + 600
        st.session_state["locked_t3"] = base_price + 900
    elif "BEARISH" in direction:
        st.session_state["locked_t1"] = base_price - 300
        st.session_state["locked_t2"] = base_price - 600
        st.session_state["locked_t3"] = base_price - 900
    else:
        st.session_state["locked_t1"] = base_price + 300
        st.session_state["locked_t2"] = base_price + 600
        st.session_state["locked_t3"] = base_price + 900
        
    st.session_state["last_direction"] = direction

entry_display = st.session_state["locked_entry"]
        
t1 = st.session_state["locked_t1"]
t2 = st.session_state["locked_t2"]
t3 = st.session_state["locked_t3"]
    
tc1, tc2, tc3, tc4 = st.columns(4)
with tc1:
    st.success(f"📥 **Entry:** {show_price(entry_display)}")
with tc2:
    st.warning(f"🎯 **Target 1:** {show_price(t1)}")
with tc3:
    st.warning(f"🎯 **Target 2:** {show_price(t2)}")
with tc4:
    st.warning(f"🎯 **Target 3:** {show_price(t3)}")


# ============================================================
# REAL TRADINGVIEW WIDGET + PLOTLY CHART
# ============================================================

st.header("📈 OFFICIAL TRADINGVIEW LIVE CHART (BTCUSDT)")
tradingview_widget = """
<div class="tradingview-widget-container" style="height:500px;width:100%">
  <div id="tradingview_advanced_chart" style="height:100%;width:100%"></div>
  <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
  <script type="text/javascript">
  new TradingView.widget(
  {
    "width": "100%",
    "height": 500,
    "symbol": "BINANCE:BTCUSDT",
    "interval": "5",
    "timezone": "Asia/Kolkata",
    "theme": "dark",
    "style": "1",
    "locale": "en",
    "toolbar_bg": "#f1f3f6",
    "enable_publishing": false,
    "hide_side_toolbar": false,
    "allow_symbol_change": true,
    "details": true,
    "studies": ["SuperTrend@tv-basicstudies"],
    "container_id": "tradingview_advanced_chart"
  });
  </script>
</div>
"""
components.html(tradingview_widget, height=520)


# ============================================================
# POSITIONS & ACTIVE ORDERS
# ============================================================

st.header("📍 REAL CURRENT POSITION")
position_size = number(position.get("size"), 0)
entry_price = number(position.get("entry_price"))

if position_size > 0:
    position_side = "LONG"
elif position_size < 0:
    position_side = "SHORT"
else:
    position_side = "FLAT"

p1, p2, p3 = st.columns(3)
with p1:
    st.metric("POSITION", position_side)
with p2:
    st.metric("SIZE", abs(position_size))
with p3:
    st.metric("ENTRY", show_price(entry_price))

st.header("📋 REAL ACTIVE ORDERS & TARGETS")
if active_orders:
    order_rows = []
    for order in active_orders:
        limit_price = number(order.get("limit_price"))
        reduce_only = str(order.get("reduce_only", "")).lower() == "true"
        order_rows.append({
            "Order ID": order.get("id", "-"),
            "Side": str(order.get("side", "")).upper(),
            "Type": order.get("order_type", order.get("type", "-")),
            "Price": show_price(limit_price) if limit_price is not None else "MARKET",
            "Quantity": order.get("size", "-"),
            "Reduce Only": "YES" if reduce_only else "NO",
            "Status": order.get("state", "-")
        })
    st.dataframe(pd.DataFrame(order_rows), use_container_width=True, hide_index=True)
else:
    st.info("No active orders found on Delta Exchange.")


# ============================================================
# TRADE HISTORY & PNL
# ============================================================

st.header("🧾 REAL TRADE HISTORY & P&L")
realized_pnl = 0.0
for fill in fills:
    pnl = number(fill.get("realized_pnl"))
    if pnl is not None:
        realized_pnl += pnl

unrealized_pnl = number(position.get("unrealized_pnl"))

x1, x2 = st.columns(2)
with x1:
    st.metric("REALIZED P&L", show_pnl(realized_pnl))
with x2:
    st.metric("UNREALIZED P&L", show_pnl(unrealized_pnl) if unrealized_pnl is not None else "₹0.00")

if fills:
    fill_rows = []
    for fill in fills:
        fill_rows.append({
            "Time": show_time(fill.get("created_at", fill.get("timestamp"))),
            "Side": str(fill.get("side", "")).upper(),
            "Price": show_price(fill.get("price") or fill.get("fill_price")),
            "Quantity": fill.get("size") or fill.get("quantity"),
            "Realized P&L": show_pnl(fill.get("realized_pnl"))
        })
    st.dataframe(pd.DataFrame(fill_rows), use_container_width=True, hide_index=True)
else:
    st.info("No trade fills available.")


# ============================================================
# MEMBER LIST & STABLE REFRESH
# ============================================================

st.header("👥 MEMBER LIST")
members = [{"Name": OWNER_NAME, "Mobile": OWNER_MOBILE, "Role": "Owner / Admin", "Status": "Active"}]
st.dataframe(pd.DataFrame(members), use_container_width=True, hide_index=True)

st.divider()
st.success("REAL-DATA MODE: Delta Exchange live feed active[span_0](start_span)[span_0](end_span).")

# Auto-refresh using Streamlit native rerun instead of browser meta reload (Stops flickering)
time.sleep(REFRESH_SECONDS)
st.rerun()

