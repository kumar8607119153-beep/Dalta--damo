# ============================================================
# SANJAY RANA - DELTA REAL TRADING DASHBOARD
# PART 1 (SETUP & API CLASS)
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

REFRESH_SECONDS = 5

REMOTE_TRADING = (
    os.getenv("REMOTE_TRADING", "false").lower() == "true"
)

DEFAULT_BUY_OFFSET = int(os.getenv("BUY_OFFSET", "-50"))
DEFAULT_SELL_OFFSET = int(os.getenv("SELL_OFFSET", "50"))
DEFAULT_ORDER_SIZE = int(os.getenv("ORDER_SIZE", "1"))
DEFAULT_LIMIT_TIMEOUT = int(os.getenv("LIMIT_TIMEOUT", "60"))

TARGET_1 = int(os.getenv("TARGET_1", "300"))
TARGET_2 = int(os.getenv("TARGET_2", "600"))
TARGET_3 = int(os.getenv("TARGET_3", "900"))


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Sanjay Rana Real Trading",
    page_icon="📈",
    layout="wide"
)

st.title("📈 SANJAY RANA — REAL TRADING DASHBOARD")
st.caption("5 Minute | ATR 10 | Multiplier 3.0 | HL2 | Confirmed Candle Close")


# ============================================================
# INDIAN TIME & HELPERS
# ============================================================

IST = timezone(timedelta(hours=5, minutes=30))

def indian_time(timestamp):
    try:
        ts = int(float(timestamp))
        if ts > 10_000_000_000:
            ts = ts // 1000
        return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    except Exception:
        return "-"

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
# DELTA API CLASS
# ============================================================

