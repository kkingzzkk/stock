import streamlit as st
import yfinance as yf
import pandas as pd
import concurrent.futures
import plotly.graph_objects as go
import numpy as np
import pytz
import textwrap
import requests
from datetime import datetime, time, timedelta

# ==========================================
# 🔑 API 설정 (형님 키 적용)
# ==========================================
FINNHUB_API_KEY = "d5p0p81r01qu6m6bocv0d5p0p81r01qu6m6bocvg"

# === [1. 페이지 설정] ===
st.set_page_config(page_title="QUANT NEXUS : SMART TRADER", page_icon="🦅", layout="wide", initial_sidebar_state="expanded")

# === [2. 관심종목 세션 초기화] ===
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = set()

# === [3. 유틸리티 함수] ===
def get_market_status():
    ny_tz = pytz.timezone('America/New_York')
    now_ny = datetime.now(ny_tz)
    if now_ny.weekday() >= 5: return "CLOSE", "마감(휴일)", "mkt-cls"
    current_time = now_ny.time()
    if time(4, 0) <= current_time < time(9, 30): return "PRE", "프리장", "mkt-pre"
    elif time(9, 30) <= current_time <= time(16, 0): return "REG", "정규장", "mkt-reg"
    elif time(16, 0) < current_time <= time(20, 0): return "AFTER", "애프터", "mkt-aft"
    else: return "CLOSE", "데이장(정보없음)", "mkt-day"

def get_timestamp_str():
    ny_tz = pytz.timezone('America/New_York')
    return datetime.now(ny_tz).strftime("%Y-%m-%d %H:%M:%S")

# 뉴스 체크 함수 (필요할 때만 호출)
def check_recent_news(ticker):
    if not FINNHUB_API_KEY: return False, None
    try:
        fr_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={fr_date}&to={to_date}&token={FINNHUB_API_KEY}"
        
        res = requests.get(url, timeout=3) # 3초 제한
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) > 0:
                return True, data[0].get('headline', '뉴스 내용 없음')
    except:
        return False, None
    return False, None

