# -*- coding: utf-8 -*-
import requests
import os
from datetime import datetime, timedelta, timezone

# 1. 安全設定
CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
USER_ID = os.getenv("LINE_USER_ID")

# 2. 家務資產清單 (請確認小米日期為 2025)
home_assets = [
    {"name": "客廳冷氣排水機", "purchase_date": "2026-04-13", "warranty_months": 36},
    {"name": "iPhone 17", "purchase_date": "2026-04-02", "warranty_months": 12},
    {"name": "iPhone 17 Pro Max", "purchase_date": "2026-04-02", "warranty_months": 12},
    {"name": "[耗材] 小米空氣清淨機X2 濾網", "purchase_date": "2025-03-01", "warranty_months": 6},
    {"name": "[耗材] SHARP空氣清淨機濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] blueair 濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] Samsung Tag x3 電池", "purchase_date": "2026-04-13", "warranty_months": 12},
]

def get_channel_access_token():
    url = "https://line.me"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "grant_type": "client_credentials",
        "client_id": str(CHANNEL_ID),
        "client_secret": str(CHANNEL_SECRET)
    }
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=15)
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except:
        return None

def process_data():
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    app_h, cons_h, soon_list, full_list_str = "", "", [], ""

    for item in home_assets:
        try:
            # 轉換日期
            p_d = datetime.strptime(item['purchase_date'], "%Y-%m-%d").replace(tzinfo=tz)
            e_d = p_d + timedelta(days=item['warranty_months'] * 30.44)
            rem = (e_d - today).days
            is_c = "[耗材]" in item['name']
            n = item['name'].replace("[耗材] ", "")
            
            if rem < 0:
                c, t, icon = (("danger", "更換期", "🔴") if is_c else ("expired", "已過期", "⚪"))
            elif rem <= 90:
                c, t, icon = ("warning", "即將到期", "⚠️")
                soon_list.append(f"🔸 {item['name']} (剩 {rem} 天)")
            else:
                c, t, icon = ("safe", "狀態正常", "✅")
            
            # 組合 HTML 表格列
            row = f"<tr><td><strong>{n}</strong></td><td>{item['purchase_date']}</td><td style='text-align:center'>{item['warranty_months']}</td><td>{e_d.strftime('%Y-%m-%d')}</td><td>{max(0, rem) if rem >= 0 else '--'}</td><td><span class='badge {c}'>{t}</span></td></tr>"
            
            if is_c: cons_h += row
            else: app_h += row
            full_list_str += f"{icon} {n} (剩 {max(0, rem)}天)\n"
        except Exception as e:
            print(f"跳過錯誤項目 {item.get('name')}: {e}")
            continue

    # 如果沒資料，補上提示列避免網頁全白
    if not app_h: app_h = "<tr><td colspan='6' style='text-align:center'>無硬體資料</td></tr>"
    if not cons_h: cons_h = "<tr><td colspan='6' style='text-align:center'>無耗材資料</td></tr>"

    style = "body{font-family:sans-serif;background:#f0f2f5;padding:20px} .card{background:#fff;border-radius:12px;box-shadow:0 5px 15px rgba(0,0,0,0.05);margin-bottom:20px;overflow:hidden;max-width:1000px;margin:auto} .title{padding:15px 25px;background:#fafafa;font-weight:bold;border-left:5px solid #3498db} table{width:100%;border-collapse:collapse} th,td{padding:12px 20px;text-align:left;border-top:1px solid #eee;font-size:14px} th{background:#f8f9fa;color:#95a5a6;font-size:12px} .badge{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:bold} .safe{background:#eafaf1;color:#27ae60} .warning{background:#fef5e7;color:#f39c12} .danger{background:#fdedec;color:#e74c3c} .expired{background:#f4f6f7;color:#95a5a6}"
    
    html_template = f"""<!DOCTYPE html>
<html>
<head><meta charset='utf-8'><style>{style}</style></head>
<body>
    <h2 style='text-align:center'>🏠 Fiona 家務資產管理</h2>
    <div class='card'>
        <div class='title'>📦 硬體設備保固</div>
        <table><thead><tr><th>名稱</th><th>購買日</th><th>月</th><th>到期</th><th>剩餘</th><th>狀態</th></tr></thead>
        <tbody>{app_h}</tbody></table>
    </div>
    <div class='card'>
        <div class='title' style='border-left-color:#e67e22'>♻️ 耗材更換追蹤</div>
        <table><thead><tr><th>名稱</th><th>更換日</th><th>月</th><th>下次</th><th>剩餘</th><th>狀態</th></tr></thead>
        <tbody>{cons_h}</tbody></table>
    </div>
</body>
</html>"""

    with open("warranty_report.html", "w", encoding="utf-8") as f:
        f.write(html_template)
    
    return soon_list, full_list_str, today.strftime('%Y-%m-%d')

def push_message(token, text):
    url = "https://line.me"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": USER_ID, "messages": [{"type": "text", "text": text}]}
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200: print("✅ LINE 訊息發送成功！")
        else: print(f"❌ 訊息發送失敗: {res.text}")
    except Exception as e: print(f"❌ 網路錯誤: {e}")

if __name__ == "__main__":
    print("🚀 啟動資產檢查任務...")
    soon_l, full_l, d_s = process_data()
    
    token = get_channel_access_token()
    if token:
        # --- 加上這行 Debug ---
        print(f"DEBUG: USER_ID={USER_ID}") 
        # ---------------------
        
        soon_msg = "\n".join(soon_l) if soon_l else "🎉 目前狀態正常"
        msg_text = f"【Fiona 家務資產報表 {d_s}】\n" + "-"*15 + f"\n🔥 即將到期提醒：\n{soon_msg}\n" + "-"*15 + f"\n📦 全清單快覽：\n{full_l}" + "-"*15
        
        push_message(token, msg_text)
    else:
        print("❌ 獲取 Token 失敗")
