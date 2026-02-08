import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import zipfile
import io
from math import floor
from datetime import datetime

# --- KONFIGURATION & CACHE ---
# Wir nutzen eine Cache-Funktion, die wir manuell leeren können
@st.cache_data(ttl=1800)
def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    return stock, stock.info, stock.history(period="max")

@st.cache_data(ttl=3600)
def get_exchange_rate(from_curr, to_curr="EUR"):
    if from_curr == to_curr or from_curr == "N/A": return 1.0
    try:
        data = yf.Ticker(f"{from_curr}{to_curr}=X").history(period="1d")
        return float(data['Close'].iloc[-1]) if not data.empty else 1.0
    except: return 1.0

# --- HILFSFUNKTIONEN ---
def get_val(df, keys):
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
    ticker_input = st.text_input("TICKER SYMBOL", placeholder="z.B. NVDA, AAPL, SAP.DE").upper()
    st.markdown('<p class="hint">Tipp: Suche Tickersymbole via Google KI Suche.</p>', unsafe_allow_html=True)

with col_ref:
    st.write(" ") # Padding
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
        with st.spinner("Analysiere Daten..."):
            stock, info, hist_full = get_stock_data(ticker_input)
            
            # --- 1. AKTIENKURS & ZEITRAUM-WÄHLER ---
            st.write("---")
            time_col1, time_col2 = st.columns([1, 2])
            with time_col1:
                curr_p = hist_full['Close'].iloc[-1]
                prev_p = hist_full['Close'].iloc[-2]
                pct_ch = ((curr_p - prev_p) / prev_p) * 100
                st.metric(info.get('shortName', ticker_input), f"{curr_p:.2f} {info.get('currency', 'USD')}", f"{pct_ch:.2f}%")
            
            with time_col2:
                period = st.radio("Chart-Zeitraum", ["1T", "1W", "1M", "6M", "1J", "5J", "Max"], horizontal=True, index=4)
            
            # Chart Logik
            p_map = {"1T":"1d","1W":"5d","1M":"1mo","6M":"6mo","1J":"1y","5J":"5y","Max":"max"}
            i_map = {"1T":"5m","1W":"15m","1M":"1d","6M":"1d","1J":"1d","5J":"1wk","Max":"1mo"}
            hist_chart = stock.history(period=p_map[period], interval=i_map[period])
            
            fig = go.Figure(go.Scatter(x=hist_chart.index, y=hist_chart['Close'], line=dict(color='#FFD700'), fill='tozeroy', fillcolor='rgba(255, 215, 0, 0.1)'))
            fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- 2. TRADE-SAFETY (AMPEL MIT ERKLÄRUNG) ---
            st.subheader("🛡️ Trade-Safety Analyse")
            vol_20d = hist_full['Volume'].tail(20).mean()
            earn_date = None
            try: earn_date = stock.calendar.iloc[0,0]
            except: pass
            days_to_earn = (earn_date.date() - datetime.now().date()).days if earn_date else None
            
            status = "GRÜN"
            reasons = []
            if days_to_earn is not None and days_to_earn <= (7 if overnight else 3):
                status = "ROT"; reasons.append(f"⚠️ **Earnings-Risiko:** Quartalszahlen in {days_to_earn} Tagen. Hier drohen Kurssprünge (Gaps) gegen dich.")
            if vol_20d < 500000:
                status = "ROT"; reasons.append("⚠️ **Liquiditäts-Risiko:** Zu wenig Handelsvolumen. Kauf/Verkauf könnte zu schlechteren Preisen erfolgen.")
            
            if status == "ROT": st.error(f"🔴 KRITISCHES RISIKO: {status}")
            else: st.success(f"🟢 HANDELBAR: {status}")
            
            with st.expander("Warum diese Bewertung?", expanded=False):
                st.write("Die Ampel prüft, ob 'Anfängerfallen' vorliegen. Rot bedeutet: Die Statistik spricht gegen einen sicheren Trade (z.B. wegen hoher Unsicherheit vor Zahlen).")
                for r in reasons: st.write(r)
                st.markdown("**Hinweis:** Prüfe immer zusätzlich aktuelle News und vergleiche die Zahlen!")

            # --- 3. POSITIONSRECHNER & ERKLÄRUNG ---
            st.write("---")
            st.subheader("📏 Positions-Kalkulation")
            curr_sym = info.get('currency', 'USD')
            ex_rate = get_exchange_rate(curr_sym, "EUR")
            risk_eur = acc_eur * (risk_p / 100)
            
            # ATR Stop
            h, l, c = hist_full["High"].tail(100), hist_full["Low"].tail(100), hist_full["Close"].tail(100)
            tr = pd.concat([(h-l).abs(), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
            atr_val = tr.rolling(14).mean().iloc[-1]
            stop_pct = (atr_val / curr_p) * 1.5 * 100
            shares = floor((risk_eur / ex_rate) / (curr_p * stop_pct / 100))
            
            c_s1, c_s2, c_s3 = st.columns(3)
            c_s1.metric("Stückzahl", f"{shares}")
            c_s2.metric("Stop-Abstand", f"{stop_pct:.2f}%")
            c_s3.metric("Stop-Preis", f"{(curr_p * (1-stop_pct/100)):.2f} {curr_sym}")

            st.markdown(f"""
            <div class="lexikon-box">
            <b>Was bedeuten diese Zahlen?</b><br>
            • <b>Stückzahl:</b> Kaufen Sie maximal {shares} Aktien. Damit halten Sie Ihr Risiko-Limit ein.<br>
            • <b>Stop-Abstand:</b> Basierend auf der normalen Schwankung (ATR) braucht die Aktie {stop_pct:.2f}% Platz.<br>
            • <b>Stop-Preis:</b> Fällt die Aktie hierhin, wird das Risiko-Budget von {risk_eur:.2f} € erreicht und der Trade beendet.
            </div>
            """, unsafe_allow_html=True)

            # --- 4. FUNDAMENTAL ANALYSE (ZEITRAUM-WÄHLER) ---
            st.write("---")
            st.subheader("📊 Fundamental-Analyse")
            fund_period = st.radio("Analyse-Zeitraum", ["Aktuellstes Jahr", "3-Jahres Durchschnitt", "5-Jahres Trend"], horizontal=True)
            
            inc = stock.financials
            bal = stock.balance_sheet
            
            if not inc.empty and not bal.empty:
                f1,f2,f3 = st.columns(3); f4,f5,f6 = st.columns(3); f7,f8,f9 = st.columns(3)
                
                # Auswahl der Datenbasis
                idx = 0 if fund_period == "Aktuellstes Jahr" else slice(0, 3 if fund_period == "3-Jahres Durchschnitt" else 5)
                
                rev = inc.loc['Total Revenue'].iloc[idx] if isinstance(idx, int) else inc.loc['Total Revenue'].iloc[idx].mean()
                ni = inc.loc['Net Income'].iloc[idx] if isinstance(idx, int) else inc.loc['Net Income'].iloc[idx].mean()
                
                f1.metric("Gewinnmarge", f"{(ni/rev)*100:.2f}%")
                f2.metric("KGV (PE)", info.get('trailingPE', 'N/A'))
                f3.metric("EK-Rendite", f"{(ni/bal.loc['Stockholders Equity'].iloc[0]*100):.2f}%")
                
                f4.metric("Umsatz (Mrd.)", f"{rev/1e9:.2f}")
                f5.metric("Liquidität", f"{(bal.loc['Total Current Assets'].iloc[0]/bal.loc['Total Current Liabilities'].iloc[0]):.2f}")
                f6.metric("Verschuldung", f"{(bal.loc['Total Debt'].iloc[0]/bal.loc['Stockholders Equity'].iloc[0]):.2f}")
                
                growth = ((inc.loc['Total Revenue'].iloc[0]/inc.loc['Total Revenue'].iloc[1])-1)*100
                f7.metric("Wachstum", f"{growth:.2f}%")
                f8.metric("KBV (P/B)", info.get('priceToBook', 'N/A'))
                f9.metric("Asset Turnover", f"{(rev/bal.loc['Total Assets'].iloc[0]):.2f}")

            # --- 5. EXPORT & HINWEIS ---
            st.write("---")
            st.download_button("🏆 KI-ANALYSE DATEN (ZIP) LADEN", io.BytesIO().getvalue(), "Ares_Data.zip")
            st.markdown("""
            <div class="disclaimer">
            <b>ACHTUNG:</b> Alle Daten stammen von Drittanbietern. Zahlen können verzögert oder fehlerhaft sein. 
            Diese App ist <u>keine</u> Anlageberatung. Prüfen Sie Informationen eigenständig gegen!
            </div>
            """, unsafe_allow_html=True)

    except Exception as e:
        st.error(f"Fehler: {e}. Bitte prüfen Sie den Ticker.")

# LEXIKON
st.write("---")
st.subheader("📘 Schnell-Lexikon")
col_l, col_r = st.columns(2)
with col_l:
    st.markdown("**Gewinnmarge:** Wie viel Gewinn pro 100€ Umsatz bleibt übrig?\n\n**KGV:** Bewertung der Aktie. Niedriger ist oft günstiger.")
with col_r:
    st.markdown("**Liquidität:** Kann die Firma ihre Rechnungen zahlen? (Sollte > 1.0 sein)\n\n**ATR:** Misst die normale tägliche Schwankung.")
st.caption("ARES 0.9 || Dein Sicherheits-Terminal für Investments")