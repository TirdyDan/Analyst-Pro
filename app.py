import logging
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, date
from math import floor
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go

# -----------------------------
# Logging & Config
# -----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ares_ultra")

CACHE_TTL = 60 * 30 
DEFAULT_MIN_VOL = 500_000

# -----------------------------
# Verbesserte Hilfsfunktionen
# -----------------------------
@st.cache_data(ttl=CACHE_TTL)
def get_exchange_rate(from_curr: str, to_curr: str = "EUR") -> float:
    """Holt den aktuellen Wechselkurs, um Risiko korrekt zu berechnen."""
    if from_curr == to_curr or from_curr == "N/A":
        return 1.0
    try:
        pair = f"{from_curr}{to_curr}=X"
        data = yf.Ticker(pair).history(period="1d")
        if not data.empty:
            return float(data['Close'].iloc[-1])
        return 1.0
    except:
        return 1.0

def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None: return None
        return float(x)
    except:
        return None

def get_val(df, keys):
    for k in keys:
        if k in df.index:
            val = df.loc[k].iloc[0]
            if pd.notnull(val): return val
    return None

# -----------------------------
# ARES Engine (Calculations)
# -----------------------------
def calc_atr_pct(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    if df.empty or len(df) < period: return None
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]
    return float(atr / close.iloc[-1] * 100.0)

def calc_max_drawdown(close_series: pd.Series) -> Optional[float]:
    if close_series.empty: return None
    pk = close_series.cummax()
    dd = (close_series / pk) - 1.0
    return float(abs(dd.min()) * 100.0)

# -----------------------------
# UI & Design
# -----------------------------
st.set_page_config(page_title="ARES", layout="centered")

