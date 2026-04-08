# -*- coding: utf-8 -*-
import yfinance as yf
import requests
import os
import math
from datetime import datetime, timedelta, timezone


# ==========================================
# 1. 安全設定區
# ==========================================
CHANNEL_ID = "2009680257"
CHANNEL_SECRET = "5d823cc03726e22b534554f2ed5e8884"
USER_ID = "U50164ea486d3fe2bd2c77d8b8633b0d0"

portfolio_data = [
    {"name": "0056 元大高股息", "ticker": "0056.TW", "shares": 2000, "cost_price": 32.38, "market": "TW"},
    {"name": "2356 英業達", "ticker": "2356.TW", "shares": 34000, "cost_price": 48.82, "market": "TW"},
    {"name": "2376 技嘉", "ticker": "2376.TW", "shares": 2000, "cost_price": 294.0, "market": "TW"},
    {"name": "2881 富邦金", "ticker": "2881.TW", "shares": 3558, "cost_price": 56.16, "market": "TW"},
    {"name": "2892 第一金", "ticker": "2892.TW", "shares": 28667, "cost_price": 17.51, "market": "TW"},
    {"name": "TSLA Tesla", "ticker": "TSLA", "shares": 45, "cost_price": 330.0, "market": "US"},
    {"name": "3988 中國銀行", "ticker": "3988.HK", "shares": 156000, "cost_price": 3.232, "market": "HK"},
    {"name": "8031 三井物產", "ticker": "8031.T", "shares": 800, "cost_price": 3591.0, "market": "JP"},
]

def get_channel_access_token():
    url = "https://api.line.me/v2/oauth/accessToken"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "grant_type": "client_credentials",
        "client_id": CHANNEL_ID,
        "client_secret": CHANNEL_SECRET
    }
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None

def get_stock_summary():
    print("正在分析資產狀況與黃金價格...")
    
    # 預設值防止計算崩潰
    rates = {"US": 32.5, "HK": 4.15, "JP": 0.21, "TW": 1.0}
    gold_usd = 0.0
    gold_twd_per_mace = 0.0
    
    try:
        data = yf.download(["USDTWD=X", "HKDTWD=X", "JPYTWD=X", "GC=F"], period="5d", progress=False, timeout=15)
        if not data.empty:
            last_data = data['Close'].ffill().iloc[-1]
            # 安全取值
            if not math.isnan(last_data.get("USDTWD=X", float('nan'))): rates["US"] = float(last_data["USDTWD=X"])
            if not math.isnan(last_data.get("HKDTWD=X", float('nan'))): rates["HK"] = float(last_data["HKDTWD=X"])
            if not math.isnan(last_data.get("JPYTWD=X", float('nan'))): rates["JP"] = float(last_data["JPYTWD=X"])
            
            gold_usd_raw = last_data.get("GC=F", 0)
            if not math.isnan(gold_usd_raw):
                gold_usd = float(gold_usd_raw)
                gold_twd_per_mace = (gold_usd / 31.1035 * 3.75) * rates["US"]
    except Exception as e:
        print(f"匯率抓取失敗: {e}")

    total_cost, total_value = 0.0, 0.0
    details = ""
    
    for item in portfolio_data:
        try:
            stock = yf.Ticker(item['ticker'])
            hist = stock.history(period="5d")
            current = hist['Close'].ffill().iloc[-1] if not hist.empty else item['cost_price']
                
            rate = rates.get(item['market'], 1.0)
            c_twd = item['shares'] * item['cost_price'] * rate
            v_twd = item['shares'] * current * rate
            
            total_cost += c_twd
            total_value += v_twd
            
            roi = ((v_twd - c_twd) / c_twd) * 100 if c_twd != 0 else 0
            
            # --- 增加股價顯示 ---
            # 根據市場決定貨幣符號
            symbol = {"US": "$", "HK": "HK$", "JP": "¥", "TW": "$"}.get(item['market'], "$")
            details += f"📈 {item['name']}\n   現價: {symbol}{current:,.2f} | 損益: {roi:.1f}%\n"
            
        except Exception as e:
            print(f"處理 {item['name']} 時出錯: {e}")
            continue 

    profit_total = total_value - total_cost
    roi_total = (profit_total / total_cost) * 100 if total_cost > 0 else 0
    
    tw_tz = timezone(timedelta(hours=8))
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')

    # 安全處理金價文字
    gold_display = f"${int(gold_twd_per_mace):,}" if gold_twd_per_mace > 0 else "暫無資料"

    message = (
        f"【Fiona 資產日報】\n"
        f"📅 {current_time}\n"
        f"------------------\n"
        f"🟡 國際金價: ${gold_usd:.1f} (USD)\n"
        f"💰 台灣金價: {gold_display} (TWD/錢)\n"
        f"------------------\n"
        f"💰 總投入: ${int(total_cost):,}\n"
        f"📊 總現值: ${int(total_value):,}\n"
        f"🔥 總損益: ${int(profit_total):,} ({roi_total:.2f}%)\n"
        f"------------------\n"
        f"{details}"
    )
    return message

def push_message(token, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": USER_ID, "messages": [{"type": "text", "text": text}]}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 訊息發送成功！")

if __name__ == "__main__":
    token = get_channel_access_token()
    if token:
        msg_text = get_stock_summary()
        push_message(token, msg_text)
