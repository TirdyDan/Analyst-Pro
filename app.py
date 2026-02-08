import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import zipfile
import io
from math import floor
from datetime import datetime

# --- KONFIGURATION & STABILER CACHE ---
@st.cache_data(ttl=1800)
def get_clean_data(ticker):
    """Speichert nur serialisierbare Daten (DataFrames/Dicts) statt Ticker-Objekte."""
    tk = yf.Ticker(ticker)
    # Wichtige Daten vorab extrahieren
    hist = tk.history(period="max")
    info = tk.info
    inc = tk.financials
    bal = tk.balance_sheet
    cf = tk.cashflow
    
    # Kalender-Daten sicher extrahieren
    cal_date = None
    try:
        if tk.calendar is not None and not tk.calendar.empty:
            cal_date = tk.calendar.iloc[0, 0]
    except: pass
    
    return hist, info, inc, bal, cf, cal_date

@st.cache_data(ttl=3600)
def get_exchange_rate(from_curr, to_curr="EUR"):
    if from_curr == to_curr or from_curr == "N/A": return 1.0
    try:
        pair = f"{from_curr}{to_curr}=X"
        data = yf.download(pair, period="1d", progress=False)
        return float(data['Close'].iloc[-1]) if not data.empty else 1.0
    except: return 1.0

# --- HILFSFUNKTIONEN ---
def get_val(df, keys):
    if df is None or df.empty: return None
    for k in keys:
        if k in df.index:
            val = df.loc[k].iloc[0]
            if pd.notnull(val): return val
    return None

