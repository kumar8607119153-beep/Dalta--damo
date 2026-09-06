import os
import time
import json
import hmac
import hashlib
import requests
from decimal import Decimal, ROUND_DOWN

# ============================================================
# PIONEX FUTURES SUPER TREND BOT
# ============================================================

BASE_URL = "https://api.pionex.com"

API_KEY = os.getenv("PIONEX_API_KEY")
API_SECRET = os.getenv("PIONEX_SECRET_KEY")

SYMBOL = "BTC_USDT_PERP"

# ---------------- SETTINGS ----------------

TIMEFRAME = "5M"

ATR_PERIOD = 10
ATR_MULTIPLIER = Decimal("3")

QUANTITY = Decimal("0.001")

ENTRY_OFFSET = Decimal("50")

TP1_POINTS = Decimal("300")
TP2_POINTS = Decimal("600")
TP3_POINTS = Decimal("900")

CHECK_SECONDS = 2

# ------------------------------------------------------------
# TEST MODE
#
# True  = bot will test API/order request and then cancel it
# False = normal live strategy
#
# FIRST RUN SHOULD BE TRUE
# ------------------------------------------------------------

TEST_MODE = True


# ============================================================
# API SIGNATURE
# ============================================================

def signed_request(method, path, params=None, body=None):

    params = dict(params or {})

    params["timestamp"] = str(
        int(time.time() * 1000)
    )

    query = "&".join(
        f"{key}={params[key]}"
        for key in sorted(params)
    )

    request_path = path

    if query:
        request_path += "?" + query

    body_text = ""

    if method in ("POST", "DELETE"):

        body_text = json.dumps(
            body or {},
            separators=(",", ":")
        )

    message = (
        method.upper()
        + request_path
        + body_text
    )

    signature = hmac.new(
        API_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "PIONEX-KEY": API_KEY,
        "PIONEX-SIGNATURE": signature,
        "Content-Type": "application/json"
    }

    return params, headers


# ============================================================
# API CALL
# ============================================================

def api_call(
    method,
    path,
    params=None,
    body=None
):

    params, headers = signed_request(
        method,
        path,
        params,
        body
    )

    url = BASE_URL + path

    if method == "GET":

        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=15
        )

    elif method == "POST":

        response = requests.post(
            url,
            params=params,
            json=body or {},
            headers=headers,
            timeout=15
        )

    elif method == "DELETE":

        response = requests.delete(
            url,
            params=params,
            json=body or {},
            headers=headers,
            timeout=15
        )

    else:
        raise ValueError(
            "Unsupported HTTP method"
        )

    print(
        "HTTP:",
        response.status_code
    )

    try:
        data = response.json()
    except Exception:

        print(
            "RAW RESPONSE:",
            response.text
        )

        raise

    if not data.get("result", False):

        print(
            "PIONEX ERROR:",
            data
        )

        raise RuntimeError(
            data
        )

    return data


# ============================================================
# MARKET KLINES
# ============================================================

def get_candles():

    data = api_call(
        "GET",
        "/api/v1/market/klines",
        params={
            "symbol": SYMBOL,
            "interval": TIMEFRAME,
            "limit": 100
        }
    )

    rows = data["data"]["klines"]

    candles = []

    for row in rows:

        if isinstance(row, dict):

            candles.append({
                "time": int(row["time"]),
                "open": Decimal(
                    str(row["open"])
                ),
                "high": Decimal(
                    str(row["high"])
                ),
                "low": Decimal(
                    str(row["low"])
                ),
                "close": Decimal(
                    str(row["close"])
                )
            })

        else:

            candles.append({
                "time": int(row[0]),
                "open": Decimal(
                    str(row[1])
                ),
                "high": Decimal(
                    str(row[2])
                ),
                "low": Decimal(
                    str(row[3])
                ),
                "close": Decimal(
                    str(row[4])
                )
            })

    return candles


# ============================================================
# ATR
# ============================================================

def calculate_atr(
    candles,
    period
):

    if len(candles) < period + 1:
        return None

    true_ranges = []

    for i in range(1, len(candles)):

        high = candles[i]["high"]
        low = candles[i]["low"]

        previous_close = (
            candles[i - 1]["close"]
        )

        tr = max(
            high - low,
            abs(high - previous_close),
            abs(low - previous_close)
        )

        true_ranges.append(tr)

    return (
        sum(
            true_ranges[-period:]
        )
        / Decimal(period)
    )


# ============================================================
# SUPERTREND 10 / 3
# ============================================================

