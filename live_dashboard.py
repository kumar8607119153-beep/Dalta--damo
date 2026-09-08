import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

st.set_page_config(page_title="Master Hub Trading Dashboard", layout="wide")

st.title("🛡️ Master Hub: Algorithmic Trading Monitoring Dashboard")
st.markdown("Independent real-time monitoring interface for multi-tenant bots.")

# Top metrics row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Active Exchanges", "2 Connected", "Binance, BingX")
col2.metric("Active Members / Users", "18 Syncing", "+2 Today")
col3.metric("BTCUSD Price", "$64,250.00", "+1.2%")
col4.metric("System Status", "Healthy", "99.9% Uptime")

st.markdown("---")

# Layout: Charts and SuperTrend
left_column, right_column = st.columns([2, 1])

with left_column:
    st.subheader("📈 BTCUSD Live Price & SuperTrend Chart")
    df = pd.DataFrame({
        'Time': pd.date_range(start='2026-09-08 10:00:00', periods=30, freq='min'),
        'Price': np.linspace(63500, 64250, 30) + np.random.normal(0, 50, 30)
    })
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Time'], y=df['Price'], mode='lines+markers', name='BTCUSD', line=dict(color='#00ffcc', width=2)))
    fig.update_layout(template='plotly_dark', margin=dict(l=20, r=20, t=20, b=20), height=350)
    st.plotly_chart(fig, use_container_width=True)

with right_column:
    st.subheader("⚡ SuperTrend & Signals")
    st.info("🟢 **BTCUSD:** BULLISH (SuperTrend Buy Signal)")
    st.success("🟢 **ETHUSD:** BULLISH (Active Trail)")
    st.warning("🟡 **SOLUSD:** SIDEWAYS (Awaiting Confirmation)")
    
    st.subheader("🔌 API Health Status")
    st.write("• Binance Futures API: 🟢 Connected (Latency: 42ms)")
    st.write("• BingX API: 🟢 Connected (Latency: 65ms)")
    st.write("• Telegram Webhook: 🟢 Active")

st.markdown("---")

# Bottom section: P&L and Order History
st.subheader("📊 Live P&L and Recent Execution History")
pnl_data = pd.DataFrame({
    'Order ID': ['#TX-9021', '#TX-9022', '#TX-9023', '#TX-9024'],
    'Asset': ['BTCUSD', 'ARKUSDT', 'BTCUSD', 'NIFTYOPT'],
    'Type': ['BUY (Long)', 'SELL (Short)', 'BUY (Long)', 'CALL (ITM)'],
    'Entry Price': [63800.5, 0.452, 64010.0, 24500.0],
    'P&L ($)': ['+$420.50', '-$45.00', '+$180.00', '+$850.00'],
    'Status': ['Closed', 'Closed', 'Open', 'Open']
})
st.dataframe(pnl_data, use_container_width=True)
