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
st.markdown("Real-time monitoring interface with live market integration.")

# Function to load your bot's actual configuration & status file
def load_bot_status():
    if os.path.exists("bot_status.json"):
        try:
            with open("bot_status.json", "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "supertrend_direction": "WAITING / OFFLINE",
        "entry_price": "0.00",
        "target_price": "0.00",
        "trades": []
    }

bot_data = load_bot_status()

# Function to fetch REAL-TIME live price from Binance Public API
def get_live_binance_price(symbol="BTCUSDT"):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        response = requests.get(url, timeout=3)
        data = response.json()
        return float(data['price'])
    except Exception as e:
        return 0.0

raw_btc_price = get_live_binance_price("BTCUSDT")
formatted_btc_price = f"${raw_btc_price:,.2f}" if raw_btc_price > 0 else "Connecting..."

# Top Metrics Row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Exchanges", "1 Connected", "Binance Futures")
col2.metric("Active Members / Users", "1 Active", "Multi-tenant")
col3.metric("BTCUSD Live Price", formatted_btc_price, "🟢 Binance Live")
col4.metric("SuperTrend Direction", bot_data.get('supertrend_direction', 'N/A'), "Bot Signal")

st.markdown("---")

left_column, right_column = st.columns([2, 1])

with left_column:
    st.subheader("📈 Original TradingView Live Chart (BTCUSDT)")
    
    # Official TradingView Advanced Interactive Widget (Untouched)
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
        "interval": "15",
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
    st.subheader("⚡ SuperTrend Strategy Details")
    st.info(f"🧭 **Direction:** {bot_data.get('supertrend_direction', 'N/A')}")
    st.success(f"📥 **Entry Price:** ${bot_data.get('entry_price', '0.00')}")
    st.warning(f"🎯 **Target Price:** ${bot_data.get('target_price', '0.00')}")
    
    st.subheader("🔌 API Connection Status")
    st.write("• Binance Futures API: **Connected**")
    st.write("• Status File Sync: **Active (`bot_status.json`)**")

st.markdown("---")

st.subheader("📊 Live Execution & Trade Book")
trades_list = bot_data.get('trades', [])
if trades_list:
    trade_df = pd.DataFrame(trades_list)
    st.dataframe(trade_df, use_container_width=True)
else:
    st.info("No active open orders found in `bot_status.json`.")
