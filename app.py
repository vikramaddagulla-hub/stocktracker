import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# -----------------------------------------------------------------------------
# 1. PAGE SETUP & MODERN DARK STYLING (NO LOGOS)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Screener Terminal | Indian Markets",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0B0E14;
        color: #E6E8EA;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .company-header {
        background: linear-gradient(135deg, #161B22 0%, #0D1117 100%);
        border: 1px solid #30363D;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
    }
    .ratio-card {
        background-color: #161B22;
        border: 1px solid #21262D;
        border-radius: 8px;
        padding: 16px;
        text-align: center;
        margin-bottom: 12px;
    }
    .ratio-label {
        font-size: 13px;
        color: #8B949E;
        margin-bottom: 4px;
        font-weight: 500;
    }
    .ratio-value {
        font-size: 18px;
        color: #F0F6FC;
        font-weight: 700;
    }
    .ratio-delta-pos { color: #3FB950; font-size: 14px; font-weight: 600; }
    .ratio-delta-neg { color: #F85149; font-size: 14px; font-weight: 600; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. EXTENDED NSE/BSE LOOKUP DATABASE
# -----------------------------------------------------------------------------
STOCK_LOOKUP = {
    # Key Indices
    "NIFTY 50 Index": "^NSEI",
    "SENSEX Index": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
    "NIFTY IT": "^CNXIT",
    
    # Major Equities
    "Reliance Industries": "RELIANCE.NS",
    "Tata Consultancy Services (TCS)": "TCS.NS",
    "Infosys": "INFY.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "State Bank of India (SBI)": "SBIN.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "Tata Steel": "TATASTEEL.NS",
    "Bharti Airtel": "BHARTIARTL.NS",
    "Larsen & Toubro (L&T)": "LT.NS",
    "ITC": "ITC.NS",
    "Hindustan Unilever (HUL)": "HINDUNILVR.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "Maruti Suzuki": "MARUTI.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "Zomato": "ZOMATO.NS",
    "Jio Financial Services": "JIOFIN.NS",
    "Adani Enterprises": "ADANIENT.NS",
    "Adani Ports": "ADANIPORTS.NS",
    
    # Growth, Microcaps & Specialized Themes
    "Apollo Micro Systems": "APOLLO.NS",
    "E2E Networks": "E2E.NS",
    "HAL (Hindustan Aeronautics)": "HAL.NS",
    "BEL (Bharat Electronics)": "BEL.NS",
    "Suzlon Energy": "SUZLON.NS",
    "KPIT Technologies": "KPITTECH.NS",
    "Tata Elxsi": "TATAELXSI.NS",
    "IDFC First Bank": "IDFCFIRSTB.NS"
}

# -----------------------------------------------------------------------------
# 3. SIDEBAR SEARCH WITH AUTOCOMPLETE & CUSTOM INPUT
# -----------------------------------------------------------------------------
st.sidebar.title("⚡ Screener Pro")

# Auto-completing search selectbox
selected_option = st.sidebar.selectbox(
    label="Search Stock or Ticker",
    options=list(STOCK_LOOKUP.keys()),
    index=None,
    placeholder="Type company name or ticker (e.g. Tata, Reliance)...",
    accept_new_options=True  # Allows typing unlisted tickers directly (e.g., WIPRO.NS)
)

# Resolve selected option to a ticker symbol
if selected_option is None:
    selected_option = "Reliance Industries"

if selected_option in STOCK_LOOKUP:
    user_ticker = STOCK_LOOKUP[selected_option]
else:
    # If user typed a custom ticker directly
    user_ticker = selected_option.upper().strip()
    if not user_ticker.endswith(".NS") and not user_ticker.endswith(".BO") and not user_ticker.startswith("^"):
        user_ticker += ".NS"

timeframe = st.sidebar.select_slider(
    "Chart Period",
    options=["1d", "5d", "1mo", "6mo", "1y", "5y", "max"],
    value="1y"
)

# -----------------------------------------------------------------------------
# 4. DATA FETCHING
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_stock_data(symbol):
    t = yf.Ticker(symbol)
    info = t.info
    hist = t.history(period="5y")
    return info, hist

try:
    with st.spinner(f"Loading live market data for {user_ticker}..."):
        info, hist = load_stock_data(user_ticker)
except Exception:
    st.error(f"Could not load data for symbol: `{user_ticker}`. Ensure it is a valid NSE/BSE symbol.")
    st.stop()

# -----------------------------------------------------------------------------
# 5. CLEAN COMPANY HEADER (NO LOGOS)
# -----------------------------------------------------------------------------
company_name = info.get("longName") or info.get("shortName") or selected_option
current_price = info.get("currentPrice") or info.get("regularMarketPrice") or (hist['Close'].iloc[-1] if not hist.empty else 0.0)
prev_close = info.get("previousClose", current_price)
price_change = current_price - prev_close if prev_close else 0
pct_change = (price_change / prev_close) * 100 if prev_close else 0

st.markdown(f"""
<div class="company-header">
    <h1 style="margin:0; font-size: 28px; color: #F0F6FC;">{company_name}</h1>
    <p style="margin:6px 0 0 0; color: #8B949E; font-size: 14px;">
        {info.get('sector', 'Index / Asset')} | {info.get('industry', 'N/A')} | <b>Ticker: {user_ticker}</b>
    </p>
    <h2 style="margin:12px 0 0 0; font-size: 32px;">
        ₹{current_price:,.2f} 
        <span class="{ 'ratio-delta-pos' if price_change >= 0 else 'ratio-delta-neg' }">
            {price_change:+.2f} ({pct_change:+.2f}%)
        </span>
    </h2>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 6. KEY FINANCIAL RATIOS GRID
# -----------------------------------------------------------------------------
st.subheader("Key Ratios & Metrics")

r1, r2, r3, r4, r5, r6 = st.columns(6)

def fmt_num(val, suffix="", is_currency=False):
    if val is None or val == "N/A": return "N/A"
    prefix = "₹" if is_currency else ""
    return f"{prefix}{val:,.2f}{suffix}"

def fmt_market_cap(val):
    if not val: return "N/A"
    return f"₹{val / 1e7:,.0f} Cr."

with r1:
    st.markdown(f"""<div class="ratio-card">
        <div class="ratio-label">Market Cap</div>
        <div class="ratio-value">{fmt_market_cap(info.get('marketCap'))}</div>
    </div>""", unsafe_allow_html=True)

with r2:
    st.markdown(f"""<div class="ratio-card">
        <div class="ratio-label">Stock P/E</div>
        <div class="ratio-value">{fmt_num(info.get('trailingPE'))}</div>
    </div>""", unsafe_allow_html=True)

with r3:
    st.markdown(f"""<div class="ratio-card">
        <div class="ratio-label">ROE</div>
        <div class="ratio-value">{fmt_num(info.get('returnOnEquity', 0)*100 if info.get('returnOnEquity') else None, '%')}</div>
    </div>""", unsafe_allow_html=True)

with r4:
    st.markdown(f"""<div class="ratio-card">
        <div class="ratio-label">ROA</div>
        <div class="ratio-value">{fmt_num(info.get('returnOnAssets', 0)*100 if info.get('returnOnAssets') else None, '%')}</div>
    </div>""", unsafe_allow_html=True)

with r5:
    st.markdown(f"""<div class="ratio-card">
        <div class="ratio-label">Debt to Equity</div>
        <div class="ratio-value">{fmt_num(info.get('debtToEquity'))}</div>
    </div>""", unsafe_allow_html=True)

with r6:
    st.markdown(f"""<div class="ratio-card">
        <div class="ratio-label">52W High / Low</div>
        <div class="ratio-value" style="font-size: 13px;">
            ₹{info.get('fiftyTwoWeekHigh', 0):,.0f} / ₹{info.get('fiftyTwoWeekLow', 0):,.0f}
        </div>
    </div>""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 7. TABBED DETAILED ANALYTICS
# -----------------------------------------------------------------------------
tab_chart, tab_summary, tab_financials = st.tabs(["📉 Interactive Chart", "📌 About & Business", "📊 Balance Sheet Ratios"])

with tab_chart:
    if not hist.empty:
        chart_data = hist.tail(252 if timeframe == "1y" else (30 if timeframe == "1mo" else len(hist)))

        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=chart_data.index,
            open=chart_data['Open'], high=chart_data['High'],
            low=chart_data['Low'], close=chart_data['Close'],
            name="Price"
        ))
        
        chart_data['SMA50'] = chart_data['Close'].rolling(50).mean()
        fig.add_trace(go.Scatter(
            x=chart_data.index, y=chart_data['SMA50'], 
            mode='lines', name='50 SMA', line=dict(color='#E3B341', width=1.5)
        ))

        fig.update_layout(
            template="plotly_dark",
            height=500,
            margin=dict(l=10, r=10, t=10, b=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_rangeslider_visible=False
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No historical chart data available for this symbol.")

with tab_summary:
    st.markdown("### Business Summary")
    st.write(info.get('longBusinessSummary', 'No detailed business summary available for this asset.'))

with tab_financials:
    st.markdown("### Financial Overview")
    fin_df = pd.DataFrame({
        "Metric": ["Book Value", "Price to Book (P/B)", "Dividend Yield", "Profit Margins", "Beta (Volatility)"],
        "Value": [
            fmt_num(info.get('bookValue'), is_currency=True),
            fmt_num(info.get('priceToBook')),
            fmt_num(info.get('dividendYield', 0)*100 if info.get('dividendYield') else None, '%'),
            fmt_num(info.get('profitMargins', 0)*100 if info.get('profitMargins') else None, '%'),
            fmt_num(info.get('beta'))
        ]
    })
    st.dataframe(fin_df, use_container_width=True, hide_index=True)