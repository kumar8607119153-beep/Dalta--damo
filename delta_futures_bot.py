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
# DELTA EXCHANGE INDIA - BTCUSD PRODUCTION BOT
#
# TIMEFRAME : 5 MINUTES
# SUPERTREND: ATR 10 / MULTIPLIER 3
#
# BUY  : Bearish -> Bullish
#        Entry = signal candle close - 50
#
# SELL : Bullish -> Bearish
#        Entry = signal candle close + 50
#
# TP1 / TP2 / TP3:
# BUY  = Entry +300 / +600 / +900
# SELL = Entry -300 / -600 / -900
#
# FEATURES:
# - Production API
# - Duplicate order protection
# - Closed candle only
# - Entry fill detection
# - TP1/TP2/TP3
# - Reversal cancellation
# - Exchange-side restart recovery
# - No local state dependency for open orders
# ============================================================


load_dotenv()


# ============================================================
# CONFIG
# ============================================================

API_KEY = os.getenv("DELTA_API_KEY", "").strip()
API_SECRET = os.getenv("DELTA_API_SECRET", "").strip()

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://api.india.delta.exchange"
).rstrip("/")

SYMBOL = "BTCUSD"
INTERVAL = "5m"

ATR_PERIOD = 10
ST_MULTIPLIER = Decimal("3")

ENTRY_OFFSET = Decimal("50")

TP1_OFFSET = Decimal("300")
TP2_OFFSET = Decimal("600")
TP3_OFFSET = Decimal("900")

ORDER_SIZE = 3

POLL_SECONDS = 5

CLIENT_PREFIX = "STBOT"

STATE_FILE = "delta_bot_state.json"


# ============================================================
# SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "delta-futures-production-bot/1.0"
})


# ============================================================
# GLOBAL PRODUCT DATA
# ============================================================

PRODUCT_ID = None
TICK_SIZE = Decimal("0.1")


# ============================================================
# LOCAL STATE
# ============================================================

state = {
    "last_signal_candle": None,
    "active_side": None,
    "entry_price": None,
    "entry_order_id": None,
    "tp_order_ids": []
}


# ============================================================
# STATE FUNCTIONS
# ============================================================

def load_state():

    global state

    if not os.path.exists(STATE_FILE):
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

    except Exception as e:

        print("STATE LOAD ERROR:", e)


def save_state():

    try:

        with open(
            STATE_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                state,
                f,
                indent=2
            )

    except Exception as e:

        print("STATE SAVE ERROR:", e)


# ============================================================
# CREDENTIALS
# ============================================================

def require_credentials():

    if not API_KEY:
        raise RuntimeError("DELTA_API_KEY is missing")

    if not API_SECRET:
        raise RuntimeError("DELTA_API_SECRET is missing")


# ============================================================
# SIGNATURE
# ============================================================

