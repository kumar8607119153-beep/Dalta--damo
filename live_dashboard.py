import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# PAGE CONFIGURATION (Mobile Friendly)
# ==========================================
st.set_page_config(
    page_title="Master Algorithmic Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==========================================
# MASTER NAVIGATION HUB (Sidebar Links)
# ==========================================
st.sidebar.title("🚀 GHA-Trading Master Hub")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Select Dashboard View:",
    [
        "📊 Complete Overview (All-in-One)",
        "📈 Live Chart & Trade Levels",
        "⚡ SuperTrend Status Hub",
        "🔗 Connected Exchange APIs",
        "👥 Admin & Multi-Tenant Users",
        "💰 Positions, P&L & Order History"
    ]
)

# ==========================================
# HEADER STATUS (Independent Monitoring)
# ==========================================
st.title("⚡ Algorithmic Trading Ecosystem - Master Dashboard")
st.markdown("*Safety Protocol: Read-Only Independent Monitoring Hub. Even if exchange API fails, dashboard runs smoothly.*")

col_s1, col_s2, col_s3, col_s4 = st.columns(4)
with col_s1:
    st.markdown("**BOT STATUS**\n\n🟢 RUNNING")
with col_s2:
    st.markdown("**API STATUS**\n\n⚠️ CHECK API (Independent)")
with col_s3:
    st.markdown("**MARKET**\n\n🪙 BTCUSD Futures")
with col_s4:
    st.markdown(f"**LAST UPDATE**\n\n⏱️ `{datetime.now().strftime('%H:%M:%S')}`")

st.markdown("---")

# ==========================================
# VIEW 1: COMPLETE OVERVIEW (ALL-IN-ONE)
# ==========================================
if page == "📊 Complete Overview (All-in-One)":
    st.subheader("🌐 Ecosystem Comprehensive Summary")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Active SuperTrend", "BUY 🟢", "Value: 70,150")
    with c2:
        st.metric("Connected APIs", "4 Exchanges", "Binance, Bybit, OKX, Delta")
    with c3:
        st.metric("Active Users", "152 Members", "Synced with Admin")
    with c4:
        st.metric("Live Net P&L", "+₹450.00 🚀", "Gross: +₹500 | Fee: ₹50")

    st.markdown("---")

    col_api_snap, col_user_snap = st.columns(2)
    with col_api_snap:
        st.markdown("### 🔌 Connected Exchange APIs")
        api_snapshot = [
            {"Exchange": "Binance Futures", "Status": "Connected 🟢"},
            {"Exchange": "Bybit Derivatives", "Status": "Connected 🟢"},
            {"Exchange": "OKX Trading", "Status": "API Warning ⚠️"},
            {"Exchange": "Delta Exchange", "Status": "Connected 🟢"}
        ]
        st.table(pd.DataFrame(api_snapshot))

    with col_user_snap:
        st.markdown("### 👥 Admin & Member Hub")
        user_snapshot = [
            {"Admin ID": "ADMIN_MASTER_01", "Role": "Signal Broadcaster"},
            {"Total Users": "152 Active Members", "Sync Status": "Fully Synced 🟢"}
        ]
        st.table(pd.DataFrame(user_snapshot))

    st.markdown("---")
    st.info("💡 Note: Dashboard runs independently on the VPS. Exchange-specific API execution errors do not crash this monitoring interface.")

# ==========================================
# VIEW 2: LIVE CHART & TRADE LEVELS
# ==========================================
elif page == "📈 Live Chart & Trade Levels":
    st.subheader("🕯️ BTCUSD Live Price Chart with Technical Markers")
    
    df_chart = pd.DataFrame({
        'Time': pd.date_range(start='2026-09-08 10:00:00', periods=10, freq='5min'),
        'Open': [70000, 70050, 70100, 70080, 70150, 70200, 70180, 70250, 70220, 70300],
        'High': [70080, 70120, 70160, 70150, 70230, 70280, 70250, 70320, 70300, 70380],
        'Low': [69950, 70020, 70060, 70040, 70110, 70170, 70140, 70210, 70190, 70260],
        'Close': [70050, 70100, 70080, 70150, 70200, 70180, 70250, 70220, 70300, 70350]
    })

    fig = go.Figure(data=[go.Candlestick(
        x=df_chart['Time'],
        open=df_chart['Open'],
        high=df_chart['High'],
        low=df_chart['Low'],
        close=df_chart['Close'],
        name='BTCUSD'
    )])

    fig.add_hline(y=70350, line_dash="dash", line_color="green", annotation_text="TP1: 70,350")
    fig.add_hline(y=70500, line_dash="dash", line_color="green", annotation_text="TP2: 70,500")
    fig.add_hline(y=69850, line_dash="dash", line_color="red", annotation_text="Stop Loss (SL): 69,850")
    fig.add_hline(y=70000, line_dash="dot", line_color="orange", annotation_text="Trailing Stop Loss (TSL): 70,000")

    fig.update_layout(template="plotly_dark", height=500, title="BTCUSD Candles, Entries & Target Levels")
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# VIEW 3: SUPERTREND STATUS HUB
# ==========================================
elif page == "⚡ SuperTrend Status Hub":
    st.subheader("📊 SuperTrend Status Hub")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("SuperTrend Direction", "🟢 BUY")
    with col2:
        st.metric("Current ST Value", "70,150.00")
    with col3:
        st.metric("Trend Status", "Active Trend")
        
    st.markdown("---")
    st.success("Current Bot Strategy: Running active SuperTrend monitoring.")

