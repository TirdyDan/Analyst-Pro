import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io

# --- UI DESIGN (Anthrazit & Gold) ---
st.set_page_config(page_title="Analyst Version: Ares", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; border-bottom: 2px solid #FFD700; padding-bottom: 10px; }
    h2, h3 { color: #FFD700 !important; }
    
    /* Style für das Dropdown (Selectbox) */
    .stSelectbox div div {
        background-color: #2d2d2d !important;
        color: #FFD700 !important;
        border: 1px solid #FFD700 !important;
    }
    
    .stButton>button {
        background-color: #FFD700; color: #000000;
        border-radius: 5px; border: none; width: 100%;
        font-weight: bold; height: 3.5em;
    }
    .stButton>button:hover { background-color: #e6c200; box-shadow: 0px 0px 15px rgba(255, 215, 0, 0.4); }
    
    input { background-color: #2d2d2d !important; color: white !important; border: 1px solid #FFD700 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Analyst by TirdyDan")

# --- EINGABE-BEREICH ---
ticker = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. MSFT, SAP.DE, 6762.T").upper()

# Das neue Dropdown-Menü
anzahl_jahre = st.selectbox(
    "ANALYSE-ZEITRAUM (JAHRE ZURÜCK)",
    options=[1, 2, 3, 4, 5],
    index=4  # Standardmäßig auf 5 Jahre eingestellt
)

if ticker:
    try:
        with st.spinner(f'Extrahiere Daten der letzten {anzahl_jahre} Jahre...'):
            stock = yf.Ticker(ticker)
            
            # Daten abrufen
            # .iloc[:, :anzahl_jahre] nimmt die ersten X Spalten (die neuesten Jahre)
            balance = stock.balance_sheet.iloc[:, :anzahl_jahre]
            income = stock.financials.iloc[:, :anzahl_jahre]
            cashflow = stock.cashflow.iloc[:, :anzahl_jahre]
            
            st.subheader(f"Status: {ticker} | Zeitraum: {anzahl_jahre} Jahr(e)")
            
            # --- ZIP ERSTELLUNG ---
            zip_buffer = io.BytesIO()
            files_added = 0
            
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                if not balance.empty:
                    zf.writestr(f"{ticker}_Bilanz_{anzahl_jahre}J.csv", balance.to_csv())
                    files_added += 1
                if not income.empty:
                    zf.writestr(f"{ticker}_GuV_{anzahl_jahre}J.csv", income.to_csv())
                    files_added += 1
                if not cashflow.empty:
                    zf.writestr(f"{ticker}_Cashflow_{anzahl_jahre}J.csv", cashflow.to_csv())
                    files_added += 1

            if files_added > 0:
                st.success(f"✓ {files_added} Tabellen für {anzahl_jahre} Jahre generiert.")
                
                st.download_button(
                    label=f"🏆 DATEN-PAKET ({anzahl_jahre} JAHRE) LADEN",
                    data=zip_buffer.getvalue(),
                    file_name=f"{ticker}_{anzahl_jahre}Y_Analysis.zip",
                    mime="application/zip"
                )
            else:
                st.warning("Keine historischen Tabellen gefunden. (Krypto/Gold haben oft keine Bilanzen)")

    except Exception as e:
        st.error(f"Fehler: {e}")

st.write("---")
st.caption(f"Free Version Ares || Ares is developed by TirdyDan")