def calculate_supertrend(
    candles
):

    if len(candles) < ATR_PERIOD + 2:
        return None

    direction = 1

    upper_band = None
    lower_band = None

    for i in range(
        ATR_PERIOD,
        len(candles)
    ):

        current = candles[:i + 1]

        current_atr = calculate_atr(
            current,
            ATR_PERIOD
        )

        if current_atr is None:
            continue

        high = candles[i]["high"]
        low = candles[i]["low"]
        close = candles[i]["close"]

        hl2 = (
            high + low
        ) / Decimal("2")

        basic_upper = (
            hl2
            + ATR_MULTIPLIER * current_atr
        )

        basic_lower = (
            hl2
            - ATR_MULTIPLIER * current_atr
        )

        if upper_band is None:

            upper_band = basic_upper
            lower_band = basic_lower

        else:

            previous_close = (
                candles[i - 1]["close"]
            )

            if (
                basic_upper < upper_band
                or previous_close > upper_band
            ):

                upper_band = basic_upper

            if (
                basic_lower > lower_band
                or previous_close < lower_band
            ):

                lower_band = basic_lower

        if (
            direction == -1
            and close > upper_band
        ):

            direction = 1

        elif (
            direction == 1
            and close < lower_band
        ):

            direction = -1

    if direction == 1:
        return "BUY"

    return "SELL"


# ============================================================
# PLACE LIMIT ORDER
# ============================================================

def place_limit_order(
    side,
    price,
    quantity,
    reduce_only=False
):

    client_id = (
        "ST10-" +
        str(int(time.time() * 1000))
    )

    body = {
        "symbol": SYMBOL,
        "side": side,
        "type": "LIMIT",
        "size": str(quantity),
        "price": str(price),
        "reduceOnly": reduce_only,
        "clientOrderId": client_id
    }

    print()
    print("================================")
    print("SENDING ORDER")
    print("SIDE :", side)
    print("PRICE:", price)
    print("SIZE :", quantity)
    print("REDUCE:", reduce_only)
    print("================================")

    data = api_call(
        "POST",
        "/uapi/v1/trade/order",
        body=body
    )

    order_id = (
        data["data"]["orderId"]
    )

    print(
        "ORDER ACCEPTED"
    )

    print(
        "ORDER ID:",
        order_id
    )

    return order_id


# ============================================================
# GET ORDER
# ============================================================

def get_order(order_id):

    data = api_call(
        "GET",
        "/uapi/v1/trade/order",
        params={
            "symbol": SYMBOL,
            "orderId": order_id
        }
    )

    return data["data"]


# ============================================================
# CANCEL ORDER
# ============================================================

def cancel_order(order_id):

    print(
        "CANCELLING:",
        order_id
    )

    api_call(
        "DELETE",
        "/uapi/v1/trade/order",
        body={
            "symbol": SYMBOL,
            "orderId": order_id
        }
    )

    print(
        "ORDER CANCELLED"
    )


# ============================================================
# TP ORDERS
# ============================================================

def create_tp_orders(
    entry_price,
    entry_side,
    quantity
):

    part = (
        quantity / Decimal("3")
    )

    if entry_side == "BUY":

        exit_side = "SELL"

        tp1 = (
            entry_price
            + TP1_POINTS
        )

        tp2 = (
            entry_price
            + TP2_POINTS
        )

        tp3 = (
            entry_price
            + TP3_POINTS
        )

    else:

        exit_side = "BUY"

        tp1 = (
            entry_price
            - TP1_POINTS
        )

        tp2 = (
            entry_price
            - TP2_POINTS
        )

        tp3 = (
            entry_price
            - TP3_POINTS
        )

    print(
        "TP1:",
        tp1
    )

    print(
        "TP2:",
        tp2
    )

    print(
        "TP3:",
        tp3
    )

    place_limit_order(
        exit_side,
        tp1,
        part,
        True
    )

    place_limit_order(
        exit_side,
        tp2,
        part,
        True
    )

    place_limit_order(
        exit_side,
        tp3,
        quantity - part - part,
        True
    )


# ============================================================
# FIRST API / ORDER TEST
# ============================================================

def run_order_test():

    print()
    print("======================================")
    print(" PIONEX FUTURES API ORDER TEST")
    print("======================================")

    candles = get_candles()

    if not candles:

        print(
            "ERROR: No market data"
        )

        return

    # Use latest closed candle
    candle = candles[-2]

    price = candle["close"]

    print(
        "BTC PRICE:",
        price
    )

    # BUY LIMIT 50 points below
    test_price = (
        price - ENTRY_OFFSET
    )

    print(
        "TEST BUY LIMIT:",
        test_price
    )

    try:

        order_id = place_limit_order(
            "BUY",
            test_price,
            QUANTITY,
            False
        )

        print()
        print(
            "SUCCESS:"
        )

        print(
            "Pionex accepted the order."
        )

        print(
            "Order ID:",
            order_id
        )

        time.sleep(2)

        order = get_order(
            order_id
        )

        print(
            "ORDER STATUS:",
            order.get("status")
        )

        # Test mode = cancel after checking
        if TEST_MODE:

            print()
            print(
                "TEST MODE = TRUE"
            )

            print(
                "Cancelling test order..."
            )

            cancel_order(
                order_id
            )

            print(
                "TEST COMPLETED"
            )

    except Exception as e:

        print()
        print(
            "ORDER TEST FAILED"
        )

        print(
            repr(e)
        )


# ============================================================
# MAIN STRATEGY
# ============================================================

