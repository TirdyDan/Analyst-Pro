import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io

# --- HILFSFUNKTION FÜR ROBUSTE DATENABFRAGE ---
def get_financial_value(df, possible_keys):
    """Sucht in einem Dataframe nach dem ersten existierenden Key."""
    for key in possible_keys:
        if key in df.index:
            val = df.loc[key].iloc[0]
            if pd.notnull(val) and val != 0:
                return val
    return None

# --- UI DESIGN (Anthrazit & Gold) ---
st.set_page_config(page_title="Ares Global Analyst 0.6", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; border-bottom: 2px solid #FFD700; padding-bottom: 10px; }
    h2, h3 { color: #FFD700 !important; font-family: 'Georgia', serif; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 5px; font-weight: bold; width: 100%; height: 3.5em; }
    input { background-color: #2d2d2d !important; color: white !important; border: 1px solid #FFD700 !important; }
    .hint { color: #888; font-size: 0.85rem; margin-top: -10px; margin-bottom: 15px; }
    
    /* Metriken Styling */
    [data-testid="stMetricValue"] { color: #FFD700 !important; font-size: 1.6rem; }
    [data-testid="stMetricLabel"] { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Ares 0.6")

# --- EINGABE-BEREICH ---
ticker = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. AAPL, MSFT, SAP.DE, VOE.VI").upper()
st.markdown('<p class="hint">Verwende zum Beispiel die Google KI Suche um Tickersymbole herauszufinden.</p>', unsafe_allow_html=True)

anzahl_jahre = st.selectbox("ANALYSE-ZEITRAUM (JAHRE ZURÜCK)", options=[1, 2, 3, 4, 5], index=4)

# --- ANALYSE ---
if ticker:
    try:
        with st.spinner(f'Analysiere {ticker}...'):
            stock = yf.Ticker(ticker)
            info = stock.info
            income = stock.financials
            balance = stock.balance_sheet
            cashflow = stock.cashflow
            
            if not income.empty and not balance.empty:
                st.subheader(f"📊 Global Quick-Check: {ticker}")
                
                # --- KPI BERECHNUNGEN ---
                # 1. Marge & Profit
                rev = get_financial_value(income, ['Total Revenue', 'Operating Revenue'])
                net_inc = get_financial_value(income, ['Net Income', 'Net Income Common Stockholders'])
                ebitda = get_financial_value(income, ['EBITDA', 'Normalized EBITDA'])
                
                # 2. Liquidität & Schulden
                assets = get_financial_value(balance, ['Total Current Assets', 'Current Assets'])
                liabs = get_financial_value(balance, ['Total Current Liabilities', 'Current Liabilities'])
                total_debt = get_financial_value(balance, ['Total Debt', 'Long Term Debt'])
                equity = get_financial_value(balance, ['Stockholders Equity', 'Total Equity Gross Minority Interest'])
                
                # --- METRIKEN ANZEIGEN (3x3 Raster) ---
                c1, c2, c3 = st.columns(3)
                c4, c5, c6 = st.columns(3)
                c7, c8, c9 = st.columns(3)

                # Zeile 1: Rentabilität
                c1.metric("Gewinnmarge", f"{(net_inc/rev)*100:.2f}%" if rev and net_inc else "N/A")
                c2.metric("EBITDA-Marge", f"{(ebitda/rev)*100:.2f}%" if rev and ebitda else "N/A")
                c3.metric("Eigenkapitalrendite", f"{(net_inc/equity)*100:.2f}%" if net_inc and equity else "N/A")

                # Zeile 2: Stabilität & Bewertung
                c4.metric("KGV (PE Ratio)", f"{info.get('trailingPE', 'N/A')}")
                c5.metric("Liquidität (Ratio)", f"{assets/liabs:.2f}" if assets and liabs else "N/A")
                c6.metric("Verschuldungsgrad", f"{total_debt/equity:.2f}" if total_debt and equity else "N/A")

                # Zeile 3: Markt & Wachstum
                rev_growth = None
                if len(income.columns) > 1:
                    r_now = income.loc['Total Revenue'].iloc[0] if 'Total Revenue' in income.index else None
                    r_prev = income.loc['Total Revenue'].iloc[1] if 'Total Revenue' in income.index else None
                    if r_now and r_prev: rev_growth = ((r_now - r_prev) / r_prev) * 100
                
                c7.metric("Umsatzwachstum", f"{rev_growth:.2f}%" if rev_growth else "N/A")
                c8.metric("KBV (P/B Ratio)", f"{info.get('priceToBook', 'N/A')}")
                div_yield = info.get('dividendYield')
                c9.metric("Dividendenrendite", f"{div_yield*100:.2f}%" if div_yield else "0.00%")

                st.write("---")

                # --- DOWNLOAD ---
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    zf.writestr(f"{ticker}_Bilanz.csv", balance.iloc[:, :anzahl_jahre].to_csv())
                    zf.writestr(f"{ticker}_GuV.csv", income.iloc[:, :anzahl_jahre].to_csv())
                    zf.writestr(f"{ticker}_Cashflow.csv", cashflow.iloc[:, :anzahl_jahre].to_csv())

                st.download_button(
                    label=f"🏆 DATEN-PAKET ({anzahl_jahre} JAHRE) LADEN",
                    data=zip_buffer.getvalue(),
                    file_name=f"Ares_{ticker}_Full_Analysis.zip",
                    mime="application/zip"
                )
            else:
                st.warning("Keine Finanzdaten gefunden. Prüfen Sie den Ticker.")

    except Exception as e:
        st.error(f"Fehler: {e}")

# --- DETAIL-ERKLÄRUNGEN ---
st.write("### 📘 Kennzahlen-Lexikon (Deep Dive)")
exp_col1, exp_col2 = st.columns(2)

with exp_col1:
    st.markdown("""
    **1. Gewinnmarge (Net Profit Margin)** Zeigt, wie viel Prozent des Umsatzes nach Abzug aller Kosten als Reingewinn übrig bleiben.  
    *Ideal: > 10%*
    
    **2. EBITDA-Marge** Misst die operative Leistungsfähigkeit vor Zinsen, Steuern und Abschreibungen. Gut zum Branchenvergleich.
    
    **3. Eigenkapitalrendite (ROE)** Wie effizient nutzt die Firma das Geld der Eigentümer, um Gewinn zu machen?  
    *Ideal: > 15%*
    
    **4. KGV (Kurs-Gewinn-Verhältnis)** Gibt an, das Wievielfache des Gewinns der Markt bereit ist zu zahlen.  
    *Niedrig = Günstig / Hoch = Teuer*
    
    **5. Liquidität (Current Ratio)** Kann die Firma kurzfristige Schulden mit ihrem Barvermögen decken?  
    *Ideal: > 1.5*
    """)

with exp_col2:
    st.markdown("""
    **6. Verschuldungsgrad (Debt-to-Equity)** Verhältnis von Schulden zu Eigenkapital. Zu hohe Werte deuten auf Risiko hin.  
    *Ideal: < 1.0 (branchenabhängig)*
    
    **7. Umsatzwachstum** Die prozentuale Veränderung des Umsatzes zum Vorjahr. Ein Zeichen für Marktdynamik.
    
    **8. KBV (Kurs-Buchwert-Verhältnis)** Vergleicht den Börsenwert mit dem Substanzwert (Eigenkapital).  
    *Werte < 1 gelten oft als 'Schnäppchen'.*
    
    **9. Dividendenrendite** Der prozentuale Anteil des Gewinns, der direkt als Cash an dich ausgeschüttet wird.
    """)

st.write("---")
st.write("### 🔗 Wikipedia-Referenzen")
st.caption("Klicke auf die Links, um die mathematische Herkunft zu verstehen:")
wiki_links = [
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
st.markdown(" • ".join(wiki_links))

st.write("---")
st.caption("Ares 0.6 || Fokus: Fundamentale 360°-Analyse")