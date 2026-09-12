# ================================================================
# SANJAY RANA - REAL LIMIT ORDER + TP SPLIT (CONTINUOUS LOOP)
# Same SuperTrend + Entry Offset + Target logic as original file
# TP1 = 50%, TP2 = 30%, TP3 = 20% of Order Size (integer lots)
# Automatic cancel on SuperTrend direction change - runs continuously
# ================================================================

import os
import time
import json
import hmac
import hashlib
from datetime import datetime, timezone, timedelta
from urllib.parse import urlencode

import requests
import pandas as pd


# ============================================================
# SETTINGS (same as original file)
# ============================================================

BASE_URL = "https://api.india.delta.exchange"
SYMBOL = "BTCUSD"
PRODUCT_ID = 27

TIMEFRAME = "5m"
CANDLE_SECONDS = 300

ATR_PERIOD = 10
MULTIPLIER = 3.0

BUY_OFFSET = -50
SELL_OFFSET = 50

TARGET_1 = 300
TARGET_2 = 600
TARGET_3 = 900

REFRESH_SECONDS = 5   # kitni der mein dobara check kare (loop interval)

# ------------------------------------------------------------
# ORDER SIZE (50/30/20 integer split ke liye)
# ------------------------------------------------------------
ORDER_SIZE = 10
TP1_QTY = int(ORDER_SIZE * 0.50)   # 5
TP2_QTY = int(ORDER_SIZE * 0.30)   # 3
TP3_QTY = ORDER_SIZE - TP1_QTY - TP2_QTY   # 2


# ============================================================
# CREDENTIALS - apni NEW API key/secret yahan daalein
# ============================================================

API_KEY = "your_new_api_key_here"
API_SECRET = "your_new_api_secret_here"


# ============================================================
# INDIAN TIME (same as original file)
# ============================================================

IST = timezone(timedelta(hours=5, minutes=30))


def indian_time(timestamp):
    try:
        ts = int(float(timestamp))
        if ts > 10_000_000_000:
            ts = ts // 1000
        return datetime.fromtimestamp(
            ts, tz=timezone.utc
        ).astimezone(IST).strftime("%Y-%m-%d %H:%M:%S IST")
    except Exception:
        return "-"


def show_price(val):
    try:
        if val is None or pd.isna(val):
            return "-"
        return f"${float(val):,.2f}"
    except Exception:
        return str(val)


def number(val, default=0.0):
    try:
        if val is None or pd.isna(val):
            return default
        return float(val)
    except Exception:
        return default


# ============================================================
# DELTA API CLASS (same signature/request logic as original file)
# ============================================================

