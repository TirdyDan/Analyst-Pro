import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io

# --- UI DESIGN (Anthrazit & Gold) ---
st.set_page_config(page_title="Analyst Pro Gold", layout="centered")

st.markdown("""
    <style>
    /* Hintergrund auf Anthrazit */
    .stApp {
        background-color: #1e1e1e;
        color: #ffffff;
    }
    
    /* Hauptüberschrift in GOLD */
    h1 {
        color: #FFD700 !important;
        font-family: 'Georgia', serif;
        text-align: center;
        text-transform: uppercase;
        letter-spacing: 2px;
        border-bottom: 2px solid #FFD700;
        padding-bottom: 10px;
    }
    
    h2, h3 {
        color: #FFD700 !important;
    }

    /* Buttons Schwarz/Gold */
    .stButton>button {
        background-color: #FFD700;
        color: #000000;
        border-radius: 5px;
        border: none;
        width: 100%;
        font-weight: bold;
        height: 3.5em;
        transition: 0.3s;
    }
    .stButton>button:hover {
        background-color: #e6c200;
        color: #000000;
        box-shadow: 0px 0px 15px rgba(255, 215, 0, 0.4);
    }
    
    /* Eingabefelder */
    input {
        background-color: #2d2d2d !important;
        color: white !important;
        border: 1px solid #FFD700 !important;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("Financial Analyst Pro")
st.write("")

ticker = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. NVDA, TSLA, SAP.DE").upper()

if ticker:
    try:
        with st.spinner('Extrahiere Finanzdaten...'):
            stock = yf.Ticker(ticker)
            
            # Daten explizit abrufen (Force Download)
            balance = stock.balance_sheet
            income = stock.financials
            cashflow = stock.cashflow
            info = stock.info

            # Kurze Info-Kacheln für die App-Ansicht
            st.subheader(f"Snapshot: {info.get('longName', ticker)}")
            c1, c2, c3 = st.columns(3)
            c1.metric("KGV", info.get('trailingPE', 'N/A'))
            c2.metric("Marge", f"{info.get('operatingMargins', 0)*100:.1f}%")
            c3.metric("Preis/Buch", info.get('priceToBook', 'N/A'))

            # --- ZIP ERSTELLUNG ---
            zip_buffer = io.BytesIO()
            files_added = 0
            
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                # 1. Bilanz hinzufügen
                if not balance.empty:
                    zf.writestr(f"{ticker}_Bilanz.csv", balance.to_csv())
                    files_added += 1
                
                # 2. Gewinnrechnung hinzufügen
                if not income.empty:
                    zf.writestr(f"{ticker}_GuV.csv", income.to_csv())
                    files_added += 1
                
                # 3. Cashflow hinzufügen
                if not cashflow.empty:
                    zf.writestr(f"{ticker}_Cashflow.csv", cashflow.to_csv())
                    files_added += 1
                
                # 4. Erweiterte Summary TXT
                summary_content = f"""FINANZ-ANALYSE REPORT: {ticker}
========================================
Name: {info.get('longName')}
Sektor: {info.get('sector')}
Industrie: {info.get('industry')}

WICHTIGE KENNZAHLEN:
-------------------
KGV (Trailing): {info.get('trailingPE')}
Forward KGV: {info.get('forwardPE')}
Eigenkapitalrendite (ROE): {info.get('returnOnEquity')}
Dividendenrendite: {info.get('dividendYield', 0)*100:.2f}%
Verschuldungsgrad (D/E): {info.get('debtToEquity')}
Cashbestand: {info.get('totalCash')}
-------------------
Generiert am: {pd.Timestamp.now()}
"""
                zf.writestr(f"{ticker}_Zusammenfassung.txt", summary_content)
                files_added += 1

            if files_added > 1:
                st.write("---")
                st.success(f"Analyse abgeschlossen. {files_added} Dateien sind bereit.")
                
                # Download Button
                st.download_button(
                    label="🏆 JETZT DATEN-PAKET (ZIP) HERUNTERLADEN",
                    data=zip_buffer.getvalue(),
                    file_name=f"{ticker}_Gold_Report.zip",
                    mime="application/zip"
                )
            else:
                st.error("Yahoo Finance hat für diesen Ticker keine Tabellen-Daten geliefert. Versuche ein anderes Symbol.")

    except Exception as e:
        st.error(f"System-Fehler: {e}")

st.write("---")
st.caption("Premium Financial Tool | Version 2.0 Gold Edition")