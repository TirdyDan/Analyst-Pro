import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import zipfile
import io
from math import floor
from datetime import datetime

# --- KONFIGURATION & STABILER CACHE ---
@st.cache_data(ttl=1800)
def get_clean_data(ticker):
    """Speichert nur serialisierbare Daten (DataFrames/Dicts) statt Ticker-Objekte."""
    tk = yf.Ticker(ticker)
    hist = tk.history(period="max")
    info = tk.info
    inc = tk.financials
    bal = tk.balance_sheet
    cf = tk.cashflow

    cal_date = None
    try:
        if tk.calendar is not None and not tk.calendar.empty:
            cal_date = tk.calendar.iloc[0, 0]
    except:
        pass

    return hist, info, inc, bal, cf, cal_date

@st.cache_data(ttl=3600)
def get_exchange_rate(from_curr, to_curr="EUR"):
    if from_curr == to_curr or from_curr == "N/A": return 1.0
    try:
        pair = f"{from_curr}{to_curr}=X"
        data = yf.download(pair, period="1d", progress=False)
        return float(data['Close'].iloc[-1]) if not data.empty else 1.0
    except:
        return 1.0

# --- HILFSFUNKTIONEN ---
def get_val(df, keys):
    if df is None or df.empty: return None
    for k in keys:
        if k in df.index:
            val = df.loc[k].iloc[0]
            if pd.notnull(val): return val
    return None

