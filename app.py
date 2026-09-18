import os
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from google import genai

# -----------------------------------------------------------------------------
# 1. PAGE SETUP & MODERN DARK STYLING
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="AI Screener Terminal | Indian Markets",
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
        padding: 14px;
        text-align: center;
        margin-bottom: 10px;
    }
    .ratio-label {
        font-size: 12px;
        color: #8B949E;
        margin-bottom: 4px;
        font-weight: 500;
    }
    .ratio-value {
        font-size: 17px;
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
    "Zomato": "ZOMATO.NS",
    "Jio Financial Services": "JIOFIN.NS",
    
    # Growth, Defence & Tech
    "Apollo Micro Systems": "APOLLO.NS",
    "E2E Networks": "E2E.NS",
    "HAL (Hindustan Aeronautics)": "HAL.NS",
    "BEL (Bharat Electronics)": "BEL.NS",
    "Suzlon Energy": "SUZLON.NS",
    "IDFC First Bank": "IDFCFIRSTB.NS"
}

# -----------------------------------------------------------------------------
# 3. SIDEBAR CONFIGURATION & GEMINI API KEY HANDLING
# -----------------------------------------------------------------------------
st.sidebar.title("⚡ Screener Pro AI")

gemini_key = os.environ.get("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)

if not gemini_key:
    gemini_key = st.sidebar.text_input("Gemini API Key", type="password", help="Get your free key from aistudio.google.com")

selected_option = st.sidebar.selectbox(
    label="Search Stock or Ticker",
    options=list(STOCK_LOOKUP.keys()),
    index=None,
    placeholder="Type company name or ticker...",
    accept_new_options=True
)

if selected_option is None:
    selected_option = "Reliance Industries"

if selected_option in STOCK_LOOKUP:
    user_ticker = STOCK_LOOKUP[selected_option]
else:
    user_ticker = selected_option.upper().strip()
    if not user_ticker.endswith(".NS") and not user_ticker.endswith(".BO") and not user_ticker.startswith("^"):
        user_ticker += ".NS"

# Adjusted slider strictly for Daily Candle views
timeframe = st.sidebar.select_slider("Chart Period", options=["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], value="1y")

# -----------------------------------------------------------------------------
# 4. DATA FETCHING FUNCTION
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_stock_data(symbol):
    t = yf.Ticker(symbol)
    info = t.info
    # Fetch long-term daily data (Every row = 1 Day Candle)
    hist_daily = t.history(period="5y")
    news = t.news
    return info, hist_daily, news

try:
    with st.spinner(f"Loading live market data for {user_ticker}..."):
        info, hist_daily, news_data = load_stock_data(user_ticker)
except Exception:
    st.error(f"Could not load data for symbol: `{user_ticker}`")
    st.stop()

# -----------------------------------------------------------------------------
# 5. COMPANY HEADER
# -----------------------------------------------------------------------------
company_name = info.get("longName") or info.get("shortName") or selected_option
current_price = info.get("currentPrice") or info.get("regularMarketPrice") or (hist_daily['Close'].iloc[-1] if not hist_daily.empty else 0.0)
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
# 6. RATIOS & METRICS GRID
# -----------------------------------------------------------------------------
eps = info.get('trailingEps', 0)
book_val = info.get('bookValue', 0)
graham_num = (22.5 * eps * book_val)**0.5 if (eps and book_val and eps > 0 and book_val > 0) else None

st.subheader("Key Ratios & Custom Metrics")
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
        <div class="ratio-label">Debt to Equity</div>
        <div class="ratio-value">{fmt_num(info.get('debtToEquity'))}</div>
    </div>""", unsafe_allow_html=True)
with r5:
    st.markdown(f"""<div class="ratio-card">
        <div class="ratio-label">Price to Sales (P/S)</div>
        <div class="ratio-value">{fmt_num(info.get('priceToSalesTrailing12Months'))}</div>
    </div>""", unsafe_allow_html=True)
with r6:
    st.markdown(f"""<div class="ratio-card">
        <div class="ratio-label">Graham Number (Est.)</div>
        <div class="ratio-value">{fmt_num(graham_num, is_currency=True)}</div>
    </div>""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 7. TABBED INTERFACE (CHART, NEWS, GEMINI CHATBOT, FINANCIALS)
# -----------------------------------------------------------------------------
tab_chart, tab_news, tab_ai, tab_financials = st.tabs([
    "📉 Interactive Chart", 
    "📰 Latest News", 
    "🤖Ask Anyything", 
    "📊 Balance Sheet Ratios"
])

# TAB 1: CHART
with tab_chart:
    if not hist_daily.empty:
        # Calculate daily SMAs on the full historical context
        hist_daily['SMA50'] = hist_daily['Close'].rolling(50).mean()
        hist_daily['SMA150'] = hist_daily['Close'].rolling(150).mean()
        hist_daily['SMA200'] = hist_daily['Close'].rolling(200).mean()
        
        # Determine how many daily candles to display on the chart
        tf_map = {"1mo": 22, "3mo": 63, "6mo": 126, "1y": 252, "2y": 504, "5y": 1260, "max": len(hist_daily)}
        days = tf_map.get(timeframe, 252)
        chart_data = hist_daily.tail(days)
        
        fig = go.Figure()

        if not chart_data.empty:
            # 1. Add Daily Candlestick Trace
            fig.add_trace(go.Candlestick(
                x=chart_data.index, open=chart_data['Open'], high=chart_data['High'],
                low=chart_data['Low'], close=chart_data['Close'], name="Daily Price"
            ))
            
            # 2. Add Continuous 50, 150, 200 SMAs
            fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['SMA50'], mode='lines', name='50-Day SMA', line=dict(color='#E3B341', width=1.5)))
            fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['SMA150'], mode='lines', name='150-Day SMA', line=dict(color='#29B6F6', width=1.5)))
            fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['SMA200'], mode='lines', name='200-Day SMA', line=dict(color='#AB47BC', width=1.5)))

        fig.update_layout(template="plotly_dark", height=500, margin=dict(l=10, r=10, t=10, b=10), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No historical chart data available.")

# TAB 2: NEWS
with tab_news:
    st.markdown(f"### Recent News & Headlines for {company_name}")
    if news_data:
        for item in news_data[:6]:
            title = item.get('title', 'No Title')
            publisher = item.get('publisher', 'Unknown Source')
            link = item.get('link', '#')
            st.markdown(f"""
            <div style="background-color:#161B22; border:1px solid #30363D; border-radius:8px; padding:12px; margin-bottom:10px;">
                <h4 style="margin:0; font-size:16px;"><a href="{link}" target="_blank" style="color:#58A6FF; text-decoration:none;">{title}</a></h4>
                <p style="margin:4px 0 0 0; color:#8B949E; font-size:12px;">Source: {publisher}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No recent news updates found for this asset.")

# TAB 3: GEMINI AI CHATBOT
with tab_ai:
    st.markdown(f"### Google Gemini Assistant for **{company_name}**")
    
    if not gemini_key:
        st.warning("Please enter your free Google Gemini API Key in the left sidebar or configure it in Streamlit Secrets.")
    else:
        try:
            client = genai.Client(api_key=gemini_key)
            
            if "messages" not in st.session_state:
                st.session_state.messages = []

            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            if prompt := st.chat_input(f"Ask Gemini about {company_name}'s valuation, risks, or financial health..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)

                system_instruction = f"""
                You are a senior equity research analyst specializing in Indian Stock Markets.
                Provide structured, clear, and objective insight regarding {company_name} ({user_ticker}).

                Live Financial Context for {company_name}:
                - Current Price: ₹{current_price}
                - P/E Ratio: {info.get('trailingPE', 'N/A')}
                - Market Cap: ₹{info.get('marketCap', 0) / 1e7:,.2f} Cr
                - Debt to Equity: {info.get('debtToEquity', 'N/A')}
                - ROE: {info.get('returnOnEquity', 'N/A')}
                - Sector: {info.get('sector', 'N/A')}
                - Business Overview: {info.get('longBusinessSummary', 'N/A')[:500]}...

                Guidance:
                - Focus on fundamental metrics, industry positioning, and growth drivers.
                - Do NOT offer direct legal or financial advice (avoid explicit Buy/Sell recommendations).
                """

                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    
                    response = client.models.generate_content_stream(
                        model='gemini-3.6-flash',
                        contents=prompt,
                        config={'system_instruction': system_instruction}
                    )
                    
                    full_response = ""
                    for chunk in response:
                        if chunk.text:
                            full_response += chunk.text
                            message_placeholder.markdown(full_response + "▌")
                            
                    message_placeholder.markdown(full_response)
                    
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                
        except Exception as e:
            st.error(f"Error communicating with Gemini API: {e}")

# TAB 4: FINANCIALS
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
