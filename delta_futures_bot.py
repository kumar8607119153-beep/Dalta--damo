import os
import time
import hmac
import hashlib
import requests
import pandas as pd
from decimal import Decimal
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# DELTA DEMO / TESTNET
# ============================================================

BASE_URL = os.getenv(
    "DELTA_BASE_URL",
    "https://cdn-ind.testnet.deltaex.org"
)

API_KEY = os.getenv("DELTA_API_KEY")
API_SECRET = os.getenv("DELTA_API_SECRET")

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

# Delta contracts में quantity contract-size पर निर्भर करेगी।
ORDER_SIZE = 1

STATE_FILE = "delta_bot_state.json"


# ============================================================
# API
# ============================================================

def require_api():
    if not API_KEY or not API_SECRET:
        raise RuntimeError(
            "DELTA_API_KEY और DELTA_API_SECRET सेट करें।"
        )


def make_signature(method, path, query="", body=""):
    timestamp = str(int(time.time()))

    message = (
        method
        + timestamp
        + path
        + query
        + body
    )

    signature = hmac.new(
        API_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    return timestamp, signature


def private_request(
    method,
    path,
    params=None,
    body=None
):
    require_api()

    params = params or {}

    query = urlencode(params)

    body_text = ""

    if body is not None:
        import json
        body_text = json.dumps(
            body,
            separators=(",", ":")
        )

    timestamp, signature = make_signature(
        method,
        path,
        query,
        body_text
    )

    headers = {
        "api-key": API_KEY,
        "signature": signature,
        "timestamp": timestamp,
        "Accept": "application/json"
    }

    if body is not None:
        headers["Content-Type"] = "application/json"

    url = BASE_URL + path

    response = requests.request(
        method,
        url,
        params=params,
        data=body_text if body is not None else None,
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
            f"Delta API error {response.status_code}: {data}"
        )

    return data


def public_request(path, params=None):

    response = requests.get(
        BASE_URL + path,
        params=params or {},
        timeout=20
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# PRODUCTS
# ============================================================

def get_product():

    data = public_request(
        f"/v2/products/{SYMBOL}"
    )

    result = data.get(
        "result",
        data
    )

    print("\n========== PRODUCT ==========")
    print("Symbol:", SYMBOL)
    print(result)
    print("=============================\n")

    return result


# ============================================================
# CANDLES
# ============================================================

def get_candles():

    # Delta API का candle endpoint
    data = public_request(
        "/v2/history/candles",
        {
            "symbol": SYMBOL,
            "resolution": "5m",
            "limit": 200
        }
    )

    result = data.get(
        "result",
        data
    )

    if not result:
        return pd.DataFrame()

    rows = []

    for x in result:

        rows.append({
            "time": x.get("time"),
            "open": float(x["open"]),
            "high": float(x["high"]),
            "low": float(x["low"]),
            "close": float(x["close"])
        })

    return pd.DataFrame(rows)


# ============================================================
# SUPERTREND
# ============================================================

def calculate_supertrend(df):

    data = df.copy()

    data["prev_close"] = data["close"].shift(1)

    tr1 = (
        data["high"] -
        data["low"]
    )

    tr2 = (
        data["high"] -
        data["prev_close"]
    ).abs()

    tr3 = (
        data["low"] -
        data["prev_close"]
    ).abs()

    data["tr"] = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    # Wilder ATR
    data["atr"] = data["tr"].ewm(
        alpha=1 / ATR_PERIOD,
        adjust=False,
        min_periods=ATR_PERIOD
    ).mean()

    data["hl2"] = (
        data["high"] +
        data["low"]
    ) / 2

    multiplier = float(
        ST_MULTIPLIER
    )

    data["basic_upper"] = (
        data["hl2"] +
        multiplier *
        data["atr"]
    )

    data["basic_lower"] = (
        data["hl2"] -
        multiplier *
        data["atr"]
    )

    upper = [None] * len(data)
    lower = [None] * len(data)

    trend = [0] * len(data)

    for i in range(len(data)):

        if pd.isna(data.loc[i, "atr"]):
            continue

        if i == 0 or upper[i - 1] is None:

            upper[i] = data.loc[
                i, "basic_upper"
            ]

            lower[i] = data.loc[
                i, "basic_lower"
            ]

            trend[i] = 1

            continue

        prev_upper = upper[i - 1]
        prev_lower = lower[i - 1]

        basic_upper = data.loc[
            i, "basic_upper"
        ]

        basic_lower = data.loc[
            i, "basic_lower"
        ]

        prev_close = data.loc[
            i - 1,
            "close"
        ]

        if (
            basic_upper < prev_upper
            or prev_close > prev_upper
        ):
            upper[i] = basic_upper
        else:
            upper[i] = prev_upper

        if (
            basic_lower > prev_lower
            or prev_close < prev_lower
        ):
            lower[i] = basic_lower
        else:
            lower[i] = prev_lower

        if trend[i - 1] == 1:

            if data.loc[i, "close"] < lower[i]:
                trend[i] = -1
            else:
                trend[i] = 1

        else:

            if data.loc[i, "close"] > upper[i]:
                trend[i] = 1
            else:
                trend[i] = -1

    data["trend"] = trend

    return data


# ============================================================
# SIGNAL
# ============================================================

def get_signal():

    df = get_candles()

    if len(df) < ATR_PERIOD + 5:
        return None

    # Last candle may still be forming.
    closed = df.iloc[:-1].copy()

    st = calculate_supertrend(
        closed
    )

    previous = st.iloc[-2]
    current = st.iloc[-1]

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

    else:
        signal = None

    return {
        "signal": signal,
        "price": Decimal(
            str(current["close"])
        ),
        "candle": current["time"]
    }


# ============================================================
# PLACE ORDER
# ============================================================

def place_limit_order(
    side,
    price,
    size
):

    body = {
        "product_symbol": SYMBOL,
        "limit_price": str(price),
        "size": int(size),
        "side": side.lower(),
        "order_type": "limit_order",
        "time_in_force": "gtc",
        "client_order_id":
            f"ST_{side}_{int(time.time())}"
    }

    print("\n==============================")
    print("PLACE ORDER")
    print("Side :", side)
    print("Price:", price)
    print("Size :", size)
    print("==============================")

    result = private_request(
        "POST",
        "/v2/orders",
        body=body
    )

    print("ORDER RESULT:")
    print(result)

    return result


# ============================================================
# CANCEL ORDER
# ============================================================

def cancel_order(order_id):

    result = private_request(
        "DELETE",
        f"/v2/orders/{order_id}"
    )

    print(
        "CANCEL RESULT:",
        result
    )

    return result


# ============================================================
# TP ORDERS
# ============================================================

def create_tp_orders(
    entry_side,
    entry_price,
    size
):

    if entry_side == "BUY":

        exit_side = "sell"

        prices = [
            entry_price + TP1_OFFSET,
            entry_price + TP2_OFFSET,
            entry_price + TP3_OFFSET
        ]

    else:

        exit_side = "buy"

        prices = [
            entry_price - TP1_OFFSET,
            entry_price - TP2_OFFSET,
            entry_price - TP3_OFFSET
        ]

    # तीन बराबर हिस्से
    base = size // 3

    if base <= 0:
        print(
            "Position size TP के लिए बहुत छोटा है."
        )
        return

    sizes = [
        base,
        base,
        size - base * 2
    ]

    for i in range(3):

        if sizes[i] <= 0:
            continue

        body = {

            "product_symbol": SYMBOL,

            "limit_price":
                str(prices[i]),

            "size":
                int(sizes[i]),

            "side":
                exit_side,

            "order_type":
                "limit_order",

            "time_in_force":
                "gtc",

            "reduce_only":
                True,

            "client_order_id":
                f"ST_TP{i+1}_{int(time.time())}"
        }

        try:

            result = private_request(
                "POST",
                "/v2/orders",
                body=body
            )

            print(
                f"TP{i+1}:",
                result
            )

        except Exception as e:

            print(
                f"TP{i+1} ERROR:",
                e
            )


# ============================================================
# MAIN STRATEGY
# ============================================================

last_candle = None
pending_order = None


def run_strategy():

    global last_candle
    global pending_order

    signal_data = get_signal()

    if not signal_data:
        return

    candle = signal_data["candle"]

    if candle == last_candle:
        return

    last_candle = candle

    signal = signal_data["signal"]

    price = signal_data["price"]

    print()
    print("================================")
    print("NEW CLOSED CANDLE")
    print("Price :", price)
    print("Signal:", signal)
    print("================================")

    if not signal:
        return

    # Reversal से पहले का pending order cancel
    if pending_order:

        old_side = pending_order["side"]

        if old_side != signal:

            try:

                cancel_order(
                    pending_order["order_id"]
                )

            except Exception as e:

                print(
                    "Cancel error:",
                    e
                )

            pending_order = None

    # Entry price
    if signal == "BUY":

        entry_price = (
            price -
            ENTRY_OFFSET
        )

        side = "buy"

    else:

        entry_price = (
            price +
            ENTRY_OFFSET
        )

        side = "sell"

    result = place_limit_order(
        side,
        entry_price,
        ORDER_SIZE
    )

    order_result = result.get(
        "result",
        result
    )

    order_id = order_result.get(
        "id"
    )

    if order_id:

        pending_order = {
            "order_id": order_id,
            "side": signal,
            "price": str(entry_price)
        }

        print(
            "Pending entry:",
            pending_order
        )


# ============================================================
# CONNECTION TEST
# ============================================================

def test_connection():

    print()
    print("================================")
    print("DELTA FUTURES DEMO BOT")
    print("================================")
    print("Base URL:", BASE_URL)
    print("Symbol  :", SYMBOL)
    print("TF      :", INTERVAL)
    print("ST      : ATR 10 / 3")
    print("================================")

    product = get_product()

    print(
        "Product loaded successfully."
    )


# ============================================================
# MAIN
# ============================================================

def main():

    test_connection()

    print(
        "\nBot started..."
    )

    while True:

        try:

            run_strategy()

        except Exception as e:

            print(
                "\nBOT ERROR:",
                e
            )

        time.sleep(
            10
        )


if __name__ == "__main__":
    main()