# --- KENNZAHLEN: BESCHREIBUNGEN + WIKIPEDIA LINKS ---
# Hinweis: Wenn es keinen/keinen stabilen deutschen Artikel gibt, verlinke ich auf den englischen Wikipedia-Artikel.
METRIC_DOCS = {
    # Kurs / Markt
    "Aktienkurs": {
        "desc": "Letzter Schlusskurs (Close) aus der Kurszeitreihe. Das ist der zuletzt verfügbare Marktpreis am Periodenende.",
        "wiki": "https://de.wikipedia.org/wiki/Aktienkurs",
    },
    "Tagesänderung": {
        "desc": "Prozentuale Veränderung gegenüber dem vorherigen Schlusskurs: (Close_t - Close_{t-1}) / Close_{t-1}.",
        "wiki": "https://de.wikipedia.org/wiki/Rendite",
    },
    "Handelsvolumen": {
        "desc": "Gehandelte Stückzahl pro Tag. Hier wird Ø Volumen der letzten 20 Handelstage als Liquiditäts-Näherung genutzt.",
        "wiki": "https://de.wikipedia.org/wiki/Handelsvolumen",
    },
    "Wechselkurs": {
        "desc": "Umrechnungskurs zwischen Währungen. Hier genutzt, um das EUR-Risikobudget in die Handelswährung zu übersetzen.",
        "wiki": "https://de.wikipedia.org/wiki/Wechselkurs",
    },

    # Events
    "Earnings": {
        "desc": "Termin/Zeitraum der Ergebnisveröffentlichung (Earnings). Kann zu erhöhten Gaps/Volatilität führen; Daten können fehlen.",
        "wiki": "https://en.wikipedia.org/wiki/Earnings",
    },

    # Risiko/Trading-Kennzahlen
    "ATR": {
        "desc": "Average True Range (ATR) misst die typische Handelsspanne (Volatilität) über einen Zeitraum (hier 14).",
        "wiki": "https://en.wikipedia.org/wiki/Average_true_range",
    },
    "Stop-Loss": {
        "desc": "Stop-Loss ist eine Order/Regel, die eine Position bei Erreichen eines Preisniveaus schließt, um Verluste zu begrenzen.",
        "wiki": "https://de.wikipedia.org/wiki/Stop-Loss-Order",
    },
    "Limit-Order": {
        "desc": "Limit-Order wird nur zu einem bestimmten Preis (oder besser) ausgeführt; reduziert Slippage-Risiko bei Illiquidität.",
        "wiki": "https://de.wikipedia.org/wiki/Limitorder",
    },
    "Risikomanagement": {
        "desc": "Methoden zur Steuerung/Begrenzung von Risiken. Hier: pro Trade wird ein fixer Prozentanteil des Kontos riskiert.",
        "wiki": "https://de.wikipedia.org/wiki/Risikomanagement",
    },
    "Positionsgröße": {
        "desc": "Position sizing: Stückzahl wird aus Risikobudget und Stop-Abstand abgeleitet (kein Buy/Sell, nur Risiko-Mechanik).",
        "wiki": "https://en.wikipedia.org/wiki/Position_sizing",
    },

    # Fundamentals
    "Gewinnmarge": {
        "desc": "Netto-Marge: Reingewinn / Umsatz. Zeigt, wie viel Gewinn pro € Umsatz übrig bleibt (perioden- und branchenabhängig).",
        "wiki": "https://de.wikipedia.org/wiki/Umsatzrendite",
    },
    "EBITDA": {
        "desc": "EBITDA = Ergebnis vor Zinsen, Steuern und Abschreibungen; Proxy für operative Ertragskraft (je nach Branche).",
        "wiki": "https://de.wikipedia.org/wiki/EBITDA",
    },
    "EBITDA-Marge": {
        "desc": "EBITDA / Umsatz. Anteil operativer Ertragskraft am Umsatz (ohne Zins/Steuer/Abschreibung).",
        "wiki": "https://de.wikipedia.org/wiki/EBITDA",
    },
    "Eigenkapitalrendite": {
        "desc": "ROE: Reingewinn / Eigenkapital. Rendite auf das eingesetzte Eigenkapital (stark durch Leverage beeinflussbar).",
        "wiki": "https://de.wikipedia.org/wiki/Eigenkapitalrentabilit%C3%A4t",
    },
    "KGV": {
        "desc": "Kurs-Gewinn-Verhältnis: Preis pro Aktie / Gewinn pro Aktie. Je höher, desto ‚teurer‘ relativ zum Gewinn (vereinfacht).",
        "wiki": "https://de.wikipedia.org/wiki/Kurs-Gewinn-Verh%C3%A4ltnis",
    },
    "Current Ratio": {
        "desc": "Current Ratio: Umlaufvermögen / kurzfristige Verbindlichkeiten. Proxy für kurzfristige Zahlungsfähigkeit.",
        "wiki": "https://en.wikipedia.org/wiki/Current_ratio",
    },
    "Verschuldungsgrad": {
        "desc": "Debt-to-Equity: Schulden / Eigenkapital. Höher = mehr Leverage (Risiko/Ertragshebel).",
        "wiki": "https://de.wikipedia.org/wiki/Verschuldungsgrad",
    },
    "Umsatz": {
        "desc": "Total Revenue: Umsatzerlöse eines Zeitraums (z. B. Jahr).",
        "wiki": "https://de.wikipedia.org/wiki/Umsatz_(Wirtschaft)",
    },
    "Reingewinn": {
        "desc": "Net Income: Periodenergebnis nach allen Aufwendungen (vereinfacht).",
        "wiki": "https://de.wikipedia.org/wiki/Jahres%C3%BCberschuss",
    },
    "Wachstum": {
        "desc": "Hier: Umsatzwachstum zwischen den letzten zwei berichteten Perioden (YoY).",
        "wiki": "https://de.wikipedia.org/wiki/Wachstum",
    },
    "KBV": {
        "desc": "Kurs-Buchwert-Verhältnis: Aktienkurs / Buchwert je Aktie. Grober Value-Indikator (bilanzabhängig).",
        "wiki": "https://de.wikipedia.org/wiki/Kurs-Buchwert-Verh%C3%A4ltnis",
    },
    "Asset Turnover": {
        "desc": "Kapitalumschlag (Asset Turnover): Umsatz / Gesamtvermögen. Effizienz der Vermögensnutzung zur Umsatzgenerierung.",
        "wiki": "https://de.wikipedia.org/wiki/Kapitalumschlag",
    },
    "Eigenkapital": {
        "desc": "Stockholders’ Equity: Bilanzposition, die den Anspruch der Eigentümer am Unternehmensvermögen abbildet (vereinfacht).",
        "wiki": "https://de.wikipedia.org/wiki/Eigenkapital",
    },
    "Operativer Cashflow": {
        "desc": "Operating Cash Flow: Cashflow aus laufender Geschäftstätigkeit (oft weniger anfällig als Gewinn, aber nicht perfekt).",
        "wiki": "https://de.wikipedia.org/wiki/Cashflow",
    },
}

