import streamlit as st
import yfinance as yf
import pandas as pd
import zipfile
import io

# --- DATEN-FUNKTION (S&P 500 Liste laden) ---
@st.cache_data
def get_sp500_tickers():
    try:
        # Lade die S&P 500 Tabelle von Wikipedia
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        table = pd.read_html(url)
        df = table[0]
        
        # Erstelle die Liste im Format "Firmenname - Ticker Symbol"
        df['Display'] = df['Security'] + " - " + df['Symbol']
        
        # Alphabetisch nach Firmenname sortieren
        list_sorted = sorted(df['Display'].tolist())
        
        # Map erstellen, um vom Namen wieder auf den Ticker zu kommen
        ticker_map = dict(zip(df['Display'], df['Symbol']))
        
        return list_sorted, ticker_map
    except Exception as e:
        return [], {}

# --- UI DESIGN (Anthrazit & Gold) ---
st.set_page_config(page_title="Ares Analyst", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; border-bottom: 2px solid #FFD700; padding-bottom: 10px; }
    h2, h3 { color: #FFD700 !important; }
    
    /* Style für das Dropdown (Selectbox) */
    div[data-baseweb="select"] > div {
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

st.title("Ares")

# --- DATEN LADEN ---
sp500_list, sp500_map = get_sp500_tickers()

# --- EINGABE-BEREICH ---
ticker_input = st.text_input("TICKER SYMBOL EINGEBEN", placeholder="z.B. MSFT, SAP.DE, 6762.T").upper()

# S&P 500 HILFE DROPDOWN
selected_from_list = st.selectbox(
    "ODER AUS S&P 500 LISTE WÄHLEN (HILFE)",
    options=["-- Bitte wählen --"] + sp500_list,
    index=0
)

# Logik: Welcher Ticker soll verwendet werden?
# Wenn etwas in der Liste gewählt wurde (und es nicht der Platzhalter ist), nimm das.
# Sonst nimm die manuelle Eingabe.
final_ticker = ticker_input
if selected_from_list != "-- Bitte wählen --":
    final_ticker = sp500_map[selected_from_list]

anzahl_jahre = st.selectbox(
    "ANALYSE-ZEITRAUM (JAHRE ZURÜCK)",
    options=[1, 2, 3, 4, 5],
    index=4  # Standardmäßig auf 5 Jahre eingestellt
)

if final_ticker:
    try:
        with st.spinner(f'Extrahiere Daten für {final_ticker} der letzten {anzahl_jahre} Jahre...'):
            stock = yf.Ticker(final_ticker)
            
            # Daten abrufen
            balance = stock.balance_sheet.iloc[:, :anzahl_jahre]
            income = stock.financials.iloc[:, :anzahl_jahre]
            cashflow = stock.cashflow.iloc[:, :anzahl_jahre]
            
            if balance.empty and income.empty and cashflow.empty:
                st.warning(f"Keine Daten für '{final_ticker}' gefunden. (Evtl. Ticker-Symbol prüfen)")
            else:
                st.subheader(f"Status: {final_ticker} | Zeitraum: {anzahl_jahre} Jahr(e)")
                
                # --- ZIP ERSTELLUNG ---
                zip_buffer = io.BytesIO()
                files_added = 0
                
                with zipfile.ZipFile(zip_buffer, "w") as zf:
                    if not balance.empty:
                        zf.writestr(f"{final_ticker}_Bilanz_{anzahl_jahre}J.csv", balance.to_csv())
                        files_added += 1
                    if not income.empty:
                        zf.writestr(f"{final_ticker}_GuV_{anzahl_jahre}J.csv", income.to_csv())
                        files_added += 1
                    if not cashflow.empty:
                        zf.writestr(f"{final_ticker}_Cashflow_{anzahl_jahre}J.csv", cashflow.to_csv())
                        files_added += 1

                if files_added > 0:
                    st.success(f"✓ {files_added} Tabellen für {anzahl_jahre} Jahre generiert.")
                    
                    st.download_button(
                        label=f"🏆 DATEN-PAKET ({anzahl_jahre} JAHRE) LADEN",
                        data=zip_buffer.getvalue(),
                        file_name=f"{final_ticker}_{anzahl_jahre}Y_Analysis.zip",
                        mime="application/zip"
                    )

    except Exception as e:
        st.error(f"Fehler: {e}")

st.write("---")
st.caption(f" Ares 0.1 || Ares by TirdyDan")