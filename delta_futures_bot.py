def __init__(self, base_url: str, api_key: str, api_secret: str):
    self.base_url = base_url.rstrip("/")
    self.api_key = api_key
    self.api_secret = api_secret
    self.session = requests.Session()

def _generate_signature(self, method: str, timestamp: str, path: str, query_string: str, payload: str) -> str:
    """Generates HMAC-SHA256 signature for authentication."""
    signature_data = method + timestamp + path + query_string + payload
    secret_bytes = bytes(self.api_secret, 'utf-8')
    message_bytes = bytes(signature_data, 'utf-8')
    return hmac.new(secret_bytes, message_bytes, hashlib.sha256).hexdigest()

def request(self, method: str, path: str, params: dict = None, payload: dict = None, retries: int = 5) -> dict:
    """Executes signed HTTP requests with automatic retries and rate limit handling."""
    method = method.upper()
    url = f"{self.base_url}{path}"

    for attempt in range(1, retries + 1):
        timestamp = str(int(time.time()))

        # Format query string for signature
        query_string = ""
        if params:
            query_string = "?" + "&".join([f"{k}={v}" for k, v in params.items()])

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
                method=method,
                url=url,
                params=params,
                data=payload_str if payload else None,
                headers=headers,
                timeout=(5, 20)
            )

            if response.status_code == 429:
                logger.warning(f"HTTP 429 Rate limited. Retrying in {attempt * 2}s...")
                time.sleep(attempt * 2)
                continue

            if response.status_code in [500, 502, 503, 504]:
                logger.warning(f"HTTP {response.status_code} server error. Retrying in {attempt * 2}s...")
                time.sleep(attempt * 2)
                continue

            res_json = response.json()
            if not res_json.get("success", False):
                logger.error(f"API Error ({path}): {res_json}")
            return res_json

        except requests.RequestException as e:
            logger.warning(f"Network error on attempt {attempt}/{retries}: {e}")
            time.sleep(attempt * 2)

    logger.error(f"Failed API request after {retries} attempts: {path}")
    return {"success": False, "error": "Max retries exceeded"}

def get_candles(self, symbol: str, resolution: str, count: int = 200) -> list:
    """Fetches historical candles."""
    end_time = int(time.time())
    start_time = end_time - (count * CANDLE_SECONDS)
    path = "/v2/history/candles"
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "start": start_time,
        "end": end_time
    }
    res = self.request("GET", path, params=params)
    if res.get("success") and isinstance(res.get("result"), list):
        candles = res["result"]
        # Sort chronologically (oldest to newest)
        candles.sort(key=lambda x: x["time"])
        return candles
    return []

def get_position(self, product_id: int) -> dict:
    """Fetches live position details for the product."""
    path = "/v2/positions"
    params = {"product_id": product_id}
    res = self.request("GET", path, params=params)
    if res.get("success") and "result" in res:
        result = res["result"]
        if isinstance(result, dict):
            return result
        elif isinstance(result, list) and len(result) > 0:
            return result[0]
    return {"size": 0, "entry_price": "0"}

def get_active_orders(self, product_id: int) -> list:
    """Fetches open and pending active orders for the product."""
    path = "/v2/orders"
    params = {
        "product_ids": str(product_id),
        "states": "open,pending"
    }
    res = self.request("GET", path, params=params)
    if res.get("success") and isinstance(res.get("result"), list):
        return res["result"]
    return []

def place_order(self, product_id: int, size: int, side: str, order_type: str, limit_price: float = None, reduce_only: bool = False) -> dict:
    """Places a new order on Delta Exchange."""
    path = "/v2/orders"
    payload = {
        "product_id": product_id,
        "size": int(size),
        "side": side.lower(),
        "order_type": order_type.lower(),
        "reduce_only": "true" if reduce_only else "false"
    }
    if order_type.lower() == "limit_order" and limit_price is not None:
        payload["limit_price"] = str(round_to_tick(limit_price))

    logger.info(f"Placing order: {payload}")
    return self.request("POST", path, payload=payload)

def cancel_order(self, order_id: int, product_id: int) -> dict:
    """Cancels a specific order by order ID."""
    path = "/v2/orders"
    payload = {
        "id": order_id,
        "product_id": product_id
    }
    logger.info(f"Cancelling order ID: {order_id}")
    return self.request("DELETE", path, payload=payload)

**⬆️ Part 1 यहाँ खत्म। नीचे Part 2 इसी फाइल में continue करें।**

---

## PART 2 of 2

