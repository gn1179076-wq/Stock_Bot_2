# -*- coding: utf-8 -*-
import requests
import os
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 設定區 (由 GitHub Secrets 提供)
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
    
    app_rows, cons_rows, soon = "", "", []

    for item in home_assets:
        p_date = datetime.strptime(item['purchase_date'], "%Y-%m-%d").replace(tzinfo=tw_tz)
        expiry_date = p_date + timedelta(days=item['warranty_months'] * 30.44)
        days_left = (expiry_date - today).days
        is_cons = "[耗材]" in item['name']
        name = item['name'].replace("[耗材] ", "")

        if days_left < 0:
            cls, txt = ("danger", "更換期") if is_cons else ("expired", "已過期")
        elif days_left <= 90:
            cls, txt = "warning", "即將到期"
            soon.append(f"🔸 {item['name']} (剩 {days_left} 天)")
        else:
            cls, txt = "safe", "狀態正常"

        row = f"""<tr><td><strong>{name}</strong></td><td>{item['purchase_date']}</td><td>{item['warranty_months']}</td>
                  <td>{expiry_date.strftime('%Y-%m-%d')}</td><td>{max(0, days_left) if days_left >= 0 else '--'}</td>
                  <td><span class="badge {cls}">{txt}</span></td></tr>"""
        if is_cons: cons_rows += row
        else: app_rows += row

    return app_rows, cons_rows, soon, today.strftime('%Y-%m-%d')

def save_html(app_html, cons_html, date_str):
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
    <link href="https://googleapis.com" rel="stylesheet">
    <style>
        :root {{ --safe: #27ae60; --warning: #f39c12; --danger: #e74c3c; --expired: #95a5a6; }}
        body {{ font-family: 'Noto Sans TC', sans-serif; background: #f0f2f5; padding: 20px; color: #2c3e50; }}
        .card {{ background: white; border-radius: 12px; box-shadow: 0 5px 15px rgba(0,0,0,0.05); margin-bottom: 20px; overflow: hidden; max-width: 900px; margin-left: auto; margin-right: auto; }}
        .title {{ padding: 15px 20px; background: #fafafa; border-bottom: 1px solid #eee; font-size: 18px; font-weight: bold; border-left: 5px solid #3498db; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #f8f9fa; padding: 12px 20px; text-align: left; color: #95a5a6; font-size: 13px; }}
        td {{ padding: 15px 20px; border-top: 1px solid #eee; font-size: 14px; }}
        .badge {{ padding: 4px 10px; border-radius: 20px; font-size: 11px; font-weight: bold; }}
        .safe {{ background: #eafaf1; color: var(--safe); }} .warning {{ background: #fef5e7; color: var(--warning); }}
        .danger {{ background: #fdedec; color: var(--danger); }} .expired {{ background: #f4f6f7; color: var(--expired); }}
    </style></head><body>
    <h2 style="text-align:center">🏠 Fiona 家務資產管理</h2>
    <div class="card"><div class="title">📦 硬體設備保固</div><table>
    <thead><tr><th>名稱</th><th>購買日</th><th>保固</th><th>到期日</th><th>剩餘天數</th><th>狀態</th></tr></thead>
    <tbody>{app_html}</tbody></table></div>
    <div class="card"><div class="title" style="border-left-color:#e67e22">♻️ 耗材更換追蹤</div><table>
    <thead><tr><th>名稱</th><th>更換日</th><th>週期</th><th>下次更換</th><th>剩餘天數</th><th>狀態</th></tr></thead>
    <tbody>{cons_html}</tbody></table></div>
    </body></html>"""
    with open("warranty_report.html", "w", encoding="utf-8") as f:
        f.write(html)

def push_line(token, text):
    if not token: return
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "to": USER_ID,
        "messages":
    }
    requests.post("https://line.me", headers=headers, json=payload, timeout=10)

if __name__ == "__main__":
    app_h, cons_h, soon_l, d_s = process_data()
    save_html(app_h, cons_h, d_s)
    msg = f"【Fiona 保固報表 {d_s}】\n" + "-"*15 + "\n🔥 即將到期：\n" + ("\n".join(soon_l) if soon_l else "🎉 一切正常") + "\n" + "-"*15 + "\n💡 詳細報表見 GitHub Artifacts。"
    push_line(get_channel_access_token(), msg)
    print("✅ 執行成功")