def generate_signature(
    method,
    timestamp,
    path,
    query_string,
    body_string
):

    message = (
        method
        + timestamp
        + path
        + query_string
        + body_string
    )

    return hmac.new(
        API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


# ============================================================
# PUBLIC GET
# ============================================================

def public_get(path, params=None):

    url = BASE_URL + path

    response = session.get(
        url,
        params=params or {},
        timeout=20
    )

    try:
        data = response.json()
    except Exception:
        data = response.text

    if response.status_code >= 400:

        raise RuntimeError(
            f"PUBLIC HTTP {response.status_code}: {data}"
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

        query_string = "?" + urlencode(
            params,
            doseq=True
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

        "signature":
            signature,

        "timestamp":
            timestamp,

        "User-Agent":
            "delta-futures-production-bot/1.0"
    }

    url = BASE_URL + path

    response = session.request(
        method,
        url,
        params=params,
        data=body_string,
        headers=headers,
        timeout=20
    )

    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}

    if response.status_code >= 400:

        raise RuntimeError(
            f"HTTP {response.status_code}: {data}"
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

    data = public_get(
        f"/v2/products/{SYMBOL}"
    )

    result = data.get(
        "result",
        data
    )

    if not result:
        raise RuntimeError(
            "BTCUSD product information unavailable"
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

    print()
    print("========== PRODUCT ==========")
    print("Symbol    :", SYMBOL)
    print("Product ID:", PRODUCT_ID)
    print("Tick size :", TICK_SIZE)
    print("=============================")
    print()


# ============================================================
# PRICE
# ============================================================

def normalize_price(price):

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
        normalize_price(price),
        "f"
    )


# ============================================================
# CANDLES
# ============================================================

def get_candles(count=250):

    now = int(
        time.time()
    )

    seconds = 300

    start = (
        now
        - count * seconds
        - seconds
    )

    params = {

        "resolution":
            INTERVAL,

        "symbol":
            SYMBOL,

        "start":
            start,

        "end":
            now
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
            "No candle data returned"
        )

    result = []

    for candle in rows:

        result.append({

            "time":
                int(candle["time"]),

            "open":
                float(candle["open"]),

            "high":
                float(candle["high"]),

            "low":
                float(candle["low"]),

            "close":
                float(candle["close"]),

            "volume":
                float(
                    candle.get(
                        "volume",
                        0
                    )
                )
        })

    df = pd.DataFrame(result)

    df = df.sort_values(
        "time"
    ).drop_duplicates(
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

    upper = (
        hl2
        + float(ST_MULTIPLIER)
        * atr
    )

    lower = (
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

    for i in range(len(data)):

        if pd.isna(atr.iloc[i]):
            continue

        if (
            i == 0
            or pd.isna(atr.iloc[i - 1])
        ):

            final_upper[i] = upper.iloc[i]
            final_lower[i] = lower.iloc[i]

            trend[i] = (
                1
                if close.iloc[i] > final_upper[i]
                else -1
            )

            supertrend[i] = (
                final_lower[i]
                if trend[i] == 1
                else final_upper[i]
            )

            continue

        prev_upper = final_upper[i - 1]
        prev_lower = final_lower[i - 1]

        if (
            upper.iloc[i] < prev_upper
            or close.iloc[i - 1] > prev_upper
        ):

            final_upper[i] = upper.iloc[i]

        else:

            final_upper[i] = prev_upper

        if (
            lower.iloc[i] > prev_lower
            or close.iloc[i - 1] < prev_lower
        ):

            final_lower[i] = lower.iloc[i]

        else:

            final_lower[i] = prev_lower

        previous_trend = trend[i - 1]

        if previous_trend == 1:

            if close.iloc[i] < final_lower[i]:

                trend[i] = -1

                supertrend[i] = final_upper[i]

            else:

                trend[i] = 1

                supertrend[i] = final_lower[i]

        else:

            if close.iloc[i] > final_upper[i]:

                trend[i] = 1

                supertrend[i] = final_lower[i]

            else:

                trend[i] = -1

                supertrend[i] = final_upper[i]

    data["atr"] = atr
    data["trend"] = trend
    data["supertrend"] = supertrend

    return data


# ============================================================
# CONFIRMED SIGNAL
# ============================================================

def get_confirmed_signal():

    df = get_candles(250)

    if len(df) < ATR_PERIOD + 5:
        return None

    # Remove currently-forming candle.
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
        int(previous["trend"]) == -1
        and int(current["trend"]) == 1
    ):

        signal = "BUY"

    elif (
        int(previous["trend"]) == 1
        and int(current["trend"]) == -1
    ):

        signal = "SELL"

    return {

        "signal":
            signal,

        "close":
            Decimal(
                str(current["close"])
            ),

        "candle_id":
            int(current["time"]),

        "trend":
            int(current["trend"])
    }


# ============================================================
# OPEN ORDERS
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
# POSITION
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

    rows = result.get(
        "result",
        []
    )

    if isinstance(rows, dict):
        rows = [rows]

    for position in rows:

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

        entry = Decimal(
            str(
                position.get(
                    "entry_price",
                    "0"
                )
            )
        )

        return size, entry

    return Decimal("0"), Decimal("0")


# ============================================================
# CLIENT ID
# ============================================================

def make_client_id(tag):

    # Must remain <= 32 characters.
    return (
        f"{CLIENT_PREFIX}_{tag}_"
        f"{int(time.time() * 1000)}"
    )[:32]


# ============================================================
# FIND OUR ORDERS
# ============================================================

def bot_orders(open_orders):

    result = []

    for order in open_orders:

        client_id = str(
            order.get(
                "client_order_id",
                ""
            )
        )

        if client_id.startswith(
            CLIENT_PREFIX + "_"
        ):

            result.append(order)

    return result


# ============================================================
# CANCEL ORDER
# ============================================================

def cancel_order(order_id):

    try:

        result = signed_request(
            "DELETE",
            f"/v2/orders/{order_id}"
        )

        print(
            "CANCEL:",
            order_id,
            result
        )

        return True

    except Exception as e:

        print(
            "CANCEL ERROR:",
            order_id,
            e
        )

        return False


# ============================================================
# CANCEL BOT ENTRY ORDERS
# ============================================================

def cancel_bot_entry_orders(
    open_orders,
    reason
):

    print(
        "Cancelling bot entry orders:",
        reason
    )

    for order in open_orders:

        client_id = str(
            order.get(
                "client_order_id",
                ""
            )
        )

        if not client_id.startswith(
            CLIENT_PREFIX + "_ENTRY_"
        ):
            continue

        order_id = order.get("id")

        if order_id:
            cancel_order(order_id)


# ============================================================
# PLACE LIMIT ORDER
# ============================================================

def place_limit(
    side,
    size,
    price,
    client_id,
    reduce_only=False
):

    payload = {

        "product_id":
            PRODUCT_ID,

        "product_symbol":
            SYMBOL,

        "limit_price":
            price_string(price),

        "size":
            int(size),

        "side":
            side.lower(),

        "order_type":
            "limit_order",

        "time_in_force":
            "gtc",

        "mmp":
            "disabled",

        "post_only":
            False,

        "reduce_only":
            reduce_only,

        "client_order_id":
            client_id
    }

    print()
    print("========== ORDER ==========")
    print("Side :", side)
    print("Size :", size)
    print("Price:", payload["limit_price"])
    print("ID   :", client_id)
    print("RO   :", reduce_only)
    print("===========================")

    return signed_request(
        "POST",
        "/v2/orders",
        body=payload
    )


# ============================================================
# PLACE ENTRY
# ============================================================

def place_entry(
    side,
    signal_price,
    candle_id
):

    if side == "BUY":

        entry_price = (
            signal_price
            - ENTRY_OFFSET
        )

    else:

        entry_price = (
            signal_price
            + ENTRY_OFFSET
        )

    client_id = make_client_id(
        f"ENTRY_{side[0]}"
    )

    result = place_limit(
        side,
        ORDER_SIZE,
        entry_price,
        client_id,
        False
    )

    order = result.get(
        "result",
        result
    )

    order_id = order.get(
        "id"
    )

    state["last_signal_candle"] = candle_id

    state["active_side"] = side

    state["entry_price"] = str(
        entry_price
    )

    state["entry_order_id"] = order_id

    save_state()

    print()
    print("ENTRY CREATED")
    print("Side :", side)
    print("Price:", entry_price)
    print("Order:", order_id)

    return order


# ============================================================
# CHECK ENTRY FILL
# ============================================================

def entry_is_filled(
    open_orders
):

    for order in open_orders:

        client_id = str(
            order.get(
                "client_order_id",
                ""
            )
        )

        if not client_id.startswith(
            CLIENT_PREFIX + "_ENTRY_"
        ):
            continue

        state_value = str(
            order.get(
                "state",
                ""
            )
        ).lower()

        if state_value == "closed":

            return True

    return False


# ============================================================
# PLACE TP ORDERS
# ============================================================

def ensure_tp_orders(
    side,
    entry_price,
    position_size,
    open_orders
):

    if position_size <= 0:
        return

    # Existing bot TP orders.
    existing = []

    for order in open_orders:

        client_id = str(
            order.get(
                "client_order_id",
                ""
            )
        )

        if client_id.startswith(
            CLIENT_PREFIX + "_TP"
        ):

            existing.append(order)

    # Do not duplicate TPs.
    if existing:
        print(
            "Existing TP orders found:",
            len(existing)
        )
        return

    # For 3 contracts:
    # TP1 = 1
    # TP2 = 1
    # TP3 = remaining
    total = int(
        abs(position_si
