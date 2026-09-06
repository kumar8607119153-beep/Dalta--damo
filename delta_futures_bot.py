# ============================================================
# DELTA EXCHANGE INDIA - BTCUSD FUTURES DEMO BOT
#
# TESTNET / DEMO
#
# Timeframe : 5 minutes
# SuperTrend: ATR 10 / Multiplier 3
#
# BUY:
#   SuperTrend Bearish -> Bullish
#   BUY LIMIT = signal close - 50
#
# SELL:
#   SuperTrend Bullish -> Bearish
#   SELL LIMIT = signal close + 50
#
# TP:
#   TP1 = +/- 300
#   TP2 = +/- 600
#   TP3 = +/- 900
#
# If SuperTrend reverses before entry fills:
#   Pending entry is cancelled.
#
# IMPORTANT:
# This file uses Delta Exchange India V2 API.
#
# Environment variables:
#   DELTA_API_KEY
#   DELTA_API_SECRET
#   DELTA_BASE_URL
#
# Demo/Testnet:
#   https://cdn-ind.testnet.deltaex.org
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
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()


API_KEY = os.getenv("DELTA_API_KEY", "")
API_SECRET = os.getenv("DELTA_API_SECRET", "")

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://cdn-ind.testnet.deltaex.org"
).rstrip("/")


# ============================================================
# STRATEGY SETTINGS
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
#
# Delta BTCUSD contract_value shown by your API:
# 0.001 BTC per contract.
#
# ORDER_SIZE = number of contracts.
#
# Example:
# 3 contracts ≈ 0.003 BTC notional.
#

ORDER_SIZE = 3


# ============================================================
# BOT TIMING
# ============================================================

POLL_SECONDS = 5

STATE_FILE = "delta_bot_state.json"


# ============================================================
# SESSION
# ============================================================

session = requests.Session()

session.headers.update({
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "delta-futures-demo-bot/1.0"
})


# ============================================================
# STATE
# ============================================================

state = {
    "pending_entry": None,
    "tp_orders": [],
    "last_signal": None,
    "last_candle": None
}


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
# HELPERS
# ============================================================

def require_credentials():

    if not API_KEY:
        raise RuntimeError(
            "Missing DELTA_API_KEY"
        )

    if not API_SECRET:
        raise RuntimeError(
            "Missing DELTA_API_SECRET"
        )


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
# PUBLIC GET
# ============================================================

def public_get(
    path,
    params=None
):

    url = BASE_URL + path

    response = session.get(
        url,
        params=params or {},
        timeout=20
    )

    if response.status_code >= 400:

        try:
            error_data = response.json()
        except Exception:
            error_data = response.text

        raise RuntimeError(
            f"PUBLIC API ERROR "
            f"{response.status_code}: "
            f"{error_data}"
        )

    return response.json()


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
            separators=(
                ",",
                ":"
            )
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
            "delta-futures-demo-bot/1.0"
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
# SERVER TIME
# ============================================================

def check_server():

    try:

        data = public_get(
            "/v2/time"
        )

        print(
            "Server:",
            data
        )

    except Exception:

        print(
            "Server time endpoint "
            "not required."
        )


# ============================================================
# PRODUCT
# ============================================================

PRODUCT_ID = None

TICK_SIZE = Decimal("0.1")

CONTRACT_VALUE = Decimal("0.001")


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
            "Product information "
            "not returned."
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
    print(
        "========== PRODUCT =========="
    )

    print(
        "Symbol:",
        SYMBOL
    )

    print(
        "Product ID:",
        PRODUCT_ID
    )

    print(
        "Tick size:",
        TICK_SIZE
    )

    print(
        "Contract value:",
        CONTRACT_VALUE
    )

    print(
        "============================="
    )
    print()


# ============================================================
# PRICE ROUNDING
# ============================================================

def floor_price(
    price
):

    value = Decimal(
        str(price)
    )

    return (
        value / TICK_SIZE
    ).to_integral_value(
        rounding=ROUND_DOWN
    ) * TICK_SIZE


