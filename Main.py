# -*- coding: utf-8 -*-
import yfinance as yf
import requests
import os
import math
import json
import hashlib
import base64
import re  # 👈 新增正則表達式模組，用來過濾 LINE 的 HTML 標籤
from os import urandom
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ==========================================
# 1. 設定區
# ==========================================
# --- 機密資料 (從環境變數讀取) ---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")

# 改用 LINE Messaging API 官方建議的 ID 和 SECRET
LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_USER_ID = os.getenv("LINE_USER_ID")

REPORT_PWD = os.getenv("REPORT_PWD")  # <--- 報表解鎖密碼

# --- 一般設定 (可以直接在這裡修改) ---
NOTIFY_TARGET = "both"  # 👉 在此修改推播目標："telegram" / "line" / "both"
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
        print(f"匯率或金價抓取失敗: {e}")

    DEFAULT_RATES = {"US": 32.5, "HK": 4.15, "JP": 0.21, "TW": 1.0}
    for k, v in DEFAULT_RATES.items():
        r = rates.get(k)
        if r is None or (isinstance(r, float) and (r == 0 or math.isnan(r))):
            rates[k] = v

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
                loss_details += f"📉 <b>{item['name']}</b>\n  <code>{symbol}{item['cost_price']:,.2f} → {symbol}{current:,.2f}</code> (<b>{roi:.1f}%</b> / {loss_amt:,})\n"
            display_name = item['name'].split(' ', 1)[-1] if ' ' in item['name'] else item['name']
            market_tag_class = {"TW": "tag-tw", "US": "tag-us", "HK": "tag-hk", "JP": "tag-jp"}.get(item['market'], "tag-tw")
            badge_class = "badge-up" if roi >= 0 else "badge-down"
            profit_amt = int(v_twd - c_twd)
            profit_color = "text-green" if profit_amt >= 0 else "text-red"
            html_rows += (
                "<tr>"
                f"<td><div class='stock-name'>{display_name}</div><div class='stock-ticker'>{item['ticker']}</div></td>"
                f"<td><span class='market-tag {market_tag_class}'>{item['market']}</span></td>"
                f"<td class='right mono'>{item['shares']:,}</td>"
                f"<td class='right mono'>{symbol}{item['cost_price']:,.2f}</td>"
                f"<td class='right mono'>{symbol}{current:,.2f}</td>"
                f"<td class='right mono'>${int(v_twd):,}</td>"
                f"<td class='right mono {profit_color}'>{profit_amt:+,}</td>"
                f"<td class='right'><span class='badge {badge_class}'>{roi:+.1f}%</span></td>"
                "</tr>"
            )
        except Exception as e:
            print(f"處理出錯: {e}")
            continue

    profit_total = total_value - total_cost
    roi_total = (profit_total / total_cost) * 100 if total_cost > 0 else 0
    total_icon = "🔴" if profit_total >= 0 else "🟢"
    tw_tz = timezone(timedelta(hours=8))
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M')
    gold_display = f"${int(gold_twd_per_mace):,}" if gold_twd_per_mace > 0 else "暫無資料"
    jp_rate = rates.get('JP', 0)
    jpy_per_twd = (1 / jp_rate) if jp_rate else 0

    tg_msg = (
        f"<b>📊 Fiona 持股資產日報 ({git_branch})</b>\n"
        f"📅 {current_time}\n"
        f"--------------------------\n"
        f"🟡 國際金價: <code>${gold_usd:.1f}</code>\n"
        f"💰 台灣金價: <code>{gold_display}</code> (錢)\n"
        f"💱 美元匯率: <code>{rates['US']:.2f}</code>\n"
        f"💴 日圓匯率: 1 TWD = <code>{jpy_per_twd:.2f}</code> JPY\n"
        f"----------------
