# ============================================================
# BTCUSDT FUTURES SUPERTREND BOT
# Demo/Testnet first
#
# Strategy:
# Timeframe       : 5 minutes
# SuperTrend      : ATR 10 / Multiplier 3
#
# BUY:
#   Confirmed closed candle
#   BUY LIMIT = signal close - 50
#
# SELL:
#   Confirmed closed candle
#   SELL LIMIT = signal close + 50
#
# TP:
#   TP1 = +/- 300
#   TP2 = +/- 600
#   TP3 = +/- 900
#
# If SuperTrend reverses before entry is filled:
#   Cancel pending entry
#
# Python 3.10+
#
# Install:
# pip install requests pandas python-dotenv
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
# CONFIG
# ============================================================

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY", "")
API_SECRET = os.getenv("BINANCE_API_SECRET", "")

# DEMO / TESTNET
# Put your correct Binance Demo/Testnet REST URL here
BASE_URL = os.getenv(
    "BINANCE_BASE_URL",
    "https://testnet.binancefuture.com"
)

SYMBOL = "BTCUSDT"
INTERVAL = "5m"

ATR_PERIOD = 10
ST_MULTIPLIER = Decimal("3")

ENTRY_OFFSET = Decimal("50")

TP1_OFFSET = Decimal("300")
TP2_OFFSET = Decimal("600")
TP3_OFFSET = Decimal("900")

# IMPORTANT:
# 0.003 BTC allows approximately 0.001 BTC for each TP
ORDER_QTY = Decimal("0.003")

RECV_WINDOW = 5000

POLL_SECONDS = 3
CANDLE_CHECK_SECONDS = 5

STATE_FILE = "botstate.json"


# ============================================================
# SESSION
# ============================================================

session = requests.Session()

if API_KEY:
    session.headers.update({
        "X-MBX-APIKEY": API_KEY
    })


# ============================================================
# STATE
# ============================================================

state = {
    "pending_entry": None,
    "tp_orders": [],
    "last_signal": None,
    "last_closed_candle": None
}


def load_state():
    global state

    if not os.path.exists(STATE_FILE):
        return

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)

        if isinstance(saved, dict):
            state.update(saved)

    except Exception as e:
        print("STATE LOAD ERROR:", e)


def save_state():
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

    except Exception as e:
        print("STATE SAVE ERROR:", e)


# ============================================================
# API SIGNING
# ============================================================

def signed_request(method, path, params=None):

    if not API_KEY or not API_SECRET:
        raise RuntimeError(
            "BINANCE_API_KEY / BINANCE_API_SECRET missing."
        )

    params = dict(params or {})

    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = RECV_WINDOW

    query = urlencode(params)

    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    params["signature"] = signature

    url = BASE_URL + path

    response = session.request(
        method,
        url,
        params=params,
        timeout=15
    )

    try:
        data = response.json()
    except Exception:
        data = {
            "raw": response.text
        }

    if response.status_code >= 400:
        raise RuntimeError(
            f"HTTP {response.status_code}: {data}"
        )

    if isinstance(data, dict):
        if data.get("code", 0) not in (0, None):
            raise RuntimeError(
                f"BINANCE ERROR: {data}"
            )

    return data


