"""
delta_futures_bot.py

Delta Exchange India - BTCUSD Futures Production Bot
Strategy: SuperTrend (ATR 10, Multiplier 3) on 5m candles
- BUY flip -> Limit BUY @ signal_close - 50
- SELL flip -> Limit SELL @ signal_close + 50
- 3-tier TP (300/600/900 points), 10 lots each (30 lots total)
- Reversal with confirmed position close before opposite entry
- Restart-safe recovery from live Delta Exchange API state
- No martingale / grid / extra indicators - strategy logic unchanged from user spec
"""

import os
import time
import json
import hmac
import hashlib
import logging
import traceback
from logging.handlers import RotatingFileHandler

import requests
import pandas as pd

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv optional; env vars can also be set directly on the OS/systemd unit


# ==========================================
# CONFIGURATION (env vars - never hard-code secrets)
# ==========================================
BASE_URL = os.environ.get("DELTA_BASE_URL", "https://api.india.delta.exchange")
API_KEY = os.environ.get("DELTA_API_KEY")
API_SECRET = os.environ.get("DELTA_API_SECRET")

if not API_KEY or not API_SECRET:
    raise SystemExit(
        "DELTA_API_KEY / DELTA_API_SECRET not found in environment. "
        "Set them as environment variables or in a .env file before starting the bot."
    )

SYMBOL = "BTCUSD"
PRODUCT_ID = 27  # BTCUSD Perpetual Futures Product ID
TIMEFRAME = "5m"

# SuperTrend settings
ATR_PERIOD = 10
SUPER_TREND_MULTIPLIER = 3.0

# Entry settings
LIMIT_OFFSET_POINTS = 50.0

# Take Profit settings
TP_OFFSETS = [300.0, 600.0, 900.0]  # TP1, TP2, TP3

# Total entry quantity
TOTAL_QTY_LOTS = 30

# TP quantity distribution
TP_QTY_LOTS = [10, 10, 10]

assert sum(TP_QTY_LOTS) == TOTAL_QTY_LOTS, (
    "TP quantities must sum to TOTAL_QTY_LOTS"
)

# Main loop
LOOP_INTERVAL_SECONDS = 10

# Reversal safety
POSITION_CLOSE_CONFIRM_TIMEOUT = 30
POSITION_CLOSE_POLL_INTERVAL = 2


# ==========================================
# LOGGING
# ==========================================
logger = logging.getLogger("delta_bot")
logger.setLevel(logging.INFO)

_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s"
)

_file_handler = RotatingFileHandler(
    "delta_futures_bot.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5
)
_file_handler.setFormatter(_formatter)

_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)

logger.addHandler(_file_handler)
logger.addHandler(_console_handler)


# ==========================================
# AUTH + REST HELPER
# ==========================================
def generate_signature(secret: str, message: str) -> str:
    return hmac.new(
        bytes(secret, "utf-8"),
        bytes(message, "utf-8"),
        hashlib.sha256
    ).hexdigest()


