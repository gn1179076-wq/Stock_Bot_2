# -*- coding: utf-8 -*-
import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 取得 Token (保留你的原始設定)
# ==========================================
def get_channel_access_token():
    long_lived_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if long_lived_token:
        return long_lived_token

    cid = os.getenv("LINE_CHANNEL_ID")
    csecret = os.getenv("LINE_CHANNEL_SECRET")
    if not cid or not csecret:
        return None

    url = "https://line.me"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {"grant_type": "client_credentials", "client_id": cid, "client_secret": csecret}
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=15)
        if response.status_code == 200:
            return response.json().get("access_token")
        return None
    except Exception:
        return None

# ==========================================
# 2. 讀取家務資產清單
# ==========================================
ASSETS_FILE = "home_assets.json"

def load_assets():
    # 這裡放你提供的 JSON 資料範例，若檔案不存在則回傳此預設值
    default_data = [
        {"name": "客廳冷氣排水機", "purchase_date": "2026-04-13", "warranty_months": 36},
        {"name": "iPhone 17", "purchase_date": "2026-04-02", "warranty_months": 12},
        {"name": "iPhone 17 Pro Max", "purchase_date": "2026-04-02", "warranty_months": 12},
        {"name": "[耗材] 小米空氣清淨機X2 濾網", "purchase_date": "2026-03-01", "warranty_months": 6},
        {"name": "[耗材] SHARP空氣清淨機濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
        {"name": "[耗材] blueair 濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
        {"name": "[耗材] Samsung Tag x3 電池", "purchase_date": "2026-04-13", "warranty_months": 12},
        {"name": "桌上型電腦", "purchase_date": "2026-02-01", "warranty_months": 12, "receipt": "receipts/Destop.jpg"},
        {"name": "Samsung Z Fold7", "purchase_date": "2025-08-28", "warranty_months": 36},
        {"name": "【Samsung 三星】S27FG812SC Odyssey(27型/OLED/", "purchase_date": "2026-02-07", "warranty_months": 24, "receipt": "receipts/receipt_samsung_s27fg812sc_2026-02-07.png"},
        {"name": "[耗材] 三樓瓦斯", "purchase_date": "2026-04-14", "warranty_months": 3}
    ]
    try:
        if os.path.exists(ASSETS_FILE):
            with open(ASSETS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return default_data
    except Exception as e:
        print(f"讀取錯誤: {e}")
        return default_data

# ==========================================
# 3. 資料處理 & HTML 報表
# ==========================================
def process_data():
    tz = timezone(timedelta(hours=8))
    # 模擬今天為 2026-04-15 (對應你的測試數據)
    today = datetime(2026, 4, 15, tzinfo=tz)
    home_assets = load_assets()
    app_rows, cons_rows = "", ""
    soon_list, expired_list = [], []

    total_items = len(home_assets)
    safe_count, warning_count, danger_count = 0, 0, 0

    for item in home_assets:
        try:
            p_d = datetime.strptime(item['purchase_date'], "%Y-%m-%d").replace(tzinfo=tz)
            e_d = p_d + timedelta(days=item['warranty_months'] * 30.44)
            rem = (e_d - today).days
            is_c = "[耗材]" in item['name']
            n = item['name'].replace("[耗材] ", "")

            if rem < 0:
                badge_class, badge_text = ("danger", "需更換") if is_c else ("expired", "已過期")
                days_display = '<span class="days-cell danger-text">已逾期</span>'
                expired_list.append(item['name'])
                danger_count += 1
            elif rem <= 90:
                badge_class, badge_text = "warning", "即將到期"
                days_display = f'<span class="days-cell warning-text">{rem} 天</span>'
                soon_list.append(item['name'])
                warning_count += 1
            else:
                badge_class, badge_text = "safe", "正常"
                days_display = f'<span class="days-cell">{rem} 天</span>'
                safe_count += 1

            receipt = item.get('receipt', '')
            if receipt:
                if receipt.lower().endswith('.pdf'):
                    receipt_cell = f"<td><a class='receipt-link' href='{receipt}' target='_blank'>📄 PDF</a></td>"
                else:
                    receipt_cell = f"<td><span class='receipt-link' onclick=\"showReceipt('{receipt}')\">📎 查看</span></td>"
            else:
                receipt_cell = "<td><span class='no-receipt'>—</span></td>"

            row = (
                f"<tr>"
                f"<td><div class='item-name'>{n}</div></td>"
                f"<td>{item['purchase_date']}</td>"
                f"<td class='center'>{item['warranty_months']}</td>"
                f"<td>{e_d.strftime('%Y-%m-%d')}</td>"
                f"<td>{days_display}</td>"
                f"<td><span class='badge {badge_class}'>{badge_text}</span></td>"
                f"{receipt_cell}"
                f"</tr>"
            )

            if is_c: cons_rows += row
            else: app_rows += row

        except Exception as e:
            continue

    update_time = today.strftime('%Y-%m-%d %H:%M')

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fiona 家務資產儀表板</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, system-ui, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 24px 16px; min-height: 100vh; color: #2d3748; }}
  .container {{ max-width: 920px; margin: auto; }}
  .header {{ text-align: center; margin-bottom: 28px; }}
  .header h1 {{ font-size: 1.6rem; color: #fff; margin: 0 0 6px; }}
  .header .subtitle {{ color: rgba(255,255,255,.75); font-size: .85rem; }}
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 14px; margin-bottom: 28px; }}
  .summary-card {{ background: rgba(255,255,255,.95); border-radius: 14px; padding: 18px 14px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,.08); }}
  .summary-card .num {{ font-size: 1.8rem; font-weight: 800; }}
  .summary-card .label {{ font-size: .75rem; color: #718096; margin-top: 6px; font-weight: 600; }}
  .num.green {{ color: #38a169; }} .num.orange {{ color: #dd6b20; }} .num.red {{ color: #e53e3e; }} .num.blue {{ color: #3182ce; }}
  .card {{ background: #fff; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.1); margin-bottom: 24px; overflow: hidden; }}
  .card-header {{ padding: 16px 22px; font-weight: 700; border-bottom: 1px solid #edf2f7; display: flex; align-items: center; gap: 10px; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #f7fafc; color: #a0aec0; font-size: .72rem; padding: 12px 18px; text-align: left; text-transform: uppercase; border-bottom: 2px solid #edf2f7; }}
  td {{ padding: 14px 18px; font-size: .88rem; border-bottom: 1px solid #f7fafc; white-space: nowrap; }}
  .item-name {{ font-weight: 600; color: #2d3748; }}
  .center {{ text-align: center; }}
  .days-cell {{ font-family: monospace; font-weight: 700; }}
  .warning-text {{ color: #dd6b20; }} .danger-text {{ color: #e53e3e; }}
  .badge {{ display: inline-block; padding: 5px 14px; border-radius: 50px; font-size: .72rem; font-weight: 700; }}
  .safe {{ background: #f0fff4; color: #38a169; }} .warning {{ background: #fffaf0; color: #dd6b20; }}
  .danger {{ background: #fff5f5; color: #e53e3e; }} .expired {{ background: #edf2f7; color: #718096; }}
  .receipt-link {{ color: #4a90e2; cursor: pointer; font-weight: 600; }}
  #modal {{ display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.85); z-index:1000; justify-content:center; align-items:center; }}
  #modal img {{ max-width:90%; max-height:90%; border-radius:8px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header"><h1>🏠 Fiona 家務資產儀表板</h1><div class="subtitle">最後更新：{update_time}</div></div>
  <div class="summary">
    <div class="summary-card"><div class="num blue">{total_items}</div><div class="label">總資產</div></div>
    <div class="summary-card"><div class="num green">{safe_count}</div><div class="label">保固正常</div></div>
    <div class="summary-card"><div class="num orange">{warning_count}</div><div class="label">即將到期</div></div>
    <div class="summary-card"><div class="num red">{danger_count}</div><div class="label">已逾期</div></div>
  </div>
  <div class="card">
    <div class="card-header">🧊 電器設備保固</div>
    <div class="table-wrap"><table><thead><tr><th>名稱</th><th>購買日期</th><th class="center">月數</th><th>到期日</th><th>剩餘天數</th><th>狀態</th><th>收據</th></tr></thead><tbody>{app_rows}</tbody></table></div>
  </div>
  <div class="card">
    <div class="card-header">♻️ 耗材更換清單</div>
    <div class="table-wrap"><table><thead><tr><th>名稱</th><th>購買日期</th><th class="center">週期</th><th>建議更換日</th><th>剩餘天數</th><th>狀態</th><th>收據</th></tr></thead><tbody>{cons_rows}</tbody></table></div>
  </div>
</div>
<div id="modal" onclick="this.style.display='none'"><img id="modalImg" src=""></div>
<script>
function showReceipt(path) {{
  document.getElementById('modal').style.display = 'flex';
  document.getElementById('modalImg').src = path;
}}
</script>
</body>
</html>"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    return soon_list, expired_list

if __name__ == "__main__":
    soon, expired = process_data()
    print(f"✅ 儀表板 index.html 已產出")
