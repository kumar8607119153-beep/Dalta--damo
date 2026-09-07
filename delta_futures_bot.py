# ============================================================
# DELTA EXCHANGE INDIA - BTCUSD FUTURES
# PRODUCTION / REAL TRADING BOT
#
# STRATEGY
# ------------------------------------------------------------
# Timeframe       : 5 minutes
# SuperTrend      : ATR 10 / Multiplier 3
#
# BUY:
#   Bearish -> Bullish
#   LIMIT = signal candle close - 50
#
# SELL:
#   Bullish -> Bearish
#   LIMIT = signal candle close + 50
#
# TP:
#   BUY  : Entry +300 / +600 / +900
#   SELL : Entry -300 / -600 / -900
#
# BEFORE ENTRY FILLS:
#   Opposite SuperTrend signal
#   -> cancel pending entry
#
# SAFETY:
#   - Production API
#   - Client order IDs
#   - Duplicate protection
#   - Fill detection
#   - Restart recovery
#   - Existing-position recovery
#   - Existing-order recovery
#   - Reduce-only TP orders
#
# ENVIRONMENT VARIABLES:
#   DELTA_API_KEY
#   DELTA_API_SECRET
#   DELTA_BASE_URL
#
# Production:
#   https://api.india.delta.exchange
#
# Install:
#   pip install requests pandas python-dotenv
# ============================================================

import os
import time
import json
import hmac
import hashlib
from decimal import Decimal, ROUND_DOWN
from urllib.parse import urlencode

import requests
import pandas as pd
from dotenv import load_dotenv


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

API_KEY = os.getenv("DELTA_API_KEY", "").strip()
API_SECRET = os.getenv("DELTA_API_SECRET", "").strip()

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://api.india.delta.exchange"
).rstrip("/")


# ============================================================
# PRODUCTION CHECK
# ============================================================

if "testnet" in BASE_URL.lower():
    raise RuntimeError(
        "TESTNET URL DETECTED. "
        "Production bot refuses to start."
    )


# ============================================================
# STRATEGY
# ============================================================

SYMBOL = "BTCUSD"
INTERVAL = "5m"

ATR_PERIOD = 10
ST_MULTIPLIER = Decimal("3")

ENTRY_OFFSET = Decimal("50")

TP1_OFFSET = Decimal("300")
TP2_OFFSET = Decimal("600")
TP3_OFFSET = Decimal("900")


# ============================================================
# ORDER SIZE
# ============================================================

# 3 contracts:
# TP1 = 1 contract
# TP2 = 1 contract
# TP3 = 1 contract

ORDER_SIZE = 3


# ============================================================
# BOT
# ============================================================

POLL_SECONDS = 5

STATE_FILE = "delta_bot_state.json"

REQUEST_TIMEOUT = (5, 25)


# ============================================================
# HTTP SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "delta-btcusd-production-bot/1.0"
})


# ============================================================
# GLOBAL PRODUCT DATA
# ============================================================

PRODUCT_ID = None

TICK_SIZE = Decimal("0.1")

CONTRACT_VALUE = Decimal("0.001")


# ============================================================
# STATE
# ============================================================

state = {
    "pending_entry": None,

    "tp_orders": [],

    "last_signal": None,

    "last_candle": None,

    "position_side": None,

    "entry_price": None,

    "entry_order_id": None,

    "entry_client_order_id": None
}


# ============================================================
# STATE LOAD
# ============================================================

def load_state():

    global state

    if not os.path.exists(STATE_FILE):
        print("No previous state file found.")
        return

    try:

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            saved = json.load(f)

        if isinstance(saved, dict):
            state.update(saved)

        print("State recovered.")

    except Exception as e:

        print(
            "STATE LOAD ERROR:",
            e
        )


# ============================================================
# STATE SAVE
# ============================================================

