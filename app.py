import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io
import requests

# --- DATEN-FUNKTION (S&P 500 Liste von stabilen Quellen laden) ---
@st.cache_data(ttl=86400) # Cache für 24 Stunden
def get_sp500_tickers():
    # Primäre Quelle: GitHub (sehr stabil für CSV-Daten)
    urls = [
        "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/master/data/constituents.csv",
        "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
    ]
    
    for url in urls:
        try:
            df = pd.read_csv(url)
            # Spaltennamen normalisieren (manche Quellen nutzen 'Name', andere 'Security')
            name_col = 'Security' if 'Security' in df.columns else 'Name'
            
            # Format: Firmenname - Ticker
            df['Display'] = df[name_col] + " - " + df['Symbol']
            
            list_sorted = sorted(df['Display'].tolist())
            ticker_map = dict(zip(df['Display'], df['Symbol']))
            return list_sorted, ticker_map
        except Exception:
            continue
            
    # Letzter Fallback: Wikipedia mit Browser-Simulation
    try:
        url_wiki = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url_wiki, headers=headers, timeout=5)
        df_wiki = pd.read_html(response.text)[0]
        df_wiki['Display'] = df_wiki['Security'] + " - " + df_wiki['Symbol']
        return sorted(df_wiki['Display'].tolist()), dict(zip(df_wiki['Display'], df_wiki['Symbol']))
    except:
        return [], {}

# --- UI DESIGN (Anthrazit & Gold) ---
st.set_page_config(page_title="Ares Analyst", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; border-bottom: 2px solid #FFD700; padding-bottom: 10px; }
    h2, h3 { color: #FFD700 !important; }
    
    /* Style für das Dropdown */
    div[data-baseweb="select"] > div {
        background-color: #2d2d2d !important;
        color: #FFD700 !important;
        border: 1px solid #FFD700 !important;
    }
    
    /* Farbe der Suchergebnisse im Dropdown */
    div[data-baseweb="popover"] ul {
        background-color: #2d2d2d !important;
        color: #FFD700 !important;
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

st.title("Ares")

# --- DATEN LADEN ---
with st.spinner("Lade S&P 500 Liste..."):
    sp500_options, sp500_map = get_sp500_tickers()

# --- EINGABE-BEREICH ---
ticker_input = st.text_input("1. TICKER MANUELL (z.B. AAPL oder SAP.DE)", placeholder="Eingeben...").upper()

# S&P 500 SUCHE
if sp500_options:
    selected_company = st.selectbox(
        "2. S&P 500 SUCHE (Tippe hier den Firmennamen ein)",
        options=["-- Bitte wählen / Suche nutzen --"] + sp500_options,
        index=0,
        help="Hier klicken und einfach den Namen (z.B. Microsoft) tippen."
    )
else:
    st.error("S&P 500 Liste konnte nicht geladen werden. Bitte manuell eingeben.")
    selected_company = "-- Bitte wählen / Suche nutzen --"

# Ticker-Logik
final_ticker = ""
if selected_company != "-- Bitte wählen / Suche nutzen --":
    final_ticker = sp500_map[selected_company]
elif ticker_input:
    final_ticker = ticker_input

anzahl_jahre = st.selectbox(
    "3. ANALYSE-ZEITRAUM (JAHRE)",
    options=[1, 2, 3, 4, 5],
    index=4
)

# --- VERARBEITUNG ---
if final_ticker:
    try:
        with st.spinner(f'Analysiere {final_ticker}...'):
            stock = yf.Ticker(final_ticker)
            
            # Daten abrufen
            balance = stock.balance_sheet.iloc[:, :anzahl_jahre]
            income = stock.financials.iloc[:, :anzahl_jahre]
            cashflow = stock.cashflow.iloc[:, :anzahl_jahre]
            
            if balance.empty and income.empty:
                st.warning(f"Keine Finanzdaten für '{final_ticker}' gefunden.")
            else:
                st.subheader(f"Status: {final_ticker}")
                
                # ZIP erstellen
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
                    st.success(f"✓ {files_added} Tabellen erstellt.")
                    st.download_button(
                        label=f"🏆 DATEN-PAKET FÜR {final_ticker} LADEN",
                        data=zip_buffer.getvalue(),
                        file_name=f"{final_ticker}_Analyse.zip",
                        mime="application/zip"
                    )
    except Exception as e:
        st.error(f"Fehler: {e}")

st.write("---")
st.caption("Ares 0.1 || Ares by TirdyDan")