def caption_with_wiki(key: str) -> str:
    d = METRIC_DOCS.get(key)
    if not d:
        return ""
    return f"{d['desc']}  ([Wikipedia]({d['wiki']}))"

# --- UI DESIGN ---
st.set_page_config(page_title="ARES", layout="centered")
st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    h1, h2, h3 { color: #FFD700 !important; font-family: 'Georgia', serif; text-align: center; }
    .stMetric { background-color: #2d2d2d; padding: 15px; border-radius: 10px; border: 1px solid #FFD700; }
    .lexikon-box { background-color: #2d2d2d; padding: 15px; border-radius: 8px; border-left: 4px solid #FFD700; margin-bottom: 10px; font-size: 0.9rem; }
    .disclaimer { font-size: 0.75rem; color: #ff4b4b; text-align: center; border: 1px solid #ff4b4b; padding: 10px; border-radius: 5px; }
    .hint { color: #888; font-size: 0.85rem; text-align: center; }
    </style>
    """, unsafe_allow_html=True)

st.title("ARES")
st.markdown(
    '<div class="disclaimer"><b>Disclaimer:</b> Nur Informationszwecke. Kein Buy/Sell. Keine Anlageberatung. '
    'Datenquellen können unvollständig/verzögert sein (yfinance).</div>',
    unsafe_allow_html=True
)

# --- EINGABE & REFRESH ---
col_in, col_ref = st.columns([4, 1])
with col_in:
    ticker_input = st.text_input("TICKER SYMBOL", placeholder="z.B. OMV.VI, NVDA, AAPL").upper()
    st.markdown('<p class="hint">Tipp: Suche Tickersymbole via Google KI Suche.</p>', unsafe_allow_html=True)

with col_ref:
    st.write(" ")
    if st.button("🔄 Update"):
        st.cache_data.clear()
        st.rerun()

# Risiko-Einstellungen
with st.expander("🛡️ KONTO- & RISIKO-SETUP", expanded=False):
    c1, c2, c3 = st.columns(3)
    acc_eur = c1.number_input("Kontogröße (EUR)", value=10000, step=500)
    risk_p = c2.number_input("Risiko pro Trade (%)", value=1.0, step=0.1)
    overnight = st.selectbox("Haltedauer", ["Nur Intraday", "Über Nacht (Overnight)"], index=1) == "Über Nacht (Overnight)"

if ticker_input:
    try:
        with st.spinner("Analysiere Daten..."):
            hist_full, info, inc, bal, cf, earn_date = get_clean_data(ticker_input)

            if hist_full.empty:
                st.error("Ticker-Daten konnten nicht geladen werden.")
                st.stop()

            # --- 1. HERO SECTION: AKTIENKURS & ZEITRAUM ---
            st.write("---")
            curr_p = hist_full['Close'].iloc[-1]
            prev_p = hist_full['Close'].iloc[-2]
            pct_ch = ((curr_p - prev_p) / prev_p) * 100
            curr_sym = info.get('currency', 'USD')

            col_hero1, col_hero2 = st.columns([1, 2])
            with col_hero1:
                st.metric(info.get('shortName', ticker_input), f"{curr_p:.2f} {curr_sym}", f"{pct_ch:.2f}%")
                st.caption("**Aktienkurs:** " + caption_with_wiki("Aktienkurs"))
                st.caption("**Tagesänderung:** " + caption_with_wiki("Tagesänderung"))

            with col_hero2:
                period = st.radio("Chart-Zeitraum", ["1T", "1W", "1M", "6M", "1J", "5J", "Max"], horizontal=True, index=4)

            # Chart Logik (skaliert)
            p_map = {"1T":"1d","1W":"5d","1M":"1mo","6M":"6mo","1J":"1y","5J":"5y","Max":"max"}
            i_map = {"1T":"5m","1W":"15m","1M":"1d","6M":"1d","1J":"1d","5J":"1wk","Max":"1mo"}

            # Sub-Select für den Chart-Zeitraum
            hist_chart = yf.download(ticker_input, period=p_map[period], interval=i_map[period], progress=False)

            fig = go.Figure(go.Scatter(x=hist_chart.index, y=hist_chart['Close'], line=dict(color='#FFD700'), fill='tozeroy', fillcolor='rgba(255, 215, 0, 0.1)'))
            fig.update_yaxes(range=[hist_chart['Close'].min()*0.95, hist_chart['Close'].max()*1.3])
            fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0,r=0,t=0,b=0), xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- 2. AMPEL (SAFETY CHECK) ---
            st.subheader("🛡️ Trade-Safety Analyse")
            vol_20d = hist_full['Volume'].tail(20).mean()
            days_to_earn = (earn_date.date() - datetime.now().date()).days if earn_date else None

            status = "GRÜN"
            reasons = []
            if days_to_earn is not None and days_to_earn <= (7 if overnight else 3):
                status = "ROT"; reasons.append(f"⚠️ **Earnings:** In {days_to_earn} Tagen. Vorsicht vor Gaps!")
            if vol_20d < 500000:
                status = "ROT"; reasons.append("⚠️ **Liquidität:** Geringes Volumen (< 500k).")

            if status == "ROT": st.error(f"🔴 KRITISCHES RISIKO: {status}")
            else: st.success(f"🟢 HANDELBAR: {status}")

            with st.expander("Warum diese Bewertung?"):
                st.write("Die Ampel schützt vor typischen Anfängerfehlern rund um Events und Liquidität. Prüfen Sie immer zusätzlich News.")
                for r in reasons: st.write(r)

                st.markdown("---")
                # Kennzahlen-Erklärungen + Wiki direkt in der Ampel-Begründung
                st.markdown("**Kennzahlen-Details (Erklärung + Wikipedia):**")
                if days_to_earn is None:
                    st.write(f"- **Earnings:** N/A → yfinance liefert nicht immer einen stabilen Earnings-Termin. {caption_with_wiki('Earnings')}")
                else:
                    st.write(f"- **Earnings in Tagen:** {days_to_earn} → Abstand bis zum (gefundenen) Earnings-Termin. {caption_with_wiki('Earnings')}")

                st.write(f"- **Ø Handelsvolumen (20T):** {vol_20d:,.0f} Stück → Proxy für Liquidität. {caption_with_wiki('Handelsvolumen')}".replace(",", "."))

            # --- 3. POSITIONSRECHNER & ERKLÄRUNG ---
            st.write("---")
            st.subheader("📏 Positionsrechner")
            ex_rate = get_exchange_rate(curr_sym, "EUR")
            risk_eur = acc_eur * (risk_p / 100)

            h, l, c = hist_full["High"].tail(100), hist_full["Low"].tail(100), hist_full["Close"].tail(100)
            tr = pd.concat([(h-l).abs(), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
            atr_val = tr.rolling(14).mean().iloc[-1]
            stop_pct = (atr_val / curr_p) * 1.5 * 100
            shares = floor((risk_eur / ex_rate) / (curr_p * stop_pct / 100))

            c_s1, c_s2, c_s3 = st.columns(3)
            c_s1.metric("Stückzahl", f"{shares}")
            c_s1.caption("**Positionsgröße:** " + caption_with_wiki("Positionsgröße"))

            c_s2.metric("Stop-Abstand", f"{stop_pct:.2f}%")
            c_s2.caption("**Stop-Loss:** " + caption_with_wiki("Stop-Loss"))
            c_s2.caption("**ATR:** " + caption_with_wiki("ATR"))

            c_s3.metric("Stop-Preis", f"{(curr_p * (1-stop_pct/100)):.2f} {curr_sym}")
            c_s3.caption("**Stop-Loss:** " + caption_with_wiki("Stop-Loss"))

            st.markdown(f"""
            <div class="lexikon-box">
            <b>Was bedeuten diese Zahlen?</b><br>
            • <b>Stückzahl:</b> Kaufen Sie maximal <b>{shares}</b> Stück, sodass Ihr rechnerisches Risiko pro Trade ≈ <b>{risk_eur:.2f} EUR</b> bleibt.<br>
            • <b>Stop-Abstand:</b> Default-Stop basiert auf Volatilität: <b>Stop-Abstand = 1,5 × ATR% (14)</b>.<br>
            • <b>Stop-Preis:</b> Bei einer Long-Position wäre das rechnerisch <b>Close × (1 − Stop%)</b>.<br>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("📌 Positionsrechner: genaue Erklärung (Formeln, Währung, Annahmen)"):
                st.markdown("**1) Risikobudget (EUR)**")
                st.write(
                    f"- Kontogröße = **{acc_eur:.2f} EUR**\n"
                    f"- Risiko pro Trade = **{risk_p:.2f}%**\n"
                    f"- Risikobudget = Kontogröße × Risiko% = **{risk_eur:.2f} EUR**  "
                    f"({caption_with_wiki('Risikomanagement')})"
                )

                st.markdown("**2) Währungsumrechnung (falls Aktie nicht in EUR notiert)**")
                st.write(
                    f"- Handelswährung laut yfinance: **{curr_sym}**\n"
                    f"- Verwendeter Wechselkurs {curr_sym}→EUR: **{ex_rate:.6f}**\n"
                    f"- Um das EUR-Risikobudget in Handelswährung zu bekommen: **Risikobudget_{curr_sym} = RisikoEUR / Wechselkurs**\n\n"
                    f"{caption_with_wiki('Wechselkurs')}"
                )

                st.markdown("**3) Volatilitätsbasierter Stop (ATR)**")
                st.write(
                    "- **True Range (TR)** pro Tag ist das Maximum aus:\n"
                    "  - |High − Low|\n"
                    "  - |High − PrevClose|\n"
                    "  - |Low − PrevClose|\n"
                    "- **ATR(14)** ist der gleitende Durchschnitt der TR über 14 Tage.\n"
                    "- In dieser App: Stop-Abstand = **1,5 × ATR** relativ zum aktuellen Kurs.\n"
                    f"- Aktueller ATR-Wert (Preis-Einheiten): **{atr_val:.6f} {curr_sym}**\n"
                    f"- Stop-Abstand% = (ATR / Close) × 1,5 × 100 = **{stop_pct:.2f}%**\n\n"
                    f"{caption_with_wiki('ATR')}"
                )

                st.markdown("**4) Stop-Abstand je Aktie (in Handelswährung)**")
                stop_dist_ccy = curr_p * (stop_pct / 100)
                st.write(
                    f"- Letzter Kurs (Close): **{curr_p:.4f} {curr_sym}**\n"
                    f"- Stop-Abstand je Aktie = Close × Stop% = **{stop_dist_ccy:.6f} {curr_sym}**\n"
                    f"{caption_with_wiki('Stop-Loss')}"
                )

                st.markdown("**5) Stückzahl (Position Size)**")
                risk_ccy = (risk_eur / ex_rate)
                st.write(
                    f"- Risikobudget in Handelswährung ≈ **{risk_ccy:.6f} {curr_sym}**\n"
                    f"- Stückzahl = floor( Risikobudget_{curr_sym} / Stop-Abstand_{curr_sym} )\n"
                    f"- Stückzahl = floor( {risk_ccy:.6f} / {stop_dist_ccy:.6f} ) = **{shares}**\n\n"
                    f"{caption_with_wiki('Positionsgröße')}"
                )

                st.markdown("**6) Stop-Preis (Long-Annahme)**")
                stop_price_calc = curr_p * (1 - stop_pct/100)
                st.write(
                    f"- Stop-Preis (Long-Logik) = Close × (1 − Stop%) = **{stop_price_calc:.4f} {curr_sym}**\n"
                    "- Hinweis: Das ist eine *rechnerische* Stop-Preis-Näherung. In der Praxis können Gaps/Slippage auftreten."
                )

                st.markdown("**Wichtige Annahmen / Grenzen**")
                st.write(
                    "- Der Rechner ist **kein Buy/Sell** und **keine Anlageberatung**.\n"
                    "- Es wird **Long-Logik** angenommen (Stop unter dem aktuellen Kurs).\n"
                    "- ATR/Volatilität ist historisch — künftige Bewegungen können abweichen.\n"
                    "- Bei illiquiden Werten können Ausführungspreise vom Stop abweichen."
                )

                st.markdown("**Weiterführende Wikipedia-Links**")
                st.markdown(
                    f"- {caption_with_wiki('ATR')}\n"
                    f"- {caption_with_wiki('Stop-Loss')}\n"
                    f"- {caption_with_wiki('Limit-Order')}\n"
                    f"- {caption_with_wiki('Risikomanagement')}\n"
                    f"- {caption_with_wiki('Positionsgröße')}\n"
                    f"- {caption_with_wiki('Wechselkurs')}"
                )

            # --- 4. FUNDAMENTAL ANALYSE (9 KPIs) ---
            st.write("---")
            st.subheader("📊 Fundamental-Analyse")
            if not inc.empty and not bal.empty:
                f1,f2,f3 = st.columns(3); f4,f5,f6 = st.columns(3); f7,f8,f9 = st.columns(3)
                rev = get_val(inc, ['Total Revenue']); ni = get_val(inc, ['Net Income'])
                ebitda = get_val(inc, ['EBITDA']); eq = get_val(bal, ['Stockholders Equity'])
                ca = get_val(bal, ['Total Current Assets']); cl = get_val(bal, ['Total Current Liabilities'])
                debt = get_val(bal, ['Total Debt']); ta = get_val(bal, ['Total Assets'])

                f1.metric("Gewinnmarge", f"{(ni/rev)*100:.2f}%" if rev and ni else "N/A")
                f1.caption(caption_with_wiki("Gewinnmarge"))

                f2.metric("EBITDA-Marge", f"{(ebitda/rev)*100:.2f}%" if rev and ebitda else "N/A")
                f2.caption(caption_with_wiki("EBITDA-Marge"))

                f3.metric("EK-Rendite", f"{(ni/eq)*100:.2f}%" if ni and eq else "N/A")
                f3.caption(caption_with_wiki("Eigenkapitalrendite"))

                f4.metric("KGV (PE)", info.get('trailingPE', 'N/A'))
                f4.caption(caption_with_wiki("KGV"))

                f5.metric("Liquidität", f"{(ca/cl):.2f}" if ca and cl else "N/A")
                f5.caption(caption_with_wiki("Current Ratio"))

                f6.metric("Verschuldung", f"{(debt/eq):.2f}" if debt and eq else "N/A")
                f6.caption(caption_with_wiki("Verschuldungsgrad"))

                growth = "N/A"
                try:
                    if len(inc.columns) > 1 and 'Total Revenue' in inc.index:
                        growth = f"{((inc.loc['Total Revenue'].iloc[0]/inc.loc['Total Revenue'].iloc[1])-1)*100:.2f}%"
                except:
                    growth = "N/A"
                f7.metric("Wachstum", growth)
                f7.caption(caption_with_wiki("Wachstum"))
                f7.caption("**Umsatz:** " + caption_with_wiki("Umsatz"))

                f8.metric("KBV (P/B)", info.get('priceToBook', 'N/A'))
                f8.caption(caption_with_wiki("KBV"))

                f9.metric("Asset Turnover", f"{(rev/ta):.2f}" if rev and ta else "N/A")
                f9.caption(caption_with_wiki("Asset Turnover"))

            # --- 5. HISTORISCHE TRENDS (VON LINKS NACH RECHTS) ---
            st.write("---")
            st.subheader("📉 Historische Trends (Chronologisch)")
            trend_options = ["Umsatz", "Reingewinn", "EBITDA", "Eigenkapital", "Operativer Cashflow"]
            sel_trend = st.selectbox("Metrik wählen:", trend_options)

            t_map = {
                "Umsatz": inc.loc['Total Revenue'] if ('Total Revenue' in inc.index) else pd.Series(dtype=float),
                "Reingewinn": inc.loc['Net Income'] if ('Net Income' in inc.index) else pd.Series(dtype=float),
                "EBITDA": inc.loc['EBITDA'] if ('EBITDA' in inc.index) else pd.Series(dtype=float),
                "Eigenkapital": bal.loc['Stockholders Equity'] if ('Stockholders Equity' in bal.index) else pd.Series(dtype=float),
                "Operativer Cashflow": cf.loc['Operating Cash Flow'] if ('Operating Cash Flow' in cf.index) else pd.Series(dtype=float)
            }

            plot_data = t_map[sel_trend][::-1]
            years = [str(d.year) for d in plot_data.index] if hasattr(plot_data.index, "__iter__") else []

            fig_t = go.Figure(go.Bar(x=years, y=plot_data.values, marker_color='#FFD700'))
            fig_t.update_layout(template="plotly_dark", height=250, xaxis=dict(type='category'))
            st.plotly_chart(fig_t, use_container_width=True)

            # Erklärung + Wiki-Link zur ausgewählten Trendmetrik
            if sel_trend == "Umsatz":
                st.caption("**Umsatz:** " + caption_with_wiki("Umsatz"))
            elif sel_trend == "Reingewinn":
                st.caption("**Reingewinn:** " + caption_with_wiki("Reingewinn"))
            elif sel_trend == "EBITDA":
                st.caption("**EBITDA:** " + caption_with_wiki("EBITDA"))
            elif sel_trend == "Eigenkapital":
                st.caption("**Eigenkapital:** " + caption_with_wiki("Eigenkapital"))
            elif sel_trend == "Operativer Cashflow":
                st.caption("**Operativer Cashflow:** " + caption_with_wiki("Operativer Cashflow"))

            # --- 6. EXPORT ---
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                zf.writestr("GuV.csv", inc.to_csv()); zf.writestr("Bilanz.csv", bal.to_csv()); zf.writestr("Cashflow.csv", cf.to_csv())
            st.download_button("🏆 KI-ANALYSE DATEN (ZIP) LADEN", zip_buffer.getvalue(), f"Ares_{ticker_input}.zip")

    except Exception as e:
        st.error(f"Fehler: {e}. Versuchen Sie es erneut.")

# --- DETAILLIERTES LEXIKON ---
st.write("---")
st.subheader("📘 Kennzahlenlexikon")
lex1, lex2 = st.columns(2)
with lex1:
    st.markdown(f"""
    <div class="lexikon-box"><b>Gewinnmarge:</b> {METRIC_DOCS['Gewinnmarge']['desc']}<br><a href="{METRIC_DOCS['Gewinnmarge']['wiki']}" target="_blank">Wikipedia</a></div>
    <div class="lexikon-box"><b>EBITDA / EBITDA-Marge:</b> {METRIC_DOCS['EBITDA']['desc']}<br><a href="{METRIC_DOCS['EBITDA']['wiki']}" target="_blank">Wikipedia</a></div>
    <div class="lexikon-box"><b>EK-Rendite (ROE):</b> {METRIC_DOCS['Eigenkapitalrendite']['desc']}<br><a href="{METRIC_DOCS['Eigenkapitalrendite']['wiki']}" target="_blank">Wikipedia</a></div>
    <div class="lexikon-box"><b>KGV:</b> {METRIC_DOCS['KGV']['desc']}<br><a href="{METRIC_DOCS['KGV']['wiki']}" target="_blank">Wikipedia</a></div>
    <div class="lexikon-box"><b>KBV:</b> {METRIC_DOCS['KBV']['desc']}<br><a href="{METRIC_DOCS['KBV']['wiki']}" target="_blank">Wikipedia</a></div>
    """, unsafe_allow_html=True)
with lex2:
    st.markdown(f"""
    <div class="lexikon-box"><b>Current Ratio (Liquidität):</b> {METRIC_DOCS['Current Ratio']['desc']}<br><a href="{METRIC_DOCS['Current Ratio']['wiki']}" target="_blank">Wikipedia</a></div>
    <div class="lexikon-box"><b>Verschuldungsgrad:</b> {METRIC_DOCS['Verschuldungsgrad']['desc']}<br><a href="{METRIC_DOCS['Verschuldungsgrad']['wiki']}" target="_blank">Wikipedia</a></div>
    <div class="lexikon-box"><b>Asset Turnover:</b> {METRIC_DOCS['Asset Turnover']['desc']}<br><a href="{METRIC_DOCS['Asset Turnover']['wiki']}" target="_blank">Wikipedia</a></div>
    <div class="lexikon-box"><b>ATR & Stop:</b> {METRIC_DOCS['ATR']['desc']}<br><a href="{METRIC_DOCS['ATR']['wiki']}" target="_blank">Wikipedia</a></div>
    <div class="lexikon-box"><b>Positionsgröße:</b> {METRIC_DOCS['Positionsgröße']['desc']}<br><a href="{METRIC_DOCS['Positionsgröße']['wiki']}" target="_blank">Wikipedia</a></div>
    """, unsafe_allow_html=True)

# WIKIPEDIA LINKS (ALLE)
st.write("---")
wiki_list = [
    f"[Aktienkurs]({METRIC_DOCS['Aktienkurs']['wiki']})",
    f"[Rendite/Tagesänderung]({METRIC_DOCS['Tagesänderung']['wiki']})",
    f"[Handelsvolumen]({METRIC_DOCS['Handelsvolumen']['wiki']})",
    f"[Wechselkurs]({METRIC_DOCS['Wechselkurs']['wiki']})",
    f"[Earnings]({METRIC_DOCS['Earnings']['wiki']})",
    f"[ATR]({METRIC_DOCS['ATR']['wiki']})",
    f"[Stop-Loss]({METRIC_DOCS['Stop-Loss']['wiki']})",
    f"[Limit-Order]({METRIC_DOCS['Limit-Order']['wiki']})",
    f"[Risikomanagement]({METRIC_DOCS['Risikomanagement']['wiki']})",
    f"[Positionsgröße]({METRIC_DOCS['Positionsgröße']['wiki']})",
    f"[Gewinnmarge]({METRIC_DOCS['Gewinnmarge']['wiki']})",
    f"[EBITDA]({METRIC_DOCS['EBITDA']['wiki']})",
    f"[Eigenkapitalrendite]({METRIC_DOCS['Eigenkapitalrendite']['wiki']})",
    f"[KGV]({METRIC_DOCS['KGV']['wiki']})",
    f"[Current Ratio]({METRIC_DOCS['Current Ratio']['wiki']})",
    f"[Verschuldungsgrad]({METRIC_DOCS['Verschuldungsgrad']['wiki']})",
    f"[Wachstum]({METRIC_DOCS['Wachstum']['wiki']})",
    f"[KBV]({METRIC_DOCS['KBV']['wiki']})",
    f"[Asset Turnover]({METRIC_DOCS['Asset Turnover']['wiki']})",
    f"[Umsatz]({METRIC_DOCS['Umsatz']['wiki']})",
    f"[Reingewinn]({METRIC_DOCS['Reingewinn']['wiki']})",
    f"[Eigenkapital]({METRIC_DOCS['Eigenkapital']['wiki']})",
    f"[Operativer Cashflow]({METRIC_DOCS['Operativer Cashflow']['wiki']})",
]
st.markdown(" • ".join(wiki_list))
st.caption("ARES 0.9.6 || Full Recovery Platform")