def public_request(path, params=None):

    url = BASE_URL + path

    response = requests.get(
        url,
        params=params or {},
        timeout=15
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# EXCHANGE FILTERS
# ============================================================

TICK_SIZE = Decimal("0.10")
STEP_SIZE = Decimal("0.001")
MIN_QTY = Decimal("0.001")


def load_exchange_filters():

    global TICK_SIZE
    global STEP_SIZE
    global MIN_QTY

    data = public_request(
        "/fapi/v1/exchangeInfo"
    )

    for symbol_info in data["symbols"]:

        if symbol_info["symbol"] != SYMBOL:
            continue

        for f in symbol_info["filters"]:

            if f["filterType"] == "PRICE_FILTER":
                TICK_SIZE = Decimal(f["tickSize"])

            elif f["filterType"] == "LOT_SIZE":
                STEP_SIZE = Decimal(f["stepSize"])
                MIN_QTY = Decimal(f["minQty"])

        print()
        print("===== EXCHANGE FILTERS =====")
        print("Symbol   :", SYMBOL)
        print("Tick size:", TICK_SIZE)
        print("Step size:", STEP_SIZE)
        print("Min qty  :", MIN_QTY)
        print("============================")
        print()

        return

    raise RuntimeError(
        f"{SYMBOL} not found."
    )


def floor_step(value, step):

    value = Decimal(str(value))

    return (
        value / step
    ).to_integral_value(
        rounding=ROUND_DOWN
    ) * step


def price_format(price):

    return format(
        floor_step(price, TICK_SIZE),
        "f"
    )


def qty_format(quantity):

    return format(
        floor_step(quantity, STEP_SIZE),
        "f"
    )


# ============================================================
# MARKET DATA
# ============================================================

def get_klines(limit=250):

    data = public_request(
        "/fapi/v1/klines",
        {
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "limit": limit
        }
    )

    rows = []

    for k in data:

        rows.append({
            "open_time": int(k[0]),
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "close_time": int(k[6])
        })

    return pd.DataFrame(rows)


# ============================================================
# SUPERTREND
# ============================================================

def calculate_supertrend(df):

    data = df.copy().reset_index(drop=True)

    high = data["high"]
    low = data["low"]
    close = data["close"]

    previous_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - previous_close).abs()
    tr3 = (low - previous_close).abs()

    true_range = pd.concat(
        [tr1, tr2, tr3],
        axis=1
    ).max(axis=1)

    # Wilder RMA / TradingView-style ATR
    atr = true_range.ewm(
        alpha=1 / ATR_PERIOD,
        adjust=False,
        min_periods=ATR_PERIOD
    ).mean()

    hl2 = (high + low) / 2

    basic_upper = (
        hl2 +
        float(ST_MULTIPLIER) * atr
    )

    basic_lower = (
        hl2 -
        float(ST_MULTIPLIER) * atr
    )

    final_upper = [float("nan")] * len(data)
    final_lower = [float("nan")] * len(data)
    trend = [0] * len(data)
    supertrend = [float("nan")] * len(data)

    for i in range(len(data)):

        if pd.isna(atr.iloc[i]):
            continue

        if i == 0 or pd.isna(atr.iloc[i - 1]):

            final_upper[i] = basic_upper.iloc[i]
            final_lower[i] = basic_lower.iloc[i]

            if close.iloc[i] <= final_upper[i]:
                trend[i] = -1
                supertrend[i] = final_upper[i]
            else:
                trend[i] = 1
                supertrend[i] = final_lower[i]

            continue

        prev_upper = final_upper[i - 1]
        prev_lower = final_lower[i - 1]

        if (
            basic_upper.iloc[i] < prev_upper
            or close.iloc[i - 1] > prev_upper
        ):
            final_upper[i] = basic_upper.iloc[i]
        else:
            final_upper[i] = prev_upper

        if (
            basic_lower.iloc[i] > prev_lower
            or close.iloc[i - 1] < prev_lower
        ):
            final_lower[i] = basic_lower.iloc[i]
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
    data["supertrend"] = supertrend
    data["trend"] = trend

    return data


# ============================================================
# GET CONFIRMED SIGNAL
# ============================================================

def get_confirmed_signal():

    df = get_klines(250)

    # Last kline returned by REST can still be forming.
    # We deliberately remove it.
    if len(df) < ATR_PERIOD + 5:
        return None

    closed = df.iloc[:-1].copy()

    calculated = calculate_supertrend(closed)

    if len(calculated) < 3:
        return None

    previous = calculated.iloc[-2]
    current = calculated.iloc[-1]

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

    candle_id = int(current["open_time"])

    return {
        "signal": signal,
        "close": Decimal(
            str(current["close"])
        ),
        "candle_id": candle_id,
        "trend": int(current["trend"])
    }


# ============================================================
# ORDER HELPERS
# ============================================================

