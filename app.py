import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io

# --- UI DESIGN (Anthrazit & Gold) ---
st.set_page_config(page_title="Analyst Pro", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1 {
        color: #FFD700 !important;
        font-family: 'Georgia', serif;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 2px;
        border-bottom: 2px solid #FFD700;
        padding-bottom: 10px;
    }
    h2, h3 { color: #FFD700 !important; }
    .stButton>button {
        background-color: #FFD700; color: #000000;
        border-radius: 5px; border: none; width: 100%;
        font-weight: bold; height: 3.5em;
    }
    .stButton>button:hover { background-color: #e6c200; box-shadow: 0px 0px 15px rgba(255, 215, 0, 0.4); }
    input { background-color: #2d2d2d !important; color: white !important; border: 1px solid #FFD700 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("Analyst Pro")
st.write("")

ticker = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. NVDA, MSFT, SAP.DE").upper()

if ticker:
    try:
        with st.spinner('Extrahiere reine Finanzdaten...'):
            stock = yf.Ticker(ticker)
            
            # Tabellen abrufen
            balance = stock.balance_sheet
            income = stock.financials
            cashflow = stock.cashflow
            
            # Kurze Live-Vorschau in der App (nur zur Kontrolle)
            st.subheader(f"Datenstatus für {ticker}")
            
            # --- ZIP ERSTELLUNG (Ohne TXT Datei) ---
            zip_buffer = io.BytesIO()
            files_added = 0
            
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                # 1. Bilanz
                if not balance.empty:
                    zf.writestr(f"{ticker}_Bilanz.csv", balance.to_csv())
                    files_added += 1
                
                # 2. Gewinnrechnung (Income Statement)
                if not income.empty:
                    zf.writestr(f"{ticker}_Erfolgsrechnung.csv", income.to_csv())
                    files_added += 1
                
                # 3. Cashflow
                if not cashflow.empty:
                    zf.writestr(f"{ticker}_Cashflow.csv", cashflow.to_csv())
                    files_added += 1

            if files_added > 0:
                st.success(f"✓ {files_added} Finanztabellen wurden erfolgreich generiert.")
                st.write("Lade das Paket herunter, um die Analyse in Gemini, ChatGPT oder Claude zu starten. Es wird dringend empfohlen, für die Analyse die jeweiligen Thinkingmodelle zu verweden. Zudem gilt es, jede Analyse kritisch zu betrachten und zu hinterfragen. Benutzung auf eigenen Gefahr.")
                
                # Download Button
                st.download_button(
                    label="🏆 DATEN-PAKET (ZIP) HERUNTERLADEN",
                    data=zip_buffer.getvalue(),
                    file_name=f"{ticker}_Financial_Tables.zip",
                    mime="application/zip"
                )
            else:
                st.warning("Für diesen Ticker konnten keine Tabellen gefunden werden. Bitte prüfe das Symbol.")

    except Exception as e:
        st.error(f"Fehler beim Datenabruf: {e}")

st.write("---")
st.caption("TirdyDan Tools | Pure Gold Edition")