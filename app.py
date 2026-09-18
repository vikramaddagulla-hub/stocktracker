import os
import requests
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import PyPDF2
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from google import genai

# -----------------------------------------------------------------------------
# 1. PAGE SETUP & MODERN LIGHT STYLING
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
        background-color: #F8F9FA;
        color: #1E293B;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    .company-header {
        background: linear-gradient(135deg, #FFFFFF 0%, #F1F5F9 100%);
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.02);
    }
    .ratio-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px;
        text-align: center;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    .ratio-label {
        font-size: 12px;
        color: #64748B;
        margin-bottom: 4px;
        font-weight: 600;
    }
    .ratio-value {
        font-size: 17px;
        color: #0F172A;
        font-weight: 700;
    }
    .ratio-delta-pos { color: #16A34A; font-size: 14px; font-weight: 600; }
    .ratio-delta-neg { color: #DC2626; font-size: 14px; font-weight: 600; }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 2. EXTENDED NSE/BSE LOOKUP DATABASE
# -----------------------------------------------------------------------------
STOCK_LOOKUP = {
    "NIFTY 50 Index": "^NSEI",
    "SENSEX Index": "^BSESN",
    "BANK NIFTY": "^NSEBANK",
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
    "Apollo Micro Systems": "APOLLO.NS",
    "E2E Networks": "E2E.NS",
    "HAL (Hindustan Aeronautics)": "HAL.NS",
    "BEL (Bharat Electronics)": "BEL.NS",
    "Suzlon Energy": "SUZLON.NS",
    "IDFC First Bank": "IDFCFIRSTB.NS"
}

# -----------------------------------------------------------------------------
# 3. SIDEBAR CONFIGURATION
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

timeframe = st.sidebar.select_slider("Chart Period", options=["1mo", "3mo", "6mo", "1y", "2y", "5y", "max"], value="1y")

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Technical Indicators")
show_bb = st.sidebar.checkbox("Bollinger Bands (20, 2)")
show_macd = st.sidebar.checkbox("MACD (12, 26, 9)")
show_rsi = st.sidebar.checkbox("RSI (14)")

# -----------------------------------------------------------------------------
# 4. DATA FETCHING (Cloud Bypass & Google News)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=300)
def load_stock_data(symbol):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    t = yf.Ticker(symbol, session=session)
    info = t.info
    hist_daily = t.history(period="5y")
    return info, hist_daily

@st.cache_data(ttl=600)
def get_google_news(query):
    try:
        encoded_query = urllib.parse.quote(f"{query} stock news India")
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        response = urllib.request.urlopen(req)
        root = ET.fromstring(response.read())
        news_items = []
        for item in root.findall('.//item')[:6]:
            news_items.append({
                'title': item.find('title').text,
                'link': item.find('link').text,
                'publisher': item.find('source').text,
                'pubDate': item.find('pubDate').text
            })
        return news_items
    except Exception:
        return []

try:
    with st.spinner(f"Loading live market data for {user_ticker}..."):
        info, hist_daily = load_stock_data(user_ticker)
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
    <h1 style="margin:0; font-size: 28px; color: #0F172A;">{company_name}</h1>
    <p style="margin:6px 0 0 0; color: #64748B; font-size: 14px;">
        {info.get('sector', 'Index / Asset')} | {info.get('industry', 'N/A')} | <b>Ticker: {user_ticker}</b>
    </p>
    <h2 style="margin:12px 0 0 0; font-size: 32px; color: #0F172A;">
        ₹{current_price:,.2f} 
        <span class="{ 'ratio-delta-pos' if price_change >= 0 else 'ratio-delta-neg' }">
            {price_change:+.2f} ({pct_change:+.2f}%)
        </span>
    </h2>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 6. RATIOS & METRICS
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
    st.markdown(f"""<div class="ratio-card"><div class="ratio-label">Market Cap</div><div class="ratio-value">{fmt_market_cap(info.get('marketCap'))}</div></div>""", unsafe_allow_html=True)
with r2:
    st.markdown(f"""<div class="ratio-card"><div class="ratio-label">Stock P/E</div><div class="ratio-value">{fmt_num(info.get('trailingPE'))}</div></div>""", unsafe_allow_html=True)
with r3:
    st.markdown(f"""<div class="ratio-card"><div class="ratio-label">ROE</div><div class="ratio-value">{fmt_num(info.get('returnOnEquity', 0)*100 if info.get('returnOnEquity') else None, '%')}</div></div>""", unsafe_allow_html=True)
with r4:
    st.markdown(f"""<div class="ratio-card"><div class="ratio-label">Debt to Equity</div><div class="ratio-value">{fmt_num(info.get('debtToEquity'))}</div></div>""", unsafe_allow_html=True)
with r5:
    st.markdown(f"""<div class="ratio-card"><div class="ratio-label">Price to Sales (P/S)</div><div class="ratio-value">{fmt_num(info.get('priceToSalesTrailing12Months'))}</div></div>""", unsafe_allow_html=True)
with r6:
    st.markdown(f"""<div class="ratio-card"><div class="ratio-label">Graham Number (Est.)</div><div class="ratio-value">{fmt_num(graham_num, is_currency=True)}</div></div>""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 7. TABBED INTERFACE
# -----------------------------------------------------------------------------
tab_chart, tab_news, tab_ai, tab_financials = st.tabs([
    "📉 Interactive Chart", "📰 Latest News", "🤖 Gemini Research Copilot", "📊 Balance Sheet Ratios"
])

# TAB 1: CHART & TECHNICAL ANALYSIS
with tab_chart:
    if not hist_daily.empty:
        # Compute Indicators on full history to avoid cutoff
        hist_daily['SMA50'] = hist_daily['Close'].rolling(50).mean()
        hist_daily['SMA150'] = hist_daily['Close'].rolling(150).mean()
        hist_daily['SMA200'] = hist_daily['Close'].rolling(200).mean()
        
        # Bollinger Bands
        hist_daily['BB_Mid'] = hist_daily['Close'].rolling(window=20).mean()
        hist_daily['BB_Std'] = hist_daily['Close'].rolling(window=20).std()
        hist_daily['BB_Upper'] = hist_daily['BB_Mid'] + (2 * hist_daily['BB_Std'])
        hist_daily['BB_Lower'] = hist_daily['BB_Mid'] - (2 * hist_daily['BB_Std'])
        
        # MACD
        ema_12 = hist_daily['Close'].ewm(span=12, adjust=False).mean()
        ema_26 = hist_daily['Close'].ewm(span=26, adjust=False).mean()
        hist_daily['MACD'] = ema_12 - ema_26
        hist_daily['MACD_Signal'] = hist_daily['MACD'].ewm(span=9, adjust=False).mean()
        hist_daily['MACD_Hist'] = hist_daily['MACD'] - hist_daily['MACD_Signal']
        
        # RSI
        delta = hist_daily['Close'].diff()
        gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
        loss = (-1 * delta.clip(upper=0)).ewm(com=13, adjust=False).mean()
        rs = gain / loss
        hist_daily['RSI'] = 100 - (100 / (1 + rs))

        # Filter by timeframe slider
        tf_map = {"1mo": 22, "3mo": 63, "6mo": 126, "1y": 252, "2y": 504, "5y": 1260, "max": len(hist_daily)}
        chart_data = hist_daily.tail(tf_map.get(timeframe, 252))
        
        if not chart_data.empty:
            # Dynamic Subplot Logic
            active_subplots = sum([show_macd, show_rsi])
            rows = 1 + active_subplots
            
            if rows == 1: heights = [1.0]
            elif rows == 2: heights = [0.7, 0.3]
            else: heights = [0.5, 0.25, 0.25]

            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=heights)

            # Main Chart (Row 1)
            fig.add_trace(go.Candlestick(x=chart_data.index, open=chart_data['Open'], high=chart_data['High'], low=chart_data['Low'], close=chart_data['Close'], name="Price"), row=1, col=1)
            fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['SMA50'], mode='lines', name='50 SMA', line=dict(color='#F59E0B', width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['SMA150'], mode='lines', name='150 SMA', line=dict(color='#3B82F6', width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['SMA200'], mode='lines', name='200 SMA', line=dict(color='#8B5CF6', width=1.5)), row=1, col=1)

            if show_bb:
                fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['BB_Upper'], mode='lines', name='BB Upper', line=dict(color='#94A3B8', width=1, dash='dot')), row=1, col=1)
                fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['BB_Lower'], mode='lines', name='BB Lower', fill='tonexty', fillcolor='rgba(148,163,184,0.1)', line=dict(color='#94A3B8', width=1, dash='dot')), row=1, col=1)

            # Subplots
            curr_row = 2
            if show_macd:
                colors = ['#22C55E' if val >= 0 else '#EF4444' for val in chart_data['MACD_Hist']]
                fig.add_trace(go.Bar(x=chart_data.index, y=chart_data['MACD_Hist'], name='MACD Hist', marker_color=colors), row=curr_row, col=1)
                fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['MACD'], mode='lines', name='MACD', line=dict(color='#3B82F6', width=1.5)), row=curr_row, col=1)
                fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['MACD_Signal'], mode='lines', name='Signal', line=dict(color='#F59E0B', width=1.5)), row=curr_row, col=1)
                curr_row += 1

            if show_rsi:
                fig.add_trace(go.Scatter(x=chart_data.index, y=chart_data['RSI'], mode='lines', name='RSI', line=dict(color='#8B5CF6', width=1.5)), row=curr_row, col=1)
                fig.add_hline(y=70, line=dict(color='#EF4444', width=1, dash='dash'), row=curr_row, col=1)
                fig.add_hline(y=30, line=dict(color='#22C55E', width=1, dash='dash'), row=curr_row, col=1)

            fig.update_layout(
                template="plotly_white", 
                height=500 + (150 * active_subplots), 
                margin=dict(l=10, r=10, t=10, b=10),
                showlegend=False,
                xaxis_rangeslider_visible=False
            )
            st.plotly_chart(fig, use_container_width=True)

# TAB 2: NEWS
with tab_news:
    st.markdown(f"### Recent News & Headlines for {company_name}")
    live_news = get_google_news(company_name)
    if live_news:
        for item in live_news:
            title = item.get('title', 'No Title')
            publisher = item.get('publisher', 'Unknown Source')
            link = item.get('link', '#')
            date = item.get('pubDate', '')[:16]
            st.markdown(f"""
            <div style="background-color:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:12px; margin-bottom:10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                <h4 style="margin:0; font-size:16px;"><a href="{link}" target="_blank" style="color:#2563EB; text-decoration:none;">{title}</a></h4>
                <p style="margin:4px 0 0 0; color:#64748B; font-size:12px;">{publisher} | {date}</p>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No recent news updates found for this asset.")

# TAB 3: GEMINI AI CHATBOT WITH RAG
with tab_ai:
    st.markdown(f"### Assistant for **{company_name}**")
    
    if not gemini_key:
        st.warning("Please enter your free Google Gemini API Key in the left sidebar or configure it in Streamlit Secrets.")
    else:
        st.markdown("#### 📄 Upload a Document (Annual Report, Transcript) for Context")
        uploaded_file = st.file_uploader(f"Upload a PDF related to {company_name}", type=["pdf"])
        
        if uploaded_file is not None and "vector_store" not in st.session_state:
            with st.spinner("Processing document and building RAG index..."):
                pdf_reader = PyPDF2.PdfReader(uploaded_file)
                raw_text = "".join([page.extract_text() for page in pdf_reader.pages])
                text_chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200).split_text(raw_text)
                embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=gemini_key)
                st.session_state.vector_store = FAISS.from_texts(text_chunks, embeddings)
                st.success("Document embedded successfully! You can now ask questions about it.")

        try:
            client = genai.Client(api_key=gemini_key)
            if "messages" not in st.session_state: st.session_state.messages = []
            for message in st.session_state.messages:
                with st.chat_message(message["role"]): st.markdown(message["content"])

            if prompt := st.chat_input(f"Ask Gemini about {company_name} or query your uploaded document..."):
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"): st.markdown(prompt)

                rag_context = ""
                if "vector_store" in st.session_state:
                    docs = st.session_state.vector_store.similarity_search(prompt, k=3)
                    rag_context = "\n\n".join([doc.page_content for doc in docs])

                system_instruction = f"""
                You are an equity research analyst.
                Context for {company_name}: Price: ₹{current_price} | P/E: {info.get('trailingPE', 'N/A')} | Market Cap: ₹{info.get('marketCap', 0) / 1e7:,.2f} Cr
                DOCUMENT CONTEXT: {rag_context if rag_context else "None"}
                """

                with st.chat_message("assistant"):
                    message_placeholder = st.empty()
                    response = client.models.generate_content_stream(model='gemini-3.6-flash', contents=prompt, config={'system_instruction': system_instruction})
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
