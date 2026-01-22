import streamlit as st
import yfinance as yf
import pandas as pd
import concurrent.futures
import plotly.graph_objects as go
import numpy as np
import pytz
import requests
from datetime import datetime, time, timedelta

# ==========================================
# 🔑 API 설정
# ==========================================
FINNHUB_API_KEY = "d5p0p81r01qu6m6bocv0d5p0p81r01qu6m6bocvg"

# === [1. 페이지 설정] ===
st.set_page_config(page_title="QUANT NEXUS : ULTIMATE", page_icon="🦅", layout="wide", initial_sidebar_state="expanded")

# === [2. 관심종목 세션] ===
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = set()

# === [3. 유틸리티] ===
def get_market_status():
    ny_tz = pytz.timezone('America/New_York')
    now_ny = datetime.now(ny_tz)
    if now_ny.weekday() >= 5: return "CLOSE", "마감(휴일)", "mkt-cls"
    curr = now_ny.time()
    if time(4,0) <= curr < time(9,30): return "PRE", "프리장", "mkt-pre"
    elif time(9,30) <= curr <= time(16,0): return "REG", "정규장", "mkt-reg"
    elif time(16,0) < curr <= time(20,0): return "AFTER", "애프터", "mkt-aft"
    else: return "CLOSE", "마감", "mkt-cls"

def check_recent_news(ticker):
    if not FINNHUB_API_KEY: return False, None
    try:
        fr = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        to = datetime.now().strftime("%Y-%m-%d")
        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={fr}&to={to}&token={FINNHUB_API_KEY}"
        res = requests.get(url, timeout=2)
        if res.status_code == 200:
            data = res.json()
            if data and isinstance(data, list):
                return True, data[0].get('headline', '뉴스 내용 없음')
    except: pass
    return False, None

