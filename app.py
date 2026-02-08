import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io
import requests

# --- STABILE DATEN-FUNKTION (Ares 0.5) ---
@st.cache_data(ttl=86400)
def get_ares_global_database():
    db = {}
    
    # Hilfsfunktion zum Laden von CSVs mit Header-Simulation
    def load_source(url, sym_col, name_col, index_name, suffix=""):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=5)
            if response.status_code == 200:
                df = pd.read_csv(io.StringIO(response.text))
                for _, row in df.iterrows():
                    sym = str(row[sym_col]).strip().replace('.', '-')
                    if suffix and not sym.endswith(suffix):
                        sym = f"{sym}{suffix}"
                    name = str(row[name_col]).strip()
                    display = f"{name} ({index_name}) - {sym}"
                    db[display] = sym
        except:
            pass

    # Datenquellen (S&P 500, NASDAQ, DAX, Nikkei)
    load_source("https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv", "Symbol", "Name", "S&P 500")
    load_source("https://raw.githubusercontent.com/heisengpt/stock-tickers/main/nasdaq100.csv", "ticker", "name", "NASDAQ")
    load_source("https://raw.githubusercontent.com/datasets/dax-queries/main/data/dax-constituents.csv", "Symbol", "Name", "DAX", ".DE")
    load_source("https://raw.githubusercontent.com/datasets/nikkei-225/main/data/constituents.csv", "Symbol", "Name", "Nikkei 225", ".T")

    # Manuelles Backup für ATX & Global Giants
    internal_db = {
        "Andritz (ATX) - ANDR.VI": "ANDR.VI", "Erste Group (ATX) - EBS.VI": "EBS.VI", "OMV (ATX) - OMV.VI": "OMV.VI",
        "Verbund (ATX) - VER.VI": "VER.VI", "voestalpine (ATX) - VOE.VI": "VOE.VI", "Samsung (KR) - 005930.KS": "005930.KS",
        "TSMC (TW) - 2330.TW": "2330.TW", "Tencent (HK) - 0700.HK": "0700.HK", "Alibaba (HK) - 9988.HK": "9988.HK"
    }
    db.update(internal_db)
    return sorted(db.keys()), db

# --- UI DESIGN (Ares Anthrazit & Gold) ---
st.set_page_config(page_title="Ares Global Analyst 0.5", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; border-bottom: 2px solid #FFD700; padding-bottom: 10px; }
    h2, h3 { color: #FFD700 !important; }
    .stSelectbox div div { background-color: #2d2d2d !important; color: #FFD700 !important; border: 1px solid #FFD700 !important; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 5px; font-weight: bold; width: 100%; height: 3.5em; }
    input { background-color: #2d2d2d !important; color: white !important; border: 1px solid #FFD700 !important; }
    
    /* Metriken Styling */
    [data-testid="stMetricValue"] { color: #FFD700 !important; font-size: 1.8rem; }
    [data-testid="stMetricLabel"] { color: #ffffff !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Ares 0.5")

# --- DATEN LADEN ---
options, ticker_map = get_ares_global_database()

# --- EINGABE ---
ticker_input = st.text_input("TICKER MANUELL", placeholder="z.B. AAPL, BMW.DE...").upper()
selected_company = st.selectbox(f"SUCHE IN {len(options)} ASSETS", options=["-- Bitte wählen --"] + options)

final_ticker = ticker_map[selected_company] if selected_company != "-- Bitte wählen --" else (ticker_input if ticker_input else "")

anzahl_jahre = st.selectbox("ANALYSE-ZEITRAUM (JAHRE)", options=[1, 2, 3, 4, 5], index=4)

# --- ANALYSE & KPI BERECHNUNG ---
if final_ticker:
    try:
        with st.spinner(f'Analysiere {final_ticker}...'):
            stock = yf.Ticker(final_ticker)
            
            # Rohdaten für Berechnungen laden
            income = stock.financials
            balance = stock.balance_sheet
            
            if not income.empty and not balance.empty:
                st.subheader(f"📊 Quick-Check: {final_ticker}")
                
                # --- KPI BERECHNUNG ---
                try:
                    # 1. Net Profit Margin (Gewinnmarge)
                    net_income = income.loc['Net Income'].iloc[0]
                    total_rev = income.loc['Total Revenue'].iloc[0]
                    margin = (net_income / total_rev) * 100
                    
                    # 2. Current Ratio (Liquidität)
                    curr_assets = balance.loc['Total Current Assets'].iloc[0]
                    curr_liab = balance.loc['Total Current Liabilities'].iloc[0]
                    liquidity = curr_assets / curr_liab
                    
                    # 3. Revenue Growth (Umsatzwachstum zum Vorjahr)
                    rev_last_year = income.loc['Total Revenue'].iloc[1]
                    growth = ((total_rev - rev_last_year) / rev_last_year) * 100
                    
                    # --- DASHBOARD ANZEIGE ---
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Gewinnmarge", f"{margin:.2f}%")
                    col2.metric("Liquidität (Ratio)", f"{liquidity:.2f}")
                    col3.metric("Umsatzwachstum", f"{growth:.2f}%")
                    
                    st.write("---")
                except:
                    st.info("Einige Kennzahlen konnten für diesen Asset-Typ nicht berechnet werden.")

                # --- DOWNLOAD BEREICH ---
                # Wir nehmen nur die Jahre, die der User ausgewählt hat
                export_income = income.iloc[:, :anzahl_jahre]
                export_balance = balance.iloc[:, :anzahl_jahre]
                export_cashflow = stock.cashflow.iloc[:, :anzahl_jahre]

                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    zf.writestr(f"{final_ticker}_Bilanz.csv", export_balance.to_csv())
                    zf.writestr(f"{final_ticker}_GuV.csv", export_income.to_csv())
                    zf.writestr(f"{final_ticker}_Cashflow.csv", export_cashflow.to_csv())

                st.download_button(
                    label=f"🏆 DATEN-PAKET ({anzahl_jahre}J) HERUNTERLADEN",
                    data=zip_buffer.getvalue(),
                    file_name=f"Ares_{final_ticker}_Analysis.zip",
                    mime="application/zip"
                )
            else:
                st.warning("Keine Finanzdaten gefunden. Prüfen Sie den Ticker.")
                
    except Exception as e:
        st.error(f"Analyse nicht möglich: {e}")

st.write("---")
st.caption(f"Ares 0.5 Global Analyst")