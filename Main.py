# -*- coding: utf-8 -*-
import yfinance as yf
import requests
import os
import math
import json
import hashlib
import base64
from os import urandom
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ==========================================
# 1. 安全設定區
# ==========================================
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
REPORT_BASE_URL = "https://gn1179076-wq.github.io/Stock_Bot_2/portfolio.html"
PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到持股檔案：{PORTFOLIO_FILE}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤：{e}")
        return []

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
# 3. 抓取資料 & 產生報表
# ==========================================
def get_stock_summary(report_url_with_cache):
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
        print(f"匯率或金價抓取失敗: {e}")

    total_cost, total_value = 0.0, 0.0
    loss_details = ""
    html_rows = ""

    for item in portfolio_data:
        try:
            stock = yf.Ticker(item['ticker'])
            hist = stock.history(period="5d", timeout=30)
            current = hist['Close'].ffill().iloc[-1] if not hist.empty else item['cost_price']

            rate = rates.get(item['market'], 1.0)
            c_twd = item['shares'] * item['cost_price'] * rate
            v_twd = item['shares'] * current * rate

            total_cost += c_twd
            total_value += v_twd
            roi = ((v_twd - c_twd) / c_twd) * 100 if c_twd != 0 else 0

            symbol = {"US": "$", "HK": "HK$", "JP": "¥", "TW": "$"}.get(item['market'], "$")
            
            if roi < 0:
                loss_amt = int(v_twd - c_twd)
                loss_details += f"📉 <b>{item['name']}</b>\n <code>{symbol}{item['cost_price']:,.2f} → {symbol}{current:,.2f}</code> (<b>{roi:.1f}%</b> / {loss_amt:,})\n"

            display_name = item['name'].split(' ', 1)[-1] if ' ' in item['name'] else item['name']
            market_tag_class = {"TW": "tag-tw", "US": "tag-us", "HK": "tag-hk", "JP": "tag-jp"}.get(item['market'], "tag-tw")
            badge_class = "badge-up" if roi >= 0 else "badge-down"
            profit_amt = int(v_twd - c_twd)
            profit_color = "text-green" if profit_amt >= 0 else "text-red"

            html_rows += (
                f"<tr>"
                f"<td><div class='stock-name'>{display_name}</div><div class='stock-ticker'>{item['ticker']}</div></td>"
                f"<td><span class='market-tag {market_tag_class}'>{item['ma
