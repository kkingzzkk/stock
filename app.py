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
CONFIG = {"NAV": 10000, "BASE_BET": 0.15}

# === [7. 엔진: Logic Core] ===
@st.cache_data(ttl=600)
def get_market_data(tickers):
    tickers = list(set(tickers))
    try:
        spy = yf.download("SPY", period="6mo", progress=False)
        vix = yf.Ticker("^VIX").history(period="5d")
        regime_score = 5.0
        if not spy.empty:
            spy_ma200 = spy['Close'].rolling(200).mean().iloc[-1]
            if spy['Close'].iloc[-1] > spy_ma200: regime_score += 2.0
        if not vix.empty:
            v_val = vix['Close'].iloc[-1]
            if v_val < 20: regime_score += 3.0
            elif v_val > 30: regime_score -= 3.0
    except: regime_score = 5.0

    data_list = []
    mkt_code, mkt_label, mkt_class = get_market_status()
    
    def fetch_single(ticker):
        sc_trend, sc_squeeze, sc_vol, sc_option = 5.0, 5.0, 5.0, 5.0
        rsi, pcr, c_vol, p_vol = 50, 1.0, 0, 0
        c_pct, p_pct = 50, 50
        
        try:
            stock = yf.Ticker(ticker)
            hist_day = stock.history(period="1y") 
            if hist_day.empty or len(hist_day) < 60: return None
            
            hist_rt = stock.history(period="1d", interval="1m", prepost=True)
            cur = hist_rt['Close'].iloc[-1] if not hist_rt.empty else hist_day['Close'].iloc[-1]

            open_p, prev_c = hist_day['Open'].iloc[-1], hist_day['Close'].iloc[-2]
            diff_o, diff_p = cur - open_p, cur - prev_c
            chg_o, chg_p = (diff_o/open_p)*100, (diff_p/prev_c)*100
            
            ma20 = hist_day['Close'].rolling(20).mean()
            std20 = hist_day['Close'].rolling(20).std()
            bbw = ((ma20 + std20*2) - (ma20 - std20*2)) / ma20
            sc_squeeze = (1 - bbw.rank(pct=True).iloc[-1]) * 10
            sc_trend = 7.0 if cur > ma20.iloc[-1] else 3.0
            vol_avg = hist_day['Volume'].rolling(20).mean().iloc[-1]
            vol_ratio = hist_day['Volume'].iloc[-1] / vol_avg
            sc_vol = min(10, vol_ratio * 3)

            delta = hist_day['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean().iloc[-1]
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean().iloc[-1]
            rsi = 100 - (100 / (1 + gain/(loss if loss != 0 else 0.001)))

            try:
                opts = stock.options
                if opts:
                    chain = stock.option_chain(opts[0])
                    c_vol, p_vol = chain.calls['volume'].sum(), chain.puts['volume'].sum()
                    if c_vol > 0: pcr = p_vol / c_vol
                    sc_option = 7.0 if pcr < 0.7 else 3.0 if pcr > 1.2 else 5.0
                    total = c_vol + p_vol
                    if total > 0:
                        c_pct, p_pct = (c_vol/total)*100, (p_vol/total)*100
            except: pass

            category, strat_name, strat_class = "NONE", "관망", "st-none"
            t_days, tgt_pct, stp_pct, trl_pct, b_ratio = 5, 0.05, 0.03, 0.02, 0.0
            news_ok, news_hl = False, None
            
            if sc_vol > 7 and cur > ma20.iloc[-1] and rsi < 70:
                category, strat_name, strat_class = "SHORT", "🚀 단타", "st-gamma"
                t_days, tgt_pct, stp_pct, trl_pct, b_ratio = 1, 0.03, 0.02, 0.015, 0.05
                news_ok, news_hl = check_recent_news(ticker)
            elif sc_squeeze > 7 and sc_trend > 6:
                category, strat_name, strat_class = "SWING", "🌊 스윙", "st-squeeze"
                t_days, tgt_pct, stp_pct, trl_pct, b_ratio = 14, 0.10, 0.06, 0.04, 0.10
            elif sc_trend > 8 and regime_score > 7:
                category, strat_name, strat_class = "LONG", "🌲 장투", "st-value"
                t_days, tgt_pct, stp_pct, trl_pct, b_ratio = 90, 0.30, 0.15, 0.10, 0.15

            # 익절라인(+) 및 칼손절(-) 논리 정상화
            tgt_val = cur * (1 + tgt_pct)
            trl_val = cur * (1 + trl_pct)  # 수익 보존 (현재가 + %)
            stp_val = cur * (1 - stp_pct)  # 손실 방어 (현재가 - %)

            return {
                "Ticker": ticker, "Price": cur, "StratName": strat_name, "StratClass": strat_class,
                "Squeeze": sc_squeeze, "Trend": sc_trend, "Regime": regime_score, "Vol": sc_vol, "Option": sc_option,
                "Target": tgt_val, "Stop": stp_val, "HardStop": stp_val, "TrailStop": trl_val, "TimeStop": t_days,
                "ChgOpen": chg_o, "ChgPrev": chg_p, "DiffOpen": diff_o, "DiffPrev": diff_p,
                "RSI": rsi, "PCR": pcr, "CallVol": c_vol, "PutVol": p_vol, "CallPct": c_pct, "PutPct": p_pct,
                "History": hist_day['Close'], "MktLabel": mkt_label, "MktClass": mkt_class,
                "HighConviction": news_ok and vol_ratio >= 3.0, "NewsHeadline": news_hl,
                "BetText": "비중:최대" if b_ratio >= 0.15 else "비중:보통" if b_ratio >= 0.10 else "비중:최소" if b_ratio > 0 else "관망",
                "Journal": {"티커": ticker, "진입가": round(cur, 2), "전략": strat_name, "일시": get_timestamp_str()}
            }
        except: return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_single, t) for t in tickers]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res: data_list.append(res)
    return data_list

