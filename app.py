import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io

# --- HILFSFUNKTION FÜR ROBUSTE DATENABFRAGE ---
def get_financial_value(df, possible_keys):
    """Sucht in einem Dataframe nach dem ersten existierenden Key aus einer Liste."""
    for key in possible_keys:
        if key in df.index:
            val = df.loc[key].iloc[0]
            if pd.notnull(val) and val != 0:
                return val
    return None

# --- UI DESIGN ---
st.set_page_config(page_title="Ares Global Analyst 0.5", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; border-bottom: 2px solid #FFD700; padding-bottom: 10px; }
    h2, h3 { color: #FFD700 !important; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 5px; font-weight: bold; width: 100%; height: 3.5em; }
    input { background-color: #2d2d2d !important; color: white !important; border: 1px solid #FFD700 !important; }
    
    /* Metriken Styling */
    [data-testid="stMetricValue"] { color: #FFD700 !important; font-size: 1.8rem; }
    [data-testid="stMetricLabel"] { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Ares 0.5")

# --- EINGABE-BEREICH ---
# Suche entfernt, nur noch Ticker-Eingabe
ticker = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. AAPL, MSFT, SAP.DE, VOE.VI").upper()

anzahl_jahre = st.selectbox(
    "ANALYSE-ZEITRAUM (JAHRE ZURÜCK)",
    options=[1, 2, 3, 4, 5],
    index=4 
)

# --- ANALYSE ---
if ticker:
    try:
        with st.spinner(f'Analysiere {ticker}...'):
            stock = yf.Ticker(ticker)
            
            # Daten abrufen
            income = stock.financials
            balance = stock.balance_sheet
            cashflow = stock.cashflow
            
            if not income.empty and not balance.empty:
                st.subheader(f"📊 Quick-Check: {ticker}")
                
                # --- ROBUSTE KPI BERECHNUNG ---
                # 1. Gewinnmarge (Profit Margin)
                rev = get_financial_value(income, ['Total Revenue', 'Operating Revenue'])
                net_inc = get_financial_value(income, ['Net Income', 'Net Income Common Stockholders'])
                
                # 2. Liquidität (Current Ratio)
                assets = get_financial_value(balance, ['Total Current Assets', 'Current Assets'])
                liabs = get_financial_value(balance, ['Total Current Liabilities', 'Current Liabilities'])
                
                # 3. Umsatzwachstum (Revenue Growth)
                rev_growth = None
                if not income.empty and len(income.columns) > 1:
                    rev_now = income.loc['Total Revenue'].iloc[0] if 'Total Revenue' in income.index else None
                    rev_prev = income.loc['Total Revenue'].iloc[1] if 'Total Revenue' in income.index else None
                    if rev_now and rev_prev:
                        rev_growth = ((rev_now - rev_prev) / rev_prev) * 100

                # Anzeige in Spalten
                col1, col2, col3 = st.columns(3)
                
                if rev and net_inc:
                    col1.metric("Gewinnmarge", f"{(net_inc/rev)*100:.2f}%")
                else:
                    col1.metric("Gewinnmarge", "N/A")
                    
                if assets and liabs:
                    col2.metric("Liquidität (Ratio)", f"{assets/liabs:.2f}")
                else:
                    col2.metric("Liquidität", "N/A")
                    
                if rev_growth is not None:
                    col3.metric("Umsatzwachstum", f"{rev_growth:.2f}%")
                else:
                    col3.metric("Umsatzwachstum", "N/A")

                st.write("---")

                # --- DOWNLOAD BEREICH ---
                zip_buffer = io.BytesIO()
                files_added = 0
                
                # Begrenze Daten auf User-Auswahl
                income_exp = income.iloc[:, :anzahl_jahre]
                balance_exp = balance.iloc[:, :anzahl_jahre]
                cashflow_exp = cashflow.iloc[:, :anzahl_jahre]

                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    if not balance_exp.empty:
                        zf.writestr(f"{ticker}_Bilanz.csv", balance_exp.to_csv())
                        files_added += 1
                    if not income_exp.empty:
                        zf.writestr(f"{ticker}_GuV.csv", income_exp.to_csv())
                        files_added += 1
                    if not cashflow_exp.empty:
                        zf.writestr(f"{ticker}_Cashflow.csv", cashflow_exp.to_csv())
                        files_added += 1

                if files_added > 0:
                    st.success(f"✓ {files_added} Tabellen für {ticker} generiert.")
                    st.download_button(
                        label=f"🏆 DATEN-PAKET ({anzahl_jahre} JAHRE) LADEN",
                        data=zip_buffer.getvalue(),
                        file_name=f"{ticker}_Analysis_Ares.zip",
                        mime="application/zip"
                    )
            else:
                st.warning("Keine Finanzdaten gefunden. (Hinweis: ETFs oder Rohstoffe haben oft keine Bilanzen)")

    except Exception as e:
        st.error(f"Fehler bei der Analyse: {e}")

st.write("---")
st.caption("Ares 0.5 || Fokus: Manuelle Analyse & Deep-Data")