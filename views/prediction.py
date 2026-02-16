import streamlit as st
import plotly.express as px
import pandas as pd
import numpy as np

def render_prediction_view(df_report):
    st.title("📈 營業額預測 (Revenue Prediction)")

    if df_report.empty:
        st.info("尚未載入營運資料 (Data missing)")
        return

    # 1. Prepare Data (Daily Aggregation)
    # Ensure Date_Parsed is valid
    df = df_report[df_report['Date_Parsed'].notna()].copy()
    
    # Resample daily
    daily_rev = df.set_index('Date_Parsed').resample('D')['total_amount'].sum().reset_index()
    
    # Fill missing dates with 0 (if shop closed, revenue is 0. But for avg it drags down. 
    # For prediction of "Daily Take", 0 is valid. 
    # But usually better to predict "Business Day Average". 
    # Let's keep 0 for now as simple trend.)
    daily_rev['total_amount'] = daily_rev['total_amount'].fillna(0)

    # 2. Controls
    window = st.sidebar.slider("預測基準 (Moving Average Window)", min_value=3, max_value=60, value=28, step=1)
    
    # 3. Calculate Moving Average
    daily_rev[f'MA_{window}'] = daily_rev['total_amount'].rolling(window=window, min_periods=1).mean()
    
    # 4. Visualization
    st.subheader(f"📊 營運趨勢預測 (基於近 {window} 天平均)")
    
    # Create combined chart
    fig = px.line(daily_rev, x='Date_Parsed', y=['total_amount', f'MA_{window}'], 
                  title="每日營業額 vs 移動平均趨勢",
                  labels={'value': '金額 (TWD)', 'variable': '指標'})
    
    # Customize traces
    fig.data[0].update(opacity=0.3, name='實際日營收') # Actual
    fig.data[1].update(line=dict(width=3, color='red'), name=f'{window}日均線') # MA
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 5. Future Projection (Simple)
    st.divider()
    st.subheader("🔮 未來預測 (Projection)")
    
    last_ma = daily_rev[f'MA_{window}'].iloc[-1]
    last_date = daily_rev['Date_Parsed'].iloc[-1]
    
    c1, c2, c3 = st.columns(3)
    c1.metric("目前趨勢 (Current Trend)", f"${last_ma:,.0f} / Day")
    c2.metric("預估下週總收 (Next 7 Days)", f"${last_ma * 7:,.0f}")
    c3.metric("預估下月總收 (Next 30 Days)", f"${last_ma * 30:,.0f}")
    
    st.caption("* 此預測僅基於歷史移動平均，未考慮季節性或特殊假日 (Simple Moving Average Projection)")