def price_string(
    price
):

    return format(
        floor_price(price),
        "f"
    )


# ============================================================
# HISTORICAL CANDLES
# ============================================================
#
# IMPORTANT FIX:
#
# Delta /v2/history/candles requires:
#   resolution
#   symbol
#   start
#   end
#
# It does NOT use:
#   limit=200
#
# ============================================================

def get_candles(
    candle_count=250
):

    now = int(
        time.time()
    )

    # 5 minutes = 300 seconds
    candle_seconds = 300

    end = now

    start = (
        end
        - candle_count
        * candle_seconds
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

        # Delta normally returns:
        # time, open, high, low, close, volume

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

def calculate_supertrend(
    df
):

    data = df.copy()

    high = data["high"]

    low = data["low"]

    close = data["close"]

    previous_close = close.shift(1)

    tr1 = (
        high - low
    )

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
        + float(
            ST_MULTIPLIER
        )
        * atr
    )

    basic_lower = (
        hl2
        - float(
            ST_MULTIPLIER
        )
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
            or close.iloc[i - 1]
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
            or close.iloc[i - 1]
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

    data["supertrend"] = (
        supertrend
    )

    data["trend"] = trend

    return data


# ============================================================
# CONFIRMED SIGNAL
# ============================================================

def get_confirmed_signal():

    df = get_candles(
        250
    )

    if len(df) < (
        ATR_PERIOD + 5
    ):

        return None

    # Delta candle data can contain
    # the current unfinished candle.
    #
    # Remove the newest candle.
    closed = df.iloc[:-1].copy()

    calculated = (
        calculate_supertrend(
            closed
        )
    )

    if len(calculated) < 3:

        return None

    previous = (
        calculated.iloc[-2]
    )

    current = (
        calculated.iloc[-1]
    )

    signal = None

    if (
        previous["trend"] == -1
        and current["trend"] == 1
    ):

        signal = "BUY"

    elif (
        previous["trend"] == 1
        and current["trend"] == -1
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

        if int(
            position.get(
                "product_id",
                -1
            )
        ) == PRODUCT_ID:

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
# PLACE LIMIT ORDER
# ============================================================

def place_limit_order(
    side,
    size,
    price,
    client_order_id
):

    payload = {

        "order_type":
            "limit_order",

        "size":
            int(size),

        "side":
            side.lower(),

        "limit_price":
            price_string(price),

        "product_id":
            PRODUCT_ID,

        "time_in_force":
            "gtc",

        "client_order_id":
            client_order_id
    }

    print()
    print(
        "PLACING LIMIT ORDER"
    )

    print(
        "Side:",
        side
    )

    print(
        "Size:",
        size
    )

    print(
        "Price:",
        payload["limit_price"]
    )

    result = signed_request(

        "POST",

        "/v2/orders",

        body=payload
    )

    print(
        "ORDER RESULT:",
        result
    )

    return result


# ============================================================
# CANCEL ORDER
# ============================================================

def cancel_order(
    order_id
):

    try:

        result = signed_request(

            "DELETE",

            f"/v2/orders/{order_id}"
        )

        print(
            "CANCEL RESULT:",
            result
        )

        return True

    except Exception as e:

        print(
            "CANCEL ERROR:",
            e
        )

        return False


# ============================================================
# CANCEL PENDING ENTRY
# ============================================================

def cancel_pending_entry(
    reason
):

    pending = state.get(
        "pending_entry"
    )

    if not pending:

        return

    print()
    print(
        "CANCELLING PENDING ENTRY"
    )

    print(
        "Reason:",
        reason
    )

    order_id = pending.get(
        "order_id"
    )

    if order_id:

        cancel_order(
            order_id
        )

    state[
        "pending_entry"
    ] = None

    save_state()


# ============================================================
# PLACE ENTRY
# ============================================================

def place_entry(
    side,
    signal_price,
    candle_id
):

    if state.get(
        "pending_entry"
    ):

        print(
            "Pending entry already exists."
        )

        return

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

    client_id = (
        f"ST{side[:1]}"
        f"{int(time.
