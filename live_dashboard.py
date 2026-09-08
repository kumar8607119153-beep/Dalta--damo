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

# Admin Owner Header with Name, Contact, and PIN Number
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
st.markdown("Independent real-time monitoring interface connected with active bot state.")

# Function to read actual bot status/metrics from a JSON file (Defaults to 0 if not connected)
def load_real_bot_status():
    if os.path.exists("bot_status.json"):
        try:
            with open("bot_status.json", "r") as f:
                return json.load(f)
        except:
            pass
    return {
        "active_exchanges_count": 0,
        "exchange_names": "None Connected",
        "active_members_count": 0,
        "system_health": "Offline / Standby"
    }

bot_state = load_real_bot_status()

# Function to fetch REAL-TIME live price directly from Binance Public API
def get_live_binance_price(symbol="BTCUSDT"):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        response = requests.get(url, timeout=3)
        data = response.json()
        price = float(data['price'])
        return f"${price:,.2f}"
    except Exception as e:
        return "Market Feed Offline"

live_btc_price = get_live_binance_price("BTCUSDT")

# Top Metrics Row (Showing REAL counts or 0 if nothing is connected)
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Exchanges", f"{bot_state.get('active_exchanges_count', 0)} Connected", bot_state.get('exchange_names', 'None'))
col2.metric("Active Members / Users", f"{bot_state.get('active_members_count', 0)} Active", "Multi-tenant sync")
col3.metric("BTCUSD Live Price", live_btc_price, "🟢 Binance Live")
col4.metric("System Health", bot_state.get('system_health', 'Offline'), "Cloud Relay")

st.markdown("---")

left_column, right_column = st.columns([2, 1])

with left_column:
    st.subheader("📈 Original TradingView Live Chart (BTCUSDT)")
    
    # Official TradingView Advanced Interactive Widget (Fully intact)
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
    st.subheader("⚡ SuperTrend & Strategy Status")
    ex_count = bot_state.get('active_exchanges_count', 0)
    if ex_count > 0:
        st.success("🟢 **Bot Engine:** Running & Listening for Signals")
    else:
        st.warning("⚠️ **Bot Engine:** No Active Exchange Connected (Showing 0 State)")
        
    st.subheader("🔌 API Connection Check")
    st.write(f"• Active Exchange APIs Linked: **{ex_count}**")
    st.write(f"• Total Synced Members: **{bot_state.get('active_members_count', 0)}**")

st.markdown("---")

st.subheader("📊 Live Execution & Trade Book")
st.info("No active open orders or history found in the current session. (0 records)")
