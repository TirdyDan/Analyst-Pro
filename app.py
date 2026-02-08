import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import zipfile
import io

# --- HILFSFUNKTIONEN ---
def get_financial_value(df, possible_keys):
    for key in possible_keys:
        if key in df.index:
            val = df.loc[key].iloc[0]
            if pd.notnull(val) and val != 0:
                return val
    return None

# --- UI DESIGN ---
st.set_page_config(page_title="Ares Global Analyst 0.7", layout="centered")

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

st.title("Ares 0.7")

# --- EINGABE ---
ticker_sym = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. AAPL, MSFT, SAP.DE, VOE.VI").upper()
st.markdown('<p class="hint">Verwende zum Beispiel die Google KI Suche um Tickersymbole herauszufinden.</p>', unsafe_allow_html=True)

if ticker_sym:
    try:
        with st.spinner(f'Analysiere {ticker_sym}...'):
            stock = yf.Ticker(ticker_sym)
            info = stock.info
            
            # --- 1. INTERAKTIVER PREIS-CHART ---
            st.subheader(f"📈 Aktienkurs: {info.get('shortName', ticker_sym)}")
            
            timeframe = st.radio("ZEITRAUM WÄHLEN", ["1T", "1W", "1M", "6M", "1J", "MAX"], horizontal=True, index=4)
            period_map = {"1T": "1d", "1W": "5d", "1M": "1mo", "6M": "6mo", "1J": "1y", "MAX": "max"}
            interval_map = {"1T": "5m", "1W": "30m", "1M": "1d", "6M": "1d", "1J": "1d", "MAX": "1wk"}
            
            hist = stock.history(period=period_map[timeframe], interval=interval_map[timeframe])
            
            if not hist.empty:
                fig_price = go.Figure()
                fig_price.add_trace(go.Scatter(x=hist.index, y=hist['Close'], line=dict(color='#FFD700', width=2), fill='tozeroy', fillcolor='rgba(255, 215, 0, 0.1)'))
                fig_price.update_layout(template="plotly_dark", height=350, margin=dict(l=0, r=0, t=0, b=0), xaxis_rangeslider_visible=False)
                st.plotly_chart(fig_price, use_container_width=True)

            # --- 2. FINANZDATEN LADEN ---
            income = stock.financials
            balance = stock.balance_sheet
            cashflow = stock.cashflow
            
            if not income.empty and not balance.empty:
                st.write("---")
                st.subheader("📊 Fundamental Quick-Check")
                
                # --- KPI BERECHNUNGEN (GEPRÜFT) ---
                rev = get_financial_value(income, ['Total Revenue'])
                net_inc = get_financial_value(income, ['Net Income'])
                ebitda = get_financial_value(income, ['EBITDA'])
                assets = get_financial_value(balance, ['Total Current Assets'])
                liabs = get_financial_value(balance, ['Total Current Liabilities'])
                total_debt = get_financial_value(balance, ['Total Debt'])
                equity = get_financial_value(balance, ['Stockholders Equity'])
                
                # 3x3 Grid
                c1, c2, c3 = st.columns(3)
                c4, c5, c6 = st.columns(3)
                c7, c8, c9 = st.columns(3)

                c1.metric("Gewinnmarge", f"{(net_inc/rev)*100:.2f}%" if rev and net_inc else "N/A")
                c2.metric("EBITDA-Marge", f"{(ebitda/rev)*100:.2f}%" if rev and ebitda else "N/A")
                c3.metric("Eigenkapitalrendite", f"{(net_inc/equity)*100:.2f}%" if net_inc and equity else "N/A")

                # KGV & KBV direkt von Yahoo (Sicherste Quelle)
                c4.metric("KGV (PE Ratio)", info.get('trailingPE', 'N/A'))
                c5.metric("Liquidität (Ratio)", f"{assets/liabs:.2f}" if assets and liabs else "N/A")
                c6.metric("Verschuldungsgrad", f"{total_debt/equity:.2f}" if total_debt and equity else "N/A")

                # Umsatzwachstum
                rev_growth = "N/A"
                if len(income.columns) > 1:
                    r0, r1 = income.loc['Total Revenue'].iloc[0], income.loc['Total Revenue'].iloc[1]
                    rev_growth = f"{((r0-r1)/r1)*100:.2f}%"
                
                c7.metric("Umsatzwachstum", rev_growth)
                c8.metric("KBV (P/B Ratio)", info.get('priceToBook', 'N/A'))
                
                # DIVIDENDE FIX (Plausibilitätscheck: Renditen > 50% werden als Fehler gewertet)
                div_yield_raw = info.get('dividendYield', 0)
                if div_yield_raw and div_yield_raw < 0.5: # 0.5 entspricht 50%
                    div_display = f"{div_yield_raw*100:.2f}%"
                elif div_yield_raw and div_yield_raw >= 0.5:
                    div_display = "Datenfehler" # Schutz vor Ausreißern
                else:
                    div_display = "0.00%"
                c9.metric("Dividendenrendite", div_display)

                # --- 3. INTERAKTIVE TREND-GRAFIK (5 JAHRE) ---
                st.write("---")
                st.subheader("📉 Historische Trends (Letzte 5 Jahre)")
                
                metric_to_plot = st.selectbox("WÄHLE EINE KENNZAHL FÜR DEN TREND:", 
                                            ["Gesamtumsatz", "Reingewinn", "Operativer Cashflow", "EBITDA"])
                
                plot_map = {
                    "Gesamtumsatz": income.loc['Total Revenue'] if 'Total Revenue' in income.index else None,
                    "Reingewinn": income.loc['Net Income'] if 'Net Income' in income.index else None,
                    "Operativer Cashflow": cashflow.loc['Operating Cash Flow'] if 'Operating Cash Flow' in cashflow.index else None,
                    "EBITDA": income.loc['EBITDA'] if 'EBITDA' in income.index else None
                }
                
                data_series = plot_map[metric_to_plot]
                if data_series is not None:
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Bar(x=data_series.index.year, y=data_series.values, marker_color='#FFD700', name=metric_to_plot))
                    fig_trend.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=20, b=0))
                    st.plotly_chart(fig_trend, use_container_width=True)

                # --- DOWNLOAD ---
                st.write("---")
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    zf.writestr(f"{ticker_sym}_Bilanz.csv", balance.to_csv())
                    zf.writestr(f"{ticker_sym}_GuV.csv", income.to_csv())
                    zf.writestr(f"{ticker_sym}_Cashflow.csv", cashflow.to_csv())

                st.download_button(label=f"🏆 DOWNLOAD: {ticker_sym} ANALYSE-PAKET", data=zip_buffer.getvalue(), 
                                 file_name=f"Ares_{ticker_sym}_Full.zip", mime="application/zip")
            else:
                st.warning("Keine Finanzdaten für diesen Ticker verfügbar.")
    except Exception as e:
        st.error(f"Fehler: {e}")

