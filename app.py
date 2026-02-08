import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import zipfile
import io
import time

# --- HILFSFUNKTIONEN ---
def get_financial_value(df, possible_keys):
    for key in possible_keys:
        if key in df.index:
            val = df.loc[key].iloc[0]
            if pd.notnull(val) and val != 0:
                return val
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
ticker_sym = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. AAPL, MSFT, SAP.DE, VOE.VI").upper()
st.markdown('<p class="hint">Verwende zum Beispiel die Google KI Suche um Tickersymbole herauszufinden.</p>', unsafe_allow_html=True)

anzahl_jahre = st.selectbox("ANALYSE-ZEITRAUM (JAHRE ZURÜCK)", options=[1, 2, 3, 4, 5], index=4)

if ticker_sym:
    try:
        with st.spinner(f'Analysiere {ticker_sym}...'):
            # Wir versuchen die Daten abzurufen
            stock = yf.Ticker(ticker_sym)
            
            # --- 1. PREIS-CHART ---
            info = stock.info
            if not info or 'shortName' not in info:
                # Falls Rate Limit zuschlägt, versuchen wir es mit Minimaldaten
                st.error("Fehler: Too Many Requests (Yahoo Rate Limit). Bitte warte kurz oder versuche einen anderen Ticker.")
                st.stop()

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

            # --- 2. FINANZDATEN ---
            income = stock.financials
            balance = stock.balance_sheet
            cashflow = stock.cashflow
            
            if not income.empty and not balance.empty:
                st.write("---")
                st.subheader("📊 Fundamental Quick-Check (9 Kennzahlen)")
                
                # Berechnungswerte
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
                
                # Dividende Sicherung
                div_yield = info.get('dividendYield', 0)
                div_display = f"{div_yield*100:.2f}%" if div_yield and div_yield < 0.4 else ("0.00%" if not div_yield else "Datenfehler")
                c9.metric("Dividendenrendite", div_display)

                # --- 3. TREND-GRAFIK ---
                st.write("---")
                st.subheader("📉 Historische Trends (5 Jahre)")
                metric_to_plot = st.selectbox("WÄHLE EINE KENNZAHL:", ["Gesamtumsatz", "Reingewinn", "Operativer Cashflow", "EBITDA"])
                plot_map = {"Gesamtumsatz": 'Total Revenue', "Reingewinn": 'Net Income', "Operativer Cashflow": 'Operating Cash Flow', "EBITDA": 'EBITDA'}
                
                source_df = cashflow if metric_to_plot == "Operativer Cashflow" else income
                if plot_map[metric_to_plot] in source_df.index:
                    data = source_df.loc[plot_map[metric_to_plot]]
                    fig_trend = go.Figure(go.Bar(x=data.index.year, y=data.values, marker_color='#FFD700'))
                    fig_trend.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=20, b=0))
                    st.plotly_chart(fig_trend, use_container_width=True)

                # --- DOWNLOAD ---
                st.write("---")
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    zf.writestr(f"{ticker_sym}_Bilanz.csv", balance.to_csv())
                    zf.writestr(f"{ticker_sym}_GuV.csv", income.to_csv())
                    zf.writestr(f"{ticker_sym}_Cashflow.csv", cashflow.to_csv())
                st.download_button(label=f"🏆 DOWNLOAD {ticker_sym} PAKET", data=zip_buffer.getvalue(), file_name=f"Ares_{ticker_sym}.zip", mime="application/zip")

    except Exception as e:
        if "Too Many Requests" in str(e):
            st.error("Yahoo Finance blockiert gerade die Anfrage (Rate Limit). Bitte versuche es in 5-10 Minuten erneut.")
        else:
            st.error(f"Fehler: {e}")

# --- VOLLSTÄNDIGES LEXIKON ---
st.write("---")
st.write("### 📘 Vollständiges Kennzahlen-Lexikon")
l_col1, l_col2 = st.columns(2)
with l_col1:
    st.markdown("""
    - **Gewinnmarge:** Welcher Prozentsatz vom Umsatz bleibt als Nettogewinn? (>10% ist gut)
    - **EBITDA-Marge:** Operative Stärke ohne Steuern und Abschreibungen.
    - **Eigenkapitalrendite (ROE):** Wie effektiv arbeitet das Geld der Aktionäre? (>15% ist top)
    - **KGV (PE Ratio):** Bewertung der Aktie. Wie viele Jahresgewinne kostet die Firma?
    - **Liquidität (Current Ratio):** Kurzfristige Zahlungsfähigkeit. (Ideal > 1.5)
    """)
with l_col2:
    st.markdown("""
    - **Verschuldungsgrad:** Verhältnis Schulden zu Eigenkapital. (Ideal < 1.0)
    - **Umsatzwachstum:** Dynamik des Unternehmens im Vergleich zum Vorjahr.
    - **KBV (P/B Ratio):** Substanzwert. Preis im Vergleich zum Eigenkapital.
    - **Dividendenrendite:** Jährliche Ausschüttung in Prozent zum Aktienkurs.
    """)

# --- VOLLSTÄNDIGE LINKS ---
st.write("### 🔗 Wikipedia-Referenzen (Alle 9)")
links = [
    "[Gewinnmarge](https://de.wikipedia.org/wiki/Umsatzrendite)", 
    "[EBITDA](https://de.wikipedia.org/wiki/EBITDA)", 
    "[Eigenkapitalrendite](https://de.wikipedia.org/wiki/Eigenkapitalrendite)",
    "[KGV](https://de.wikipedia.org/wiki/Kurs-Gewinn-Verh%C3%A4ltnis)",
    "[Liquiditätsgrad](https://de.wikipedia.org/wiki/Liquidit%C3%A4tsgrad)",
    "[Verschuldungsgrad](https://de.wikipedia.org/wiki/Verschuldungsgrad)",
    "[Umsatzwachstum](https://de.wikipedia.org/wiki/Wachstumsrate)",
    "[KBV](https://de.wikipedia.org/wiki/Kurs-Buchwert-Verh%C3%A4ltnis)",
    "[Dividendenrendite](https://de.wikipedia.org/wiki/Dividendenrendite)"
]
st.markdown(" • ".join(links))

st.caption("Ares 0.8 || Stabilitäts-Fix & Vollständiges Lexikon")