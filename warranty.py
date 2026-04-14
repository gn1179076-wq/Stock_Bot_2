# -*- coding: utf-8 -*-
import requests
import os
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 安全設定 (動態讀取環境變數)
# ==========================================
def get_channel_access_token():
    cid = os.getenv("LINE_CHANNEL_ID")
    csecret = os.getenv("LINE_CHANNEL_SECRET")
    
    if not cid or not csecret:
        print("❌ 錯誤：LINE_CHANNEL_ID 或 SECRET 為空")
        return None

    # 正確的 Token 獲取網址
    url = "https://line.me"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "grant_type": "client_credentials",
        "client_id": cid,
        "client_secret": csecret
    }
    try:
        response = requests.post(url, headers=headers, data=payload, timeout=15)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"❌ Token 失敗 ({response.status_code}): {response.text}")
            return None
    except Exception as e:
        print(f"❌ Token 請求異常: {e}")
        return None

# 2. 家務資產清單 (小米日期設為 2025 以觸發紅燈)
home_assets = [
    {"name": "客廳冷氣排水機", "purchase_date": "2026-04-13", "warranty_months": 36},
    {"name": "iPhone 17", "purchase_date": "2026-04-02", "warranty_months": 12},
    {"name": "iPhone 17 Pro Max", "purchase_date": "2026-04-02", "warranty_months": 12},
    {"name": "[耗材] 小米空氣清淨機X2 濾網", "purchase_date": "2025-03-01", "warranty_months": 6},
    {"name": "[耗材] SHARP空氣清淨機濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] blueair 濾網", "purchase_date": "2026-03-01", "warranty_months": 12},
    {"name": "[耗材] Samsung Tag x3 電池", "purchase_date": "2026-04-13", "warranty_months": 12},
]

def process_data():
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    app_h, cons_h, soon_list, full_list_str = "", "", [], ""

    for item in home_assets:
        try:
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
            
            row = f"<tr><td><strong>{n}</strong></td><td>{item['purchase_date']}</td><td style='text-align:center'>{item['warranty_months']}</td><td>{e_d.strftime('%Y-%m-%d')}</td><td>{max(0, rem) if rem >= 0 else '--'}</td><td><span class='badge {c}'>{t}</span></td></tr>"
            
            if is_c: cons_h += row
            else: app_h += row
            full_list_str += f"{icon} {n} (剩 {max(0, rem)}天)\n"
        except Exception as e:
            print(f"跳過項目 {item.get('name')}: {e}")
            continue

    # HTML 樣式
    style = "body{{font-family:sans-serif;background:#f0f2f5;padding:20px}} .card{{background:#fff;border-radius:12px;box-shadow:0 5px 15px rgba(0,0,0,0.05);margin-bottom:20px;overflow:hidden;max-width:1000px;margin:auto}} .title{{padding:15px 25px;background:#fafafa;font-weight:bold;border-left:5px solid #3498db}} table{{width:100%;border-collapse:collapse}} th,td{{padding:12px 20px;text-align:left;border-top:1px solid #eee;font-size:14px}} th{{background:#f8f9fa;color:#95a5a6;font-size:12px}} .badge{{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:bold}} .safe{{background:#eafaf1;color:#27ae60}} .warning{{background:#fef5e7;color:#f39c12}} .danger{{background:#fdedec;color:#e74c3c}} .expired{{background:#f4f6f7;color:#95a5a6}}"
    html_template = f"<!DOCTYPE html><html><head><meta charset='utf-8'><style>{style}</style></head><body><h2 style='text-align:center'>🏠 Fiona 家務資產管理</h2><div class='card'><div class='title'>📦 硬體設備保固</div><table><thead><tr><th>名稱</th><th>購買日</th><th>月</th><th>到期</th><th>剩餘</th><th>狀態</th></tr></thead><tbody>{app_h if app_h else '<tr><td colspan=6>暫無資料</td></tr>'}</tbody></table></div><div class='card'><div class='title' style='border-left-color:#e67e22'>♻️ 耗材更換追蹤</div><table><thead><tr><th>名稱</th><th>更換日</th><th>月</th><th>下次</th><th>剩餘</th><th>狀態</th></tr></thead><tbody>{cons_h if cons_h else '<tr><td colspan=6>暫無資料</td></tr>'}</tbody></table></div></body></html>"

    with open("warranty_report.html", "w", encoding="utf-8") as f:
        f.write(html_template)
    
    return soon_list, full_list_str, today.strftime('%Y-%m-%d')

def push_message(token, text):
    user_id = os.getenv("LINE_USER_ID")
    if not user_id or not token:
        print("❌ 缺少 Token 或 User_ID")
        return

    url = "https://line.me"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    
    # 修正後的 payload 結構
    payload = {
        "to": user_id,
        "messages":
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            print("✅ LINE 訊息發送成功！")
        else:
            print(f"❌ 發送失敗: {res.text}")
    except Exception as e:
        print(f"❌ 網路連線錯誤: {e}")

if __name__ == "__main__":
    print("🚀 啟動資產檢查任務...")
    soon_l, full_l, d_s = process_data()
    token = get_channel_access_token()
    
    if token:
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
        print("❌ 任務失敗：無法取得 Token")
