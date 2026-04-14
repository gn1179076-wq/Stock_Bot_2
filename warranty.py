# -*- coding: utf-8 -*-
import requests
import os
from datetime import datetime, timedelta, timezone

# 1. 安全設定 (請確認與 Stock_Bot 使用相同的 Secrets 名稱)
CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
USER_ID = os.getenv("LINE_USER_ID")

# 2. 家務資產清單
home_assets = [
    {"name": "客廳冷氣排水機", "purchase_date": "2026-04-13", "warranty_months": 36},
    {"name": "iPhone 17", "purchase_date": "2026-04-02", "warranty_months": 12},
    {"name": "iPhone 17 Pro Max", "purchase_date": "2026-04-02", "warranty_months": 12},
    {"name": "[耗材] 小米空氣清淨機X2 濾網", "purchase_date": "2026-03-01", "warranty_months": 6},
    {"name": "[耗材] SHARP空氣清淨機濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] blueair 濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] Samsung Tag x3 電池", "purchase_date": "2026-04-13", "warranty_months": 12},
]

def get_channel_access_token():
    # 完全複製自股票腳本的成功寫法
    url = "https://line.me"
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
        print(f"Token 失敗: {response.status_code}")
        return None

def process_data():
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    soon_list, full_list_str = [], ""

    for item in home_assets:
        p_d = datetime.strptime(item['purchase_date'], "%Y-%m-%d").replace(tzinfo=tz)
        e_d = p_d + timedelta(days=item['warranty_months'] * 30.44)
        rem = (e_d - today).days
        is_c = "[耗材]" in item['name']
        n = item['name'].replace("[耗材] ", "")
        
        if rem < 0:
            icon = "🔴" if is_c else "⚪"
        elif rem <= 90:
            icon = "⚠️"
            soon_list.append(f"🔸 {item['name']} (剩 {rem} 天)")
        else:
            icon = "✅"
            
        full_list_str += f"{icon} {n} (剩 {max(0, rem)}天)\n"

    return soon_list, full_list_str, today.strftime('%Y-%m-%d')

def push_message(token, text):
    # 完全複製自股票腳本的成功寫法
    url = "https://line.me"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": USER_ID, "messages": [{"type": "text", "text": text}]}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 訊息發送成功！")
    else:
        print(f"訊息發送失敗: {response.status_code}")

if __name__ == "__main__":
    print("🚀 啟動資產檢查任務...")
    token = get_channel_access_token()
    if token:
        soon_l, full_l, d_s = process_data()
        
        # 組合訊息
        soon_msg = "\n".join(soon_l) if soon_l else "🎉 目前狀態正常"
        msg_text = (
            f"【Fiona 家務資產報表 {d_s}】\n"
            f"------------------\n"
            f"🔥 即將到期提醒：\n{soon_msg}\n"
            f"------------------\n"
            f"📦 全清單快覽：\n{full_l}"
            f"------------------"
        )
        push_message(token, msg_text)
    else:
        print("❌ 獲取 Token 失敗，請檢查 CHANNEL_ID 或 SECRET 是否填反")