```python
# ------------------------------------------------------------------------------
# Technical Indicator: SuperTrend
# ------------------------------------------------------------------------------
def calculate_supertrend(candles: list, period: int = ATR_PERIOD, multiplier: float = SUPERTREND_MULTIPLIER) -> list:
    """
    Calculates SuperTrend indicator on candle data.
    Returns list of dictionaries containing timestamp, close, trend (+1 for bullish, -1 for bearish), and SuperTrend line.
    """
    if len(candles) < period + 1:
        return []

    # Calculate True Range (TR)
    tr_list = []
    for i in range(len(candles)):
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        if i == 0:
            tr = high - low
        else:
            prev_close = float(candles[i - 1]["close"])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_list.append(tr)

    # Calculate ATR using Wilder's Smoothing
    atr_list = [0.0] * len(candles)
    atr_list[period - 1] = sum(tr_list[:period]) / period
    for i in range(period, len(candles)):
        atr_list[i] = (atr_list[i - 1] * (period - 1) + tr_list[i]) / period

    st_results = []
    upper_band = [0.0] * len(candles)
    lower_band = [0.0] * len(candles)
    trend = [1] * len(candles)
    supertrend = [0.0] * len(candles)

    for i in range(len(candles)):
        if i < period - 1:
            st_results.append({"time": candles[i]["time"], "close": float(candles[i]["close"]), "trend": 1, "supertrend": 0.0})
            continue

        close = float(candles[i]["close"])
        high = float(candles[i]["high"])
        low = float(candles[i]["low"])
        hl2 = (high + low) / 2.0
        atr = atr_list[i]

        basic_upper = hl2 + (multiplier * atr)
        basic_lower = hl2 - (multiplier * atr)

        if i == period - 1:
            upper_band[i] = basic_upper
            lower_band[i] = basic_lower
            trend[i] = 1
            supertrend[i] = lower_band[i]
        else:
            prev_close = float(candles[i - 1]["close"])
            prev_upper = upper_band[i - 1]
            prev_lower = lower_band[i - 1]

            upper_band[i] = basic_upper if (basic_upper < prev_upper or prev_close > prev_upper) else prev_upper
            lower_band[i] = basic_lower if (basic_lower > prev_lower or prev_close < prev_lower) else prev_lower

            prev_trend = trend[i - 1]
            if prev_trend == 1:
                if close < lower_band[i]:
                    trend[i] = -1
                    supertrend[i] = upper_band[i]
                else:
                    trend[i] = 1
                    supertrend[i] = lower_band[i]
            else:
                if close > upper_band[i]:
                    trend[i] = 1
                    supertrend[i] = lower_band[i]
                else:
                    trend[i] = -1
                    supertrend[i] = upper_band[i]

        st_results.append({
            "time": candles[i]["time"],
            "close": close,
            "trend": trend[i],
            "supertrend": supertrend[i]
        })

    return st_results


# ------------------------------------------------------------------------------
# Trading Bot Engine (Single-Run / Stateless per invocation)
# ------------------------------------------------------------------------------
class DeltaFuturesBot:
    """
    Main trading bot controller.
    Designed to be invoked ONCE per process (suitable for GitHub Actions cron).
    All duplicate-prevention logic relies on live exchange state, not memory.
    """

    def __init__(self, api_client: DeltaAPIClient):
        self.api = api_client

    def get_position_size_and_entry(self) -> tuple:
        """Fetches current position size and entry price."""
        pos = self.api.get_position(PRODUCT_ID)
        size = int(pos.get("size", 0))
        entry_price = float(pos.get("entry_price", 0.0) or 0.0)
        return size, entry_price

    def cancel_all_orders(self) -> None:
        """Cancels all active open and pending orders for this product."""
        orders = self.api.get_active_orders(PRODUCT_ID)
        for order in orders:
            self.api.cancel_order(order["id"], PRODUCT_ID)

    def close_position_and_wait(self) -> bool:
        """
        Closes existing position via market order and waits until position size
        is confirmed zero by the exchange before returning.
        """
        self.cancel_all_orders()
        size, _ = self.get_position_size_and_entry()

        if size == 0:
            return True

        close_side = "sell" if size > 0 else "buy"
        close_lots = abs(size)

        logger.info(f"Closing existing position of {size} lots with MARKET {close_side.upper()}...")
        self.api.place_order(
            product_id=PRODUCT_ID,
            size=close_lots,
            side=close_side,
            order_type="market_order",
            reduce_only=True
        )

        for attempt in range(15):
            time.sleep(1)
            current_size, _ = self.get_position_size_and_entry()
            logger.info(f"Checking position size after close attempt {attempt + 1}: {current_size} lots")
            if current_size == 0:
                logger.info("Position closure confirmed (size is 0).")
                return True

        logger.error("Failed to confirm position closure within timeout period.")
        return False

    def sync_take_profits(self) -> None:
        """
        Synchronizes active TP orders with the live open position.
        Idempotent: safe to call on every run, including after a restart.
        """
        pos_size, entry_price = self.get_position_size_and_entry()
        if pos_size == 0 or entry_price <= 0:
            # No open position -> cancel any orphan reduce_only TP orders
            orders = self.api.get_active_orders(PRODUCT_ID)
            for order in orders:
                if str(order.get("reduce_only")).lower() == "true":
                    logger.info(f"Cancelling orphan reduce_only TP order ID {order['id']}")
                    self.api.cancel_order(order["id"], PRODUCT_ID)
            return

        is_long = pos_size > 0
        abs_size = abs(pos_size)
        tp_side = "sell" if is_long else "buy"

        target_tp_prices = []
        for offset in TP_OFFSETS:
            target_price = entry_price + offset if is_long else entry_price - offset
            target_tp_prices.append(round_to_tick(target_price))

        active_orders = self.api.get_active_orders(PRODUCT_ID)
        existing_tp_orders = [
            order for order in active_orders
            if str(order.get("reduce_only")).lower() == "true" and order.get("side", "").lower() == tp_side
        ]

        num_required_tps = min(abs_size // 10, len(target_tp_prices))
        required_targets = target_tp_prices[:num_required_tps]

        matched_targets = []
        for order in existing_tp_orders:
            limit_price = round_to_tick(float(order.get("limit_price", 0)))
            order_size = int(order.get("size", 0))

            if limit_price in required_targets and limit_price not in matched_targets and order_size == 10:
                matched_targets.append(limit_price)
            else:
                logger.info(f"Cancelling redundant/mismatched TP order ID {order['id']} at price {limit_price}")
                self.api.cancel_order(order["id"], PRODUCT_ID)

        for target_price in required_targets:
            if target_price not in matched_targets:
                logger.info(f"Placing TP LIMIT {tp_side.upper()} order at {target_price} for 10 lots (reduce_only)")
                self.api.place_order(
                    product_id=PRODUCT_ID,
                    size=10,
                    side=tp_side,
                    order_type="limit_order",
                    limit_price=target_price,
                    reduce_only=True
                )

    def process_signals(self) -> None:
        """
        Single check-and-act cycle:
        1. Fetch candles, use only COMPLETED candles.
        2. Compute SuperTrend, detect crossover on the most recent completed candle.
        3. Act on BUY/SELL crossover with full duplicate/reversal protection based
           on LIVE exchange state (position + active orders).
        """
        candles = self.api.get_candles(SYMBOL, TIMEFRAME, count=100)
        if len(candles) < ATR_PERIOD + 2:
            logger.warning("Insufficient candles fetched for SuperTrend calculation.")
            return

        # Use only COMPLETED candles (exclude the currently forming candle)
        current_time = int(time.time())
        latest_candle_time = candles[-1]["time"]

        if current_time < latest_candle_time + CANDLE_SECONDS:
            completed_candles = candles[:-1]
        else:
            completed_candles = candles

        if len(completed_candles) < ATR_PERIOD + 2:
            logger.warning("Insufficient completed candles for SuperTrend calculation.")
            return

        st_data = calculate_supertrend(completed_candles)
        if len(st_data) < 2:
            return

        prev_st = st_data[-2]
        curr_st = st_data[-1]

        prev_trend = prev_st["trend"]
        curr_trend = curr_st["trend"]
        signal_close = curr_st["close"]
        last_completed_time = curr_st["time"]

        logger.info(
            f"Last completed candle [{datetime.fromtimestamp(last_completed_time, tz=timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}]: "
            f"Close={signal_close}, Prev Trend={prev_trend}, Curr Trend={curr_trend}"
        )

        pos_size, _ = self.get_position_size_and_entry()
        active_orders = self.api.get_active_orders(PRODUCT_ID)
        pending_entry_orders = [
            o for o in active_orders if str(o.get("reduce_only")).lower() == "false"
        ]

        # ---------------- BUY Signal: Bearish -> Bullish ----------------
        if prev_trend == -1 and curr_trend == 1:
            target_limit_price = round_to_tick(signal_close - ENTRY_OFFSET)
            logger.info(f"BUY Signal detected. Target entry price: {target_limit_price}")

            if pos_size > 0:
                logger.info("Already holding a LONG position matching this signal. Skipping (no averaging/duplicate entries).")
                return

            if pos_size < 0:
                logger.info("Reversal required: SHORT position open. Closing it first...")
                if not self.close_position_and_wait():
                    logger.error("Skipping new BUY entry because the old SHORT position failed to close cleanly.")
                    return
                pending_entry_orders = []  # cleared during close_position_and_wait via cancel_all_orders
            else:
                same_side_pending = [o for o in pending_entry_orders if o.get("side", "").lower() == "buy"]
                opposite_side_pending = [o for o in pending_entry_orders if o.get("side", "").lower() == "sell"]

                if same_side_pending:
                    logger.info("A matching BUY pending entry order already exists. Skipping duplicate placement.")
                    return

                for o in opposite_side_pending:
                    logger.info(f"Cancelling stale opposite-side pending SELL entry order ID {o['id']}")
                    self.api.cancel_order(o["id"], PRODUCT_ID)

            logger.info(f"Placing LIMIT BUY entry order for {TOTAL_LOTS} lots at {target_limit_price}")
            self.api.place_order(
                product_id=PRODUCT_ID,
                size=TOTAL_LOTS,
                side="buy",
                order_type="limit_order",
                limit_price=target_limit_price,
                reduce_only=False
            )

        # ---------------- SELL Signal: Bullish -> Bearish ----------------
        elif prev_trend == 1 and curr_trend == -1:
            target_limit_price = round_to_tick(signal_close + ENTRY_OFFSET)
            logger.info(f"SELL Signal detected. Target entry price: {target_limit_price}")

            if pos_size < 0:
                logger.info("Already holding a SHORT position matching this signal. Skipping (no averaging/duplicate entries).")
                return

            if pos_size > 0:
                logger.info("Reversal required: LONG position open. Closing it first...")
                if not self.close_position_and_wait():
                    logger.error("Skipping new SELL entry because the old LONG position failed to close cleanly.")
                    return
                pending_entry_orders = []
            else:
                same_side_pending = [o for o in pending_entry_orders if o.get("side", "").lower() == "sell"]
                opposite_side_pending = [o for o in pending_entry_orders if o.get("side", "").lower() == "buy"]

                if same_side_pending:
                    logger.info("A matching SELL pending entry order already exists. Skipping duplicate placement.")
                    return

                for o in opposite_side_pending:
                    logger.info(f"Cancelling stale opposite-side pending BUY entry order ID {o['id']}")
                    self.api.cancel_order(o["id"], PRODUCT_ID)

            logger.info(f"Placing LIMIT SELL entry order for {TOTAL_LOTS} lots at {target_limit_price}")
            self.api.place_order(
                product_id=PRODUCT_ID,
                size=TOTAL_LOTS,
                side="sell",
                order_type="limit_order",
                limit_price=target_limit_price,
                reduce_only=False
            )

        else:
            logger.info("No SuperTrend crossover on the latest completed candle. No action taken.")

    def run(self) -> None:
        """
        Single check-and-act cycle for one script invocation.
        Suitable for GitHub Actions cron (no infinite loop).
        """
        logger.info("==================================================")
        logger.info("Delta Exchange India Futures Trading Bot - Run Start")
        logger.info(f"Symbol: {SYMBOL} | Timeframe: {TIMEFRAME} | Quantity: {TOTAL_LOTS} Lots")
        logger.info(f"SuperTrend ({ATR_PERIOD}, {SUPERTREND_MULTIPLIER})")
        logger.info("==================================================")

        try:
            # Step 1: Reconcile TP orders with live position (handles restart recovery too)
            self.sync_take_profits()
        except Exception as e:
            logger.error(f"Error during TP synchronization: {e}", exc_info=True)

        try:
            # Step 2: Check latest completed candle for a SuperTrend crossover and act
            self.process_signals()
        except Exception as e:
            logger.error(f"Error during signal processing: {e}", exc_info=True)

        logger.info("Run complete. Exiting.")


# ------------------------------------------------------------------------------
# Script Entry Point
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    if API_KEY == "your_api_key_here" or API_SECRET == "your_api_secret_here":
        logger.error("Please set environment variables DELTA_API_KEY and DELTA_API_SECRET before running.")
        sys.exit(1)

    api_client = DeltaAPIClient(base_url=BASE_URL, api_key=API_KEY, api_secret=API_SECRET)
    bot = DeltaFuturesBot(api_client=api_client)

    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot manually stopped by user. Exiting safely...")
        sys.exit(0)


