# -*- coding: utf-8 -*-
import requests
import os
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 安全設定區 (透過 GitHub Secrets 讀取)
# ==========================================
CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
USER_ID = os.getenv("LINE_USER_ID")

# ==========================================
# 2. 家電與耗材清單
# ==========================================
home_assets = [
    {"name": "客廳冷氣排水機", "purchase_date": "2026-04-13", "warranty_months": 36},
    {"name": "[耗材] 小米空氣清淨機X2 濾網", "purchase_date": "2026-03-01", "warranty_months": 6},
    {"name": "[耗材] SHARP空氣清淨機濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] blueair 濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] Samsung Tag x3 電池", "purchase_date": "2026-04-13", "warranty_months": 12},
]

# ==========================================
# 3. 核心處理功能
# ==========================================
def get_channel_access_token():
    """獲取 LINE Channel Access Token"""
    url = "https://line.me"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CHANNEL_ID,
        "client_secret": CHANNEL_SECRET
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except Exception as e:
        print(f"Token 獲取失敗: {e}")
        return None

def process_and_report():
    """處理保固邏輯並產生回報內容"""
    # 設定台灣時區
    tw_tz = timezone(timedelta(hours=8))
    today = datetime.now(tw_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    
    expiring_soon = []
    already_expired_count = 0
    line_details = ""
    html_rows = ""

    for item in home_assets:
        # 解析購買日期
        p_date = datetime.strptime(item['purchase_date'], "%Y-%m-%d").replace(tzinfo=tw_tz)
        # 計算到期日 (月數 * 30.44 天)
        expiry_date = p_date + timedelta(days=item['warranty_months'] * 30.44)
        days_left = (expiry_date - today).days
        
        is_consumable = "[耗材]" in item['name']
        
        # 決定狀態、圖示與 CSS 類別
        if days_left < 0:
            already_expired_count += 1
            if is_consumable:
                status, icon, css = "更換期!", "🔴", "expired-cons"
            else:
                status, icon, css = "已過期", "⚪", "expired-item"
        elif days_left <= 90:
            status, icon, css = "即將到期", "⚠️", "warning"
            expiring_soon.append(f"🔸 {item['name']} (剩 {days_left} 天)")
        else:
            status, icon, css = "正常", "✅", "safe"

        # 組合 LINE 訊息內容
        line_details += f"{icon} {item['name']}\n   {expiry_date.strftime('%Y-%m-%d')} 到期\n"

        # 組合 HTML 表格列
        html_rows += f"""
            <tr class="{css}">
                <td>{item['name']}</td>
                <td>{item['purchase_date']}</td>
                <td>{item['warranty_months']}</td>
                <td>{expiry_date.strftime('%Y-%m-%d')}</td>
                <td>{days_left if days_left >= 0 else 'EXPIRED'}</td>
                <td>{status}</td>
            </tr>
        """

    # 製作 LINE 訊息字串
    line_msg = (
        f"【Fiona 家務資產報表】\n📅 檢查日期: {today.strftime('%Y-%m-%d')}\n"
        f"------------------\n"
        f"🔥 三個月內到期/更換：\n" + ("\n".join(expiring_soon) if expiring_soon else "🎉 目前狀態良好") +
        f"\n------------------\n"
        f"📦 全資產狀態總覽：\n{line_details}"
        f"------------------\n"
        f"💡 已過期或需更換：{already_expired_count} 個"
    )

    # 製作 HTML 檔案
    html_content = f"""
    <html><head><meta charset="utf-8">
    <style>
        body {{ font-family: 'PingFang TC', 'Microsoft JhengHei', sans-serif; margin: 20px; background: #f4f7f6; }}
        h2 {{ color: #2c3e50; text-align: center; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        th, td {{ padding: 15px; border-bottom: 1px solid #eee; text-align: left; }}
        th {{ background: #2ecc71; color: white; }}
        .expired-cons {{ background: #ffebee; color: #c62828; font-weight: bold; }}
        .expired-item {{ background: #f5f5f5; color: #9e9e9e; }}
        .warning {{ background: #fffde7; color: #f57f17; font-weight: bold; }}
        .safe {{ background: #f1f8e9; color: #388e3c; }}
    </style></head><body>
        <h2>🏠 Fiona 家務資產保固/耗材清單</h2>
        <table>
            <tr><th>產品名稱</th><th>購買/更換日</th><th>週期(月)</th><th>到期日期</th><th>剩餘天數</th><th>狀態</th></tr>
            {html_rows}
        </table>
    </body></html>
    """
    with open("warranty_report.html", "w", encoding="utf-8") as f:
        f.write(html_content)
        
    return line_msg

def push_message(token, text):
    """將訊息推送到 LINE"""
    if not token:
        print("❌ 錯誤: 無法取得 Token")
        return
    url = "https://line.me"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = {
        "to": USER_ID,
        "messages": [{"type": "text", "text": text}]
    }
    res = requests.post(url, headers=headers, json=payload)
    if res.status_code == 200:
        print("✅ LINE 訊息發送成功！")
    else:
        print(f"❌ LINE 訊息發送失敗: {res.text}")

if __name__ == "__main__":
    # 執行保固與耗材分析
    token = get_channel_access_token()
    msg_text = process_and_report()
    
    # 發送訊息
    push_message(token, msg_text)
    print("✅ 處理完畢！HTML 報表與 LINE 訊息已同步生成。")