class DeltaAPI:

    def __init__(self, api_key=None, api_secret=None):
        self.api_key = str(api_key or "").strip()
        self.api_secret = str(api_secret or "").strip()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Sanjay-Rana-Real-Trading-Bot",
            "Accept": "application/json"
        })

    def make_signature(self, method, timestamp, path, query_string="", body=""):
        message = method.upper() + timestamp + path + query_string + body
        return hmac.new(
            self.api_secret.encode("utf-8"),
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
            query_string = "?" + urlencode(params, doseq=True)

        headers = {
            "Accept": "application/json",
            "User-Agent": "Sanjay-Rana-Real-Trading-Bot"
        }

        if private:
            if not self.api_key or not self.api_secret:
                return {"success": False, "error": "API key/secret missing"}

            timestamp = str(int(time.time()))
            signature = self.make_signature(method, timestamp, path, query_string, payload)

            headers.update({
                "api-key": self.api_key,
                "timestamp": timestamp,
                "signature": signature,
                "Content-Type": "application/json"
            })

        try:
            url = BASE_URL + path + query_string
            response = self.session.request(
                method.upper(),
                url,
                data=payload if payload else None,
                headers=headers,
                timeout=(3, 27)
            )
            try:
                return response.json()
            except Exception:
                return {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def candles(self):
        end = int(time.time())
        start = end - (4320 * CANDLE_SECONDS)
        return self.request(
            "GET", "/v2/history/candles",
            params={"symbol": SYMBOL, "resolution": TIMEFRAME, "start": start, "end": end}
        )

    def open_orders(self):
        return self.request(
            "GET", "/v2/orders",
            params={"product_id": PRODUCT_ID, "state": "open"},
            private=True
        )

    def position(self):
        return self.request(
            "GET", "/v2/positions",
            params={"product_id": PRODUCT_ID},
            private=True
        )

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
    df = df.drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return df


# ============================================================
# SUPERTREND CALCULATION (same as original file)
# ============================================================

def calculate_supertrend(df):

    prev_close = df["close"].shift(1)
    tr1 = df["high"] - df["low"]
    tr2 = (df["high"] - prev_close).abs()
    tr3 = (df["low"] - prev_close).abs()
    df["TR"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    df["ATR"] = float("nan")
    first_atr = df["TR"].iloc[:ATR_PERIOD].mean()
    df.loc[ATR_PERIOD - 1, "ATR"] = first_atr

    for i in range(ATR_PERIOD, len(df)):
        previous_atr = df.loc[i - 1, "ATR"]
        current_tr = df.loc[i, "TR"]
        df.loc[i, "ATR"] = (previous_atr * (ATR_PERIOD - 1) + current_tr) / ATR_PERIOD

    df["HL2"] = (df["high"] + df["low"]) / 2.0

    df["UP"] = float("nan")
    df["DN"] = float("nan")
    df["TREND"] = float("nan")
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
            df.loc[i, "UP"] = upper_basic
            df.loc[i, "DN"] = lower_basic
            df.loc[i, "TREND"] = 1
            df.loc[i, "SUPERTREND"] = upper_basic
            continue

        previous_up = df.loc[i - 1, "UP"]
        previous_dn = df.loc[i - 1, "DN"]
        previous_trend = df.loc[i - 1, "TREND"]
        previous_close = df.loc[i - 1, "close"]

        if pd.isna(previous_up):
            previous_up = upper_basic
        if pd.isna(previous_dn):
            previous_dn = lower_basic
        if pd.isna(previous_trend):
            previous_trend = 1

        if lower_basic > previous_dn or previous_close < previous_dn:
            lower_band = lower_basic
        else:
            lower_band = previous_dn

        if upper_basic < previous_up or previous_close > previous_up:
            upper_band = upper_basic
        else:
            upper_band = previous_up

        trend = previous_trend
        close = df.loc[i, "close"]

        if previous_trend == 1:
            trend = -1 if close > upper_band else 1
        else:
            trend = 1 if close < lower_band else -1

        df.loc[i, "UP"] = upper_band
        df.loc[i, "DN"] = lower_band
        df.loc[i, "TREND"] = trend
        df.loc[i, "SUPERTREND"] = lower_band if trend == -1 else upper_band

        if trend == -1 and previous_trend == 1:
            df.loc[i, "SIGNAL"] = "BUY"
        elif trend == 1 and previous_trend == -1:
            df.loc[i, "SIGNAL"] = "SELL"

    return df


# ============================================================
# ONE CYCLE OF LOGIC (called repeatedly inside the loop)
# ============================================================

def run_cycle(api, state):

    candle_response = api.candles()
    df = make_dataframe(candle_response)

    if df.empty:
        print(indian_time(time.time()), "- Delta se candle data nahi mila.")
        return

    current_candle_start = (int(time.time()) // CANDLE_SECONDS) * CANDLE_SECONDS
    df = df[df["time"] < current_candle_start].copy().reset_index(drop=True)

    if len(df) < ATR_PERIOD + 5:
        print(indian_time(time.time()), "- SuperTrend ke liye enough candles nahi hain.")
        return

    df = calculate_supertrend(df)

    signal_rows = df[df["SIGNAL"].isin(["BUY", "SELL"])].copy()
    last_candle = df.iloc[-1]
    current_trend = int(last_candle["TREND"])

    # ------------------------------------------------------------
    # CANCEL PENDING OPPOSITE ORDER ON DIRECTION CHANGE
    # Yeh har cycle mein check hota hai, isliye continuous chalta rahega
    # ------------------------------------------------------------

    open_orders_response = api.open_orders()
    open_orders = get_result(open_orders_response)
    if not isinstance(open_orders, list):
        open_orders = []

    for order in open_orders:
        order_side_existing = str(order.get("side", "")).lower()
        order_id = order.get("id")

        should_cancel = (
            (order_side_existing == "buy" and current_trend == 1) or
            (order_side_existing == "sell" and current_trend == -1)
        )

        if should_cancel and order_id is not None:
            cancel_result = api.cancel_order(order_id)
            print(
                indian_time(time.time()),
                f"- Pending {order_side_existing.upper()} order {order_id} "
                f"CANCELLED (direction changed). Success:", cancel_result.get("success")
            )
            if order_id == state.get("last_entry_order_id"):
                state["last_entry_order_id"] = None
                state["tp_placed"] = False

    if len(signal_rows) == 0:
        print(indian_time(time.time()), "- No confirmed SuperTrend entry mila.")
        return

    current_entry = signal_rows.iloc[-1]
    signal_direction = str(current_entry["SIGNAL"])
    signal_entry_price = float(current_entry["close"])
    signal_time = indian_time(current_entry["time"])

    # ------------------------------------------------------------
    # ENTRY PRICE WITH OFFSET
    # ------------------------------------------------------------

    if signal_direction == "BUY":
        limit_entry_price = signal_entry_price + BUY_OFFSET
        target1 = limit_entry_price + TARGET_1
        target2 = limit_entry_price + TARGET_2
        target3 = limit_entry_price + TARGET_3
        order_side = "buy"
        tp_side = "sell"
    else:
        limit_entry_price = signal_entry_price + SELL_OFFSET
        target1 = limit_entry_price - TARGET_1
        target2 = limit_entry_price - TARGET_2
        target3 = limit_entry_price - TARGET_3
        order_side = "sell"
        tp_side = "buy"

    # ------------------------------------------------------------
    # PREVENT DUPLICATE ENTRY ORDER FOR SAME SIGNAL CANDLE
    # ------------------------------------------------------------

    if state.get("last_order_signal") == signal_time:
        # Isi signal ka order pehle hi place ho chuka hai
        pass
    else:
        entry_result = api.place_limit_order(
            side=order_side,
            size=ORDER_SIZE,
            limit_price=limit_entry_price
        )

        if entry_result.get("success"):
            new_order_id = entry_result.get("result", {}).get("id")
            state["last_order_signal"] = signal_time
            state["last_entry_order_id"] = new_order_id
            state["tp_placed"] = False
            state["tp_side"] = tp_side
            state["target1"] = target1
            state["target2"] = target2
            state["target3"] = target3

            print(
                indian_time(time.time()),
                f"- ENTRY {signal_direction} order placed. Order ID: {new_order_id} "
                f"@ {show_price(limit_entry_price)}"
            )
        else:
            print(
                indian_time(time.time()),
                "- ENTRY ORDER FAILED:", entry_result.get("error")
            )

    # ------------------------------------------------------------
    # CHECK POSITION, PLACE TP ORDERS ONCE (50/30/20 split)
    # ------------------------------------------------------------

    if not state.get("tp_placed") and state.get("last_entry_order_id"):

        position_response = api.position()
        position_data = get_result(position_response)

        position = {}
        if isinstance(position_data, list) and position_data:
            position = position_data[0]
        elif isinstance(position_data, dict):
            position = position_data

        position_size = number(position.get("size"), 0)

        if position_size != 0:
            tp_side = state.get("tp_side")

            tp1_result = api.place_limit_order(side=tp_side, size=TP1_QTY, limit_price=state["target1"])
            tp2_result = api.place_limit_order(side=tp_side, size=TP2_QTY, limit_price=state["target2"])
            tp3_result = api.place_limit_order(side=tp_side, size=TP3_QTY, limit_price=state["target3"])

            print(
                indian_time(time.time()),
                "- TP orders placed. TP1:", tp1_result.get("success"),
                "| TP2:", tp2_result.get("success"),
                "| TP3:", tp3_result.get("success")
            )

            state["tp_placed"] = True


# ============================================================
# MAIN LOOP - RUKEGA NAHI, CONTINUOUSLY CHALTA RAHEGA
# ============================================================

def main():

    api = DeltaAPI(API_KEY, API_SECRET)

    state = {
        "last_order_signal": "",
        "last_entry_order_id": None,
        "tp_placed": False,
        "tp_side": "",
        "target1": None,
        "target2": None,
        "target3": None,
    }

    print("Algo shuru ho raha hai. Rukega nahi, Ctrl+C se manually band kar sakte hain.")

    while True:
        try:
            run_cycle(api, state)
        except Exception as e:
            print(indian_time(time.time()), "- Cycle error:", str(e))

        time.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    main()