def get_open_order(order_id):

    try:

        return signed_request(
            "GET",
            "/fapi/v1/order",
            {
                "symbol": SYMBOL,
                "orderId": order_id
            }
        )

    except Exception as e:

        print(
            "ORDER STATUS ERROR:",
            e
        )

        return None


def get_position():

    data = signed_request(
        "GET",
        "/fapi/v2/positionRisk",
        {
            "symbol": SYMBOL
        }
    )

    if isinstance(data, list):

        for p in data:

            if p["symbol"] == SYMBOL:

                qty = Decimal(
                    str(p["positionAmt"])
                )

                entry_price = Decimal(
                    str(p["entryPrice"])
                )

                return qty, entry_price

    return Decimal("0"), Decimal("0")


# ============================================================
# CANCEL ORDER
# ============================================================

def cancel_order(order_id):

    try:

        result = signed_request(
            "DELETE",
            "/fapi/v1/order",
            {
                "symbol": SYMBOL,
                "orderId": order_id
            }
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
# CANCEL ALL BOT TP ORDERS
# ============================================================

def cancel_tp_orders():

    orders = state.get(
        "tp_orders",
        []
    )

    for item in orders:

        order_id = item.get(
            "orderId"
        )

        if order_id:

            print(
                "Cancelling TP:",
                order_id
            )

            cancel_order(order_id)

    state["tp_orders"] = []

    save_state()


# ============================================================
# PLACE ENTRY
# ============================================================

def place_entry(
    side,
    signal_price,
    candle_id
):

    if state["pending_entry"]:

        print(
            "Pending entry already exists."
        )

        return

    if side == "BUY":

        order_price = (
            signal_price -
            ENTRY_OFFSET
        )

    else:

        order_price = (
            signal_price +
            ENTRY_OFFSET
        )

    quantity = floor_step(
        ORDER_QTY,
        STEP_SIZE
    )

    if quantity < MIN_QTY:

        raise RuntimeError(
            f"ORDER_QTY too small. "
            f"Minimum={MIN_QTY}"
        )

    client_id = (
        f"ST_ENTRY_"
        f"{side}_"
        f"{candle_id}"
    )

    params = {

        "symbol": SYMBOL,

        "side": side,

        "type": "LIMIT",

        "timeInForce": "GTC",

        "quantity": qty_format(
            quantity
        ),

        "price": price_format(
            order_price
        ),

        "newClientOrderId": client_id,

        "newOrderRespType": "RESULT"
    }

    print()
    print("================================")
    print("PLACING ENTRY")
    print("Signal      :", side)
    print("Signal Price:", signal_price)
    print("Entry Price :", params["price"])
    print("Quantity    :", params["quantity"])
    print("================================")
    print()

    result = signed_request(
        "POST",
        "/fapi/v1/order",
        params
    )

    state["pending_entry"] = {

        "orderId": result["orderId"],

        "clientOrderId": client_id,

        "side": side,

        "signalPrice": str(
            signal_price
        ),

        "entryPrice": params["price"],

        "candleId": candle_id
    }

    state["last_signal"] = side

    save_state()

    print(
        "ENTRY ORDER CREATED:",
        result
    )


# ============================================================
# CANCEL PENDING ENTRY
# ============================================================

def cancel_pending_entry(reason):

    pending = state.get(
        "pending_entry"
    )

    if not pending:
        return

    print()
    print(
        "CANCEL ENTRY:",
        reason
    )

    cancel_order(
        pending["orderId"]
    )

    state["pending_entry"] = None

    save_state()


# ============================================================
# PLACE TP ORDERS
# ============================================================

def create_tp_orders(
    entry_side,
    entry_price,
    position_qty
):

    position_qty = abs(
        Decimal(str(position_qty))
    )

    if position_qty < MIN_QTY:
        print(
            "Position too small for TP orders."
        )
        return

    # Remove old TP orders first
    cancel_tp_orders()

    exit_side = (
        "SELL"
        if entry_side == "BUY"
        else "BUY"
    )

    if entry_side == "BUY":

        prices = [

            entry_price +
            TP1_OFFSET,

            entry_price +
            TP2_OFFSET,

            entry_price +
            TP3_OFFSET
        ]

    else:

        prices = [

            entry_price -
            TP1_OFFSET,

            entry_price -
            TP2_OFFSET,

            entry_price -
            TP3_OFFSET
        ]

    # Split position into 3 parts
    base_qty = floor_step(
        position_qty / Decimal("3"),
        STEP_SIZE
    )

    quantities = [
        base_qty,
        base_qty,
        base_qty
    ]

    # Give any rounding remainder to TP3
    used = base_qty * Decimal("3")

    remainder = floor_step(
        position_qty - used,
        STEP_SIZE
    )

    quantities[2] += remainder

    print()
    print("================================")
    print("CREATING TAKE PROFITS")
    print("Entry side :", entry_side)
    print("Entry price:", entry_price)
    print("Position   :", position_qty)
    print("================================")

    for i in range(3):

        qty = quantities[i]

        if qty < MIN_QTY:
            print(
                f"TP{i + 1} skipped: "
                f"quantity {qty} below minimum."
            )
            continue

        client_id = (
            f"ST_TP{i + 1}_"
            f"{int(time.time() * 1000)}"
        )

        params = {

            "symbol": SYMBOL,

            "side": exit_side,

            "type": "LIMIT",

            "timeInForce": "GTC",

            "quantity": qty_format(
                qty
            ),

            "price": price_format(
                prices[i]
            ),

            "reduceOnly": "true",

            "newClientOrderId": client_id,

            "newOrderRespType": "RESULT"
        }

        try:

            result = signed_request(
                "POST",
                "/fapi/v1/order",
                params
            )

            print(
                f"TP{i + 1} CREATED:",
                result
            )

            state["tp_orders"].append({

                "orderId":
                    result["orderId"],

                "clientOrderId":
                    client_id,

                "price":
                    params["price"],

                "quantity":
                    params["quantity"]
            })

            save_state()

        except Exception as e:

            print(
                f"TP{i + 1} ERROR:",
                e
            )


# ============================================================
# CHECK ENTRY
# ============================================================

def check_pending_entry():

    pending = state.get(
        "pending_entry"
    )

    if not pending:
        return

    order = get_open_order(
        pending["orderId"]
    )

    if not order:
        return

    status = order.get(
        "status"
    )

    executed_qty = Decimal(
        str(
            order.get(
                "executedQty",
                "0"
            )
        )
    )

    avg_price = Decimal(
        str(
            order.get(
                "avgPrice",
                "0"
            )
        )
    )

    print(
        "ENTRY STATUS:",
        status,
        "| filled:",
        executed_qty
    )

    # FULLY FILLED
    if status == "FILLED":

        entry_side = pending["side"]

        if avg_price <= 0:

            avg_price = Decimal(
                pending["entryPrice"]
            )

        print()
        print(
            "ENTRY FULLY FILLED!"
        )

        create_tp_orders(
            entry_side,
            avg_price,
            executed_qty
        )

        state["pending_entry"] = None

        save_state()

        return

    # PARTIAL FILL
    if status == "PARTIALLY_FILLED":

        print(
            "ENTRY PARTIALLY FILLED:",
            executed_qty
        )

        return

    # TERMINAL STATES
    if status in (
        "CANCELED",
        "EXPIRED",
        "REJECTED"
    ):

        print(
            "ENTRY FINISHED:",
            status
        )

        # If some quantity filled before cancellation,
        # protect that position with TPs.
        if executed_qty > 0:

            position_qty, position_price = (
                get_position()
            )

            if position_qty != 0:

                create_tp_orders(
                    pending["side"],
                    position_price,
                    abs(position_qty)
                )

        state["pending_entry"] = None

        save_state()


# ============================================================
# REVERSAL HANDLER
# ============================================================

def handle_signal(signal_data):

    if not signal_data:
        return

    signal = signal_data["signal"]

    candle_id = signal_data["candle_id"]

    signal_price = signal_data["close"]

    # Same candle already proces