def send_request(
    method: str,
    path: str,
    query_params: dict = None,
    payload: dict = None,
    max_retries: int = 5,
    retry_backoff_base: float = 2.0
):
    """
    Authenticated request with retry/backoff for network errors,
    timeouts and rate limits.

    Returns parsed JSON dict on success/failure.
    """

    query_params = query_params or {}

    query_string = ""

    if query_params:
        query_string = "?" + "&".join(
            f"{k}={v}" for k, v in query_params.items()
        )

    payload_str = json.dumps(payload) if payload else ""

    url = f"{BASE_URL}{path}{query_string}"

    for attempt in range(1, max_retries + 1):

        try:
            timestamp = str(int(time.time()))

            signature_data = (
                method
                + timestamp
                + path
                + query_string
                + payload_str
            )

            signature = generate_signature(
                API_SECRET,
                signature_data
            )

            headers = {
                "api-key": API_KEY,
                "timestamp": timestamp,
                "signature": signature,
                "User-Agent": "delta-futures-bot",
                "Content-Type": "application/json",
            }

            response = requests.request(
                method,
                url,
                data=(
                    payload_str
                    if method in ("POST", "PUT", "DELETE")
                    else None
                ),
                headers=headers,
                timeout=(5, 20),
            )

            # ------------------------------------------
            # RATE LIMIT
            # ------------------------------------------
            if response.status_code == 429:

                wait = retry_backoff_base * attempt

                logger.warning(
                    f"Rate limit hit on {method} {path}. "
                    f"Retrying in {wait:.1f}s "
                    f"(attempt {attempt}/{max_retries})"
                )

                time.sleep(wait)
                continue

            # ------------------------------------------
            # JSON RESPONSE
            # ------------------------------------------
            try:
                data = response.json()

            except ValueError:

                logger.error(
                    f"Non-JSON response from {method} {path}: "
                    f"{response.text[:300]}"
                )

                time.sleep(retry_backoff_base)
                continue

            # ------------------------------------------
            # SUCCESS
            # ------------------------------------------
            if response.status_code in (200, 201):
                return data

            # ------------------------------------------
            # API ERROR
            # ------------------------------------------
            error_info = (
                data.get("error", {})
                if isinstance(data, dict)
                else {}
            )

            logger.error(
                f"API error on {method} {path} "
                f"[{response.status_code}]: "
                f"code={error_info.get('code')} "
                f"context={error_info.get('context')}"
            )

            return data

        except requests.exceptions.Timeout:

            logger.error(
                f"Timeout on {method} {path} "
                f"(attempt {attempt}/{max_retries})"
            )

        except requests.exceptions.ConnectionError as e:

            logger.error(
                f"Connection error on {method} {path}: {e} "
                f"(attempt {attempt}/{max_retries})"
            )

        except requests.exceptions.RequestException as e:

            logger.error(
                f"Network error on {method} {path}: {e} "
                f"(attempt {attempt}/{max_retries})"
            )

        time.sleep(
            retry_backoff_base * attempt
        )

    logger.error(
        f"Max retries exhausted for {method} {path}. "
        f"Giving up on this call."
    )

    return {
        "success": False,
        "error": {
            "code": "max_retries_exhausted"
        }
    }


# ==========================================
# SUPERTREND
# ==========================================
def calculate_supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0
) -> pd.DataFrame:

    df = df.copy()

    # ------------------------------------------
    # TRUE RANGE
    # ------------------------------------------
    df["high_low"] = (
        df["high"] - df["low"]
    )

    df["high_close"] = (
        df["high"]
        - df["close"].shift(1)
    ).abs()

    df["low_close"] = (
        df["low"]
        - df["close"].shift(1)
    ).abs()

    df["tr"] = df[
        ["high_low", "high_close", "low_close"]
    ].max(axis=1)

    # ------------------------------------------
    # ATR
    # ------------------------------------------
    df["atr"] = df["tr"].ewm(
        alpha=1 / period,
        adjust=False
    ).mean()

    # ------------------------------------------
    # BASIC BANDS
    # ------------------------------------------
    hl2 = (
        df["high"] + df["low"]
    ) / 2

    df["basic_ub"] = (
        hl2 + (multiplier * df["atr"])
    )

    df["basic_lb"] = (
        hl2 - (multiplier * df["atr"])
    )

    # ------------------------------------------
    # FINAL BANDS
    # ------------------------------------------
    final_ub = [0.0] * len(df)
    final_lb = [0.0] * len(df)

    supertrend = [0.0] * len(df)

    # 1 = Bullish
    # -1 = Bearish
    direction = [1] * len(df)

    for i in range(1, len(df)):

        # --------------------------------------
        # FINAL UPPER BAND
        # --------------------------------------
        if (
            df["basic_ub"].iloc[i]
            < final_ub[i - 1]
            or
            df["close"].iloc[i - 1]
            > final_ub[i - 1]
        ):

            final_ub[i] = (
                df["basic_ub"].iloc[i]
            )

        else:

            final_ub[i] = (
                final_ub[i - 1]
            )

        # --------------------------------------
        # FINAL LOWER BAND
        # --------------------------------------
        if (
            df["basic_lb"].iloc[i]
            > final_lb[i - 1]
            or
            df["close"].iloc[i - 1]
            < final_lb[i - 1]
        ):

            final_lb[i] = (
                df["basic_lb"].iloc[i]
            )

        else:

            final_lb[i] = (
                final_lb[i - 1]
            )

        # --------------------------------------
        # TREND DIRECTION
        # --------------------------------------
        if (
            direction[i - 1] == 1
            and
            df["close"].iloc[i]
            < final_lb[i]
        ):

            direction[i] = -1

        elif (
            direction[i - 1] == -1
            and
            df["close"].iloc[i]
            > final_ub[i]
        ):

            direction[i] = 1

        else:

            direction[i] = (
                direction[i - 1]
            )

        # --------------------------------------
        # SUPERTREND VALUE
        # --------------------------------------
        supertrend[i] = (
            final_ub[i]
            if direction[i] == -1
            else final_lb[i]
        )

    df["supertrend"] = supertrend
    df["trend"] = direction

    return df