def save_state():

    temporary_file = STATE_FILE + ".tmp"

    try:

        with open(
            temporary_file,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                state,
                f,
                indent=2
            )

        os.replace(
            temporary_file,
            STATE_FILE
        )

    except Exception as e:

        print(
            "STATE SAVE ERROR:",
            e
        )


# ============================================================
# CREDENTIALS
# ============================================================

def require_credentials():

    if not API_KEY:

        raise RuntimeError(
            "DELTA_API_KEY is missing."
        )

    if not API_SECRET:

        raise RuntimeError(
            "DELTA_API_SECRET is missing."
        )


# ============================================================
# SIGNATURE
# ============================================================

def generate_signature(
    method,
    timestamp,
    path,
    query_string,
    body
):

    message = (
        method
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


# ============================================================
# PUBLIC REQUEST
# ============================================================

def public_get(
    path,
    params=None
):

    url = BASE_URL + path

    response = session.get(
        url,
        params=params or {},
        timeout=REQUEST_TIMEOUT
    )

    try:
        data = response.json()
    except Exception:
        data = response.text

    if response.status_code >= 400:

        raise RuntimeError(
            f"PUBLIC API ERROR "
            f"{response.status_code}: "
            f"{data}"
        )

    return data


# ============================================================
# SIGNED REQUEST
# ============================================================

def signed_request(
    method,
    path,
    params=None,
    body=None
):

    require_credentials()

    method = method.upper()

    params = params or {}

    body = body or {}

    timestamp = str(
        int(time.time())
    )

    query_string = ""

    if params:

        query_string = (
            "?"
            + urlencode(
                params,
                doseq=True
            )
        )

    body_string = ""

    if body:

        body_string = json.dumps(
            body,
            separators=(",", ":")
        )

    signature = generate_signature(
        method,
        timestamp,
        path,
        query_string,
        body_string
    )

    headers = {

        "Accept":
            "application/json",

        "Content-Type":
            "application/json",

        "api-key":
            API_KEY,

        "timestamp":
            timestamp,

        "signature":
            signature,

        "User-Agent":
            "delta-btcusd-production-bot/1.0"
    }

    url = BASE_URL + path

    response = session.request(
        method,
        url,
        params=params,
        data=body_string,
        headers=headers,
        timeout=REQUEST_TIMEOUT
    )

    try:

        data = response.json()

    except Exception:

        data = {
            "raw": response.text
        }

    if response.status_code >= 400:

        raise RuntimeError(
            f"HTTP {response.status_code}: "
            f"{data}"
        )

    if isinstance(data, dict):

        if data.get("success") is False:

            raise RuntimeError(
                f"DELTA API ERROR: {data}"
            )

    return data


# ============================================================
# PRODUCT
# ============================================================

def load_product():

    global PRODUCT_ID
    global TICK_SIZE
    global CONTRACT_VALUE

    data = public_get(
        f"/v2/products/{SYMBOL}"
    )

    result = data.get(
        "result",
        data
    )

    if not result:

        raise RuntimeError(
            "BTCUSD product information not returned."
        )

    PRODUCT_ID = int(
        result["id"]
    )

    TICK_SIZE = Decimal(
        str(
            result.get(
                "tick_size",
                "0.1"
            )
        )
    )

    CONTRACT_VALUE = Decimal(
        str(
            result.get(
                "contract_value",
                "0.001"
            )
        )
    )

    print()
    print("========================================")
    print(" PRODUCTION PRODUCT")
    print("========================================")
    print("Symbol         :", SYMBOL)
    print("Product ID     :", PRODUCT_ID)
    print("Tick size      :", TICK_SIZE)
    print("Contract value :", CONTRACT_VALUE)
    print("========================================")
    print()


# ============================================================
# PRICE FORMAT
# ============================================================

def floor_price(price):

    value = Decimal(
        str(price)
    )

    return (
        value / TICK_SIZE
    ).to_integral_value(
        rounding=ROUND_DOWN
    ) * TICK_SIZE


def price_string(price):

    return format(
        floor_price(price),
        "f"
    )


# ============================================================
# CANDLES
# ============================================================

def get_candles(
    candle_count=250
):

    now = int(
        time.time()
    )

    candle_seconds = 300

    end = now

    start = (
        end
        - candle_count * candle_seconds
        - candle_seconds
    )

    params = {

        "resolution":
            INTERVAL,

        "symbol":
            SYMBOL,

        "start":
            start,

        "end":
            end
    }

    data = public_get(
        "/v2/history/candles",
        params
    )

    rows = data.get(
        "result",
        []
    )

    if not rows:

        raise RuntimeError(
            "No candle data returned."
        )

    result = []

    for candle in rows:

        result.append({

            "time":
                int(
                    candle["time"]
                ),

            "open":
                float(
                    candle["open"]
                ),

            "high":
                float(
                    candle["high"]
                ),

            "low":
                float(
                    candle["low"]
                ),

            "close":
                float(
                    candle["close"]
                ),

            "volume":
                float(
                    candle.get(
                        "volume",
                        0
                    )
                )
        })

    df = pd.DataFrame(
        result
    )

    df = df.sort_values(
        "time"
    ).reset_index(
        drop=True
    )

    return df


# ============================================================
# SUPERTREND
# ============================================================

def calculate_supertrend(df):

    data = df.copy()

    high = data["high"]

    low = data["low"]

    close = data["close"]

    previous_close = close.shift(1)

    tr1 = high - low

    tr2 = (
        high - previous_close
    ).abs()

    tr3 = (
        low - previous_close
    ).abs()

    true_range = pd.concat(
        [
            tr1,
            tr2,
            tr3
        ],
        axis=1
    ).max(
        axis=1
    )

    atr = true_range.ewm(
        alpha=1 / ATR_PERIOD,
        adjust=False,
        min_periods=ATR_PERIOD
    ).mean()

    hl2 = (
        high + low
    ) / 2

    basic_upper = (
        hl2
        + float(ST_MULTIPLIER)
        * atr
    )

    basic_lower = (
        hl2
        - float(ST_MULTIPLIER)
        * atr
    )

    final_upper = [
        float("nan")
    ] * len(data)

    final_lower = [
        float("nan")
    ] * len(data)

    trend = [
        0
    ] * len(data)

    supertrend = [
        float("nan")
    ] * len(data)

    for i in range(
        len(data)
    ):

        if pd.isna(
            atr.iloc[i]
        ):

            continue

        if (
            i == 0
            or pd.isna(
                atr.iloc[i - 1]
            )
        ):

            final_upper[i] = (
                basic_upper.iloc[i]
            )

            final_lower[i] = (
                basic_lower.iloc[i]
            )

            if (
                close.iloc[i]
                <= final_upper[i]
            ):

                trend[i] = -1

                supertrend[i] = (
                    final_upper[i]
                )

            else:

                trend[i] = 1

                supertrend[i] = (
                    final_lower[i]
                )

            continue

        prev_upper = (
            final_upper[i - 1]
        )

        prev_lower = (
            final_lower[i - 1]
        )

        if (
            basic_upper.iloc[i]
            < prev_upper
            or
            close.iloc[i - 1]
            > prev_upper
        ):

            final_upper[i] = (
                basic_upper.iloc[i]
            )

        else:

            final_upper[i] = (
                prev_upper
            )

        if (
            basic_lower.iloc[i]
            > prev_lower
            or
            close.iloc[i - 1]
            < prev_lower
        ):

            final_lower[i] = (
                basic_lower.iloc[i]
            )

        else:

            final_lower[i] = (
                prev_lower
            )

        previous_trend = (
            trend[i - 1]
        )

        if previous_trend == 1:

            if (
                close.iloc[i]
                < final_lower[i]
            ):

                trend[i] = -1

                supertrend[i] = (
                    final_upper[i]
                )

            else:

                trend[i] = 1

                supertrend[i] = (
                    final_lower[i]
                )

        else:

            if (
                close.iloc[i]
                > final_upper[i]
            ):

                trend[i] = 1

                supertrend[i] = (
                    final_lower[i]
                )

            else:

                trend[i] = -1

                supertrend[i] = (
                    final_upper[i]
                )

    data["atr"] = atr

    data["supertrend"] = supertrend

    data["trend"] = trend

    return data


# ============================================================
# CONFIRMED SIGNAL
# ============================================================

def get_confirmed_signal():

    df = get_candles(
        250
    )

    if len(df) < ATR_PERIOD + 5:

        return None

    # Last candle may still be forming.
    closed = df.iloc[:-1].copy()

    calculated = calculate_supertrend(
        closed
    )

    if len(calculated) < 3:

        return None

    previous = calculated.iloc[-2]

    current = calculated.iloc[-1]

    signal = None

    if (
        previous["trend"] == -1
        and
        current["trend"] == 1
    ):

        signal = "BUY"

    elif (
        previous["trend"] == 1
        and
        current["trend"] == -1
    ):

        signal = "SELL"

    return {

        "signal":
            signal,

        "close":
            Decimal(
                str(
                    current["close"]
                )
            ),

        "candle_id":
            int(
                current["time"]
            ),

        "trend":
            int(
                current["trend"]
            )
    }


# ============================================================
# GET OPEN ORDERS
# ============================================================

def get_open_orders():

    result = signed_request(
        "GET",
        "/v2/orders",
        {
            "product_id":
                PRODUCT_ID,

            "state":
                "open"
        }
    )

    return result.get(
        "result",
        []
    )


# ============================================================
# GET ORDER BY CLIENT ID
# ============================================================

def get_order_by_client_id(
    client_order_id
):

    if not client_order_id:

        return None

    try:

        result = signed_request(
            "GET",
            "/v2/orders/client_order_id/"
            + client_order_id
        )

        return result.get(
            "result"
        )

    except Exception as e:

        print(
            "CLIENT ORDER LOOKUP ERROR:",
            e
        )

        return None


# ============================================================
# GET POSITION
# ============================================================

def get_position():

    result = signed_request(
        "GET",
        "/v2/positions",
        {
            "product_id":
                PRODUCT_ID
        }
    )

    data = result.get(
        "result",
        []
    )

    if isinstance(
        data,
        dict
    ):

        data = [data]

    for position in data:

        try:

            pid = int(
                position.get(
                    "product_id",
                    -1
                )
            )

        except Exception:

            continue

        if pid != PRODUCT_ID:

            continue

        size = Decimal(
            str(
                position.get(
                    "size",
                    "0"
                )
            )
        )

        entry_price = Decimal(
            str(
                position.get(
                    "entry_price",
                    "0"
                )
            )
        )

        return (
            size,
            entry_price
        )

    return (
        Decimal("0"),
        Decimal("0")
    )


# ============================================================
# ORDER STATE HELPERS
# ============================================================

def normalize_order_result(
    result
):

    if not result:

        return None

    if isinstance(
        result,
        dict
    ):

        if "result" in result:

            return result["result"]

        return result

    return None


def get_order_id(
    order
):

    if not order:

        return None

    return (
        order.get("id")
        or
        order.get("order_id")
    )


# ============================================================
# DUPLICATE PROTECTION
# ============================================================

def find_existing_client_order(
    client_order_id
):

    # First inspect open orders.
    try:

        orders = get_open_orders()

        for order in orders:

            if (
                order.get(
                    "client_order_id"
                )
                ==
                client_order_id
            ):

                return order

    except Exception as e:

        print(
            "OPEN ORDER DUPLICATE CHECK ERROR:",
            e
        )

    # Then ask Delta directly.
    return get_order_by_client_id(
        client_order_id
    )


# ============================================================
# PLACE LIMIT ORDER
# ============================================================

def place_limit_order(
    side,
    size,
    price,
    client_order_id,
    reduce_only=False
):

    client_order_id = str(
        client_order_id
    )[:32]

    existing = (
