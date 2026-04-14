# -*- coding: utf-8 -*-
import requests
import os
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 設定區
# ==========================================
CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
USER_ID = os.getenv("LINE_USER_ID")

home_assets = [
    {"name": "客廳冷氣排水機", "purchase_date": "2026-04-13", "warranty_months": 36},
    {"name": "[耗材] 小米空氣清淨機X2 濾網", "purchase_date": "2026-03-01", "warranty_months": 6},
    {"name": "[耗材] SHARP空氣清淨機濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] blueair 濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] Samsung Tag x3 電池", "purchase_date": "2026-04-13", "warranty_months": 12},
]

# ==========================================
# 2. 核心邏輯
# ==========================================
def get_channel_access_token():
    url = "https://line.me"
    payload = {"grant_type": "client_credentials", "client_id": CHANNEL_ID, "client_secret": CHANNEL_SECRET}
    try:
        res = requests.post(url, data=payload, timeout=10)
        return res.json().get("access_token") if res.status_code == 200 else None
    except:
        return None

def process_data():
    tw_tz = timezone(timedelta(hours=8))
    today = datetime.now(tw_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    
    appliance_rows = ""
    consumable_rows = ""
    soon = []

    for item in home_assets:
        p_date = datetime.strptime(item['purchase_date'], "%Y-%m-%d").replace(tzinfo=tw_tz)
        expiry_date = p_date + timedelta(days=item['warranty_months'] * 30.44)
        days_left = (expiry_date - today).days
        is_consumable = "[耗材]" in item['name']
        display_name = item['name'].replace("[耗材] ", "")

        if days_left < 0:
            status_cls, status_text = ("danger", "更換期") if is_consumable else ("expired", "已過期")
        elif days_left <= 90:
            status_cls, status_text = "warning", "即將到期"
            soon.append(f"🔸 {item['name']} (剩 {days_left} 天)")
        else:
            status_cls, status_text = "safe", "狀態正常"

        row_html = f"""
            <tr>
                <td><strong>{display_name}</strong></td>
                <td>{item['purchase_date']}</td>
                <td>{item['warranty_months']}</td>
                <td>{expiry_date.strftime('%Y-%m-%d')}</td>
                <td>{days_left if days_left >= 0 else '--'}</td>
                <td><span class="badge {status_cls}">{status_text}</span></td>
            </tr>
        """
        if is_consumable: consumable_rows += row_html
        else: appliance_rows += row_html

    return appliance_rows, consumable_rows, soon, today.strftime('%Y-%m-%d')

def save_html(appliances, consumables, date_str):
    html_template = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://googleapis.com" rel="stylesheet">
        <style>
            :root {{ --safe: #27ae60; --warning: #f39c12; --danger: #e74c3c; --expired: #95a5a6; }}
            body {{ font-family: 'Noto Sans TC', sans-serif; background-color: #f0f2f5; margin: 0; padding: 40px 20px; color: #2c3e50; line-height: 1.6; }}
            .container {{ max-width: 900px; margin: auto; }}
            .header {{ text-align: center; margin-bottom: 40px; }}
            .header h1 {{ margin: 0; color: #2c3e50; font-size: 28px; }}
            .card {{ background: white; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); margin-bottom: 30px; overflow: hidden; }}
            .card-title {{ padding: 20px 25px; margin: 0; background: #fafafa; border-bottom: 1px solid #eee; font-size: 18px; color: #34495e; border-left: 5px solid #3498db; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th {{ background: #fdfdfd; padding: 15px 25px; text-align: left; font-size: 13px; color: #95a5a6; }}
            td {{ padding: 18px 25px; border-top: 1px solid #f6f8f9; font-size: 15px; }}
            .badge {{ padding: 6px 12px; border-radius: 50px; font-size: 12px; font-weight: bold; }}
            .safe {{ background: #eafaf1; color: var(--safe); }}
            .warning {{ background: #fef5e7; color: var(--warning); }}
            .danger {{ background: #fdedec; color: var(--danger); }}
            .expired {{ background: #f4f6f7; color: var(--expired); }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header"><h1>🏠 Fiona 家務資產管理</h1><p>更新：{date_str}</p></div>
            <div class="card"><h3 class="card-title">📦 硬體設備保固</h3><table>
            <thead><tr><th>產品名稱</th><th>購買日</th><th>保固</th><th>到期日</th><th>剩餘天數</th><th>狀態</th></tr></thead>
            <tbody>{appliances}</tbody></table></div>
            <div class="card"><h3 class="card-title" style="border-left-color: #e67e22;">♻️ 耗材更換追蹤</h3><table>
            <thead><tr><th>產品名稱</th><th>更換日</th><th>週期</th><th>下次更換</th><th>剩餘天數</th><th>狀態</th></tr></thead>
            <tbody>{consumables}</tbody></table></div>
        </div>
    </body>
    </html>
    """
    with open("warranty_report.html", "w", encoding="utf-8") as f:
        f.write(html_template)

def push_line(token, text):
    if not token: return
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # 修正語法錯誤：補齊 messages 的值
    payload = {
        "to": USER_ID, 
        "messages":
    }
    try:
        requests.post("https://line.me", headers=headers, json=payload, timeout=10)
    except:
        pass

if __name__ == "__main__":
    app_rows, cons_rows, soon_list, d_str = process_data()
    save_html(app_rows, cons_rows, d_str)
    
    line_msg = f"【Fiona 保固報表 {d_str}】\n"
    line_msg += "------------------\n"
    line_msg += "🔥 即將到期：\n" + ("\n".join(soon_list) if soon_list else "🎉 一切正常") + "\n"
    line_msg += "------------------\n💡 詳細報表見 GitHub Artifacts。"
    
    token = get_channel_access_token()
    push_line(token, line_msg)
    print("✅ 美化版報表更新成功！")