# === [4. 스타일] ===
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    .metric-card { background-color: #1E1E1E; border: 1px solid #444; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
    .price-row { display: flex; justify-content: space-between; align-items: center; padding: 2px 0; font-size: 13px; border-bottom: 1px solid #333; }
    .price-val { font-weight: bold; color: white; font-family: monospace; font-size: 13px; }
    .score-container { display: flex; justify-content: space-between; margin-top: 10px; background-color: #252526; padding: 6px; border-radius: 4px; }
    .score-item { text-align: center; font-size: 10px; color: #888; width: 24%; }
    .score-val { font-weight: bold; font-size: 13px; display: block; margin-top: 2px; }
    .sc-high { color: #00FF00; } .sc-mid { color: #FFD700; } .sc-low { color: #FF4444; }
    .price-target-box { display: flex; justify-content: space-between; background-color: #151515; padding: 8px; border-radius: 4px; margin-top: 8px; border: 1px dashed #444; }
    .pt-item { text-align: center; width: 33%; font-size: 12px; }
    .pt-val { font-weight: bold; font-size: 13px; color: white; }
    .exit-box { background-color: #2d3436; border-left: 3px solid #636e72; padding: 8px; font-size: 11px; color: #dfe6e9; margin-top: 10px; }
    .ticker-header { font-size: 18px; font-weight: bold; color: #00CCFF; text-decoration: none !important; }
    .badge { padding: 2px 5px; border-radius: 3px; font-size: 9px; font-weight: bold; color: white; margin-left: 5px; }
    .news-line { color: #ffa502; font-size: 12px; margin-top: 4px; padding: 4px; background-color: #2d2d2d; border-radius: 4px; display: block; border-left: 3px solid #ffa502; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .mkt-pre { background-color: #d29922; color: black; } .mkt-reg { background-color: #238636; } .mkt-aft { background-color: #1f6feb; } .mkt-cls { background-color: #6e7681; }
    .st-gamma { background-color: #6c5ce7; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .st-squeeze { background-color: #0984e3; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .st-value { background-color: #00b894; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
    .st-none { background-color: #333; color: #777; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
    .st-highconv { background-color: #e17055; color: white; padding: 2px 6px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-left: 5px; }
</style>
""", unsafe_allow_html=True)

# === [5. 27개 섹터 (레버리지 2종 추가됨)] ===
SECTORS = {
    "01. 🔥 지수 레버리지 (2x/3x)": ["TQQQ", "SQQQ", "SOXL", "SOXS", "UPRO", "SPXU", "TMF", "TMV", "LABU", "LABD", "FNGU", "FNGD", "BULZ", "BERZ", "YINN", "YANG", "UVXY", "BOIL", "KOLD"],
    "02. 💣 개별주 레버리지 (2x/3x)": ["NVDL", "NVDS", "TSLL", "TSLQ", "AMZU", "AAPU", "GOOX", "MSFU", "CONL", "MSTX", "MSTY", "BITX", "NVDX", "BABX"],
    "03. 🇺🇸 시장 지수 (1x)": ["SPY", "QQQ", "DIA", "IWM", "VTI", "VOO", "TLT", "HYG", "VXX"],
    "04. 🚀 빅테크 (M7+)": ["NVDA", "MSFT", "GOOGL", "AMZN", "META", "PLTR", "AVGO", "ADBE", "CRM", "AMD", "IBM", "NOW", "INTC", "QCOM", "AMAT", "MU", "LRCX", "ADI", "SNOW", "DDOG", "NET", "MDB", "PANW", "CRWD", "ZS", "FTNT", "TEAM", "WDAY", "SMCI", "ARM", "PATH", "AI", "SOUN", "BBAI", "ORCL", "CSCO"],
    "05. 💾 반도체": ["NVDA", "TSM", "AVGO", "AMD", "INTC", "ASML", "AMAT", "LRCX", "MU", "QCOM", "ADI", "TXN", "MRVL", "KLAC", "NXPI", "STM", "ON", "MCHP", "MPWR", "TER", "ENTG", "SWKS", "QRVO", "WOLF", "COHR", "IPGP", "LSCC", "RMBS", "FORM", "ACLS", "CAMT", "UCTT", "ICHR", "AEHR", "GFS"],
    "06. 🧈 금/광물/희토류": ["MP", "UUUU", "LAC", "ALTM", "SGML", "PLL", "LTHM", "REMX", "TMC", "NB", "TMQ", "TMRC", "RIO", "BHP", "VALE", "FCX", "SCCO", "AA", "GOLD", "NEM", "KL", "GDX", "GDXJ", "GLD", "SLV"],
    "07. 💊 바이오 & 비만": ["LLY", "NVO", "AMGN", "PFE", "VKTX", "ALT", "ZP", "GILD", "BMY", "JNJ", "ABBV", "MRK", "BIIB", "REGN", "VRTX", "MRNA", "BNTX", "NVS", "AZN", "SNY", "CRSP", "EDIT", "NTLA", "BEAM"],
    "08. 🏦 핀테크 & 크립토": ["COIN", "MSTR", "HOOD", "SQ", "PYPL", "SOFI", "AFRM", "UPST", "MARA", "RIOT", "CLSK", "HUT", "WULF", "CIFR", "IREN", "CORZ", "SDIG", "V", "MA", "AXP", "DFS", "COF", "NU", "LC"],
    "09. 🛡️ 방산 & 우주": ["RTX", "LMT", "NOC", "GD", "BA", "LHX", "HII", "LDOS", "AXON", "KTOS", "AVAV", "RKLB", "SPCE", "ASTS", "LUNR", "PL", "SPIR", "BKSY", "VSAT", "IRDM", "JOBY", "ACHR"],
    "10. ⚡ 에너지 & 원전": ["CCJ", "UUUU", "NXE", "UEC", "DNN", "SMR", "BWXT", "LEU", "OKLO", "FLR", "URA", "CEG", "VST", "XOM", "CVX", "SLB", "OXY", "VLO", "HAL", "MPC"],
    "11. 🛍️ 소비재 & 럭셔리": ["LVMUY", "RACE", "NKE", "LULU", "ONON", "DECK", "CROX", "RL", "TPR", "CPRI", "EL", "COTY", "ULTA", "ELF", "WMT", "COST", "TGT", "HD", "LOW", "SBUX", "MCD", "CMG", "KO", "PEP"],
    "12. 🦍 밈(Meme)": ["GME", "AMC", "RDDT", "DJT", "TSLA", "PLTR", "SOFI", "OPEN", "LCID", "RIVN", "CHPT", "NKLA", "SPCE", "BB", "NOK", "KOSS", "CVNA", "AI"],
    "13. ⚛️ 양자컴퓨터": ["IONQ", "RGTI", "QUBT", "HON", "IBM", "GOOGL", "FORM", "D-WAVE", "QBTS", "QMCO"],
    "14. 🤖 로봇 & 자동화": ["ISRG", "TER", "PATH", "SYM", "ABB", "CGNX", "ROBO", "BOTZ", "IRBT", "DE", "CAT", "EMR"],
    "15. ☁️ 클라우드/SaaS": ["CRM", "NOW", "SNOW", "DDOG", "NET", "MDB", "TEAM", "WDAY", "ADBE", "PANW", "CRWD", "ZS", "OKTA", "PLTR", "SHOP", "MELI", "SE"],
    "16. 🎮 게임 & 메타버스": ["RBLX", "U", "EA", "TTWO", "SONY", "NTES", "MSFT", "NVDA", "CRSR", "LOGI"],
    "17. 🎬 미디어 & 스트리밍": ["NFLX", "DIS", "WBD", "PARA", "SPOT", "ROKU", "CMCSA", "GOOGL", "AMZN", "AAPL"],
    "18. 💰 금융 (은행/투자)": ["JPM", "BAC", "WFC", "C", "GS", "MS", "HSBC", "UBS", "BLK", "SCHW"],
    "19. ☀️ 태양광 & 친환경": ["ENPH", "SEDG", "FSLR", "NEE", "RUN", "CSIQ", "DQ", "JKS", "PLUG", "FCEL", "BE", "STEM", "TAN", "ICLN"],
    "20. 🏗️ 산업재": ["UPS", "FDX", "CAT", "DE", "HON", "GE", "MMM", "UNP", "EMR", "ETN", "URI", "PWR"],
    "21. 🏠 리츠 (부동산)": ["AMT", "PLD", "CCI", "EQIX", "O", "DLR", "WELL", "SPG", "VICI", "PSA"],
    "22. ✈️ 여행 & 레저": ["BKNG", "ABNB", "MAR", "HLT", "RCL", "CCL", "DAL", "UAL", "LUV", "EXPE", "TRIP", "MGM", "LVS", "DKNG"],
    "23. 🥤 식음료": ["PEP", "KO", "MDLZ", "MNST", "HSY", "KDP", "GIS", "K", "SBUX", "CMG", "MCD", "YUM", "DPZ"],
    "24. 🔐 사이버보안": ["PANW", "CRWD", "FTNT", "NET", "ZS", "OKTA", "CYBR", "HACK", "CIBR", "DOCU", "DBX"],
    "25. 🇨🇳 중국": ["BABA", "PDD", "JD", "BIDU", "TCEHY", "NIO", "XPEV", "LI", "FXI", "KWEB"],
    "26. 🌐 글로벌": ["SONY", "TM", "HMC", "SHEL", "TTE", "ASML", "TSM", "AZN", "NVS"]
}
ALL_TICKERS = sorted(list(set([ticker for s in SECTORS.values() for ticker in s])))

# === [6. 설정값] ===
CONFIG = {"NAV": 10000}

# === [7. 엔진: Logic Core] ===
@st.cache_data(ttl=600)
def get_market_data(tickers):
    data_list = []
    mkt_code, mkt_label, mkt_class = get_market_status()
    
    def fetch_single(ticker):
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 60: return None
            
            cur = hist['Close'].iloc[-1]
            open_price = hist['Open'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            diff_open, diff_prev = cur - open_price, cur - prev_close
            chg_open, chg_prev = (diff_open/open_price)*100, (diff_prev/prev_close)*100
            
            # 지표 계산
            ma20 = hist['Close'].rolling(20).mean()
            std = hist['Close'].rolling(20).std()
            bbw = ((ma20 + std*2) - (ma20 - std*2)) / ma20
            sc_squeeze = (1 - bbw.rank(pct=True).iloc[-1]) * 10
            
            vol_avg = hist['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = hist['Volume'].iloc[-1] / vol_avg
            sc_vol = min(10, vol_ratio * 3)
            
            # 전략 및 타이트한 가격 로직 (익절라인 정상화: 현재가 + %)
            cat, s_name, s_class = "NONE", "관망", "st-none"
            tgt_pct, stp_pct, trl_pct, t_limit = 0.05, 0.03, 0.015, "5일"

            if sc_vol > 7 and cur > ma20.iloc[-1]: # 단타
                cat, s_name, s_class = "SHORT", "🚀 단타", "st-gamma"
                tgt_pct, stp_pct, trl_pct, t_limit = 0.03, 0.02, 0.01, "당일 청산"
            elif sc_squeeze > 7: # 스윙
                cat, s_name, s_class = "SWING", "🌊 스윙", "st-squeeze"
                tgt_pct, stp_pct, trl_pct, t_limit = 0.10, 0.06, 0.04, "14일"
            elif cur > ma20.iloc[-1] * 1.05: # 장투
                cat, s_name, s_class = "LONG", "🌲 장투", "st-value"
                tgt_pct, stp_pct, trl_pct, t_limit = 0.30, 0.15, 0.10, "90일"

            # 뉴스 체크
            is_hc, news_hl = False, None
            if vol_ratio > 3.0:
                ok, hl = check_recent_news(ticker)
                if ok: is_hc, news_hl = True, hl

            journal = {"ticker": ticker, "squeeze": sc_squeeze, "entry": cur, "category": cat, "timestamp": get_timestamp_str()}

            return {
                "Ticker": ticker, "Price": cur, "StratName": s_name, "StratClass": s_class,
                "Squeeze": sc_squeeze, "Trend": 8.0 if cur > ma20.iloc[-1] else 3.0, "Vol": sc_vol, "Regime": 5.0,
                "Target": cur*(1+tgt_pct), "Stop": cur*(1-stp_pct), "Trail": cur*(1+trl_pct), "Time": t_limit,
                "DiffOpen": diff_open, "ChgOpen": chg_open, "DiffPrev": diff_prev, "ChgPrev": chg_prev,
                "History": hist['Close'], "MktL": mkt_label, "MktC": mkt_class, "HC": is_hc, "News": news_hl, "Journal": journal
            }
        except: return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(fetch_single, t) for t in tickers]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: data_list.append(res)
    return data_list

# === [8. UI 메인] ===
with st.sidebar:
    st.title("🪟 KOREAN MASTER")
    st.caption(f"NAV: ${CONFIG['NAV']:,}")
    mode = st.radio("모드", ["📌 섹터별", "🔍 검색", "⭐ 관심종목"])
    target_tickers = []
    if mode == "📌 섹터별":
        sec = st.selectbox("섹터 선택", list(SECTORS.keys()))
        target_tickers = SECTORS[sec]
    elif mode == "🔍 검색":
        t_input = st.text_input("티커 입력 (쉼표 구분)", "AAPL,TSLA,NVDA")
        target_tickers = [x.strip().upper() for x in t_input.split(',')]
    elif mode == "⭐ 관심종목":
        target_tickers = list(st.session_state.watchlist)
    
    if st.button("🔄 새로고침"): st.cache_data.clear(); st.rerun()

st.title(f"🇺🇸 {mode}")
market_data = get_market_data(target_tickers)

if market_data:
    tab1, tab2 = st.tabs(["📊 대시보드", "💰 상세 리포트"])
    with tab1:
        cols = st.columns(3)
        for i, row in enumerate(market_data):
            with cols[i % 3]:
                is_fav = row['Ticker'] in st.session_state.watchlist
                if st.button("❤️" if is_fav else "🤍", key=f"fav_{i}"):
                    if is_fav: st.session_state.watchlist.remove(row['Ticker'])
                    else: st.session_state.watchlist.add(row['Ticker'])
                    st.rerun()
                
                badge = "<span class='st-highconv'>🔥 High Conviction</span>" if row['HC'] else ""
                news = f"<span class='news-line'>📰 {row['News']}</span>" if row['News'] else ""
                c_op = "#00FF00" if row['ChgOpen'] >= 0 else "#FF4444"
                c_pr = "#00FF00" if row['ChgPrev'] >= 0 else "#FF4444"

                html = f"""<div class="metric-card">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <a href="https://finance.yahoo.com/quote/{row['Ticker']}" target="_blank" class="ticker-header">{row['Ticker']}</a>
                        <div>{badge}<span class="badge {row['MktC']}">{row['MktL']}</span></div>
                    </div>
                    {news}
                    <div class="price-row" style="margin-top:10px;"><span class="price-label">현재가(24h)</span><span class="price-val">${row['Price']:.2f}</span></div>
                    <div class="price-row"><span class="price-label">시가대비</span><span class="price-val" style="color:{c_op}">{row['DiffOpen']:+.2f} ({row['ChgOpen']:+.2f}%)</span></div>
                    <div class="price-row"><span class="price-label">전일대비</span><span class="price-val" style="color:{c_pr}">{row['DiffPrev']:+.2f} ({row['ChgPrev']:+.2f}%)</span></div>
                    <div style="text-align:center; margin:10px 0;"><span class="{row['StratClass']}">{row['StratName']}</span></div>
                    <div class="score-container">
                        <div class="score-item">응축<br><span class="score-val {'sc-high' if row['Squeeze']>=7 else 'sc-low'}">{row['Squeeze']:.0f}</span></div>
                        <div class="score-item">추세<br><span class="score-val {'sc-high' if row['Trend']>=7 else 'sc-low'}">{row['Trend']:.0f}</span></div>
                        <div class="score-item">수급<br><span class="score-val {'sc-high' if row['Vol']>=7 else 'sc-low'}">{row['Vol']:.0f}</span></div>
                    </div>
                    <div class="price-target-box">
                        <div class="pt-item"><span class="pt-label" style="color:#aaa;">목표가</span><span class="pt-val" style="color:#00FF00;">${row['Target']:.2f}</span></div>
                        <div class="pt-item"><span class="pt-label" style="color:#aaa;">손절가</span><span class="pt-val" style="color:#FF4444;">${row['Stop']:.2f}</span></div>
                    </div>
                    <div class="exit-box">
                        <span style="color:#00FF00; font-weight:bold;">✅ 익절라인: ${row['Trail']:.2f}</span><br>
                        <span style="color:#FF4444;">🚨 칼손절가: ${row['Stop']:.2f}</span><br>
                        <span style="color:#aaa;">⏳ 전략 유효기간: {row['Time']}</span>
                    </div>
                </div>"""
                st.markdown(html, unsafe_allow_html=True)
                fig = go.Figure(go.Scatter(y=row['History'], mode='lines', line=dict(color='#00CCFF', width=1.5), fill='tozeroy'))
                fig.update_layout(height=60, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True, key=f"chart_{i}", config={'displayModeBar': False})
    with tab2:
        cols = st.columns(3)
        for i, row in enumerate(market_data):
            with cols[i % 3]:
                # 카드 형식으로 상세 리포트 렌더링 (드래그/JSON 삭제)
                st.info(f"📌 {row['Ticker']} 투자 리포트")
                st.json(row['Journal'])