# === [4. 스타일(CSS)] ===
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    .metric-card { background-color: #1E1E1E; border: 1px solid #444; border-radius: 8px; padding: 15px; margin-bottom: 15px; position: relative; }
    
    .price-row { display: flex; justify-content: space-between; align-items: center; padding: 2px 0; font-size: 13px; border-bottom: 1px solid #333; }
    .price-label { color: #aaa; font-size: 11px; }
    .price-val { font-weight: bold; color: white; font-family: monospace; font-size: 13px; }

    .score-container { display: flex; justify-content: space-between; margin-top: 10px; margin-bottom: 8px; background-color: #252526; padding: 6px; border-radius: 4px; }
    .score-item { text-align: center; font-size: 10px; color: #888; width: 19%; }
    .score-val { font-weight: bold; font-size: 13px; display: block; margin-top: 2px; }
    .sc-high { color: #00FF00; } .sc-mid { color: #FFD700; } .sc-low { color: #FF4444; }
    
    .indicator-box { background-color: #252526; border-radius: 4px; padding: 6px; margin-top: 8px; font-size: 11px; color: #ccc; text-align: center; border: 1px solid #333; }
    .opt-row { display: flex; justify-content: space-between; font-size: 11px; margin-top: 4px; font-weight: bold; }
    .opt-call { color: #00FF00; } .opt-put { color: #FF4444; }
    .opt-bar-bg { background-color: #333; height: 5px; border-radius: 2px; overflow: hidden; display: flex; margin-top: 3px; }
    .opt-bar-c { background-color: #00FF00; height: 100%; }
    .opt-bar-p { background-color: #FF4444; height: 100%; }

    .price-target-box { display: flex; justify-content: space-between; background-color: #151515; padding: 8px; border-radius: 4px; margin-top: 8px; margin-bottom: 8px; border: 1px dashed #444; }
    .pt-item { text-align: center; width: 33%; font-size: 12px; }
    .pt-label { color: #aaa; font-size: 10px; display: block; }
    .pt-val { font-weight: bold; font-size: 13px; color: white; }
    .pt-entry { color: #74b9ff; } .pt-target { color: #00FF00; } .pt-stop { color: #FF4444; }

    .exit-box { background-color: #2d3436; border-left: 3px solid #636e72; padding: 8px; font-size: 11px; color: #dfe6e9; margin-top: 10px; }
    .exit-primary { color: #fff; font-weight: bold; border-left-color: #00FF00 !important; }
    .bet-badge { font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 4px; color: black; float: right; margin-top: 5px; }
    .bet-bg { background-color: #74b9ff; }

    .ticker-header { font-size: 18px; font-weight: bold; color: #00CCFF; text-decoration: none !important; }
    .ticker-header:hover { color: #fff !important; text-decoration: underline !important; }
    .badge { padding: 2px 5px; border-radius: 3px; font-size: 9px; font-weight: bold; color: white; margin-left: 5px; vertical-align: middle;}
    .mkt-pre { background-color: #d29922; color: black; }
    .mkt-reg { background-color: #238636; color: white; }
    .mkt-aft { background-color: #1f6feb; color: white; }
    .mkt-cls { background-color: #6e7681; color: white; }
    .mkt-day { background-color: #e17055; color: white; }
    
    .st-gamma { background-color: #6c5ce7; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block; }
    .st-squeeze { background-color: #0984e3; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block;}
    .st-value { background-color: #00b894; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block;}
    .st-risk { background-color: #d63031; color: white; padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; display:inline-block;}
    .st-none { background-color: #333; color: #777; padding: 3px 8px; border-radius: 4px; font-size: 11px; display:inline-block;}
    
    .st-highconv { background-color: #e17055; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; display:inline-block; margin-left: 5px; vertical-align: middle; }
    .news-line { color: #ffa502; font-size: 12px; margin-top: 4px; padding: 4px; background-color: #2d2d2d; border-radius: 4px; display: block; border-left: 3px solid #ffa502; }
</style>
""", unsafe_allow_html=True)

# === [5. 데이터 설정] ===
SECTORS = {
    "01. 🇺🇸 시장 지수": ["SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "TLT", "HYG", "UVXY", "VXX"],
    "02. 🔥 지수 3배 (ETF)": ["TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXU", "TMF", "TMV", "LABU", "LABD", "FNGU", "FNGD", "BULZ", "BERZ", "YINN", "YANG"],
    "03. 💣 개별주 2배/3배 (야수)": ["NVDL", "NVDS", "TSLL", "TSLQ", "AMZU", "AAPU", "GOOX", "MSFU", "CONL", "MSTX", "MSTY", "BITX"],
    "04. 🚀 빅테크 (M7+)": ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AAPL", "PLTR", "AVGO", "ORCL", "SMCI", "ARM", "IBM", "CSCO"],
    "05. 💾 반도체": ["NVDA", "TSM", "AVGO", "AMD", "INTC", "ASML", "AMAT", "MU", "QCOM", "LRCX", "TXN", "ADI", "MRVL", "ON", "STM"],
    "06. 💊 바이오": ["LLY", "NVO", "AMGN", "PFE", "VKTX", "GILD", "BMY", "JNJ", "ISRG", "MRK", "BIIB", "REGN", "MRNA", "VRTX", "CRSP"],
    "07. 🛡️ 방산/우주": ["RTX", "LMT", "NOC", "GD", "BA", "RKLB", "AXON", "KTOS", "PL", "SPCE", "LUNR", "ASTS", "LHX", "HII"],
    "08. ⚡ 에너지/원전": ["XOM", "CVX", "SLB", "OXY", "VLO", "HAL", "MPC", "COP", "CCJ", "FCX", "USO", "XLE", "CEG", "SMR", "OKLO", "UUUU"],
    "09. 🏦 금융/핀테크": ["JPM", "BAC", "WFC", "C", "GS", "MS", "NU", "UBS", "XLF", "BLK", "PYPL", "SQ", "HOOD", "AFRM", "UPST", "SOFI"],
    "10. 🪙 크립토": ["IBIT", "BITO", "COIN", "MSTR", "MSTY", "MARA", "RIOT", "CLSK", "HUT", "WULF", "CIFR", "IREN"],
    "11. 🚘 전기차/자율주행": ["TSLA", "RIVN", "LCID", "NIO", "XPEV", "LI", "F", "GM", "LAZR", "MBLY", "QS", "BLNK", "CHPT"],
    "12. 🛍️ 소비재/리테일": ["AMZN", "WMT", "COST", "TGT", "HD", "LOW", "NKE", "LULU", "SBUX", "MCD", "CMG", "KO", "PEP", "CELH"],
    "13. ☁️ 클라우드/SaaS": ["CRM", "NOW", "SNOW", "DDOG", "NET", "MDB", "TEAM", "WDAY", "ADBE", "PANW", "CRWD", "ZS", "OKTA", "PLTR"],
    "14. 🦍 밈(Meme)": ["GME", "AMC", "RDDT", "DJT", "KOSS", "BB", "NOK", "CHWY", "CVNA", "OPEN", "Z"],
    "15. 🇨🇳 중국": ["BABA", "PDD", "JD", "BIDU", "TCEHY", "NIO", "XPEV", "LI", "BEKE", "TCOM", "FXI", "KWEB"],
    "16. ✈️ 여행/항공": ["BKNG", "ABNB", "DAL", "UAL", "CCL", "RCL", "LUV", "JETS", "TRIP", "EXPE", "HLT", "MAR"],
    "17. 🏠 리츠 (부동산)": ["O", "AMT", "PLD", "CCI", "EQIX", "MAIN", "VICI", "XLRE", "SPG", "ADC", "VNO"],
    "18. 🏗️ 산업재": ["CAT", "DE", "GE", "MMM", "HON", "UNP", "EMR", "PAVE", "URI", "ETN"],
    "19. ☀️ 태양광/친환경": ["ENPH", "SEDG", "FSLR", "NEE", "RUN", "CSIQ", "TAN", "ICLN", "BEP"],
    "20. 🧈 금/광물": ["GOLD", "NEM", "KL", "GDX", "GDXJ", "GLD", "SLV", "AEM", "FCX", "SCCO"],
    "21. ⛏️ 희토류": ["MP", "LAC", "ALTM", "SGML", "VALE", "LIT", "REMX", "ALB"],
    "22. ⚛️ 양자컴퓨터": ["IONQ", "RGTI", "QUBT", "IBM", "GOOGL", "D-WAVE", "QBTS"],
    "23. 🚢 해운/물류": ["ZIM", "GSL", "UPS", "FDX", "DAC", "SBLK", "NAT"],
    "24. 📡 통신/5G": ["VZ", "T", "TMUS", "CMCSA", "CHTR", "NOK", "ERIC"],
    "25. 🎬 미디어": ["NFLX", "DIS", "WBD", "SPOT", "ROKU", "PARA", "CMCSA"],
    "26. 🤖 로봇": ["ISRG", "TER", "PATH", "ABB", "ROBO", "BOTZ"],
    "27. 🧬 유전자": ["VRTX", "CRSP", "NTLA", "BEAM", "EDIT", "ARKG", "DNA"],
    "28. 🥤 식음료": ["KO", "PEP", "MCD", "SBUX", "CMG", "HSY", "MNST", "K", "GIS"],
    "29. 🏥 의료기기": ["ISRG", "SYK", "BSX", "MDT", "EW", "ZBH"],
    "30. 🪵 원자재": ["AA", "X", "CLF", "NUE", "STLD"],
    "31. 🌐 글로벌": ["TSM", "ASML", "BABA", "SONY", "TM", "HMC", "SHEL", "TTE"]
}
ALL_TICKERS = sorted(list(set([ticker for sector in SECTORS.values() for ticker in sector])))

INDEX_CONSTITUENTS = {
    "NASDAQ100": ["AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "AVGO", "COST", "PEP", "CSCO", "TMUS", "CMCSA", "INTC", "AMD", "QCOM", "TXN", "AMGN", "HON", "INTU", "SBUX", "GILD", "MDLZ", "BKNG", "ADI", "ISRG", "ADP", "REGN", "VRTX", "LRCX", "PANW", "SNPS", "CDNS", "KLAC", "ASML", "MELI", "MNST", "ORCL", "MAR", "NXPI", "CTAS", "FTNT", "DXCM", "WDAY", "MCHP", "AEP", "KDP", "LULU", "MRVL", "ADSK"],
    "SP500_TOP": ["MSFT", "AAPL", "NVDA", "AMZN", "GOOGL", "META", "BRK.B", "TSLA", "LLY", "AVGO", "JPM", "V", "UNH", "XOM", "MA", "JNJ", "HD", "PG", "COST", "MRK", "ABBV", "CRM", "CVX", "BAC", "AMD", "NFLX", "PEP", "KO", "WMT", "ADBE", "TMO", "ACN", "LIN", "MCD", "CSCO", "ABT", "DIS", "INTU", "WFC", "VZ", "CMCSA", "QCOM", "DHR", "CAT", "TXN", "AMGN", "IBM", "PM", "UNP", "GE"],
    "RUSSELL_GROWTH": ["SMCI", "MSTR", "COIN", "CVNA", "AFRM", "DKNG", "HOOD", "RIVN", "SOFI", "PLTR", "PATH", "U", "RBLX", "OPEN", "LCID", "MARA", "RIOT", "CLSK", "GME", "AMC", "UPST", "AI", "IONQ", "RGTI", "QUBT", "JOBY", "ACHR", "ASTS", "LUNR", "RKLB"]
}

# === [6. 설정값 (기본)] ===
CONFIG = {
    "NAV": 10000, 
}

# === [7. 엔진: Logic Core] ===
@st.cache_data(ttl=600)
def get_market_data(tickers):
    tickers = list(set(tickers))
    
    try:
        spy = yf.download("SPY", period="6mo", progress=False)
        vix = yf.Ticker("^VIX").history(period="5d")
        if isinstance(spy.columns, pd.MultiIndex): spy.columns = spy.columns.get_level_values(0)
        spy_trend = 1 if spy['Close'].iloc[-1] > spy['Close'].rolling(200).mean().iloc[-1] else 0
        vix_val = vix['Close'].iloc[-1]
        
        regime_score = 5.0
        if spy_trend: regime_score += 2.0
        if vix_val < 20: regime_score += 3.0
        elif vix_val < 25: regime_score += 1.0
        elif vix_val > 30: regime_score -= 3.0
        regime_score = max(0, min(10, regime_score))
    except: regime_score = 5.0

    data_list = []
    mkt_code, mkt_label, mkt_class = get_market_status()
    
    def fetch_single(ticker):
        try:
            # 1. 차트 데이터 확보
            stock = yf.Ticker(ticker)
            hist_day = stock.history(period="1y") 
            if hist_day.empty or len(hist_day) < 120: return None
            
            hist_15m = stock.history(period="5d", interval="15m")
            has_intraday = False if (hist_15m is None or len(hist_15m) < 30) else True
            
            hist_rt = stock.history(period="1d", interval="1m", prepost=True)
            if not hist_rt.empty: cur = hist_rt['Close'].iloc[-1]
            else: cur = hist_day['Close'].iloc[-1]

            # Price Diff
            open_price = hist_day['Open'].iloc[-1]
            prev_close = hist_day['Close'].iloc[-2]
            diff_open = cur - open_price
            diff_prev = cur - prev_close
            chg_open = (diff_open / open_price) * 100
            chg_prev = (diff_prev / prev_close) * 100
            
            # Factors
            ma20 = hist_day['Close'].rolling(20).mean()
            std = hist_day['Close'].rolling(20).std()
            bbw_series = ((ma20 + std*2) - (ma20 - std*2)) / ma20
            bbw_rank = bbw_series.rolling(window=120, min_periods=60).apply(lambda x: pd.Series(x).rank(pct=True).iloc[-1]).iloc[-1]
            if np.isnan(bbw_rank): bbw_rank = 0.5
            sc_squeeze = (1 - bbw_rank) * 10
            
            subset = hist_day.iloc[-60:].copy()
            top3_vol = subset['Volume'].nlargest(3).index
            anchor = top3_vol.max()
            avwap_sub = subset.loc[anchor:]
            avwap = (avwap_sub['Close'] * avwap_sub['Volume']).cumsum().iloc[-1] / avwap_sub['Volume'].cumsum().iloc[-1]
            
            sc_trend = 5.0
            if cur > ma20.iloc[-1]: sc_trend