st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Georgia', serif; }
    .stButton>button { background-color: #FFD700; color: #000; border-radius: 5px; font-weight: bold; width: 100%; }
    input { background-color: #2d2d2d !important; color: white !important; border: 1px solid #FFD700 !important; }
    [data-testid="stMetricValue"] { color: #FFD700 !important; }
    .status-card { background-color: #2d2d2d; padding: 20px; border-radius: 10px; border-left: 5px solid #FFD700; }
    </style>
    """, unsafe_allow_html=True)

st.title("ARES")

# Input Bereich
col_t, col_m = st.columns([3, 1])
with col_t:
    user_ticker = st.text_input("TICKER SYMBOL", placeholder="z.B. NVDA, SAP.DE, VOE.VI").upper()
    st.caption("Verwende zum Beispiel die Google KI Suche um Tickersymbole herauszufinden.")
with col_m:
    market = st.selectbox("Markt", ["USA", "DE", "AT", "CH", "UK", "FR", "CA"])

# Risiko Einstellungen
with st.expander("🛡️ RISIKO-PARAMETER ANPASSEN", expanded=False):
    c1, c2, c3 = st.columns(3)
    acc_size = c1.number_input("Kontogröße (EUR)", value=10000)
    risk_p = c2.number_input("Risiko pro Trade (%)", value=1.0)
    overnight = c3.checkbox("Overnight halten?", value=True)

# -----------------------------
# Hauptlogik
# -----------------------------
if user_ticker:
    suffix_map = {"USA": "", "DE": ".DE", "AT": ".VI", "CH": ".SW", "UK": ".L", "FR": ".PA", "CA": ".TO"}
    ticker = user_ticker if "." in user_ticker else f"{user_ticker}{suffix_map[market]}"
    
    try:
        with st.spinner("Analysiere Markt-Daten..."):
            stock = yf.Ticker(ticker)
            info = stock.info
            df = stock.history(period="1y")
            
            if df.empty:
                st.error("Keine Daten gefunden. Bitte Ticker prüfen.")
                st.stop()

            # --- 1. PREIS CHART (+30% Headroom) ---
            max_p = df['Close'].max()
            fig = go.Figure(go.Scatter(x=df.index, y=df['Close'], line=dict(color='#FFD700'), fill='tozeroy'))
            fig.update_yaxes(range=[df['Close'].min()*0.9, max_p*1.3])
            fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)

            # --- 2. TRAFFIC LIGHT EVALUATION ---
            atr = calc_atr_pct(df)
            mdd = calc_max_drawdown(df['Close'])
            vol_20d = df['Volume'].tail(20).mean()
            
            # Earnings Check
            earnings_date = None
            try:
                cal = stock.calendar
                if cal is not None and not cal.empty:
                    earnings_date = cal.iloc[0, 0]
            except: pass
            
            days_to_earn = (earnings_date.date() - datetime.now().date()).days if earnings_date else None
            
            # Ampel-Logik
            reasons = []
            color = "GRÜN"
            
            if days_to_earn is not None and days_to_earn <= (7 if overnight else 3):
                color = "ROT"
                reasons.append(f"⚠️ Earnings in {days_to_earn} Tagen! (Event-Risiko)")
            elif days_to_earn is None:
                reasons.append("⚪ Keine Earnings-Daten (Vorsicht geboten)")
            
            if vol_20d < DEFAULT_MIN_VOL:
                color = "ROT"
                reasons.append(f"⚠️ Geringe Liquidität (< {DEFAULT_MIN_VOL} Ø Vol)")
                
            if mdd > 45:
                if color != "ROT": color = "GELB"
                reasons.append("⚠️ Hoher historischer Drawdown (>45%)")

            # Anzeige Ampel
            if color == "ROT": st.error(f"🔴 STATUS: {color}")
            elif color == "GELB": st.warning(f"🟡 STATUS: {color}")
            else: st.success(f"🟢 STATUS: {color}")
            
            for r in reasons: st.write(r)

            # --- 3. POSITIONSGRÖSSE (MIT WÄHRUNGS-FIX) ---
            st.write("---")
            st.subheader("📏 Positionsrechner")
            
            ticker_curr = info.get("currency", "USD")
            ex_rate = get_exchange_rate(ticker_curr, "EUR") # Umrechnung von Ticker-Währung zu EUR
            
            # Wieviel EUR darf ich verlieren?
            risk_eur = acc_size * (risk_p / 100)
            # Wieviel ist das in der Aktien-Währung?
            risk_in_ticker_curr = risk_eur / ex_rate
            
            # Stop-Abstand (Default 1.5 * ATR)
            stop_dist_pct = (atr * 1.5) if atr else 5.0
            last_price = df['Close'].iloc[-1]
            stop_price = last_price * (1 - stop_dist_pct/100)
            
            shares = floor(risk_in_ticker_curr / (last_price * stop_dist_pct / 100))
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Stückzahl", f"{shares}")
            c2.metric("Risiko (€)", f"{risk_eur:.2f} €")
            c3.metric("Stop-Preis", f"{stop_price:.2f} {ticker_curr}")
            st.caption(f"Berechnet mit 1.5x ATR-Abstand ({stop_dist_pct:.2f}%) und Wechselkurs 1 {ticker_curr} = {ex_rate:.4f} EUR")

            # --- 4. FUNDAMENTAL QUICK-CHECK ---
            st.write("---")
            st.subheader("📊 Fundamental Check (Aktuellstes Jahr)")
            inc = stock.financials
            bal = stock.balance_sheet
            
            if not inc.empty and not bal.empty:
                f1, f2, f3 = st.columns(3)
                rev = get_val(inc, ['Total Revenue'])
                ni = get_val(inc, ['Net Income'])
                ebitda = get_val(inc, ['EBITDA'])
                equity = get_val(bal, ['Stockholders Equity'])
                debt = get_val(bal, ['Total Debt'])
                
                f1.metric("Gewinnmarge", f"{(ni/rev)*100:.2f}%" if rev and ni else "N/A")
                f2.metric("KGV", info.get('trailingPE', 'N/A'))
                f3.metric("EK-Rendite", f"{(ni/equity)*100:.2f}%" if ni and equity else "N/A")
            
            # --- 5. HISTORISCHE TRENDS (Clean Years) ---
            st.write("---")
            st.subheader("📉 Historische Trends")
            sel_metric = st.selectbox("Trend wählen", ["Total Revenue", "Net Income", "EBITDA"])
            if sel_metric in inc.index:
                data = inc.loc[sel_metric]
                years = [str(d.year) for d in data.index]
                fig_t = go.Figure(go.Bar(x=years, y=data.values, marker_color='#FFD700'))
                fig_t.update_layout(template="plotly_dark", height=250, xaxis=dict(type='category'))
                st.plotly_chart(fig_t, use_container_width=True)

    except Exception as e:
        st.error(f"Fehler bei der Analyse: {e}")

# Lexikon & Footer
st.write("---")
with st.expander("📘 KENNZAHLEN LEXIKON"):
    st.write("Gewinnmarge: Effizienz | KGV: Bewertung | EK-Rendite: Rentabilität | ATR: Volatilität")
st.caption("ARES 0.8 || Risk & Fundamental Integration")