def run_strategy():

    print()
    print(
        "======================================"
    )
    print(
        " PIONEX FUTURES SUPER TREND BOT"
    )
    print(
        "======================================"
    )

    print(
        "SYMBOL:",
        SYMBOL
    )

    print(
        "TIMEFRAME:",
        TIMEFRAME
    )

    print(
        "SUPERTREND:",
        ATR_PERIOD,
        ATR_MULTIPLIER
    )

    print(
        "QUANTITY:",
        QUANTITY
    )

    print(
        "ENTRY OFFSET:",
        ENTRY_OFFSET
    )

    print(
        "TP:",
        TP1_POINTS,
        TP2_POINTS,
        TP3_POINTS
    )

    entry_order_id = None
    entry_side = None
    entry_price = None

    last_closed_candle = None

    tp_created = False

    while True:

        try:

            candles = get_candles()

            if len(candles) < (
                ATR_PERIOD + 5
            ):

                time.sleep(
                    CHECK_SECONDS
                )

                continue

            # Latest candle may still be running.
            # Therefore use previous candle.
            closed_candle = candles[-2]

            candle_time = (
                closed_candle["time"]
            )

            # ------------------------------------------------
            # Existing pending entry
            # ------------------------------------------------

            if entry_order_id:

                order = get_order(
                    entry_order_id
                )

                status = order.get(
                    "status"
                )

                filled_size = Decimal(
                    str(
                        order.get(
                            "filledSize",
                            "0"
                        )
                    )
                )

                print(
                    "ENTRY STATUS:",
                    status,
                    "FILLED:",
                    filled_size
                )

                # Pionex Futures uses CLOSED
                # for filled/cancelled/rejected.
                if (
                    status == "CLOSED"
                    and filled_size > 0
                ):

                    actual_price = Decimal(
                        str(
                            order.get(
                                "price",
                                entry_price
                            )
                        )
                    )

                    print(
                        "ENTRY FILLED:",
                        actual_price
                    )

                    if not tp_created:

                        create_tp_orders(
                            actual_price,
                            entry_side,
                            filled_size
                        )

                        tp_created = True

                    entry_order_id = None

                elif (
                    status == "CLOSED"
                    and filled_size == 0
                ):

                    entry_order_id = None
                    entry_side = None
                    entry_price = None

            # ------------------------------------------------
            # Process only once per closed candle
            # ------------------------------------------------

            if (
                candle_time
                == last_closed_candle
            ):

                time.sleep(
                    CHECK_SECONDS
                )

                continue

            last_closed_candle = candle_time

            signal = calculate_supertrend(
                candles
            )

            close_price = (
                closed_candle["close"]
            )

            print()
            print(
                "5M CANDLE CLOSED"
            )

            print(
                "PRICE:",
                close_price
            )

            print(
                "SIGNAL:",
                signal
            )

            # ------------------------------------------------
            # Existing pending entry
            # ------------------------------------------------

            if entry_order_id:

                if signal != entry_side:

                    print(
                        "SIGNAL REVERSED"
                    )

                    print(
                        "CANCELLING ENTRY"
                    )

                    cancel_order(
                        entry_order_id
                    )

                    entry_order_id = None
                    entry_side = None
                    entry_price = None
                    tp_created = False

                continue

            # ------------------------------------------------
            # BUY
            # ------------------------------------------------

            if signal == "BUY":

                entry_price = (
                    close_price
                    - ENTRY_OFFSET
                )

                entry_order_id = (
                    place_limit_order(
                        "BUY",
                        entry_price,
                        QUANTITY,
                        False
                    )
                )

                entry_side = "BUY"
                tp_created = False

            # ------------------------------------------------
            # SELL
            # ------------------------------------------------

            elif signal == "SELL":

                entry_price = (
                    close_price
                    + ENTRY_OFFSET
                )

                entry_order_id = (
                    place_limit_order(
                        "SELL",
                        entry_price,
                        QUANTITY,
                        False
                    )
                )

                entry_side = "SELL"
                tp_created = False

        except Exception as e:

            print()
            print(
                "BOT ERROR:"
            )

            print(
                repr(e)
            )

        time.sleep(
            CHECK_SECONDS
        )


# ============================================================
# START
# ============================================================

def main():

    if not API_KEY:

        raise RuntimeError(
            "PIONEX_API_KEY is missing"
        )

    if not API_SECRET:

        raise RuntimeError(
            "PIONEX_SECRET_KEY is missing"
        )

    # --------------------------------------------------------
    # FIRST: test API/order
    # --------------------------------------------------------

    run_order_test()

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # TEST_MODE=True means test order is cancelled.
    #
    # Strategy will NOT be started automatically.
    #
    # Change TEST_MODE=False only after the order test
    # successfully reaches Pionex.
    # --------------------------------------------------------

    if TEST_MODE:

        print()
        print(
            "======================================"
        )

        print(
            "TEST_MODE = TRUE"
        )

        print(
            "API/order test finished."
        )

        print(
            "No live strategy started."
        )

        print(
            "After confirming the test order works,"
        )

        print(
            "change TEST_MODE to False."
        )

        print(
            "======================================"
        )

        return

    # --------------------------------------------------------
    # LIVE STRATEGY
    # --------------------------------------------------------

    run_
