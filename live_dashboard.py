import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
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
st.markdown("Direct mirror interface synchronized strictly with your bot's execution state.")

# Function to load exact bot parameters from bot_status.json (matching delta_futures_bot.py structure)
def load_bot_file_status():
    if os.path.exists("bot_status.json"):
        try:
            with open("bot_status.json", "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "symbol": "BTC/USDT:USDT",
        "timeframe": "5m",
        "supertrend_direction": "WAITING",
        "btc_price": "0.00",
        "entry_price": "0.00",
        "target_1": "0.00",
        "target_2": "0.00",
        "target_3": "0.00",
        "trades": []
    }

bot_data = load_bot_file_status()

# Top Metrics Row reflecting exact file data
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Exchange", "Delta Exchange", bot_data.get('symbol', 'BTC/USDT:USDT'))
col2.metric("Timeframe / Strategy", bot_data.get('timeframe', '5m'), "ATR(14) Mult(3.0)")
col3.metric("Live Price (From Bot)", f"${bot_data.get('btc_price', '0.00')}")
col4.metric("SuperTrend Signal", bot_data.get('supertrend_direction', 'WAITING'))

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
    st.subheader("⚡ Bot SuperTrend & 3 Targets")
    st.info(f"🧭 **Direction:** {bot_data.get('supertrend_direction', 'N/A')}")
    st.success(f"📥 **Entry Price:** ${bot_data.get('entry_price', '0.00')}")
    st.warning(f"🎯 **Target 1 (+10.0):** ${bot_data.get('target_1', '0.00')}")
    st.warning(f"🎯 **Target 2 (+20.0):** ${bot_data.get('target_2', '0.00')}")
    st.warning(f"🎯 **Target 3 (+30.0):** ${bot_data.get('target_3', '0.00')}")
    
    st.subheader("🔌 Data Sync Status")
    st.write("• Source File: **`bot_status.json`**")
    st.write("• Status: **Mirroring exact bot script output**")

st.markdown("---")

st.subheader("📊 Live Execution & Trade Book")
trades_list = bot_data.get('trades', [])
if trades_list:
    trade_df = pd.DataFrame(trades_list)
    st.dataframe(trade_df, use_container_width=True)
else:
    st.info("No active trades found in `bot_status.json`.")