# --- LEXIKON & WIKIPEDIA (UNTERHALB) ---
st.write("### 📘 Kennzahlen-Lexikon")
exp1, exp2 = st.columns(2)
with exp1:
    st.markdown("**Gewinnmarge:** Reingewinn/Umsatz. | **EBITDA:** Operativer Gewinn vor Steuern/Abschreibung. | **ROE:** Verzinsung des Eigenkapitals.")
with exp2:
    st.markdown("**KGV:** Preis pro 1€ Gewinn. | **Liquidität:** Kurzfr. Zahlungsfähigkeit. | **Debt-to-Equity:** Verschuldungsgrad.")

st.write("### 🔗 Wikipedia-Referenzen")
links = ["[Gewinnmarge](https://de.wikipedia.org/wiki/Umsatzrendite)", "[KGV](https://de.wikipedia.org/wiki/Kurs-Gewinn-Verh%C3%A4ltnis)", 
         "[EBITDA](https://de.wikipedia.org/wiki/EBITDA)", "[Liquidität](https://de.wikipedia.org/wiki/Liquidit%C3%A4tsgrad)", 
         "[ROE](https://de.wikipedia.org/wiki/Eigenkapitalrendite)", "[Verschuldungsgrad](https://de.wikipedia.org/wiki/Verschuldungsgrad)"]
st.markdown(" • ".join(links))

st.write("---")
st.caption("Ares 0.7 || Fokus: Visualisierung & Datenintegrität")