def create_chart(data, ticker, unique_id):
    color = '#00FF00' if data.iloc[-1] >= data.iloc[0] else '#FF4444'
    fig = go.Figure(go.Scatter(y=data, mode='lines', line=dict(color=color, width=2), fill='tozeroy'))
    fig.update_layout(height=50, margin=dict(l=0,r=0,t=0,b=0), xaxis=dict(visible=False), yaxis=dict(visible=False), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    return fig

# === [8. UI 메인] ===
with st.sidebar:
    st.title("🪟 KOREAN MASTER")
    st.caption(f"NAV: ${CONFIG['NAV']:,}")
    mode = st.radio("분석 모드", ["📌 섹터별 보기", "🔍 무제한 검색", "⭐ 내 관심종목 보기"])
    target_tickers = []
    
    if mode == "📌 섹터별 보기":
        selected_sector = st.selectbox("섹터 선택", list(SECTORS.keys())) # 드래그 삭제 -> 드롭다운 변경 완료
        target_tickers = SECTORS[selected_sector]
    elif mode == "🔍 무제한 검색":
        search_txt = st.text_input("티커 입력 (쉼표 구분)", "NVDA,TSLA")
        target_tickers = [t.strip().upper() for t in search_txt.split(',')]
    else: target_tickers = list(st.session_state.watchlist)
    
    if st.button("🔄 새로고침"): st.cache_data.clear(); st.rerun()

st.title(f"🇺🇸 {mode}")
if target_tickers:
    market_data = get_market_data(target_tickers)
    if not market_data:
        st.warning("데이터를 불러올 수 없거나 유효하지 않은 티커입니다.")
    else:
        tab1, tab2 = st.tabs(["📊 대시보드", "💰 상세 리포트"])
        with tab1:
            cols = st.columns(3)
            for i, row in enumerate(market_data):
                with cols[i % 3]:
                    def get_c(v): return "sc-high" if v >= 7 else "sc-mid" if v >= 4 else "sc-low"
                    is_fav = row['Ticker'] in st.session_state.watchlist
                    if st.button("❤️" if is_fav else "🤍", key=f"f_{i}"):
                        if is_fav: st.session_state.watchlist.remove(row['Ticker'])
                        else: st.session_state.watchlist.add(row['Ticker'])
                        st.rerun()
                    
                    badge = "<span class='st-highconv'>🔥 High Conviction</span>" if row['HighConviction'] else ""
                    news = f"<span class='news-line'>📰 {row['NewsHeadline']}</span>" if row['NewsHeadline'] else ""
                    c_o, c_p = ("#00FF00" if row['ChgOpen'] >= 0 else "#FF4444"), ("#00FF00" if row['ChgPrev'] >= 0 else "#FF4444")

                    html = f"""<div class="metric-card">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <a href="https://finance.yahoo.com/quote/{row['Ticker']}" target="_blank" class="ticker-header">{row['Ticker']}</a>
                            <div>{badge}<span class="badge {row['MktClass']}">{row['MktLabel']}</span></div>
                        </div>
                        {news}
                        <div class="price-row" style="margin-top:10px;"><span class="price-label">현재가</span><span class="price-val">${row['Price']:.2f}</span></div>
                        <div class="price-row"><span class="price-label">시가대비</span><span class="price-val" style="color:{c_o}">{row['DiffOpen']:+.2f} ({row['ChgOpen']:+.2f}%)</span></div>
                        <div class="price-row"><span class="price-label">전일대비</span><span class="price-val" style="color:{c_p}">{row['DiffPrev']:+.2f} ({row['ChgPrev']:+.2f}%)</span></div>
                        <div style="text-align:center; margin:10px 0;"><span class="{row['StratClass']}">{row['StratName']}</span></div>
                        <div class="score-container">
                            <div class="score-item">응축<br><span class="score-val {get_c(row['Squeeze'])}">{row['Squeeze']:.0f}</span></div>
                            <div class="score-item">추세<br><span class="score-val {get_c(row['Trend'])}">{row['Trend']:.0f}</span></div>
                            <div class="score-item">장세<br><span class="score-val {get_c(row['Regime'])}">{row['Regime']:.0f}</span></div>
                            <div class="score-item">수급<br><span class="score-val {get_c(row['Vol'])}">{row['Vol']:.0f}</span></div>
                        </div>
                        <div class="price-target-box">
                            <div class="pt-item"><span class="pt-label">목표가</span><span class="pt-val" style="color:#00FF00">${row['Target']:.2f}</span></div>
                            <div class="pt-item"><span class="pt-label">손절가</span><span class="pt-val" style="color:#FF4444">${row['Stop']:.2f}</span></div>
                        </div>
                        <div class="exit-box">
                            <span style="color:#00FF00; font-weight:bold;">✅ 수익보존(익절): ${row['TrailStop']:.2f}</span><br>
                            <span style="color:#FF4444;">🚨 칼손절라인: ${row['HardStop']:.2f}</span><br>
                            <span style="color:#aaa;">⏳ 전략 유효기간: {row['TimeStop']}일</span>
                        </div>
                        <div style="margin-top:10px; font-size:11px; color:#888;">RSI: {row['RSI']:.0f} | PCR: {row['PCR']:.2f}</div>
                    </div>"""
                    st.markdown(html, unsafe_allow_html=True)
                    st.plotly_chart(create_chart(row['History'], row['Ticker'], i), use_container_width=True, key=f"c_{i}", config={'displayModeBar':False})
        
        # [수정 완료] AI 리포트 원복: 카드+JSON 형태
        with tab2:
            cols = st.columns(3)
            for i, row in enumerate(market_data):
                with cols[i % 3]:
                    render_card(row, f"list_{i}")
                    st.json(row['Journal'])