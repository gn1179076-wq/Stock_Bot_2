# -*- coding: utf-8 -*-
import yfinance as yf
import requests
import os
import math
import json
import hashlib
import base64
import re  
from os import urandom
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ==========================================
# 1. 設定區
# ==========================================
# --- 機密資料 (從環境變數讀取) ---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_USER_ID = os.getenv("LINE_USER_ID")

REPORT_PWD = os.getenv("REPORT_PWD")  # <--- 報表解鎖密碼

# --- 一般設定 (可以直接在這裡修改) ---
NOTIFY_TARGET = "line"  # 👉 在此修改推播目標："telegram" / "line" / "both"
REPORT_BASE_URL = "https://gn1179076-wq.github.io/Stock_Bot_2/portfolio.html"
PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到持股檔案：{PORTFOLIO_FILE}")
        return[]
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤：{e}")
        return[]

# ==========================================
# 2. Telegram 推播函式
# ==========================================
def push_tg_message(text):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("❌ 錯誤：請在 GitHub Secrets 中設定 TG_BOT_TOKEN 與 TG_CHAT_ID")
        return
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code == 200:
            print("✅ Telegram 股票日報發送成功！")
        else:
            print(f"❌ Telegram 發送失敗 ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Telegram 連線異常: {e}")

# ==========================================
# 3. LINE 推播函式 (自動取得 Token + 拔除 HTML 標籤)
# ==========================================
def push_line_message(text):
    if not LINE_CHANNEL_ID or not LINE_CHANNEL_SECRET or not LINE_USER_ID:
        print("❌ 錯誤：找不到 LINE_CHANNEL_ID, LINE_CHANNEL_SECRET 或 LINE_USER_ID 環境變數")
        return

    try:
        # 第一步：使用 Channel ID & Secret 取得暫時性的 Access Token
        oauth_url = "https://api.line.me/v2/oauth/accessToken"
        oauth_data = {
            "grant_type": "client_credentials",
            "client_id": LINE_CHANNEL_ID,
            "client_secret": LINE_CHANNEL_SECRET
        }
        token_res = requests.post(oauth_url, data=oauth_data, timeout=15)
        if token_res.status_code != 200:
            print(f"❌ LINE Token 取得失敗 ({token_res.status_code}): {token_res.text}")
            return
        
        access_token = token_res.json().get("access_token")

        # 第二步：過濾掉 HTML 標籤 (因為 LINE 不支援 Telegram 的 HTML 標籤)
        clean_text = re.sub('<.*?>', '', text)

        # 第三步：發送訊息
        push_url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "to": LINE_USER_ID,
            "messages":[{"type": "text", "text": clean_text}]
        }
        
        push_res = requests.post(push_url, headers=headers, json=payload, timeout=15)
        if push_res.status_code == 200:
            print("✅ LINE 股票日報發送成功！")
        else:
            print(f"❌ LINE 發送失敗 ({push_res.status_code}): {push_res.text}")

    except Exception as e:
        print(f"❌ LINE 連線異常: {e}")

# ==========================================
# 4. 抓取資料 & 產生報表
# ==========================================
def get_stock_summary(report_url, git_branch="unknown_branch"):
    print("正在分析資產狀況與黃金價格...")
    portfolio_data = load_portfolio()
    rates = {"US": 32.5, "HK": 4.15, "JP": 0.21, "TW": 1.0}
    gold_usd = 0.0
    gold_twd_per_mace = 0.0
    try:
        data = yf.download(["USDTWD=X", "HKDTWD=X", "JPYTWD=X", "GC=F"], period="5d", progress=False, timeout=30, threads=False)
        if not data.empty:
            last_data = data['Close'].ffill().iloc[-1]
            if not math.isnan(last_data.get("USDTWD=X", float('nan'))): rates["US"] = float(last_data["USDTWD=X"])
            if not math.isnan(last_data.get("HKDTWD=X", float('nan'))): rates["HK"] = float(last_data["HKDTWD=X"])
            if not math.isnan(last_data.get("JPYTWD=X", float('nan'))): rates["JP"] = float(last_data["JPYTWD=X"])
            gold_usd_raw = last_data.get("GC=F", 0)
            if not math.isnan(gold_usd_raw):
                gold_usd = float(gold_usd_raw)
                gold_twd_per_mace = (gold_usd / 31.1035 * 3.75) * rates["US"]
    except Exception as e:
        print(f"匯率或
