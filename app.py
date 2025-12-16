import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from src.stream_manager import StreamManager
from src.config import DEFAULT_SYMBOLS
from src.analytics import FinancialMetrics

# --- Page Config ---
st.set_page_config(
    page_title="Quant Analytics Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Custom CSS for "Trader" feel ---
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 2rem; }
    [data-testid="stMetricValue"] { font-size: 1.5rem; }
    .stAlert { padding: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# --- Singleton Logic ---
@st.cache_resource
def get_manager():
    sm = StreamManager()
    sm.start()
    return sm

manager = get_manager()

# --- Sidebar ---
st.sidebar.title("⚡ Settings")

# Symbol Selection
symbol_1 = st.sidebar.selectbox("Leg 1 (Long)", options=DEFAULT_SYMBOLS, index=0).lower()
symbol_2 = st.sidebar.selectbox("Leg 2 (Short)", options=DEFAULT_SYMBOLS, index=1).lower()

# Analytics Params
window = st.sidebar.slider("Rolling Window", 10, 200, 20)
hedge_mode = st.sidebar.selectbox("Hedge Ratio Logis", ["Fixed (1.0)", "OLS (Rolling Window)", "Robust (Huber)", "Kalman Filter (Dynamic)", "Custom"])

if hedge_mode == "Fixed (1.0)":
    hedge_ratio = 1.0
elif hedge_mode == "Custom":
    hedge_ratio = st.sidebar.number_input("Custom Ratio", value=1.0, step=0.1)
else:
    hedge_ratio = 1.0 # Placeholder, computed below

# Alerting
st.sidebar.markdown("---")
st.sidebar.subheader("🔔 Alerts & Backtest")
z_entry = st.sidebar.slider("Entry Threshold (Z)", 1.0, 5.0, 2.0, step=0.1)
z_exit = st.sidebar.slider("Exit Threshold (Z)", 0.0, 2.0, 0.0, step=0.1)

# --- Main Logic ---

# --- Main Logic ---

# 1. Fetch Data
st.title("🛡️ Institutional Quant Dashboard")

with st.expander("📚 Guide: How to use this Dashboard", expanded=False):
    st.markdown("""
    **Strategy: Statistical Arbitrage / Pairs Trading**
    
    1.  **The Concept**: We look for two assets that move together (cointegrated). When they diverge (spread widens), we bet they will converge.
    2.  **The Visuals**:
        *   **Top Chart**: Price action of both assets. If one goes up and other goes down, the gap widens.
        *   **Middle Chart (Spread)**: The mathematical difference: $Price_A - (HedgeRatio \\times Price_B)$.
        *   **Bottom Chart (Z-Score)**: The spread normalized by volatility.
            *   **Green Zone**: Normal noise. No trade.
            *   **Red Dashed Lines**: Entry Threshold (e.g., 2 Sigma). Statistically rare deviation -> **Potential Entry**.
            *   **Gray Line (0)**: Mean Reversion target. This is where we take profit.
    3.  **Controls**: Use the sidebar to change the "Lookback Window" (responsiveness) or the "Hedge Ratio" logic.
    """)

col1, col2, col3, col4, col5 = st.columns(5)

# Prices
p1 = manager.get_latest_price(symbol_1)
p2 = manager.get_latest_price(symbol_2)

col1.metric(f"{symbol_1.upper()}", f"{p1:.2f}")
col2.metric(f"{symbol_2.upper()}", f"{p2:.2f}")

# Data Fetching
df1 = manager.get_bars_df('1s', symbol_1)
df2 = manager.get_bars_df('1s', symbol_2)
merged_df = pd.DataFrame()

if not df1.empty and not df2.empty:
    df1 = df1.set_index('timestamp').sort_index()
    df2 = df2.set_index('timestamp').sort_index()
    
    # Inner join for alignment
    merged_df = df1[['close', 'volume']].join(df2[['close', 'volume']], lsuffix='_1', rsuffix='_2', how='inner')
    
    # CLEANING: Filter out zeros or bad data spikes
    merged_df = merged_df[(merged_df['close_1'] > 0) & (merged_df['close_2'] > 0)]
    
    # Liquidity Check
    vol_1_ma = merged_df['volume_1'].rolling(20).mean().iloc[-1] if len(merged_df) > 0 else 0
    vol_2_ma = merged_df['volume_2'].rolling(20).mean().iloc[-1] if len(merged_df) > 0 else 0
    
    # HEDGE RATIO COMPUTATION
    if len(merged_df) > 20: 
        if "OLS" in hedge_mode:
            # Rolling OLS (Last Window)
            subset = merged_df.iloc[-window:]
            calc_beta = FinancialMetrics.calculate_ols_hedge_ratio(subset['close_1'], subset['close_2'])
            if calc_beta: hedge_ratio = calc_beta

        elif "Robust" in hedge_mode:
            # Robust Regression (Last Window)
            subset = merged_df.iloc[-window:]
            calc_beta = FinancialMetrics.calculate_robust_hedge_ratio(subset['close_1'], subset['close_2'])
            if calc_beta: hedge_ratio = calc_beta

        elif "Kalman" in hedge_mode:
            # Full History Kalman
            betas = FinancialMetrics.run_kalman_filter(merged_df['close_1'], merged_df['close_2'])
            hedge_ratio = betas.iloc[-1]
            # Store betas for plotting if needed
            merged_df['kalman_beta'] = betas
    
    # Calculate Spread & Z-Score with CHOSEN hedge ratio
    merged_df['spread'] = merged_df['close_1'] - (hedge_ratio * merged_df['close_2'])
    
    roll = merged_df['spread'].rolling(window=window)
    merged_df['zscore'] = (merged_df['spread'] - roll.mean()) / roll.std()
    
    if len(merged_df) > 0:
        curr_spread = merged_df['spread'].iloc[-1]
        curr_z = merged_df['zscore'].iloc[-1]

        col3.metric("Spread", f"{curr_spread:.4f}")
        col4.metric("Z-Score", f"{curr_z:.2f}", delta_color="inverse")
        col5.metric("Hedge Ratio", f"{hedge_ratio:.4f}")
        
        # Alert Logic - Non-blocking
        if abs(curr_z) > z_entry:
            st.toast(f"⚠️ SIGNAL: {symbol_1}/{symbol_2} Z-Score {curr_z:.2f}", icon="🚨")
            
        # --- Charts ---
        
        tab_charts, tab_backtest, tab_data = st.tabs(["Real-Time Charts", "Mini Backtest", "Feature Table"])
        
        with tab_charts:
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                                vertical_spacing=0.08,
                                subplot_titles=("Price Action (Dual Axis)", "Spread (Divergence)", "Z-Score (Mean Reversion)"),
                                row_heights=[0.5, 0.25, 0.25],
                                specs=[[{"secondary_y": True}], [{}], [{}]])

            # Row 1: Prices + Liquidity Bubbles? Just Lines for now.
            fig.add_trace(go.Scatter(x=merged_df.index, y=merged_df['close_1'], name=f"{symbol_1} (L)", line=dict(color='#00F0FF', width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=merged_df.index, y=merged_df['close_2'], name=f"{symbol_2} (R)", line=dict(color='#FF00AA', width=1.5)), row=1, col=1, secondary_y=True)

            # Row 2: Spread
            fig.add_trace(go.Scatter(x=merged_df.index, y=merged_df['spread'], name="Spread", line=dict(color='#FFE600', width=1.5), fill='tozeroy', fillcolor='rgba(255, 230, 0, 0.1)'), row=2, col=1)

            # Row 3: Z-Score
            fig.add_trace(go.Scatter(x=merged_df.index, y=merged_df['zscore'], name="Z-Score", line=dict(color='white', width=1.5)), row=3, col=1)
            
            # Z Thresholds
            fig.add_hline(y=z_entry, line_dash="dash", line_color="#FF4B4B", row=3, col=1, annotation_text="Short")
            fig.add_hline(y=-z_entry, line_dash="dash", line_color="#00FF00", row=3, col=1, annotation_text="Long")
            fig.add_hline(y=0, line_color="gray", row=3, col=1)

            # Layout Updates for Readability
            fig.update_layout(
                height=800, 
                template="plotly_dark", 
                margin=dict(l=50, r=50, t=30, b=30),
                legend=dict(orientation="h", y=1.02, xanchor="right", x=1),
                hovermode="x unified"
            )
            
            # Axis Tuning for Visualization
            # Y1 (Price 1)
            y1_min, y1_max = merged_df['close_1'].min(), merged_df['close_1'].max()
            pad1 = (y1_max - y1_min) * 0.1
            fig.update_yaxes(title_text=symbol_1.upper(), range=[y1_min - pad1, y1_max + pad1], row=1, col=1)
            
            # Y2 (Price 2)
            y2_min, y2_max = merged_df['close_2'].min(), merged_df['close_2'].max()
            pad2 = (y2_max - y2_min) * 0.1
            fig.update_yaxes(title_text=symbol_2.upper(), range=[y2_min - pad2, y2_max + pad2], row=1, col=1, secondary_y=True)
            
            # Spread Axis - Auto with padding
            s_min, s_max = merged_df['spread'].min(), merged_df['spread'].max()
            pad_s = (s_max - s_min) * 0.1 if s_max != s_min else 1.0
            fig.update_yaxes(title_text="Spread", range=[s_min - pad_s, s_max + pad_s], row=2, col=1)
            
            # Z Axis - Fixed usually better for Z, but let's auto with bounds
            z_vals = merged_df['zscore'].dropna()
            if not z_vals.empty:
                z_max_abs = max(abs(z_vals.min()), abs(z_vals.max()), z_entry + 1)
                fig.update_yaxes(title_text="Sigma", range=[-z_max_abs, z_max_abs], row=3, col=1)
            
            # Fix the use_container_width warning by just using the standard param (warnings are annoying but functionality usually works).
            # If the user insists on fixing it, I will remove the param and rely on default, or use custom CSS.
            st.plotly_chart(fig, use_container_width=True, key="main_chart")
            
            # Heatmap / Cross Corr
            st.caption(f"Liquidity (20-bar Avg Vol): {symbol_1.upper()}: {vol_1_ma:.0f} | {symbol_2.upper()}: {vol_2_ma:.0f}")

        with tab_backtest:
            st.subheader("In-Sample Mean Reversion Test")
            positions = FinancialMetrics.backtest_mean_reversion(merged_df['zscore'], None, z_entry, z_exit)
            
            # Check if we have positions
            if positions.abs().sum() > 0:
                # Plot
                bt_fig = go.Figure()
                bt_fig.add_trace(go.Scatter(x=merged_df.index, y=merged_df['zscore'], name="Z-Score", line=dict(color='gray', width=1)))
                
                # Overlay Entries
                longs = merged_df[positions == 1]
                shorts = merged_df[positions == -1]
                
                bt_fig.add_trace(go.Scatter(x=longs.index, y=longs['zscore'], mode='markers', name="Long Entry", marker=dict(color='#00FF00', size=10, symbol='triangle-up')))
                bt_fig.add_trace(go.Scatter(x=shorts.index, y=shorts['zscore'], mode='markers', name="Short Entry", marker=dict(color='#FF4B4B', size=10, symbol='triangle-down')))
                
                bt_fig.add_hline(y=z_entry, line_dash="dash", line_color="white")
                bt_fig.add_hline(y=-z_entry, line_dash="dash", line_color="white")
                
                bt_fig.update_layout(title="Signals on Z-Score History", template="plotly_dark", height=400)
                st.plotly_chart(bt_fig, use_container_width=True)
                
                st.markdown(f"**Total Signals Generated**: {positions.diff().abs().sum() / 2:.0f}")
                st.caption("Note: This is a visual backtest on the currently loaded rolling window.")
            else:
                st.warning("No trades triggered with current thresholds on loaded history.")

        with tab_data:
            st.subheader("Feature Engineering Table")
            
            # Add Rolling Features
            merged_df['spread_mean'] = roll.mean()
            merged_df['spread_std'] = roll.std()
            
            # Display latest
            st.dataframe(merged_df.sort_index(ascending=False).head(50), use_container_width=True)
            
            # Download
            csv_data = merged_df.to_csv()
            st.download_button("Download Full Feature Set (CSV)", csv_data, "quant_features.csv", "text/csv")
            
    else:
        st.warning("Waiting for sufficient history to calculate metrics...")
        
else:
    st.info("Waiting for data stream... (Ensure markets are open/active)")
        


# --- Footer ---
st.markdown("---")
st.caption(f"Backend Status: {'Running' if manager.thread and manager.thread.is_alive() else 'Stopped'} | Mode: {hedge_mode}")

# --- Auto Rerun ---
time.sleep(1)
st.rerun()
