# ============================================================
# ONE CYCLE OF LOGIC (called repeatedly inside the loop)
# ============================================================

def run_cycle(api, state):

    now_str = indian_time(time.time())
    print("=" * 70)
    print(f"[{now_str}] Cycle chal rahi hai... (checking market)")

    candle_response = api.candles()
    df = make_dataframe(candle_response)

    if df.empty:
        print(f"[{now_str}] STATUS: Delta se candle data nahi mila.")
        return

    current_candle_start = (int(time.time()) // CANDLE_SECONDS) * CANDLE_SECONDS
    df = df[df["time"] < current_candle_start].copy().reset_index(drop=True)

    if len(df) < ATR_PERIOD + 5:
        print(f"[{now_str}] STATUS: SuperTrend ke liye enough candles nahi hain.")
        return

    df = calculate_supertrend(df)

    signal_rows = df[df["SIGNAL"].isin(["BUY", "SELL"])].copy()
    last_candle = df.iloc[-1]
    current_trend = int(last_candle["TREND"])
    current_close = float(last_candle["close"])

    direction_text = "BUY / BULLISH" if current_trend == -1 else "SELL / BEARISH"

    # ------------------------------------------------------------
    # ALWAYS PRINT CURRENT STATUS (heartbeat) - har cycle mein
    # ------------------------------------------------------------

    print(f"[{now_str}] SUPERTREND DIRECTION : {direction_text}")
    print(f"[{now_str}] LAST CLOSE           : {show_price(current_close)}")
    print(f"[{now_str}] ENTRY ORDER PLACED?  : {'YES - ID ' + str(state.get('last_entry_order_id')) if state.get('last_entry_order_id') else 'NO'}")
    print(f"[{now_str}] TP ORDERS PLACED?    : {'YES' if state.get('tp_placed') else 'NO'}")

    # ------------------------------------------------------------
    # CANCEL PENDING OPPOSITE ORDER ON DIRECTION CHANGE
    # ------------------------------------------------------------

    open_orders_response = api.open_orders()
    open_orders = get_result(open_orders_response)
    if not isinstance(open_orders, list):
        open_orders = []

    print(f"[{now_str}] OPEN ORDERS COUNT     : {len(open_orders)}")

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
                f"[{now_str}] ACTION: Pending {order_side_existing.upper()} order {order_id} "
                f"CANCELLED (direction changed). Success: {cancel_result.get('success')}"
            )
            if order_id == state.get("last_entry_order_id"):
                state["last_entry_order_id"] = None
                state["tp_placed"] = False

    if len(signal_rows) == 0:
        print(f"[{now_str}] STATUS: Abhi tak koi confirmed SuperTrend signal nahi mila.")
        return

    current_entry = signal_rows.iloc[-1]
    signal_direction = str(current_entry["SIGNAL"])
    signal_entry_price = float(current_entry["close"])
    signal_time = indian_time(current_entry["time"])

    print(f"[{now_str}] LATEST SIGNAL          : {signal_direction} @ {show_price(signal_entry_price)} (Candle: {signal_time})")

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
        print(f"[{now_str}] STATUS: Is signal candle ({signal_time}) ka order pehle hi ho chuka hai. Wait...")
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
                f"[{now_str}] ACTION: NEW {signal_direction} ENTRY order placed. "
                f"Order ID: {new_order_id} @ {show_price(limit_entry_price)}"
            )
        else:
            print(f"[{now_str}] ERROR: ENTRY ORDER FAILED - {entry_result.get('error')}")

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

        print(f"[{now_str}] POSITION SIZE CHECK   : {position_size}")

        if position_size != 0:
            tp_side = state.get("tp_side")

            tp1_result = api.place_limit_order(side=tp_side, size=TP1_QTY, limit_price=state["target1"])
            tp2_result = api.place_limit_order(side=tp_side, size=TP2_QTY, limit_price=state["target2"])
            tp3_result = api.place_limit_order(side=tp_side, size=TP3_QTY, limit_price=state["target3"])

            print(
                f"[{now_str}] ACTION: TP orders placed. "
                f"TP1: {tp1_result.get('success')} | TP2: {tp2_result.get('success')} | TP3: {tp3_result.get('success')}"
            )

            state["tp_placed"] = True
        else:
            print(f"[{now_str}] STATUS: Entry order abhi pending hai (position open nahi hui). TP orders wait kar rahe hain.")