# ==========================================
# BOT CLASS
# ==========================================
class DeltaFuturesBot:

    def __init__(self):

        # --------------------------------------
        # CANDLE STATE
        # --------------------------------------
        self.last_processed_candle_time = None

        # --------------------------------------
        # PENDING ENTRY ORDER
        # --------------------------------------
        self.pending_entry_order_id = None
        self.pending_entry_side = None
        # "buy" / "sell"

        # --------------------------------------
        # POSITION STATE
        # --------------------------------------
        self.position_side = None
        # "BUY" / "SELL" / None

        self.position_size = 0
        self.entry_price = 0.0

        # --------------------------------------
        # TP ORDER TRACKING
        # --------------------------------------
        self.tp_orders = []
        # [
        #   {
        #       id,
        #       price,
        #       size,
        #       offset,
        #       filled
        #   }
        # ]


    # ==========================================
    # MARKET DATA
    # ==========================================
    def fetch_historical_candles(self) -> pd.DataFrame:

        end_time = int(time.time())

        start_time = (
            end_time
            - (200 * 5 * 60)
        )

        params = {
            "symbol": SYMBOL,
            "resolution": TIMEFRAME,
            "start": start_time,
            "end": end_time,
        }

        res = send_request(
            "GET",
            "/v2/history/candles",
            query_params=params
        )

        if (
            res
            and res.get("success")
            and res.get("result")
        ):

            df = pd.DataFrame(
                res["result"]
            )

            if df.empty:
                return pd.DataFrame()

            df["time"] = pd.to_datetime(
                df["time"],
                unit="s"
            )

            df = df.sort_values(
                "time"
            ).reset_index(drop=True)

            return df

        logger.warning(
            "Failed to fetch candle data."
        )

        return pd.DataFrame()


    # ==========================================
    # POSITION
    # ==========================================
    def get_position(self):

        """
        Returns:
            size:int
            entry_price:float

        Positive size = BUY/LONG
        Negative size = SELL/SHORT
        Zero = No position
        """

        res = send_request(
            "GET",
            "/v2/positions",
            query_params={
                "product_id": PRODUCT_ID
            }
        )

        if (
            res
            and res.get("success")
            and isinstance(
                res.get("result"),
                dict
            )
        ):

            result = res["result"]

            size = int(
                result.get("size") or 0
            )

            entry_price = float(
                result.get("entry_price")
                or 0.0
            )

            return size, entry_price

        return 0, 0.0


    # ==========================================
    # OPEN ORDERS
    # ==========================================
    def get_open_orders(self):

        res = send_request(
            "GET",
            "/v2/orders",
            query_params={
                "product_ids": PRODUCT_ID,
                "states": "open,pending"
            }
        )

        if (
            res
            and res.get("success")
            and isinstance(
                res.get("result"),
                list
            )
        ):

            return res["result"]

        return []


    # ==========================================
    # GET SINGLE ORDER
    # ==========================================
    def get_order_by_id(self, order_id):

        res = send_request(
            "GET",
            f"/v2/orders/{order_id}"
        )

        if (
            res
            and res.get("success")
        ):

            return res.get("result")

        return None


    # ==========================================
    # PLACE LIMIT ORDER
    # ==========================================
    def place_limit_order(
        self,
        side: str,
        price: float,
        size: int,
        reduce_only: bool = False
    ):

        payload = {
            "product_id": PRODUCT_ID,
            "size": int(size),
            "side": side.lower(),
            "order_type": "limit_order",
            "limit_price": str(price),
            "reduce_only": (
                "true"
                if reduce_only
                else "false"
            ),
        }

        res = send_request(
            "POST",
            "/v2/orders",
            payload=payload
        )

        if (
            res
            and res.get("success")
            and res.get("result")
        ):

            order = res["result"]

            logger.info(
                f"LIMIT {side.upper()} order placed | "
                f"id={order['id']} "
                f"price={price} "
                f"size={size} "
                f"reduce_only={reduce_only}"
            )

            return order

        logger.error(
            f"Failed to place LIMIT "
            f"{side.upper()} order "
            f"at {price} "
            f"size={size}"
        )

        return None


    # ==========================================
    # PLACE MARKET ORDER
    # ==========================================
    def place_market_order(
        self,
        side: str,
        size: int
    ):

        payload = {
            "product_id": PRODUCT_ID,
            "size": int(size),
            "side": side.lower(),
            "order_type": "market_order",
        }

        res = send_request(
            "POST",
            "/v2/orders",
            payload=payload
        )

        if (
            res
            and res.get("success")
            and res.get("result")
        ):

            order = res["result"]

            logger.info(
                f"MARKET {side.upper()} order placed | "
                f"id={order['id']} "
                f"size={size}"
            )

            return order

        logger.error(
            f"Failed to place MARKET "
            f"{side.upper()} order "
            f"size={size}"
        )

        return None


    # ==========================================
    # CANCEL ORDER
    # ==========================================
    def cancel_order_by_id(
        self,
        order_id
    ):

        payload = {
            "id": int(order_id),
            "product_id": PRODUCT_ID
        }

        res = send_request(
            "DELETE",
            "/v2/orders",
            payload=payload
        )

        if (
            res
            and res.get("success")
        ):

            logger.info(
                f"Order cancelled | "
                f"id={order_id}"
            )

            return True

        logger.warning(
            f"Could not cancel order "
            f"id={order_id} "
            f"(may already be filled/cancelled)"
        )

        return False


    # ==========================================
    # EDIT ORDER SIZE
    # ==========================================
    def edit_order_size(
        self,
        order_id,
        new_size
    ):

        payload = {
            "id": int(order_id),
            "product_id": PRODUCT_ID,
            "size": int(new_size)
        }

        res = send_request(
            "PUT",
            "/v2/orders",
            payload=payload
        )

        if (
            res
            and res.get("success")
        ):

            logger.info(
                f"Order size synchronized | "
                f"id={order_id} "
                f"new_size={new_size}"
            )

            return True

        logger.warning(
            f"Could not edit order "
            f"id={order_id} "
            f"to size={new_size}"
        )

        return False


    # ==========================================
    # REVERSAL HELPER
    # ==========================================
    def close_position_and_confirm(
        self,
        side_to_close: str,
        size: int
    ) -> bool:

        """
        Existing opposite position ko
        market order se close karta hai.

        Uske baad Delta Exchange se confirm karta hai
        ki position size == 0 ho gaya hai.

        Confirm hone ke baad hi opposite setup continue hoga.
        """

        logger.info(
            f"Reversal: closing existing position "
            f"via MARKET "
            f"{side_to_close.upper()} "
            f"size={size}"
        )

        order = self.place_market_order(
            side_to_close,
            size
        )

        if order is None:

            logger.error(
                "Reversal: failed to submit "
                "closing market order. "
                "Aborting reversal this cycle."
            )

            return False

        waited = 0

        while (
            waited
            < POSITION_CLOSE_CONFIRM_TIMEOUT
        ):

            time.sleep(
                POSITION_CLOSE_POLL_INTERVAL
            )

            waited += (
                POSITION_CLOSE_POLL_INTERVAL
            )

            cur_size, _ = self.get_position()

            if cur_size == 0:

          # ==========================================
    # TP MANAGEMENT
    # ==========================================
    def setup_tp_orders(
        self,
        position_side: str,
        entry_price: float
    ):
        """
        Open position ke liye 3 separate
        reduce-only LIMIT TP orders place karta hai.

        BUY:
            TP1 = Entry + 300
            TP2 = Entry + 600
            TP3 = Entry + 900

        SELL:
            TP1 = Entry - 300
            TP2 = Entry - 600
            TP3 = Entry - 900
        """

        # Purane tracked TP orders cancel karo
        self.cancel_tracked_tp_orders()

        tp_side = (
            "sell"
            if position_side == "BUY"
            else "buy"
        )

        self.tp_orders = []

        for offset, qty in zip(
            TP_OFFSETS,
            TP_QTY_LOTS
        ):

            if position_side == "BUY":
                tp_price = (
                    entry_price + offset
                )
            else:
                tp_price = (
                    entry_price - offset
                )

            order = self.place_limit_order(
                side=tp_side,
                price=tp_price,
                size=qty,
                reduce_only=True
            )

            if order:

                self.tp_orders.append(
                    {
                        "id": order["id"],
                        "price": tp_price,
                        "size": qty,
                        "offset": offset,
                        "filled": False,
                    }
                )

                logger.info(
                    f"TP set | "
                    f"offset={offset} "
                    f"price={tp_price} "
                    f"size={qty} "
                    f"order_id={order['id']}"
                )

            else:

                logger.error(
                    f"Failed to place TP "
                    f"at offset {offset} "
                    f"for {position_side} position."
                )


    # ==========================================
    # CANCEL TRACKED TP ORDERS
    # ==========================================
    def cancel_tracked_tp_orders(self):

        for tp in self.tp_orders:

            if not tp.get("filled"):

                self.cancel_order_by_id(
                    tp["id"]
                )

        self.tp_orders = []


    # ==========================================
    # SYNCHRONIZE TP ORDERS
    # ==========================================
    def synchronize_tp_orders(
        self,
        current_position_size: int
    ):
        """
        TP orders ko live position ke size ke saath
        synchronize karta hai.

        Agar TP1 fill ho gaya:
            position size kam hoga
            remaining TP orders adjust honge.

        Agar TP2 fill ho gaya:
            remaining TP3 synchronize hoga.

        Agar position completely close:
            remaining TP cancel honge.
        """

        if not self.tp_orders:
            return

        # --------------------------------------
        # POSITION COMPLETELY CLOSED
        # --------------------------------------
        if current_position_size == 0:

            logger.info(
                "Position fully closed. "
                "Cancelling remaining TP orders."
            )

            self.cancel_tracked_tp_orders()

            self.position_side = None
            self.position_size = 0
            self.entry_price = 0.0

            return

        # --------------------------------------
        # CHECK EACH TP ORDER
        # --------------------------------------
        still_active = []

        for tp in self.tp_orders:

            if tp.get("filled"):
                continue

            order = self.get_order_by_id(
                tp["id"]
            )

            if order is None:

                still_active.append(tp)
                continue

            state = order.get("state")

            # ----------------------------------
            # TP FILLED
            # ----------------------------------
            if state == "closed":

                tp["filled"] = True

                logger.info(
                    f"TP FILLED | "
                    f"offset={tp['offset']} "
                    f"price={tp['price']} "
                    f"size={tp['size']} "
                    f"order_id={tp['id']}"
                )

            # ----------------------------------
            # TP CANCELLED
            # ----------------------------------
            elif state == "cancelled":

                logger.warning(
                    f"TP order cancelled externally | "
                    f"id={tp['id']}"
                )

            else:

                still_active.append(tp)

        # Filled TP ko tracking se hatao
        self.tp_orders = still_active

        active_orders = [
            tp
            for tp in self.tp_orders
            if not tp.get("filled")
        ]

        if not active_orders:
            return

        # --------------------------------------
        # POSITION SIZE RECONCILIATION
        # --------------------------------------
        remaining_tp_size = sum(
            tp["size"]
            for tp in active_orders
        )

        target_size = abs(
            current_position_size
        )

        if (
            remaining_tp_size
            != target_size
        ):

            logger.info(
                f"TP synchronization required | "
                f"TP size={remaining_tp_size} "
                f"Position size={target_size}"
            )

            # Sabse door wala TP choose karo
            furthest = max(
                active_orders,
                key=lambda t: t["offset"]
            )

            difference = (
                remaining_tp_size
                - target_size
            )

            new_size = (
                furthest["size"]
                - difference
            )

            if new_size > 0:

                if self.edit_order_size(
                    furthest["id"],
                    new_size
                ):

                    furthest["size"] = (
                        new_size
                    )

            else:

                logger.warning(
                    "TP synchronization mismatch "
                    "could not be automatically corrected."
                )


    # ==========================================
    # RESTART RECOVERY
    # ==========================================
    def recover_state(self):

        logger.info(
            "========== RESTART RECOVERY: "
            "checking live account state =========="
        )

        size, entry_price = (
            self.get_position()
        )

        open_orders = (
            self.get_open_orders()
        )

        logger.info(
            f"Recovery: current position "
            f"size={size}, "
            f"entry_price={entry_price}"
        )

        logger.info(
            f"Recovery: open orders "
            f"count={len(open_orders)}"
        )

        # --------------------------------------
        # SHOW EXISTING ORDERS
        # --------------------------------------
        for order in open_orders:

            logger.info(
                f"Recovery order | "
                f"id={order.get('id')} "
                f"side={order.get('side')} "
                f"price={order.get('limit_price')} "
                f"size={order.get('size')} "
                f"unfilled={order.get('unfilled_size')} "
                f"reduce_only={order.get('reduce_only')} "
                f"state={order.get('state')}"
            )

        # ======================================
        # POSITION EXISTS
        # ======================================
        if size != 0:

            self.position_side = (
                "BUY"
                if size > 0
                else "SELL"
            )

            self.position_size = size
            self.entry_price = entry_price

            tp_side = (
                "sell"
                if self.position_side == "BUY"
                else "buy"
            )

            self.tp_orders = []

            # ----------------------------------
            # RE-ATTACH EXISTING TP ORDERS
            # ----------------------------------
            for order in open_orders:

                reduce_only = order.get(
                    "reduce_only"
                )

                if (
                    reduce_only in (
                        True,
                        "true",
                        "True"
                    )
                    and
                    order.get("side")
                    == tp_side
                ):

                    try:

                        order_price = float(
                            order.get(
                                "limit_price"
                            )
                        )

                        order_size = int(
                            order.get(
                                "size"
                            )
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        continue

                    offset = abs(
                        order_price
                        - entry_price
                    )

                    self.tp_orders.append(
                        {
                            "id": order["id"],
                            "price": order_price,
                            "size": order_size,
                            "offset": offset,
                            "filled": False,
                        }
                    )

            # ----------------------------------
            # EXISTING TP FOUND
            # ----------------------------------
            if self.tp_orders:

                logger.info(
                    f"Recovery: re-attached "
                    f"{len(self.tp_orders)} "
                    f"existing TP order(s) "
                    f"to {self.position_side} position."
                )

            # ----------------------------------
            # POSITION BUT NO TP
            # ----------------------------------
            else:

                logger.warning(
                    "Recovery: open position found "
                    "but no TP orders detected. "
                    "Creating fresh TP orders."
                )

                self.setup_tp_orders(
                    self.position_side,
                    entry_price
                )

            # Existing position means no
            # pending entry should be tracked
            self.pending_entry_order_id = None
            self.pending_entry_side = None

        # ======================================
        # NO POSITION
        # ======================================
        else:

            # ----------------------------------
            # FIND PENDING ENTRY ORDER
            # ----------------------------------
            entry_candidates = []

            for order in open_orders:

                reduce_only = order.get(
                    "reduce_only"
                )

                if reduce_only in (
                    False,
                    "false",
                    "False",
                    None
                ):

                    entry_candidates.append(
                        order
                    )

            if entry_candidates:

                order = entry_candidates[0]

                self.pending_entry_order_id = (
                    order["id"]
                )

                self.pending_entry_side = (
                    order["side"]
                )

                logger.info(
                    f"Recovery: re-attached "
                    f"pending entry order "
                    f"id={order['id']} "
                    f"side={order['side']}"
                )

            # ----------------------------------
            # CANCEL ORPHAN TP ORDERS
            # ----------------------------------
            orphan_tp = []

            for order in open_orders:

                reduce_only = order.get(
                    "reduce_only"
                )

                if reduce_only in (
                    True,
                    "true",
                    "True"
                ):

                    orphan_tp.append(
                        order
                    )

            for order in orphan_tp:

                logger.warning(
                    f"Recovery: cancelling "
                    f"orphan reduce-only order "
                    f"id={order['id']} "
                    f"(no open position)."
                )

                self.cancel_order_by_id(
                    order["id"]
                )


    # ==========================================
    # CANCEL PENDING ENTRY
    # ==========================================
    def cancel_pending_entry(self):

        if (
            self.pending_entry_order_id
            is not None
        ):

            logger.info(
                f"Cancelling pending entry "
                f"order id="
                f"{self.pending_entry_order_id}"
            )

            self.cancel_order_by_id(
                self.pending_entry_order_id
            )

            self.pending_entry_order_id = None
            self.pending_entry_side = None


    # ==========================================
    # PROCESS BUY SIGNAL
    # ==========================================
    def process_buy_signal(
        self,
        signal_price: float
    ):

        logger.info(
            f"[BUY SIGNAL] "
            f"SuperTrend Bearish -> Bullish | "
            f"Signal Price={signal_price}"
        )

        pos_size, entry_price = (
            self.get_position()
        )

        # --------------------------------------
        # EXISTING SHORT POSITION
        # --------------------------------------
        if pos_size < 0:

            logger.info(
                f"BUY reversal detected. "
                f"Existing SELL position="
                f"{abs(pos_size)} lots"
            )

            # Cancel TP orders first
            self.cancel_tracked_tp_orders()

            # Close SHORT
            closed = (
                self.close_position_and_confirm(
                    side_to_close="buy",
                    size=abs(pos_size)
                )
            )

            if not closed:

                logger.error(
                    "BUY reversal aborted because "
                    "existing SELL position was "
                    "not confirmed closed."
                )

                return

        # --------------------------------------
        # FLAT
        # --------------------------------------
        elif pos_size == 0:

            self.cancel_pending_entry()

            # Cancel any orphan open orders
            open_orders = (
                self.get_open_orders()
            )

            for order in open_orders:

                reduce_only = order.get(
                    "reduce_only"
                )

                if reduce_only in (
                    True,
                    "true",
                    "True"
                ):

                    self.cancel_order_by_id(
                        order["id"]
                    )

        # --------------------------------------
        # BUY ENTRY
        # --------------------------------------
        limit_buy_price = round(
            signal_price
            - LIMIT_OFFSET_POINTS,
            1
        )

        logger.info(
            f"Placing LIMIT BUY | "
            f"Signal={signal_price} "
            f"Entry={limit_buy_price} "
            f"Offset=-{LIMIT_OFFSET_POINTS} "
            f"Qty={TOTAL_QTY_LOTS}"
        )

        order = self.place_limit_order(
            side="buy",
            price=limit_buy_price,
            size=TOTAL_QTY_LOTS,
            reduce_only=False
        )

        if order:

            self.pending_entry_order_id = (
                order["id"]
            )

            self.pending_entry_side = "buy"

            logger.info(
                f"Pending BUY entry saved | "
                f"id={order['id']}"
            )


    # ==========================================
    # PROCESS SELL SIGNAL
    # ==========================================
    def process_sell_signal(
        self,
        signal_price: float
    ):

        logger.info(
            f"[SELL SIGNAL] "
            f"SuperTrend Bullish -> Bearish | "
            f"Signal Price={signal_price}"
        )

        pos_size, entry_price = (
            self.get_position()
        )

        # --------------------------------------
        # EXISTING LONG POSITION
        # --------------------------------------
        if pos_size > 0:

            logger.info(
                f"SELL reversal detected. "
                f"Existing BUY position="
                f"{pos_size} lots"
            )

            # Cancel TP orders first
            self.cancel_tracked_tp_orders()

            # Close LONG
            closed = (
                self.close_position_and_confirm(
                    side_to_close="sell",
                    size=pos_size
                )
            )

            if not closed:

                logger.error(
                    "SELL reversal aborted because "
                    "existing BUY position was "
                    "not confirmed closed."
                )

                return

        # --------------------------------------
        # FLAT
        # --------------------------------------
        elif pos_size == 0:

            self.cancel_pending_entry()

            # Cancel orphan reduce-only orders
            open_orders = (
                self.get_open_orders()
            )

            for order in open_orders:

                reduce_only = order.get(
                    "reduce_only"
                )

                if reduce_only in (
                    True,
                    "true",
                    "True"
                ):

                    self.cancel_order_by_id(
                        order["id"]
                    )

        # --------------------------------------
        # SELL ENTRY
        # --------------------------------------
        limit_sell_price = round(
            signal_price
            + LIMIT_OFFSET_POINTS,
            1
        )

        logger.info(
            f"Placing LIMIT SELL | "
            f"Signal={signal_price} "
            f"Entry={limit_sell_price} "
            f"Offset=+{LIMIT_OFFSET_POINTS} "
            f"Qty={TOTAL_QTY_LOTS}"
        )

        order = self.place_limit_order(
            side="sell",
            price=limit_sell_price,
            size=TOTAL_QTY_LOTS,
            reduce_only=False
        )

        if order:

            self.pending_entry_order_id = (
                order["id"]
            )

            self.pending_entry_side = "sell"

            logger.info(
                f"Pending SELL entry saved | "
                f"id={order['id']}"
            )


    # ==========================================
    # STRATEGY LOGIC
    # ==========================================
    def execute_strategy_logic(self):

        df = (
            self.fetch_historical_candles()
        )

        if df.empty:

            logger.warning(
                "No candle data available."
            )

            return

        if len(df) < ATR_PERIOD + 5:

            logger.warning(
                "Insufficient candle data "
                "for SuperTrend calculation."
            )

            return

        # --------------------------------------
        # CALC
