import time
import json
import hmac
import hashlib
import logging
import os
import sys
import requests
from datetime import datetime, timezone
from decimal import Decimal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("DeltaBot")

ATR_PERIOD = 14
SUPERTREND_MULTIPLIER = 3.0
TIMEFRAME = "5m"
CANDLE_SECONDS = 300

SYMBOL = "BTCUSD"
PRODUCT_ID = 27

TOTAL_LOTS = 10
ENTRY_OFFSET = 5.0
TP_OFFSETS = [10.0, 20.0, 30.0]

BASE_URL = os.getenv("DELTA_BASE_URL", "https://api.india.delta.exchange")
API_KEY = os.getenv("DELTA_API_KEY", "your_api_key_here")
API_SECRET = os.getenv("DELTA_API_SECRET", "your_api_secret_here")

def round_to_tick(price: float, tick_size: float = 0.5) -> float:
    return round(round(price / tick_size) * tick_size, 2)

class DeltaAPIClient:
    def __init__(self, base_url: str, api_key: str, api_secret: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()

    def _generate_signature(self, method: str, timestamp: str, path: str, query_string: str, payload: str) -> str:
        signature_data = method + timestamp + path + query_string + payload
        secret_bytes = bytes(self.api_secret, "utf-8")
        message_bytes = bytes(signature_data, "utf-8")
        return hmac.new(secret_bytes, message_bytes, hashlib.sha256).hexdigest()

    def request(self, method: str, path: str, params: dict = None, payload: dict = None, retries: int = 5) -> dict:
        method = method.upper()
        url = f"{self.base_url}{path}"
        for attempt in range(1, retries + 1):
            timestamp = str(int(time.time()))
            query_string = "?" + "&".join([f"{k}={v}" for k, v in params.items()]) if params else ""
            payload_str = json.dumps(payload) if payload else ""
            signature = self._generate_signature(method, timestamp, path, query_string, payload_str)
            headers = {
                "api-key": self.api_key,
                "timestamp": timestamp,
                "signature": signature,
                "Content-Type": "application/json",
                "User-Agent": "python-rest-client"
            }
            try:
                response = self.session.request(
                    method=method, url=url, params=params,
                    data=payload_str if payload else None, headers=headers, timeout=(5, 20)
                )
                if response.status_code in [429, 500, 502, 503, 504]:
                    time.sleep(attempt * 2)
                    continue
                res_json = response.json()
                return res_json
            except requests.RequestException:
                time.sleep(attempt * 2)
        return {"success": False, "error": "Max retries exceeded"}

    def get_candles(self, symbol: str, resolution: str, count: int = 200) -> list:
        end_time = int(time.time())
        start_time = end_time - (count * CANDLE_SECONDS)
        res = self.request("GET", "/v2/history/candles", params={"symbol": symbol, "resolution": resolution, "start": start_time, "end": end_time})
        if res.get("success") and isinstance(res.get("result"), list):
            candles = res["result"]
            candles.sort(key=lambda x: x["time"])
            return candles
        return []

    def get_position(self, product_id: int) -> dict:
        res = self.request("GET", "/v2/positions", params={"product_id": product_id})
        if res.get("success") and "result" in res:
            result = res["result"]
            if isinstance(result, dict):
                return result
            elif isinstance(result, list) and len(result) > 0:
                return result[0]
        return {"size": 0, "entry_price": "0"}

    def get_active_orders(self, product_id: int) -> list:
        res = self.request("GET", "/v2/orders", params={"product_ids": str(product_id), "states": "open,pending"})
        if res.get("success") and isinstance(res.get("result"), list):
            return res["result"]
        return []

    def get_ticker_price(self, symbol: str) -> float:
        res = self.request("GET", "/v2/tickers", params={"symbol": symbol})
        if res.get("success"):
            result = res.get("result")
            if isinstance(result, list) and result:
                result = result[0]
            if isinstance(result, dict):
                for key in ("mark_price", "close", "last_price"):
                    if result.get(key) is not None:
                        return float(result[key])
        return 0.0

    def place_order(self, product_id: int, size: int, side: str, order_type: str, limit_price: float = None, reduce_only: bool = False) -> dict:
        payload = {
            "product_id": product_id, "size": int(size),
            "side": side.lower(), "order_type": order_type.lower(),
            "reduce_only": "true" if reduce_only else "false"
        }
        if order_type.lower() == "limit_order" and limit_price is not None:
            payload["limit_price"] = str(round_to_tick(limit_price))
        return self.request("POST", "/v2/orders", payload=payload)

    def cancel_order(self, order_id: int, product_id: int) -> dict:
        return self.request("DELETE", "/v2/orders", payload={"id": order_id, "product_id": product_id})

def calculate_supertrend(candles: list, period: int = ATR_PERIOD, multiplier: float = SUPERTREND_MULTIPLIER) -> list:
    if len(candles) < period + 1:
        return []
    tr_list = []
    for i in range(len(candles)):
        high, low = float(candles[i]["high"]), float(candles[i]["low"])
        tr = high - low if i == 0 else max(high - low, abs(high - float(candles[i - 1]["close"])), abs(low - float(candles[i - 1]["close"])))
        tr_list.append(tr)
    atr_list = [0.0] * len(candles)
    atr_list[period - 1] = sum(tr_list[:period]) / period
    for i in range(period, len(candles)):
        atr_list[i] = ((atr_list[i - 1] * (period - 1)) + tr_list[i]) / period
    st_results = []
    upper_band, lower_band, trend, supertrend = [0.0]*len(candles), [0.0]*len(candles), [1]*len(candles), [0.0]*len(candles)
    for i in range(len(candles)):
        if i < period - 1:
            st_results.append({"time": candles[i]["time"], "close": float(candles[i]["close"]), "trend": 1, "supertrend": 0.0})
            continue
        close, high, low = float(candles[i]["close"]), float(candles[i]["high"]), float(candles[i]["low"])
        hl2, atr = (high + low) / 2.0, atr_list[i]
        basic_upper, basic_lower = hl2 + (multiplier * atr), hl2 - (multiplier * atr)
        if i == period - 1:
            upper_band[i], lower_band[i], trend[i], supertrend[i] = basic_upper, basic_lower, 1, basic_lower
        else:
            prev_close = float(candles[i - 1]["close"])
            prev_upper, prev_lower = upper_band[i - 1], lower_band[i - 1]
            upper_band[i] = basic_upper if (basic_upper < prev_upper or prev_close > prev_upper) else prev_upper
            lower_band[i] = basic_lower if (basic_lower > prev_lower or prev_close < prev_lower) else prev_lower
            prev_trend = trend[i - 1]
            if prev_trend == 1:
                trend[i], supertrend[i] = (-1, upper_band[i]) if close < lower_band[i] else (1, lower_band[i])
            else:
                trend[i], supertrend[i] = (1, lower_band[i]) if close > upper_band[i] else (-1, upper_band[i])
        st_results.append({"time": candles[i]["time"], "close": close, "trend": trend[i], "supertrend": supertrend[i]})
    return st_results
class DeltaFuturesBot:
    def __init__(self, api_client: DeltaAPIClient):
        self.api = api_client

    def get_position_size_and_entry(self) -> tuple:
        pos = self.api.get_position(PRODUCT_ID)
        return int(pos.get("size", 0)), float(pos.get("entry_price", 0.0) or 0.0)

    def cancel_all_orders(self) -> None:
        for order in self.api.get_active_orders(PRODUCT_ID):
            self.api.cancel_order(order["id"], PRODUCT_ID)

    def close_position_and_wait(self) -> bool:
        self.cancel_all_orders()
        size, _ = self.get_position_size_and_entry()
        if size == 0:
            return True
        close_side = "sell" if size > 0 else "buy"
        self.api.place_order(product_id=PRODUCT_ID, size=abs(size), side=close_side, order_type="market_order", reduce_only=True)
        for _ in range(15):
            time.sleep(1)
            if self.get_position_size_and_entry()[0] == 0:
                return True
        return False

    def sync_take_profits(self) -> None:
        pos_size, entry_price = self.get_position_size_and_entry()
        if pos_size == 0 or entry_price <= 0:
            for order in self.api.get_active_orders(PRODUCT_ID):
                if str(order.get("reduce_only")).lower() == "true":
                    self.api.cancel_order(order["id"], PRODUCT_ID)
            return

    def monitor_entry_orders(self) -> None:
        print("\n========== ENTRY ORDER MONITOR ==========")
        try:
            current_price = self.api.get_ticker_price(SYMBOL)
            if current_price <= 0:
                print("Current market price unavailable.")
                return
            entry_orders = [o for o in self.api.get_active_orders(PRODUCT_ID) if str(o.get("reduce_only")).lower() == "false"]
            print(f"Current Market Price : {current_price}")
            if not entry_orders:
                print("No OPEN/PENDING entry orders.")
                print("=========================================")
                return
            for order in entry_orders:
                order_id = order.get("id")
                side = str(order.get("side", "")).upper()
                order_price = float(order.get("limit_price") or order.get("price") or 0)
                size = order.get("size")
                status = order.get("state") or order.get("status") or "OPEN"
                if order_price > 0:
                    distance = abs(current_price - order_price)
                    print("-----------------------------------------")
                    print(f"Order ID       : {order_id}")
                    print(f"Side           : {side}")
                    print(f"Order Price    : {order_price}")
                    print(f"Quantity       : {size}")
                    print(f"Current Price  : {current_price}")
                    print(f"DISTANCE       : {distance:.2f} POINTS")
                    print(f"Status         : {status}")
            print("=========================================")
        except Exception as e:
            logger.error(f"Order monitor error: {e}", exc_info=True)

    def process_signals(self) -> None:
        candles = self.api.get_candles(SYMBOL, TIMEFRAME, count=100)
        if len(candles) < ATR_PERIOD + 2:
            return
        completed_candles = candles[:-1] if int(time.time()) < candles[-1]["time"] + CANDLE_SECONDS else candles
        if len(completed_candles) < ATR_PERIOD + 2:
            return
        st_data = calculate_supertrend(completed_candles)
        if len(st_data) < 2:
            return
        prev_trend, curr_trend, signal_close = st_data[-2]["trend"], st_data[-1]["trend"], st_data[-1]["close"]
        pos_size, _ = self.get_position_size_and_entry()
        pending_entry_orders = [o for o in self.api.get_active_orders(PRODUCT_ID) if str(o.get("reduce_only")).lower() == "false"]

        if prev_trend == -1 and curr_trend == 1:
            target_limit_price = round_to_tick(signal_close - ENTRY_OFFSET)
            if pos_size > 0:
                return
            if pos_size < 0:
                if not self.close_position_and_wait():
                    return
                pending_entry_orders = []
            else:
                if [o for o in pending_entry_orders if o.get("side", "").lower() == "buy"]:
                    return
                for o in [o for o in pending_entry_orders if o.get("side", "").lower() == "sell"]:
                    self.api.cancel_order(o["id"], PRODUCT_ID)
            self.api.place_order(product_id=PRODUCT_ID, size=TOTAL_LOTS, side="buy", order_type="limit_order", limit_price=target_limit_price, reduce_only=False)

        elif prev_trend == 1 and curr_trend == -1:
            target_limit_price = round_to_tick(signal_close + ENTRY_OFFSET)
            if pos_size < 0:
                return
            if pos_size > 0:
                if not self.close_position_and_wait():
                    return
                pending_entry_orders = []
            else:
                if [o for o in pending_entry_orders if o.get("side", "").lower() == "sell"]:
                    return
                for o in [o for o in pending_entry_orders if o.get("side", "").lower() == "buy"]:
                    self.api.cancel_order(o["id"], PRODUCT_ID)
            self.api.place_order(product_id=PRODUCT_ID, size=TOTAL_LOTS, side="sell", order_type="limit_order", limit_price=target_limit_price, reduce_only=False)

    def run(self) -> None:
        try:
            self.sync_take_profits()
        except Exception as e:
            logger.error(f"Error during TP synchronization: {e}", exc_info=True)
        try:
            self.monitor_entry_orders()
        except Exception as e:
            logger.error(f"Error during order monitoring: {e}", exc_info=True)
        try:
            self.process_signals()
        except Exception as e:
            logger.error(f"Error during signal processing: {e}", exc_info=True)

if __name__ == "__main__":
    client = DeltaAPIClient(BASE_URL, API_KEY, API_SECRET)
    bot = DeltaFuturesBot(client)
    bot.run()
