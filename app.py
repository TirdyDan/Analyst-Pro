import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io
import requests

# --- STABILE GLOBAL-DATEN FUNKTION (GITHUB RAW CSVs) ---
@st.cache_data(ttl=86400)
def get_ares_global_database():
    all_tickers = {}
    
    # Liste der stabilen GitHub-Quellen
    sources = [
        {
            "name": "S&P 500 (USA)",
            "url": "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv",
            "symbol_col": "Symbol", "name_col": "Name", "suffix": ""
        },
        {
            "name": "STOXX 600 (Europa)",
            "url": "https://raw.githubusercontent.com/pmo-financial-analysis/stoxx600/main/stoxx600_constituents.csv",
            "symbol_col": "Ticker", "name_col": "Name", "suffix": "" # Suffixe sind hier meist schon drin
        },
        {
            "name": "DAX (Deutschland)",
            "url": "https://raw.githubusercontent.com/datasets/dax-queries/master/data/dax-constituents.csv",
            "symbol_col": "Symbol", "name_col": "Name", "suffix": ".DE"
        },
        {
            "name": "Nikkei 225 (Japan)",
            "url": "https://raw.githubusercontent.com/datasets/nikkei-225/master/data/constituents.csv",
            "symbol_col": "Symbol", "name_col": "Name", "suffix": ".T"
        }
    ]

    for source in sources:
        try:
            df = pd.read_csv(source["url"])
            for _, row in df.iterrows():
                raw_sym = str(row[source["symbol_col"]])
                # Yahoo Suffix Logik
                clean_sym = raw_sym if ("." in raw_sym or source["suffix"] == "") else f"{raw_sym}{source['suffix']}"
                
                # Anzeige-Format: "Name (Index) - Ticker"
                display_name = f"{row[source['name_col']]} ({source['name']}) - {clean_sym}"
                all_tickers[display_name] = clean_sym
        except:
            continue # Falls eine Quelle offline ist, laden die anderen weiter

    # WICHTIG: Manueller "Global Giants" Core als Sicherheitsnetz (Asien Power)
    core_giants = {
        "Samsung Electronics (KR) - 005930.KS": "005930.KS",
        "TSMC (TW) - 2330.TW": "2330.TW",
        "Tencent (HK) - 0700.HK": "0700.HK",
        "Alibaba (HK) - 9988.HK": "9988.HK",
        "Hyundai (KR) - 005380.KS": "005380.KS",
        "voestalpine (AT) - VOE.VI": "VOE.VI",
        "Erste Group (AT) - EBS.VI": "EBS.VI",
        "OMV (AT) - OMV.VI": "OMV.VI"
    }
    all_tickers.update(core_giants)
    
    return sorted(all_tickers.keys()), all_tickers

# --- UI DESIGN (Ares Anthrazit & Gold) ---
st.set_page_config(page_title="Ares Global Analyst", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; border-bottom: 2px solid #FFD700; padding-bottom: 10px; }
    div[data-baseweb="select"] > div { background-color: #2d2d2d !important; color: #FFD700 !important; border: 1px solid #FFD700 !important; }
    .stButton>button { background-color: #FFD700; color: #000000; border-radius: 5px; font-weight: bold; width: 100%; height: 3.5em; }
    input { background-color: #2d2d2d !important; color: white !important; border: 1px solid #FFD700 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Ares Global")

# --- DATEN LADEN ---
with st.spinner("Lade globale Marktdaten (GitHub Stable)..."):
    display_list, ticker_map = get_ares_global_database()

# --- EINGABE-BEREICH ---
ticker_input = st.text_input("MANUELLER TICKER", placeholder="z.B. MSFT, SAP.DE...").upper()

selected_from_list = st.selectbox(
    "GLOBALE SUCHE (S&P500, STOXX600, DAX, ASIEN)",
    options=["-- Bitte wählen / Suche starten --"] + display_list
)

final_ticker = ""
if selected_from_list != "-- Bitte wählen / Suche starten --":
    final_ticker = ticker_map[selected_from_list]
elif ticker_input:
    final_ticker = ticker_input

anzahl_jahre = st.selectbox("ZEITRAUM (JAHRE)", options=[1, 2, 3, 4, 5], index=4)

# --- VERARBEITUNG ---
if final_ticker:
    try:
        with st.spinner(f'Extrahiere Fundamentaldaten für {final_ticker}...'):
            stock = yf.Ticker(final_ticker)
            
            # Yahoo Finance Abfrage
            balance = stock.balance_sheet.iloc[:, :anzahl_jahre]
            income = stock.financials.iloc[:, :anzahl_jahre]
            cashflow = stock.cashflow.iloc[:, :anzahl_jahre]
            
            if balance.empty and income.empty:
                st.warning(f"Keine Daten für {final_ticker} gefunden. Prüfen Sie ggf. das Suffix.")
            else:
                st.subheader(f"Analyse: {final_ticker}")
                
                zip_buffer = io.BytesIO()
                files_added = 0
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    if not balance.empty:
                        zf.writestr(f"{final_ticker}_Bilanz.csv", balance.to_csv())
                        files_added += 1
                    if not income.empty:
                        zf.writestr(f"{final_ticker}_GuV.csv", income.to_csv())
                        files_added += 1
                    if not cashflow.empty:
                        zf.writestr(f"{final_ticker}_Cashflow.csv", cashflow.to_csv())
                        files_added += 1

                if files_added > 0:
                    st.success(f"✓ {files_added} Tabellen erfolgreich generiert.")
                    st.download_button(
                        label=f"🏆 DOWNLOAD: {final_ticker} PAKET",
                        data=zip_buffer.getvalue(),
                        file_name=f"Ares_{final_ticker}_Data.zip",
                        mime="application/zip"
                    )
    except Exception as e:
        st.error(f"Fehler: {e}")

st.write("---")
st.caption("Ares 0.3 Big Markets || Ares by TirdyDan")