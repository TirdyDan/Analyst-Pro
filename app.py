import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import zipfile
import io
from math import floor
from datetime import datetime

# --- HELPER FUNCTIONS ---
def get_val(df, keys):
    for k in keys:
        if k in df.index:
            val = df.loc[k].iloc[0]
            if pd.notnull(val): return val
    return None

@st.cache_data(ttl=1800)
def get_exchange_rate(from_curr, to_curr="EUR"):
    if from_curr == to_curr or from_curr == "N/A": return 1.0
    try:
        data = yf.Ticker(f"{from_curr}{to_curr}=X").history(period="1d")
        return float(data['Close'].iloc[-1]) if not data.empty else 1.0
    except: return 1.0

# --- UI SETUP ---
st.set_page_config(page_title="ARES", layout="centered")
st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; }
    .stMetric { background-color: #2d2d2d; padding: 15px; border-radius: 10px; border: 1px solid #FFD700; }
    [data-testid="stMetricValue"] { color: #FFD700 !important; font-size: 2.2rem !important; font-weight: bold; }
    .lexikon-box { background-color: #2d2d2d; padding: 20px; border-radius: 10px; border-left: 5px solid #FFD700; margin-bottom: 20px; }
    .hint { color: #888; font-size: 0.85rem; text-align: center; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

st.title("ARES")

# --- INPUT ---
ticker_input = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. AAPL, NVDA, SAP.DE").upper()
st.markdown('<p class="hint">Verwende zum Beispiel die Google KI Suche um Tickersymbole herauszufinden.</p>', unsafe_allow_html=True)

with st.expander("🛡️ RISIKO- & KONTO-EINSTELLUNGEN", expanded=True):
    c1, c2, c3 = st.columns(3)
    acc_eur = c1.number_input("Kontogröße (EUR)", value=10000, step=500)
    risk_p = c2.number_input("Risiko pro Trade (%)", value=1.0, step=0.1)
    overnight = st.selectbox("Position über Nacht halten?", ["Nein", "Ja"], index=1) == "Ja"

if ticker_input:
    try:
        with st.spinner("Extrahiere Marktdaten..."):
            stock = yf.Ticker(ticker_input)
            info = stock.info
            df_price = stock.history(period="1y")
            
            if df_price.empty:
                st.error("Ticker nicht gefunden. Bitte Symbol prüfen.")
                st.stop()

            # --- 1. HERO SECTION: AKTIENKURS ---
            curr_p = df_price['Close'].iloc[-1]
            prev_p = df_price['Close'].iloc[-2]
            change = curr_p - prev_p
            pct_change = (change / prev_p) * 100
            curr_sym = info.get('currency', 'USD')

            st.write("---")
            st.metric(label=f"{info.get('shortName', ticker_input)} ({curr_sym})", 
                      value=f"{curr_p:.2f} {curr_sym}", 
                      delta=f"{change:.2f} ({pct_change:.2f}%)")
            
            # Preis Chart
            fig = go.Figure(go.Scatter(x=df_price.index, y=df_price['Close'], line=dict(color='#FFD700'), fill='tozeroy', fillcolor='rgba(255, 215, 0, 0.1)'))
            fig.update_yaxes(range=[df_price['Close'].min()*0.95, curr_p*1.3])
            fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- 2. TRADE-SAFETY (AMPEL) ---
            st.subheader("🛡️ Trade-Safety Check")
            vol_20d = df_price['Volume'].tail(20).mean()
            earn_date = None
            try: earn_date = stock.calendar.iloc[0,0]
            except: pass
            days_to_earn = (earn_date.date() - datetime.now().date()).days if earn_date else None
            
            status = "GRÜN"
            reasons = []
            if days_to_earn is not None and days_to_earn <= (7 if overnight else 3):
                status = "ROT"; reasons.append(f"Earnings-Event in {days_to_earn} Tagen! (Hohes Gap-Risiko)")
            if vol_20d < 500000:
                status = "ROT"; reasons.append("Geringe Liquidität (< 500k Vol)")
            
            if status == "ROT": st.error(f"🔴 STATUS: {status}")
            else: st.success(f"🟢 STATUS: {status}")
            for r in reasons: st.write(f"- {r}")

            # --- 3. POSITIONSRECHNER ---
            st.write("---")
            st.subheader("📏 Positions-Kalkulation")
            ex_rate = get_exchange_rate(curr_sym, "EUR")
            risk_eur = acc_eur * (risk_p / 100)
            risk_ticker_curr = risk_eur / ex_rate
            
            h, l, c = df_price["High"], df_price["Low"], df_price["Close"]
            tr = pd.concat([(h-l).abs(), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
            atr_val = tr.rolling(14).mean().iloc[-1]
            stop_pct = (atr_val / curr_p) * 1.5 * 100
            shares = floor(risk_ticker_curr / (curr_p * stop_pct / 100))
            
            c_s1, c_s2, c_s3 = st.columns(3)
            c_s1.metric("Stückzahl", f"{shares}")
            c_s2.metric("Stop-Abstand", f"{stop_pct:.2f}%")
            c_s3.metric("Stop-Preis", f"{(curr_p * (1-stop_pct/100)):.2f} {curr_sym}")

            # --- 4. FUNDAMENTAL CHECK (9 KPIs) ---
            st.write("---")
            st.subheader("📊 Fundamental-Analyse (9 Kennzahlen)")
            inc = stock.financials
            bal = stock.balance_sheet
            cf = stock.cashflow
            
            if not inc.empty and not bal.empty:
                f1,f2,f3 = st.columns(3); f4,f5,f6 = st.columns(3); f7,f8,f9 = st.columns(3)
                rev = get_val(inc, ['Total Revenue']); ni = get_val(inc, ['Net Income'])
                ebitda = get_val(inc, ['EBITDA']); eq = get_val(bal, ['Stockholders Equity'])
                debt = get_val(bal, ['Total Debt']); ca = get_val(bal, ['Total Current Assets'])
                cl = get_val(bal, ['Total Current Liabilities']); ta = get_val(bal, ['Total Assets'])

                f1.metric("Gewinnmarge", f"{(ni/rev)*100:.2f}%" if rev and ni else "N/A")
                f2.metric("EBITDA-Marge", f"{(ebitda/rev)*100:.2f}%" if rev and ebitda else "N/A")
                f3.metric("EK-Rendite", f"{(ni/eq)*100:.2f}%" if ni and eq else "N/A")
                f4.metric("KGV (PE)", info.get('trailingPE', 'N/A'))
                f5.metric("Liquidität", f"{(ca/cl):.2f}" if ca and cl else "N/A")
                f6.metric("Verschuldung", f"{(debt/eq):.2f}" if debt and eq else "N/A")
                f7.metric("Umsatz-Wachstum", f"{((inc.loc['Total Revenue'].iloc[0]/inc.loc['Total Revenue'].iloc[1])-1)*100:.2f}%" if len(inc.columns)>1 else "N/A")
                f8.metric("KBV (P/B)", info.get('priceToBook', 'N/A'))
                f9.metric("Asset Turnover", f"{(rev/ta):.2f}" if rev and ta else "N/A")

                # --- 5. HISTORISCHE TRENDS (CHRONOLOGISCH) ---
                st.write("---")
                st.subheader("📉 Historische Trends")
                
                
                
                trend_options = ["Umsatz", "Reingewinn", "EBITDA", "Eigenkapital", "Gesamtschulden", "Operativer Cashflow"]
                sel_trend = st.selectbox("Metrik für Zeitverlauf wählen:", trend_options)
                
                t_map = {
                    "Umsatz": inc.loc['Total Revenue'], "Reingewinn": inc.loc['Net Income'],
                    "EBITDA": inc.loc['EBITDA'], "Eigenkapital": bal.loc['Stockholders Equity'],
                    "Gesamtschulden": bal.loc['Total Debt'], "Operativer Cashflow": cf.loc['Operating Cash Flow']
                }
                
                plot_data = t_map[sel_trend][::-1] # Chronologische Umkehrung
                years = [str(d.year) for d in plot_data.index]
                
                fig_t = go.Figure(go.Bar(x=years, y=plot_data.values, marker_color='#FFD700'))
                fig_t.update_layout(template="plotly_dark", height=300, xaxis=dict(type='category'))
                st.plotly_chart(fig_t, use_container_width=True)

                # --- 6. EXPORT ---
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    zf.writestr(f"GuV.csv", inc.to_csv()); zf.writestr(f"Bilanz.csv", bal.to_csv()); zf.writestr(f"Cashflow.csv", cf.to_csv())
                st.download_button(label="🏆 DOWNLOAD KI-DATEN-PAKET (ZIP)", data=zip_buffer.getvalue(), file_name=f"Ares_Export_{ticker_input}.zip")

    except Exception as e:
        st.error(f"Fehler: {e}")

# --- DETAILLIERTES KENNZAHLENLEXIKON ---
st.write("---")
st.subheader("📘 ARES Kennzahlenlexikon (Detail)")

with st.container():
    col_lex1, col_lex2 = st.columns(2)
    
    with col_lex1:
        st.markdown("""
        <div class="lexikon-box">
        <b>1. Gewinnmarge (Profit Margin)</b><br>
        <i>Formel: Reingewinn / Gesamtumsatz</i><br>
        Zeigt, wie viel Prozent vom Umsatz nach Abzug aller Kosten als Reingewinn übrig bleiben. Ein Wert über 10% gilt als solide.
        </div>
        <div class="lexikon-box">
        <b>2. EBITDA-Marge</b><br>
        <i>Formel: EBITDA / Gesamtumsatz</i><br>
        Misst die operative Rentabilität vor Zinsen, Steuern und Abschreibungen. Gut geeignet, um Firmen der gleichen Branche weltweit zu vergleichen.
        </div>
        <div class="lexikon-box">
        <b>3. Eigenkapitalrendite (ROE)</b><br>
        <i>Formel: Reingewinn / Eigenkapital</i><br>
        Gibt an, wie effektiv das Unternehmen das Geld der Eigentümer verzinst. Werte über 15% deuten auf ein starkes Geschäftsmodell hin.
        </div>
        <div class="lexikon-box">
        <b>4. KGV (Kurs-Gewinn-Verhältnis)</b><br>
        <i>Formel: Aktienkurs / Gewinn pro Aktie</i><br>
        Die wichtigste Bewertungskennzahl. Sie sagt aus, das Wievielfache des Jahresgewinns der Markt aktuell für die Aktie zahlt.
        </div>
        <div class="lexikon-box">
        <b>5. Liquidität (Current Ratio)</b><br>
        <i>Formel: Umlaufvermögen / Kurzfr. Schulden</i><br>
        Kann die Firma ihre Rechnungen bezahlen? Ein Wert unter 1.0 ist kritisch, ein Wert über 1.5 gilt als sehr sicher.
        </div>
        """, unsafe_allow_html=True)

    with col_lex2:
        st.markdown("""
        <div class="lexikon-box">
        <b>6. Verschuldungsgrad (Debt-to-Equity)</b><br>
        <i>Formel: Gesamtschulden / Eigenkapital</i><br>
        Zeigt die Abhängigkeit von Fremdkapital. Ein Wert über 1.0 bedeutet, dass mehr Schulden als Eigenkapital vorhanden sind.
        </div>
        <div class="lexikon-box">
        <b>7. Umsatz-Wachstum</b><br>
        <i>Formel: (Umsatz heute / Umsatz Vorjahr) - 1</i><br>
        Der Motor der Aktie. Steigendes Wachstum ist meist die Voraussetzung für langfristig steigende Kurse.
        </div>
        <div class="lexikon-box">
        <b>8. KBV (Kurs-Buchwert-Verhältnis)</b><br>
        <i>Formel: Aktienkurs / Buchwert pro Aktie</i><br>
        Vergleicht den Preis mit dem Substanzwert der Firma. Beliebt bei Value-Investoren, um "Schnäppchen" zu finden.
        </div>
        <div class="lexikon-box">
        <b>9. Asset Turnover (Kapitalumschlag)</b><br>
        <i>Formel: Umsatz / Gesamtvermögen</i><br>
        Misst die Effizienz, mit der das Unternehmen seine Vermögenswerte einsetzt, um Umsatz zu generieren. Höhere Werte sind besser.
        </div>
        """, unsafe_allow_html=True)

# --- WIKIPEDIA REFERENZEN ---
st.write("---")
st.write("### 🔗 Wikipedia-Referenzen")
wiki_list = [
    "[Gewinnmarge](https://de.wikipedia.org/wiki/Umsatzrendite)", "[EBITDA](https://de.wikipedia.org/wiki/EBITDA)", 
    "[ROE](https://de.wikipedia.org/wiki/Eigenkapitalrendite)", "[KGV](https://de.wikipedia.org/wiki/Kurs-Gewinn-Verh%C3%A4ltnis)",
    "[Liquidität](https://de.wikipedia.org/wiki/Liquidit%C3%A4tsgrad)", "[Verschuldungsgrad](https://de.wikipedia.org/wiki/Verschuldungsgrad)",
    "[Wachstumsrate](https://de.wikipedia.org/wiki/Wachstumsrate)", "[KBV](https://de.wikipedia.org/wiki/Kurs-Buchwert-Verh%C3%A4ltnis)",
    "[Kapitalumschlag](https://de.wikipedia.org/wiki/Kapitalumschlagsh%C3%A4ufigkeit)"
]
st.markdown(" • ".join(wiki_list))
st.caption("ARES 0.8.4 || Professional Analysis Engine")