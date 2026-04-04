# -*- coding: utf-8 -*-
import yfinance as yf
import requests
import os
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 安全設定區 (請填入妳的 Channel 資訊)
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

# ==========================================
# 2. 自動向 LINE 請求臨時 Token (OAuth 2.0)
# ==========================================
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
    else:
        print(f"無法取得 Token: {response.text}")
        return None

# ==========================================
# 3. 抓取數據與格式化訊息 (與之前邏輯相同)
# ==========================================
import yfinance as yf
from datetime import datetime, timezone, timedelta

def get_stock_summary():
    print("正在分析資產狀況（包含假日相容模式）...")
    
    # --- 1. 匯率抓取邏輯 (改用 5d 確保假日有資料) ---
    try:
        # 抓取 5 天內的資料，應付週末或國定連假
        fx = yf.download(["USDTWD=X", "HKDTWD=X", "JPYTWD=X"], period="5d", progress=False, timeout=15)
        if not fx.empty:
            # 使用 ffill() 填補空值，再拿最後一筆有效收盤價
            last_fx = fx['Close'].ffill().iloc[-1]
            rates = {
                "US": float(last_fx["USDTWD=X"]),
                "HK": float(last_fx["HKDTWD=X"]),
                "JP": float(last_fx["JPYTWD=X"]),
                "TW": 1.0
            }
        else:
            raise ValueError("Yahoo Finance 回傳空匯率表")
    except Exception as e:
        print(f"匯率抓取失敗 ({e})，使用預設匯率...")
        rates = {"US": 32.5, "HK": 4.15, "JP": 0.21, "TW": 1.0}
    
    total_cost, total_value = 0.0, 0.0
    details = ""
    
    # --- 2. 投資組合計算 ---
    for item in portfolio_data:
        try:
            stock = yf.Ticker(item['ticker'])
            # 關鍵修正：抓取 5d 歷史紀錄，避免股市未開盤時傳回空值
            hist = stock.history(period="5d")
            
            if not hist.empty:
                # 取得最後一個有效的收盤價
                current = hist['Close'].ffill().iloc[-1]
            else:
                # 萬一真的沒資料，先用成本價撐著，不讓程式當掉
                print(f"警告: 無法取得 {item['name']} 最新價，暫以成本計算")
                current = item['cost_price']
                
            rate = rates.get(item['market'], 1.0)
            
            c_twd = item['shares'] * item['cost_price'] * rate
            v_twd = item['shares'] * current * rate
            
            total_cost += c_twd
            total_value += v_twd
            
            # 計算該標的損益率
            roi = ((v_twd - c_twd) / c_twd) * 100 if c_twd != 0 else 0
            details += f"📈 {item['name']}: {roi:.1f}%\n"
            
        except Exception as e:
            print(f"處理 {item['name']} ({item['ticker']}) 時出錯: {e}")
            continue 

    # --- 3. 總結計算與訊息組合 ---
    profit_total = total_value - total_cost
    roi_total = (profit_total / total_cost) * 100 if total_cost > 0 else 0
    
    # 設定台灣時區
    tw_tz = timezone(timedelta(hours=8))
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')

    message = (
        f"【Fiona 資產日報】\n"
        f"📅 {current_time}\n"
        f"------------------\n"
        f"💰 總投入: ${int(total_cost):,}\n"
        f"📊 總現值: ${int(total_value):,}\n"
        f"🔥 總損益: ${int(profit_total):,} ({roi_total:.2f}%)\n"
        f"------------------\n"
        f"{details}"
    )
    return message


# ==========================================
# 4. 發送 LINE 訊息
# ==========================================
def push_message(token, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": USER_ID,
        "messages": [{"type": "text", "text": text}]
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 訊息發送成功！")
    else:
        print(f"發送失敗: {response.text}")

if __name__ == "__main__":
    # 步驟 1: 領取臨時 Token
    token = get_channel_access_token()
    if token:
        # 步驟 2: 整理數據
        msg_text = get_stock_summary()
        # 步驟 3: 發送
        push_message(token, msg_text)
