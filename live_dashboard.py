# ============================================================
# CURRENT + PREVIOUS SUPERTREND ENTRY
# ============================================================

signal_rows = df[df["SIGNAL"] != ""].copy()

st.header("🎯 SUPERTREND ENTRIES")

if len(signal_rows) >= 1:

    current = signal_rows.iloc[-1]

    current_signal = current["SIGNAL"]
    current_price = float(current["close"])

    current_time = datetime.fromtimestamp(
        int(current["time"]),
        tz=timezone.utc
    ).strftime("%Y-%m-%d %H:%M:%S UTC")

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "CURRENT ENTRY",
            f"{current_signal} @ {current_price:,.2f}"
        )
        st.caption(current_time)


    if len(signal_rows) >= 2:

        previous = signal_rows.iloc[-2]

        previous_signal = previous["SIGNAL"]
        previous_price = float(previous["close"])

        previous_time = datetime.fromtimestamp(
            int(previous["time"]),
            tz=timezone.utc
        ).strftime("%Y-%m-%d %H:%M:%S UTC")

        with c2:
            st.metric(
                "PREVIOUS ENTRY",
                f"{previous_signal} @ {previous_price:,.2f}"
            )
            st.caption(previous_time)

    else:

        with c2:
            st.metric(
                "PREVIOUS ENTRY",
                "NO PREVIOUS SIGNAL"
            )

else:

    st.info("Abhi koi SuperTrend entry signal nahi mila.")
