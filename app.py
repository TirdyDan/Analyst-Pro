import streamlit as st
import yfinance as yf
import pandas as pd
import os
from datetime import datetime

# --- UI DESIGN (Schwarz-Weiß) ---
st.set_page_config(page_title="Analyst Pro", layout="centered")

st.markdown("""
    <style>
    /* Hintergrund und Textfarben */
    .main { background-color: #ffffff; color: #000000; }
    h1, h2, h3 { color: #000000 !important; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    
    /* Buttons schwarz weiß */
    .stButton>button {
        background-color: #000000;
        color: #ffffff;
        border-radius: 0px;
        border: 1px solid #000000;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #ffffff;
        color: #000000;
    }
    
    /* Input Felder */
    .stTextInput>div>div>input {
        border-radius: 0px;
        border: 1px solid #000000;
    }
    </style>
    """, unsafe_allow_html=True)

# --- APP LOGIK ---
st.title("FINANCIAL ANALYST PRO")
st.write("---")

# Eingabemaske
col1, col2 = st.columns(2)
with col1:
    ticker = st.text_input("TICKER SYMBOL", placeholder="z.B. AAPL").upper()
with col2:
    # Standardmäßig der aktuelle Ordner
    save_path = st.text_input("SPEICHERORT (PFAD)", value=os.getcwd())

# Auswahl der Datenfelder
st.subheader("NOTWENDIGE DATENFELDER")
include_balance = st.checkbox("Bilanz (Balance Sheet)", value=True)
include_income = st.checkbox("Gewinnrechnung (Income Statement)", value=True)
include_cashflow = st.checkbox("Cashflow-Rechnung", value=True)
include_ratios = st.checkbox("Wichtige Kennzahlen (KGV, ROE, etc.)", value=True)

if st.button("DATEN EXTRAHIEREN & SPEICHERN"):
    if ticker:
        try:
            with st.spinner('Verarbeite...'):
                stock = yf.Ticker(ticker)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M")
                folder_name = os.path.join(save_path, f"{ticker}_{timestamp}")
                
                # Ordner erstellen
                if not os.path.exists(folder_name):
                    os.makedirs(folder_name)
                
                # Daten sammeln und speichern
                results = []
                if include_balance:
                    stock.balance_sheet.to_csv(f"{folder_name}/balance_sheet.csv")
                    results.append("Bilanz")
                if include_income:
                    stock.financials.to_csv(f"{folder_name}/income.csv")
                    results.append("Gewinnrechnung")
                if include_cashflow:
                    stock.cashflow.to_csv(f"{folder_name}/cashflow.csv")
                    results.append("Cashflow")
                
                if include_ratios:
                    info = stock.info
                    with open(f"{folder_name}/ratios.txt", "w") as f:
                        f.write(f"KGV: {info.get('trailingPE')}\nROE: {info.get('returnOnEquity')}\nYield: {info.get('dividendYield')}")
                    results.append("Kennzahlen")

                st.success(f"ERFOLG: {', '.join(results)} gespeichert in:")
                st.code(folder_name)
        except Exception as e:
            st.error(f"FEHLER: {str(e)}")
    else:
        st.warning("BITTE TICKER EINGEBEN")

st.write("---")
st.caption("Minimalist Analysis Tool v1.0 | Black & White Edition")