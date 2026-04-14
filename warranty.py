# -*- coding: utf-8 -*-
import requests
import os
from datetime import datetime, timedelta, timezone

# 1. 設定區 (由 GitHub Secrets 提供)
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

# 3. 核心邏輯
def get_channel_access_token():
    url = "https://line.me"
    p = {"grant_type": "client_credentials", "client_id": CHANNEL_ID, "client_secret": CHANNEL_SECRET}
    try:
        res = requests.post(url, data=p, timeout=10)
        return res.json().get("access_token") if res.status_code == 200 else None
    except: return None

def process_data():
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    app_h, cons_h, soon = "", "", []
    for item in home_assets:
        p_d = datetime.strptime(item['purchase_date'], "%Y-%m-%d").replace(tzinfo=tz)
        e_d = p_d + timedelta(days=item['warranty_months'] * 30.44)
        rem = (e_d - today).days
        is_c = "[耗材]" in item['name']
        n = item['name'].replace("[耗材] ", "")
        
        if rem < 0:
            c, t = ("danger", "更換期") if is_c else ("expired", "已過期")
        elif rem <= 90:
            c, t = "warning", "即將到期"
            soon.append(f"🔸 {item['name']} (剩 {rem} 天)")
        else:
            c, t = "safe", "狀態正常"
            
        row = f"<tr><td><strong>{n}</strong></td><td>{item['purchase_date']}</td><td style='text-align:center'>{item['warranty_months']}</td><td>{e_d.strftime('%Y-%m-%d')}</td><td>{max(0, rem) if rem >= 0 else '--'}</td><td><span class='badge {c}'>{t}</span></td></tr>"
        if is_c: cons_h += row
        else: app_h += row
        
    # --- HTML 生成 (已移除多餘的括號) ---
    h = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>body{{font-family:sans-serif;background:#f0f2f5;padding:40px 20px}} .card{{background:#fff;border-radius:12px;box-shadow:0 5px 15px rgba(0,0,0,0.05);margin-bottom:20px;overflow:hidden;max-width:1000px;margin:auto}} .title{{padding:15px 25px;background:#fafafa;font-weight:bold;border-left:5px solid #3498db}} table{{width:100%;border-collapse:collapse}} th,td{{padding:15px 25px;text-align:left;border-top:1px solid #eee;font-size:14px}} th{{background:#fdfdfd;color:#95a5a6;font-size:12px}} .badge{{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:bold}} .safe{{background:#eafaf1;color:#27ae60}} .warning{{background:#fef5e7;color:#f39c12}} .danger{{background:#fdedec;color:#e74c3c}} .expired{{background:#f4f6f7;color:#95a5a6}}</style></head><body><h2 style='text-align:center'>🏠 Fiona 家務資產管理</h2><div class='card'><div class='title'>📦 硬體設備保固</div><table><thead><tr><th>名稱</th><th>購買日</th><th style='text-align:center'>月</th><th>到期</th><th>剩餘</th><th>狀態</th></tr></thead><tbody>{app_h}</tbody></table></div><div class='card'><div class='title' style='border-left-color:#e67e22'>♻️ 耗材更換追蹤</div><table><thead><tr><th>名稱</th><th>更換日</th><th style='text-align:center'>月</th><th>下次</th><th>剩餘</th><th>狀態</th></tr></thead><tbody>{cons_h}</tbody></table></div></body></html>"
    with open("warranty_report.html", "w", encoding="utf-8") as f: f.write(h)
    
    return soon, today.strftime('%Y-%m-%d')

def push_button_message(token, soon_list, date_str):
    if not token: return
    
    # 組合內容摘要
    summary = "🔥 即將到期提醒：\n" + ("\n".join(soon_list) if soon_list else "🎉 所有資產目前均在保固/效期內。")
    report_url = "https://github.io"
    
    url = "https://line.me"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    # LINE 按鈕範本 JSON 格式
    payload = {
        "to": USER_ID,
        "messages":,
                    "actions": [
                        {
                            "type": "uri",
                            "label": "查看完整彩色報表",
                            "uri": report_url
                        }
                    ]
                }
            }
        ]
    }
    requests.post(url, headers=headers, json=payload, timeout=10)

if __name__ == "__main__":
    soon_l, d_s = process_data()
    token = get_channel_access_token()
    push_button_message(token, soon_l, d_s)
    print("✅ 任務執行成功")