# --- UI DESIGN ---
st.set_page_config(page_title="ARES", layout="centered")
st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; }
    .stMetric { background-color: #2d2d2d; padding: 15px; border-radius: 10px; border: 1px solid #FFD700; }
    .lexikon-box { background-color: #2d2d2d; padding: 15px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 10px; font-size: 0.9rem; }
    .disclaimer { font-size: 0.75rem; color: #ff4b4b; text-align: center; border: 1px solid #ff4b4b; padding: 10px; border-radius: 5px; }
    .hint { color: #888; font-size: 0.85rem; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

st.title("ARES")

# --- EINGABE & REFRESH ---
col_in, col_ref = st.columns([4, 1])
with col_in:
    ticker_input = st.text_input("TICKER SYMBOL", placeholder="z.B. OMV.VI, NVDA, AAPL").upper()
    st.markdown('<p class="hint">Tipp: Suche Tickersymbole via Google KI Suche.</p>', unsafe_allow_html=True)

with col_ref:
    st.write(" ") # Space
    if st.button("🔄 Update"):
        st.cache_data.clear()
        st.rerun()

# Risiko-Einstellungen
with st.expander("🛡️ KONTO- & RISIKO-SETUP", expanded=False):
    c1, c2, c3 = st.columns(3)
    acc_eur = c1.number_input("Kontogröße (EUR)", value=10000, step=500)
    risk_p = c2.number_input("Risiko pro Trade (%)", value=1.0, step=0.1)
    overnight = st.selectbox("Haltedauer", ["Nur Intraday", "Über Nacht (Overnight)"], index=1) == "Über Nacht (Overnight)"

if ticker_input:
    try:
        with st.spinner("Analysiere Markt-Daten..."):
            # Daten stabil laden
            hist_full, info, inc, bal, cf, earn_date = get_clean_data(ticker_input)
            
            if hist_full.empty:
                st.error("Keine Kursdaten gefunden. Bitte Ticker prüfen.")
                st.stop()

            # --- 1. AKTIENKURS & CHART ---
            st.write("---")
            curr_p = hist_full['Close'].iloc[-1]
            prev_p = hist_full['Close'].iloc[-2]
            pct_ch = ((curr_p - prev_p) / prev_p) * 100
            curr_sym = info.get('currency', 'EUR')

            c_hero1, c_hero2 = st.columns([1, 2])
            with c_hero1:
                st.metric(info.get('shortName', ticker_input), f"{curr_p:.2f} {curr_sym}", f"{pct_ch:.2f}%")
            
            with c_hero2:
                period = st.radio("Zeitraum", ["1T", "1W", "1M", "6M", "1J", "5J", "Max"], horizontal=True, index=4)

            # Chart-Anpassung
            p_map = {"1T":"1d","1W":"5d","1M":"1mo","6M":"6mo","1J":"1y","5J":"5y","Max":"max"}
            i_map = {"1T":"5m","1W":"15m","1M":"1d","6M":"1d","1J":"1d","5J":"1wk","Max":"1mo"}
            
            # Sub-Select für Chart (direkt von Yahoo für Interval-Support)
            hist_chart = yf.download(ticker_input, period=p_map[period], interval=i_map[period], progress=False)
            
            fig = go.Figure(go.Scatter(x=hist_chart.index, y=hist_chart['Close'], line=dict(color='#FFD700'), fill='tozeroy', fillcolor='rgba(255, 215, 0, 0.1)'))
            fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- 2. AMPEL (SAFETY CHECK) ---
            st.subheader("🛡️ Trade-Safety Analyse")
            vol_20d = hist_full['Volume'].tail(20).mean()
            days_to_earn = (earn_date.date() - datetime.now().date()).days if earn_date else None
            
            status = "GRÜN"
            reasons = []
            if days_to_earn is not None and days_to_earn <= (7 if overnight else 3):
                status = "ROT"; reasons.append(f"⚠️ **Earnings:** In {days_to_earn} Tagen.")
            if vol_20d < 300000:
                status = "ROT"; reasons.append("⚠️ **Liquidität:** Geringes Volumen.")
            
            if status == "ROT": st.error(f"🔴 KRITISCHES RISIKO: {status}")
            else: st.success(f"🟢 HANDELBAR: {status}")
            for r in reasons: st.write(r)

            # --- 3. POSITIONSRECHNER ---
            st.write("---")
            st.subheader("📏 Positionsrechner")
            ex_rate = get_exchange_rate(curr_sym, "EUR")
            risk_eur = acc_eur * (risk_p / 100)
            
            # ATR Berechnung (100 Tage Fenster für Stabilität)
            h, l, c = hist_full["High"].tail(100), hist_full["Low"].tail(100), hist_full["Close"].tail(100)
            tr = pd.concat([(h-l).abs(), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
            atr_val = tr.rolling(14).mean().iloc[-1]
            stop_pct = (atr_val / curr_p) * 1.5 * 100
            
            shares = floor((risk_eur / ex_rate) / (curr_p * stop_pct / 100))
            
            c_s1, c_s2, c_s3 = st.columns(3)
            c_s1.metric("Stückzahl", f"{shares}")
            c_s2.metric("Stop-Abstand", f"{stop_pct:.2f}%")
            c_s3.metric("Stop-Preis", f"{(curr_p * (1-stop_pct/100)):.2f} {curr_sym}")

            # --- 4. FUNDAMENTAL ANALYSE (9 KPIs) ---
            st.write("---")
            st.subheader("📊 Fundamental-Analyse (Latest Fiscal)")
            if not inc.empty and not bal.empty:
                f1,f2,f3 = st.columns(3); f4,f5,f6 = st.columns(3); f7,f8,f9 = st.columns(3)
                rev = get_val(inc, ['Total Revenue']); ni = get_val(inc, ['Net Income'])
                ebitda = get_val(inc, ['EBITDA']); eq = get_val(bal, ['Stockholders Equity'])
                ca = get_val(bal, ['Total Current Assets']); cl = get_val(bal, ['Total Current Liabilities'])
                debt = get_val(bal, ['Total Debt']); ta = get_val(bal, ['Total Assets'])

                f1.metric("Gewinnmarge", f"{(ni/rev)*100:.2f}%" if rev and ni else "N/A")
                f2.metric("EBITDA-Marge", f"{(ebitda/rev)*100:.2f}%" if rev and ebitda else "N/A")
                f3.metric("EK-Rendite", f"{(ni/eq)*100:.2f}%" if ni and eq else "N/A")
                f4.metric("KGV (PE)", info.get('trailingPE', 'N/A'))
                f5.metric("Liquidität", f"{(ca/cl):.2f}" if ca and cl else "N/A")
                f6.metric("Verschuldung", f"{(debt/eq):.2f}" if debt and eq else "N/A")
                
                growth = "N/A"
                if len(inc.columns) > 1:
                    growth = f"{((inc.loc['Total Revenue'].iloc[0]/inc.loc['Total Revenue'].iloc[1])-1)*100:.2f}%"
                f7.metric("Wachstum", growth)
                f8.metric("KBV (P/B)", info.get('priceToBook', 'N/A'))
                f9.metric("Asset Turnover", f"{(rev/ta):.2f}" if rev and ta else "N/A")

            # --- 5. EXPORT ---
            st.write("---")
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                zf.writestr("GuV.csv", inc.to_csv()); zf.writestr("Bilanz.csv", bal.to_csv()); zf.writestr("Cashflow.csv", cf.to_csv())
            st.download_button("🏆 KI-ANALYSE DATEN (ZIP) LADEN", zip_buffer.getvalue(), f"Ares_{ticker_input}.zip")

    except Exception as e:
        st.error(f"Datenfehler: {e}. Versuchen Sie es erneut.")

# DISCLAIMER & LEXIKON
st.markdown("---")
st.markdown('<div class="disclaimer"><b>ACHTUNG:</b> Keine Anlageberatung. Zahlen können fehlerhaft sein.</div>', unsafe_allow_html=True)
st.caption("ARES 0.9.1 || Stable Analysis Platform")