class DeltaAPI:
    def __init__(self, api_key="", api_secret=""):
        self.api_key = api_key if api_key else API_KEY
        self.api_secret = api_secret if api_secret else API_SECRET
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Sanjay-Rana-Real-Trading-Bot",
            "Accept": "application/json"
        })

    def make_signature(self, method, timestamp, path, query_string="", body=""):
        message = method.upper() + timestamp + path + query_string + body
        secret_to_use = self.api_secret if self.api_secret else API_SECRET
        return hmac.new(
            secret_to_use.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

    def request(self, method, path, params=None, body=None, private=False):
        params = params or {}
        body = body or {}
        payload = ""

        if body:
            payload = json.dumps(body, separators=(",", ":"))

        query_string = ""
        if params:
            parts = [f"{key}={value}" for key, value in params.items()]
            query_string = "?" + "&".join(parts)

        headers = {
            "Accept": "application/json",
            "User-Agent": "Sanjay-Rana-Real-Trading-Bot"
        }

        key_to_use = self.api_key if self.api_key else API_KEY
        secret_to_use = self.api_secret if self.api_secret else API_SECRET

        if private:
            if not key_to_use or not secret_to_use:
                return {"success": False, "error": "API key/secret missing"}

            timestamp = str(int(time.time()))
            signature = self.make_signature(method, timestamp, path, query_string, payload)

            headers.update({
                "api-key": key_to_use,
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
                return {"success": False, "error": response.text}
            return data
        except Exception as e:
            return {"success": False, "error": str(e)}

    def candles(self):
        end = int(time.time())
        start = end - (500 * CANDLE_SECONDS)
        return self.request("GET", "/v2/history/candles", params={"symbol": SYMBOL, "resolution": TIMEFRAME, "start": start, "end": end})

    def ticker(self):
        return self.request("GET", f"/v2/tickers/{SYMBOL}")

    def open_orders(self):
        return self.request("GET", "/v2/orders", params={"product_id": PRODUCT_ID, "state": "open"}, private=True)

    def position(self):
        return self.request("GET", "/v2/positions", params={"product_id": PRODUCT_ID}, private=True)

    def place_limit_order(self, side, size, limit_price):
        body = {
            "product_id": PRODUCT_ID,
            "product_symbol": SYMBOL,
            "limit_price": str(limit_price),
            "size": int(size),
            "side": side,
            "order_type": "limit_order"
        }
        return self.request("POST", "/v2/orders", body=body, private=True)

    def cancel_order(self, order_id):
        return self.request("DELETE", f"/v2/orders/{order_id}", private=True)


API_KEY = os.getenv("DELTA_API_KEY", "")
API_SECRET = os.getenv("DELTA_API_SECRET", "")
api = DeltaAPI()


# ============================================================
# OWNER API + MEMBER UI
# ============================================================

st.divider()
st.header("👑 OWNER API")

owner_col1, owner_col2 = st.columns(2)
with owner_col1:
    owner_api_key_input = st.text_input("🔑 Owner API Key", type="password", key="owner_api_key_input")
with owner_col2:
    owner_api_secret_input = st.text_input("🔐 Owner API Secret", type="password", key="owner_api_secret_input")

if st.button("🔗 TEST OWNER API", key="test_owner_api_button"):
    if not owner_api_key_input or not owner_api_secret_input:
        st.error("❌ Owner API Key और API Secret दोनों डालें।")
    else:
        try:
            owner_client = DeltaAPI(owner_api_key_input, owner_api_secret_input)
            owner_result = owner_client.position()
            if owner_result.get("success"):
                st.success("🟢 OWNER API CONNECTED")
                st.session_state["owner_api_connected"] = True
            else:
                st.error("🔴 OWNER API CONNECTION FAILED")
                st.session_state["owner_api_connected"] = False
        except Exception as e:
                st.error(f"❌ Owner API Error: {e}")

if "members" not in st.session_state:
    st.session_state["members"] = []

if st.button("➕ ADD MEMBER", key="add_member_button"):
    st.session_state["members"].append({"name": f"Member {len(st.session_state['members']) + 1}", "api_key": "", "api_secret": "", "connected": False, "active": False})
# ============================================================
# SANJAY RANA - DELTA REAL TRADING DASHBOARD
# PART 2 (ENGINE, CHART & REFRESH)
# ============================================================

def get_result(data):
    if not data or not data.get("success"):
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
    return pd.DataFrame(rows).drop_duplicates("time").sort_values("time").reset_index(drop=True)

candle_response = api.candles()
df = make_dataframe(candle_response)

if not df.empty:
    current_candle_start = (int(time.time()) // CANDLE_SECONDS) * CANDLE_SECONDS
    df = df[df["time"] < current_candle_start].copy().reset_index(drop=True)

    if len(df) >= ATR_PERIOD + 5:
        prev_close = df["close"].shift(1)
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - prev_close).abs()
        tr3 = (df["low"] - prev_close).abs()
        df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        df["ATR"] = float("nan")
        df.loc[ATR_PERIOD - 1, "ATR"] = df["TR"].iloc[:ATR_PERIOD].mean()

        for i in range(ATR_PERIOD, len(df)):
            df.loc[i, "ATR"] = (df.loc[i - 1, "ATR"] * (ATR_PERIOD - 1) + df.loc[i, "TR"]) / ATR_PERIOD

        df["HL2"] = (df["high"] + df["low"]) / 2.0
        df["TREND"] = 1
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
                df.loc[i, "SUPERTREND"] = upper_basic
                continue

            prev_up = df.loc[i - 1, "SUPERTREND"]
            prev_trend = df.loc[i - 1, "TREND"]
            prev_close = df.loc[i - 1, "close"]

            if prev_trend == 1:
                trend = -1 if df.loc[i, "close"] > upper_basic else 1
            else:
                trend = 1 if df.loc[i, "close"] < lower_basic else -1

            df.loc[i, "TREND"] = trend
            df.loc[i, "SUPERTREND"] = lower_basic if trend == -1 else upper_basic

        last_candle = df.iloc[-1]
        current_direction = "BUY / BULLISH 🟢" if int(last_candle["TREND"]) == -1 else "SELL / BEARISH 🔴"
        
        st.divider()
        st.header("📈 SUPERTREND — 5 MINUTE")
        c1, c2, c3 = st.columns(3)
        c1.metric("CURRENT DIRECTION", current_direction)
        c2.metric("CURRENT CLOSE", show_price(last_candle["close"]))
        c3.metric("SUPERTREND", show_price(last_candle["SUPERTREND"]))


# ============================================================
# REAL POSITION & LIVE MARKET
# ============================================================

st.divider()
st.header("📍 REAL POSITION & LIVE MARKET")

position_data = get_result(api.position())
position = position_data[0] if isinstance(position_data, list) and position_data else {}
position_size = number(position.get("size"), 0)
position_side = "LONG 🟢" if position_size > 0 else ("SHORT 🔴" if position_size < 0 else "FLAT ⚪")

p1, p2, p3, p4 = st.columns(4)
p1.metric("POSITION", position_side)
p2.metric("SIZE", str(abs(position_size)))
p3.metric("ENTRY PRICE", show_price(position.get("entry_price")))
p4.metric("UNREALIZED P&L", f"₹{number(position.get('unrealized_pnl'), 0):,.2f}")


# ============================================================
# TRADINGVIEW LIVE CHART (FULL SCREEN EMBED)
# ============================================================

st.divider()
st.header("📊 TRADINGVIEW LIVE CHART")

components.html(
    """
    <div class="tradingview-widget-container" style="height:100vh;width:100%;">
      <div class="tradingview-widget-container__widget" style="height:100%;width:100%;"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
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
    height=800,
    scrolling=False
)


# ============================================================
# AUTO REFRESH LOOP
# ============================================================

time.sleep(REFRESH_SECONDS)
st.rerun()
      
