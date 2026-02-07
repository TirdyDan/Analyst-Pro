import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io

# --- UI DESIGN (Schwarz-Weiß) ---
st.set_page_config(page_title="Analyst Pro", layout="centered")

st.markdown("""
    <style>
    .main { background-color: #ffffff; color: #000000; }
    h1, h2, h3 { color: #000000 !important; font-family: 'Helvetica Neue', Arial, sans-serif; }
    .stButton>button {
        background-color: #000000; color: #ffffff; border-radius: 0px;
        border: 1px solid #000000; width: 100%; height: 3em; font-weight: bold;
    }
    .stButton>button:hover { background-color: #ffffff; color: #000000; }
    .stTextInput>div>div>input { border-radius: 0px; border: 1px solid #000000; }
    </style>
    """, unsafe_allow_html=True)

st.title("ANALYST PRO")
st.write("---")

ticker = st.text_input("TICKER SYMBOL EINGEBEN (z.B. AAPL, MSFT, SAP.DE)", "").upper()

if ticker:
    try:
        with st.spinner('Daten werden geladen...'):
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Kennzahlen-Vorschau
            col1, col2, col3 = st.columns(3)
            col1.metric("P/E (KGV)", info.get('trailingPE', 'N/A'))
            col2.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.2f}%")
            col3.metric("DIVIDENDE", f"{info.get('dividendYield', 0)*100:.2f}%")

            # --- ZIP ERSTELLUNG (IM SPEICHER) ---
            # Wir erstellen die Dateien im Arbeitsspeicher, nicht auf der Festplatte
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                # 1. Bilanz
                if not stock.balance_sheet.empty:
                    zf.writestr(f"{ticker}_balance_sheet.csv", stock.balance_sheet.to_csv())
                
                # 2. Gewinnrechnung
                if not stock.financials.empty:
                    zf.writestr(f"{ticker}_income_statement.csv", stock.financials.to_csv())
                
                # 3. Cashflow
                if not stock.cashflow.empty:
                    zf.writestr(f"{ticker}_cashflow.csv", stock.cashflow.to_csv())
                
                # 4. Zusammenfassung (Summary TXT)
                summary_text = f"Analyse für {ticker}\n" + "-"*20 + \
                               f"\nName: {info.get('longName')}" + \
                               f"\nKGV: {info.get('trailingPE')}" + \
                               f"\nBörsenwert: {info.get('marketCap')}"
                zf.writestr(f"{ticker}_summary.txt", summary_text)

            st.write("---")
            st.success("Alle Datenfelder wurden erfolgreich generiert.")
            
            # Der Download-Button für das ZIP
            st.download_button(
                label="📥 DATEN-PAKET (ZIP) HERUNTERLADEN",
                data=zip_buffer.getvalue(),
                file_name=f"{ticker}_Financial_Data.zip",
                mime="application/zip"
            )

    except Exception as e:
        st.error(f"Fehler: {e}")

st.write("---")
st.caption("v1.2 | Local Export Edition")