# ==========================================
# VIEW 4: CONNECTED EXCHANGE APIS
# ==========================================
elif page == "🔗 Connected Exchange APIs":
    st.subheader("🔗 Connected Exchange APIs List")
    
    api_list = [
        {"Exchange Name": "Binance Futures", "API Key Label": "MAIN_BINANCE_KEY", "Connection Status": "Connected 🟢", "Latency": "42 ms"},
        {"Exchange Name": "Bybit Derivatives", "API Key Label": "BYBIT_SUB_KEY", "Connection Status": "Connected 🟢", "Latency": "38 ms"},
        {"Exchange Name": "OKX Trading", "API Key Label": "OKX_MAIN_API", "Connection Status": "API Error ⚠️ (Check Key)", "Latency": "N/A"},
        {"Exchange Name": "Delta Exchange", "API Key Label": "DELTA_PRIMARY_API", "Connection Status": "Connected 🟢", "Latency": "29 ms"}
    ]
    st.table(pd.DataFrame(api_list))
    st.warning("Note: If any exchange shows an API error, order placement on that specific exchange may pause, but the server dashboard and monitoring remain fully active.")

# ==========================================
# VIEW 5: ADMIN & MULTI-TENANT USERS
# ==========================================
elif page == "👥 Admin & Multi-Tenant Users":
    st.subheader("👑 Admin Control & Connected Members Hub")
    
    col_adm1, col_adm2 = st.columns(2)
    with col_adm1:
        st.markdown("### 🎙️ Admin Master Panel")
        st.info("Status: **Active & Broadcasting**\n\nAdmin ID: `ADMIN_MASTER_01`\n\nSignal Mode: `Automated`")
    
    with col_adm2:
        st.markdown("### 👥 Connected Members / Users")
        st.metric("Total Active Members", "152 Users")

    member_data = [
        {"Member ID": "USR_101", "Assigned Exchange": "Binance", "Sync Status": "Synced 🟢", "Last Signal Received": "BUY 70100"},
        {"Member ID": "USR_102", "Assigned Exchange": "Bybit", "Sync Status": "Synced 🟢", "Last Signal Received": "BUY 70100"},
        {"Member ID": "USR_103", "Assigned Exchange": "Delta", "Sync Status": "Synced 🟢", "Last Signal Received": "BUY 70100"},
        {"Member ID": "USR_104", "Assigned Exchange": "OKX", "Sync Status": "OKX API Issue ⚠️", "Last Signal Received": "Paused"}
    ]
    st.table(pd.DataFrame(member_data))

# ==========================================
# VIEW 6: POSITIONS, P&L & ORDER HISTORY
# ==========================================
elif page == "💰 Positions, P&L & Order History":
    st.subheader("💰 Current Positions & Live P&L Breakdown")
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown("""
        ### 📍 Active Position
        * **Position Type:** `LONG` 🟢
        * **Entry Price:** `70,100`
        * **Current Market Price:** `70,250`
        * **Quantity / Size:** `2 Contracts`
        """)
    with col_p2:
        st.markdown("""
        ### 📊 Profit & Loss (P&L)
        * **Gross P&L:** `+₹500.00` 🟢
        * **Estimated Fees:** `₹50.00`
        * **Net P&L:** `+₹450.00` 🚀
        """)

    st.markdown("---")
    st.subheader("📋 Recent Order History & Execution Logs")
    order_history = [
        {"Time": "10:01:12", "Side": "BUY", "Type": "LIMIT", "Price": 70100, "Qty": 1, "Status": "FILLED 🟢"},
        {"Time": "10:05:40", "Side": "BUY", "Type": "LIMIT", "Price": 70050, "Qty": 1, "Status": "FILLED 🟢"},
        {"Time": "10:15:22", "Side": "SELL", "Type": "MARKET", "Price": 70300, "Qty": 1, "Status": "PENDING TP ⏳"},
        {"Time": "10:30:00", "Side": "SELL", "Type": "STOP-LOSS", "Price": 69850, "Qty": 1, "Status": "ACTIVE 🛡️"}
    ]
    st.table(pd.DataFrame(order_history))

# Footer
st.markdown("---")
st.markdown("<p style='text-align: center; color: gray;'>GHA-Trading Master Ecosystem | Independent Read-Only Monitoring Dashboard</p>", unsafe_allow_html=True)
