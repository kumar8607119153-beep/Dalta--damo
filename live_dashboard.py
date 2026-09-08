import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import requests
import json
import os

st.set_page_config(
    page_title="Master Hub Trading Dashboard",
    page_icon="📈",
    layout="wide"
)

# Admin Owner Header
st.markdown("""
    <div style="background-color: #161b22; padding: 12px 20px; border-radius: 8px; border: 1px solid #30363d; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
        <div>
            <span style="color: #8b949e; font-size: 13px;">Admin Owner:</span><br>
            <span style="color: #ffffff; font-size: 16px; font-weight: bold;">Sanjay Rana</span>
        </div>
        <div>
            <span style="color: #8b949e; font-size: 13px;">Contact Number:</span><br>
            <span style="color: #00ffcc; font-size: 16px; font-weight: bold;">8930814389</span>
        </div>
        <div>
            <span style="color: #8b949e; font-size: 13px;">PIN Number:</span><br>
            <span style="color: #00ffcc; font-size: 16px; font-weight: bold;">0000</span>
        </div>
    </div>
""", unsafe_allow_html=True)

st.title("🛡️ Master Hub: Algorithmic Trading & Live Monitoring Dashboard")
st.markdown("Real-time monitoring interface synchronized with live SuperTrend bot calculations.")

# ------------------------------------------------------------------------------
# SuperTrend & Price Calculation Engine (Matching delta_futures_bot.py)
# ------------------------------------------------------------------------------
def round_to_tick(price: float, tick_size: float = 0.5) -> float:
    return round(round(price / tick_size) * tick_size, 2)

def fetch_and_calculate_supertrend():
    try:
        # Fetching live 5m candles from Binance public API to compute exact bot logic
        url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=100"
        res = requests.get(url, timeout=5)
        data = res.json()
        
        candles = []
        for c in data:
            candles.append({
                "time": int(c[0] / 1000),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4])
            })
        
        period = 14
        multiplier = 3.0
        
        if len(candles) < period + 1:
            return None

        tr_list = []
        for i in range(len(candles)):
            high = candles[i]["high"]
            low = candles[i]["low"]
            if i == 0:
                tr = high - low
            else:
                prev_close = candles[i - 1]["close"]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)

        atr_list = [0.0] * len(candles)
        atr_list[period - 1] = sum(tr_list[:period]) / period
        for i in range(period, len(candles)):
            atr_list[i] = (atr_list[i - 1] * (period - 1) + tr_list[i]) / period

        upper_band = [0.0] * len(candles)
        lower_band = [0.0] * len(candles)
        trend = [1] * len(candles)
        supertrend = [0.0] * len(candles)

        for i in range(len(candles)):
            if i < period - 1:
                continue
            close = candles[i]["close"]
            high = candles[i]["high"]
            low = candles[i]["low"]
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
                prev_close = candles[i - 1]["close"]
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

        curr = candles[-1]
        curr_trend = trend[-1]
        close_price = curr["close"]
        
        # Calculating entry and 3 target prices based on bot parameters
        entry_offset = 5.0
        tp_offsets = [10.0, 20.0, 30.0]
        
        if curr_trend == 1:
            direction = "BULLISH 🟢"
            entry_price = round_to_tick(close_price - entry_offset)
            t1 = round_to_tick(entry_price + tp_offsets[0])
            t2 = round_to_tick(entry_price + tp_offsets[1])
            t3 = round_to_tick(entry_price + tp_offsets[2])
        else:
            direction = "BEARISH 🔴"
            entry_price = round_to_tick(close_price + entry_offset)
            t1 = round_to_tick(entry_price - tp_offsets[0])
            t2 = round_to_tick(entry_price - tp_offsets[1])
            t3 = round_to_tick(entry_price - tp_offsets[2])

        return {
            "btc_price": close_price,
            "direction": direction,
            "entry": entry_price,
            "t1": t1,
            "t2": t2,
            "t3": t3
        }
    except Exception as e:
        return None

st_data = fetch_and_calculate_supertrend()

btc_price_str = f"${st_data['btc_price']:,.2f}" if st_data else "Fetching..."
direction_str = st_data['direction'] if st_data else "Analyzing..."
entry_str = f"${st_data['entry']:,.2f}" if st_data else "N/A"
t1_str = f"${st_data['t1']:,.2f}" if st_data else "N/A"
t2_str = f"${st_data['t2']:,.2f}" if st_data else "N/A"
t3_str = f"${st_data['t3']:,.2f}" if st_data else "N/A"

# Top Metrics Row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Exchanges", "1 Connected", "Data Exchange / Binance")
col2.metric("Active Members / Users", "1 Active", "Multi-tenant")
col3.metric("BTCUSD Live Price", btc_price_str, "🟢 Live Feed")
col4.metric("SuperTrend Direction", direction_str, "Bot Formula")

st.markdown("---")

left_column, right_column = st.columns([2, 1])

with left_column:
    st.subheader("📈 Original TradingView Live Chart (BTCUSDT)")
    
    # Official TradingView Advanced Interactive Widget (Fully Preserved)
    tradingview_widget = """
    <div class="tradingview-widget-container" style="height:500px;width:100%">
      <div id="tradingview_advanced_chart" style="height:100%;width:100%"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
      <script type="text/javascript">
      new TradingView.widget(
      {
        "width": "100%",
        "height": 500,
        "symbol": "BINANCE:BTCUSDT",
        "interval": "5",
        "timezone": "Asia/Kolkata",
        "theme": "dark",
        "style": "1",
        "locale": "en",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "details": true,
        "studies": [
          "SuperTrend@tv-basicstudies"
        ],
        "container_id": "tradingview_advanced_chart"
      }
      );
      </script>
    </div>
    """
    components.html(tradingview_widget, height=520)

with right_column:
    st.subheader("⚡ SuperTrend & 3 Targets")
    st.info(f"🧭 **Trend Direction:** {direction_str}")
    st.success(f"📥 **Calculated Entry:** {entry_str}")
    st.warning(f"🎯 **Target 1 (+10):** {t1_str}")
    st.warning(f"🎯 **Target 2 (+20):** {t2_str}")
    st.warning(f"🎯 **Target 3 (+30):** {t3_str}")
    
    st.subheader("🔌 Engine Status")
    st.write("• SuperTrend Bot Script: **Active & Calculating**")
    st.write("• Parameters: **ATR(14), Mult(3.0)**")

st.markdown("---")

st.subheader("📊 Live Execution & Trade Book")
if st_data:
    pnl_data = pd.DataFrame({
        'Order ID': ['#TX-9021'],
        'Exchange': ['Data Exchange'],
        'Asset': ['BTCUSDT'],
        'Type': ['BUY (Long)' if "BULLISH" in direction_str else 'SELL (Short)'],
        'Entry': [entry_str],
        'Target 1': [t1_str],
        'Target 2': [t2_str],
        'Target 3': [t3_str],
        'Status': ['Active Bot Signal']
    })
    st.dataframe(pnl_data, use_container_width=True)
else:
    st.info("Awaiting live market tick for trade execution book...")
