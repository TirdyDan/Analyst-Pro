import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import zipfile
import io

# --- HILFSFUNKTION FÜR ROBUSTE DATENABFRAGE ---
def get_val(df, keys):
    """Sucht den neuesten Wert aus einer Liste möglicher Keys."""
    for k in keys:
        if k in df.index:
            val = df.loc[k].iloc[0]
            if pd.notnull(val): return val
    return None

def get_series(df, keys):
    """Sucht eine ganze Zeitreihe (für Diagramme)."""
    for k in keys:
        if k in df.index: return df.loc[k]
    return None

# --- UI DESIGN ---
st.set_page_config(page_title="Ares Global Analyst 0.8", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; border-bottom: 2px solid #FFD700; padding-bottom: 10px; }
    h2, h3 { color: #FFD700 !important; font-family: 'Georgia', serif; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 5px; font-weight: bold; width: 100% !important; }
    input { background-color: #2d2d2d !important; color: white !important; border: 1px solid #FFD700 !important; }
    .hint { color: #888; font-size: 0.85rem; margin-top: -10px; margin-bottom: 15px; }
    [data-testid="stMetricValue"] { color: #FFD700 !important; font-size: 1.6rem; }
    </style>
    """, unsafe_allow_html=True)

st.title("Ares 0.8")

# --- EINGABE ---
ticker_sym = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. NVDA, AAPL, SAP.DE").upper()
st.markdown('<p class="hint">Verwende zum Beispiel die Google KI Suche um Tickersymbole herauszufinden.</p>', unsafe_allow_html=True)

anzahl_jahre = st.selectbox("ANALYSE-ZEITRAUM (JAHRE ZURÜCK)", options=[1, 2, 3, 4, 5], index=4)

if ticker_sym:
    try:
        with st.spinner(f'Analysiere {ticker_sym}...'):
            stock = yf.Ticker(ticker_sym)
            info = stock.info
            
            if not info or 'shortName' not in info:
                st.error("Rate Limit erreicht oder Ticker ungültig. Bitte kurz warten.")
                st.stop()

            # --- 1. PREIS-CHART MIT +30% SKALIERUNG ---
            st.subheader(f"📈 Aktienkurs: {info.get('shortName', ticker_sym)}")
            t_frame = st.radio("ZEITRAUM", ["1T", "1W", "1M", "6M", "1J", "MAX"], horizontal=True, index=4)
            p_map = {"1T":"1d","1W":"5d","1M":"1mo","6M":"6mo","1J":"1y","MAX":"max"}
            i_map = {"1T":"5m","1W":"30m","1M":"1d","6M":"1d","1J":"1d","MAX":"1wk"}
            
            hist = stock.history(period=p_map[t_frame], interval=i_map[t_frame])
            
            if not hist.empty:
                max_p = hist['Close'].max()
                min_p = hist['Close'].min()
                fig_p = go.Figure(go.Scatter(x=hist.index, y=hist['Close'], line=dict(color='#FFD700', width=2), fill='tozeroy', fillcolor='rgba(255, 215, 0, 0.1)'))
                # Skalierung: 30% Puffer oben
                fig_p.update_yaxes(range=[min_p * 0.95, max_p * 1.3])
                fig_p.update_layout(template="plotly_dark", height=350, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
                st.plotly_chart(fig_p, use_container_width=True)

            # --- 2. FINANZDATEN (LATEST FISCAL) ---
            income = stock.financials
            balance = stock.balance_sheet
            cashflow = stock.cashflow
            
            if not income.empty and not balance.empty:
                st.write("---")
                st.subheader("📊 Fundamental Quick-Check (Aktuellstes Fiskaljahr)")
                
                # Rohwerte ziehen
                rev = get_val(income, ['Total Revenue'])
                net_inc = get_val(income, ['Net Income'])
                ebitda = get_val(income, ['EBITDA'])
                c_assets = get_val(balance, ['Total Current Assets'])
                c_liabs = get_val(balance, ['Total Current Liabilities'])
                debt = get_val(balance, ['Total Debt', 'Long Term Debt'])
                equity = get_val(balance, ['Stockholders Equity'])

                c1,c2,c3 = st.columns(3); c4,c5,c6 = st.columns(3); c7,c8,c9 = st.columns(3)

                # Zeile 1: Profit
                c1.metric("Gewinnmarge", f"{(net_inc/rev)*100:.2f}%" if rev and net_inc else "N/A")
                c2.metric("EBITDA-Marge", f"{(ebitda/rev)*100:.2f}%" if rev and ebitda else "N/A")
                c3.metric("Eigenkapitalrendite", f"{(net_inc/equity)*100:.2f}%" if net_inc and equity else "N/A")

                # Zeile 2: Bewertung & Liquidität
                c4.metric("KGV (PE Ratio)", info.get('trailingPE', 'N/A'))
                c5.metric("Liquidität (Ratio)", f"{c_assets/c_liabs:.2f}" if c_assets and c_liabs else "N/A")
                c6.metric("Verschuldungsgrad", f"{debt/equity:.2f}" if debt and equity else "N/A")

                # Zeile 3: Wachstum & Dividende (KORREKTUR)
                rev_g = "N/A"
                if len(income.columns) > 1:
                    r0, r1 = income.loc['Total Revenue'].iloc[0], income.loc['Total Revenue'].iloc[1]
                    rev_g = f"{((r0-r1)/r1)*100:.2f}%"
                
                c7.metric("Umsatzwachstum", rev_g)
                c8.metric("KBV (P/B Ratio)", info.get('priceToBook', 'N/A'))
                
                # PRÄZISE DIVIDENDE (z.B. NVDA 0.02%)
                div_val = info.get('dividendYield')
                if div_val is not None:
                    # Yahoo liefert 0.0002 für 0.02%. Wir zeigen 3 Dezimalstellen für Präzision.
                    c9.metric("Dividendenrendite", f"{div_val*100:.3f}%")
                else:
                    c9.metric("Dividendenrendite", "0.000%")

                # --- 3. TREND-GRAFIK (ALLE 9 KENNZAHLEN) ---
                st.write("---")
                st.subheader("📉 Historische Trends (5 Jahre)")
                
                # Mapping für alle 9 Kennzahlen
                trend_options = [
                    "Gesamtumsatz", "Reingewinn", "EBITDA", 
                    "Eigenkapital", "Gesamtschulden", "Umlaufvermögen", 
                    "Kurzfr. Verbindlichkeiten", "Operativer Cashflow", "Free Cashflow"
                ]
                sel_trend = st.selectbox("KENNZAHL FÜR DIAGRAMM WÄHLEN:", trend_options)
                
                trend_map = {
                    "Gesamtumsatz": (income, ['Total Revenue']),
                    "Reingewinn": (income, ['Net Income']),
                    "EBITDA": (income, ['EBITDA']),
                    "Eigenkapital": (balance, ['Stockholders Equity']),
                    "Gesamtschulden": (balance, ['Total Debt', 'Long Term Debt']),
                    "Umlaufvermögen": (balance, ['Total Current Assets']),
                    "Kurzfr. Verbindlichkeiten": (balance, ['Total Current Liabilities']),
                    "Operativer Cashflow": (cashflow, ['Operating Cash Flow']),
                    "Free Cashflow": (cashflow, ['Free Cash Flow'])
                }
                
                target_df, keys = trend_map[sel_trend]
                data_series = get_series(target_df, keys)
                
                if data_series is not None:
                    fig_t = go.Figure(go.Bar(x=data_series.index.year, y=data_series.values, marker_color='#FFD700'))
                    fig_t.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=20,b=0))
                    st.plotly_chart(fig_t, use_container_width=True)

                # --- DOWNLOAD ---
                st.write("---")
                zip_b = io.BytesIO()
                with zipfile.ZipFile(zip_b, "w") as zf:
                    zf.writestr(f"{ticker_sym}_Bilanz.csv", balance.iloc[:, :anzahl_jahre].to_csv())
                    zf.writestr(f"{ticker_sym}_GuV.csv", income.iloc[:, :anzahl_jahre].to_csv())
                    zf.writestr(f"{ticker_sym}_Cashflow.csv", cashflow.iloc[:, :anzahl_jahre].to_csv())
                st.download_button(label=f"🏆 DOWNLOAD {ticker_sym} PAKET", data=zip_b.getvalue(), file_name=f"Ares_{ticker_sym}.zip", mime="application/zip")

    except Exception as e:
        st.error(f"Datenfehler: {e}")

# --- VOLLSTÄNDIGES LEXIKON ---
st.write("---")
st.write("### 📘 Kennzahlen-Lexikon")
col_l, col_r = st.columns(2)
with col_l:
    st.markdown("- **Gewinnmarge:** Reingewinn/Umsatz. Effizienz-Check.\n- **EBITDA-Marge:** Operative Kraft vor Steuern.\n- **Eigenkapitalrendite:** Verzinsung des Kapitals.\n- **KGV:** Bewertung (Preis pro 1€ Gewinn).\n- **Liquidität:** Kurzfr. Zahlungsfähigkeit.")
with col_r:
    st.markdown("- **Verschuldungsgrad:** Schulden zu Eigenkapital.\n- **Umsatzwachstum:** Dynamik zum Vorjahr.\n- **KBV:** Preis zu Substanzwert.\n- **Dividendenrendite:** Jährliche Bar-Ausschüttung.")

st.write("### 🔗 Wikipedia-Referenzen")
w_links = [
    "[Gewinnmarge](https://de.wikipedia.org/wiki/Umsatzrendite)", "[EBITDA](https://de.wikipedia.org/wiki/EBITDA)", 
    "[Eigenkapitalrendite](https://de.wikipedia.org/wiki/Eigenkapitalrendite)", "[KGV](https://de.wikipedia.org/wiki/Kurs-Gewinn-Verh%C3%A4ltnis)",
    "[Liquidität](https://de.wikipedia.org/wiki/Liquidit%C3%A4tsgrad)", "[Verschuldungsgrad](https://de.wikipedia.org/wiki/Verschuldungsgrad)",
    "[Umsatzwachstum](https://de.wikipedia.org/wiki/Wachstumsrate)", "[KBV](https://de.wikipedia.org/wiki/Kurs-Buchwert-Verh%C3%A4ltnis)",
    "[Dividendenrendite](https://de.wikipedia.org/wiki/Dividendenrendite)"
]
st.markdown(" • ".join(w_links))
st.caption("Ares 0.8 || Präzisions-Update & Chart-Scaling")