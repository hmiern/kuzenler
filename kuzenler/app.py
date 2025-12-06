# app.py
import pandas as pd
import pandas_ta as ta
import streamlit as st
import time
import json
from websocket import create_connection
import plotly.graph_objects as go
from datetime import datetime
import threading
import ccxt

st.set_page_config(page_title="Hami Sinyal Canlı Dashboard", layout="wide")
st.title("Hami Sinyal Canlı Web Dashboard")

coins = ["BTC/USDT","ETH/USDT","EIGEN/USDT","ETHFI/USDT","TIA/USDT"]
table_placeholder = st.empty()
notif_placeholder = st.empty()
grafik_placeholder = st.empty()
log_placeholder = st.empty()

onceki_sinyaller = {}
log_df = pd.DataFrame(columns=["Coin","Sinyal","RSI","Fiyat","Zaman"])

# Tarayıcı bildirim JS fonksiyonu
def send_browser_notification(title, message):
    st.components.v1.html(f"""
        <script>
        if (Notification.permission !== "granted")
            Notification.requestPermission();
        else {{
            new Notification("{title}", {{
                body: "{message}",
                icon: "https://cdn-icons-png.flaticon.com/512/833/833524.png"
            }});
        }}
        </script>
    """, height=0, width=0)

# Coin verilerini CCXT ile al ve teknik göstergeleri hesapla
def hesapla_goster(symbol):
    exchange = ccxt.binance()
    try:
        bars = exchange.fetch_ohlcv(symbol, timeframe="15m", limit=200)
        df = pd.DataFrame(bars, columns=["time","open","high","low","close","volume"])
        df["RSI"] = ta.rsi(df["close"], length=14)
        macd = ta.macd(df["close"])
        df["MACD"] = macd["MACD_12_26_9"]
        df["SIGNAL"] = macd["MACDs_12_26_9"]
        bb = ta.bbands(df["close"], length=20, std=2)
        df["BBU"] = bb["BBU_20_2.0"]
        df["BBL"] = bb["BBL_20_2.0"]

        last = df.iloc[-1]
        rsi = last["RSI"]
        macd_val = last["MACD"]
        sig_val = last["SIGNAL"]
        price = last["close"]

        signal = "Nötr"
        if rsi < 35 and macd_val > sig_val and price <= last["BBL"] * 1.01:
            signal = "KESİN AL 🚀"
        elif rsi > 65 and macd_val < sig_val and price >= last["BBU"] * 0.99:
            signal = "KESİN SAT 🔻"
        elif rsi < 40:
            signal = "Olası Yükseliş ↗"
        elif rsi > 60:
            signal = "Olası Düşüş ↘"

        return {"Coin": symbol, "Sinyal": signal, "RSI": round(rsi,1), "Fiyat": price, "df": df}
    except Exception as e:
        return {"Coin": symbol, "Sinyal": f"Hata: {e}", "RSI": None, "Fiyat": None, "df": None}

# Filtre seçeneği
filtre_secim = st.selectbox("Filtrele:", ["Tümü", "KESİN AL / SAT"])

# Arka planda veri çekme fonksiyonu
def veri_guncelle():
    global log_df
    while True:
        results = []
        for coin in coins:
            sonuc = hesapla_goster(coin)
            results.append({k:v for k,v in sonuc.items() if k!="df"})

            # Bildirim
            onceki = onceki_sinyaller.get(coin)
            if sonuc["Sinyal"] != "Nötr" and sonuc["Sinyal"] != onceki:
                send_browser_notification(coin, sonuc["Sinyal"])
            onceki_sinyaller[coin] = sonuc["Sinyal"]

            # Log
            if sonuc["Sinyal"] != "Nötr":
                log_df = pd.concat([log_df, pd.DataFrame([{
                    "Coin":coin,
                    "Sinyal":sonuc["Sinyal"],
                    "RSI":sonuc["RSI"],
                    "Fiyat":sonuc["Fiyat"],
                    "Zaman":datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])], ignore_index=True)

            # Grafik
            df_plot = sonuc["df"]
            if df_plot is not None:
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=df_plot['time'], open=df_plot['open'], high=df_plot['high'],
                    low=df_plot['low'], close=df_plot['close'], name=coin
                ))
                fig.add_trace(go.Scatter(x=df_plot['time'], y=df_plot['RSI'], mode='lines', name='RSI', line=dict(color='orange')))
                grafik_placeholder.plotly_chart(fig, use_container_width=True)

        # DataFrame ve filtreleme
        df_results = pd.DataFrame(results)
        if filtre_secim == "KESİN AL / SAT":
            df_results = df_results[df_results["Sinyal"].str.contains("AL|SAT")]

        # Renkli stil
        def renk_stili(val):
            if "AL" in str(val):
                return 'background-color: #00ff00; color: black; font-weight: bold;'
            elif "SAT" in str(val):
                return 'background-color: #ff4d4d; color: white; font-weight: bold;'
            elif "Yükseliş" in str(val):
                return 'background-color: #99ff99; color: black;'
            elif "Düşüş" in str(val):
                return 'background-color: #ff9999; color: black;'
            else:
                return ''

        table_placeholder.write(df_results.style.applymap(renk_stili, subset=["Sinyal"]))
        log_placeholder.dataframe(log_df)
        st.info("Son güncelleme: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        time.sleep(20)

# Arka planda threading ile başlat
threading.Thread(target=veri_guncelle, daemon=True).start()
