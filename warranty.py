# -*- coding: utf-8 -*-
import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. Telegram 推播函式
# ==========================================
def push_tg_message(text):
    tg_token = os.getenv("TG_BOT_TOKEN")
    tg_chat_id = os.getenv("TG_CHAT_ID")
    
    if not tg_token or not tg_chat_id:
        print("❌ 錯誤：請在 GitHub Secrets 中設定 TG_BOT_TOKEN 與 TG_CHAT_ID")
        return

    url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
    payload = {
        "chat_id": tg_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            print("✅ Telegram 訊息發送成功！")
        else:
            print(f"❌ Telegram 發送失敗 ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Telegram 連線異常: {e}")


# ==========================================
# 2. 讀取家務資產清單
# ==========================================
ASSETS_FILE = "home_assets.json"

def load_assets():
    try:
        with open(ASSETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到資產檔案：{ASSETS_FILE}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤：{e}")
        return []


# ==========================================
# 3. 資料處理 & HTML 報表產生
# ==========================================
def process_data():
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    home_assets = load_assets()
    
    # 排序：按到期日排序
    home_assets = sorted(home_assets, key=lambda x: datetime.strptime(x['purchase_date'], "%Y-%m-%d") + timedelta(days=x['warranty_months'] * 30.44))
    
    app_rows, cons_rows, sub_rows = "", "", ""
    soon_list, expired_list = [], []
    full_list_str = ""

    # 統計數據
    total_items = len(home_assets)
    safe_count, warning_count, danger_count = 0, 0, 0

    for item in home_assets:
        try:
            p_d = datetime.strptime(item['purchase_date'], "%Y-%m-%d").replace(tzinfo=tz)
            e_d = p_d + timedelta(days=item['warranty_months'] * 30.44)
            rem = (e_d - today).days
            
            is_c = "[耗材]" in item['name']
            is_s = "[訂閱]" in item['name']
            n = item['name'].replace("[耗材] ", "").replace("[訂閱] ", "")

            # 狀態判斷
            if rem < 0:
                badge_text = "需續訂" if is_s else ("需更換" if is_c else "已過期")
                badge_class, icon = ("danger", "🔴") if (is_s or is_c) else ("expired", "🔴")
                days_display = '<span class="days-cell danger-text">已逾期</span>'
                expired_list.append(f"{icon} {item['name']} ({badge_text})")
                danger_count += 1
            elif rem <= 20:
                badge_class, badge_text, icon = "warning", "即將到期", "⚠️"
                days_display = f'<span class="days-cell warning-text">{rem} 天</span>'
                soon_list.append(f"🔸 {item['name']} (剩 {rem} 天)")
                warning_count += 1
            else:
                badge_class, badge_text, icon = "safe", "正常", "✅"
                days_display = f'<span class="days-cell">{rem} 天</span>'
                safe_count += 1

            # --- 核心邏輯：區分 訂閱/耗材(顯示費用) 與 硬體(顯示收據) ---
            if is_s or is_c:
                fee = item.get('fee', '—')
                extra_cell = f"<td class='center'><span style='color:#667eea;font-weight:600'>{fee}</span></td>"
            else:
                receipt = item.get('receipt', '')
                if receipt:
                    if receipt.lower().endswith('.pdf'):
                        extra_cell = f"<td><a class='receipt-link' href='{receipt}' target='_blank'>📄 PDF</a></td>"
                    else:
                        extra_cell = f"<td><a class='receipt-link' onclick=\"showReceipt('{receipt}')\">📎 查看</a></td>"
                else:
                    extra_cell = "<td><span class='no-receipt'>—</span></td>"

            # 組合表格行
            row_html = (
                f"<tr>"
                f"<td><div class='item-name'>{n}</div></td>"
                f"<td>{item['purchase_date']}</td>"
                f"<td class='center'>{item['warranty_months']}</td>"
                f"<td>{e_d.strftime('%Y-%m-%d')}</td>"
                f"<td>{days_display}</td>"
                f"<td><span class='badge {badge_class}'>{badge_text}</span></td>"
                f"{extra_cell}"
                f"</tr>"
            )

            if is_s:
                sub_rows += row_html
            elif is_c:
                cons_rows += row_html
            else:
                app_rows += row_html
            
        except Exception as e:
            print(f"跳過項目 {item.get('name')}: {e}")
            continue

    update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

    # ---- HTML 報表內容 ----
    report_content = f"""
  <div class="header">
    <h1>🏠 Fiona 家務資產儀表板</h1>
    <div class="subtitle">自動追蹤保固 &amp; 耗材更換週期</div>
  </div>
  <div class="summary">
    <div class="summary-card"><div class="num blue">{total_items}</div><div class="label">管理項目</div></div>
    <div class="summary-card"><div class="num green">{safe_count}</div><div class="label">狀態正常</div></div>
    <div class="summary-card"><div class="num orange">{warning_count}</div><div class="label">即將到期</div></div>
    <div class="summary-card"><div class="num red">{danger_count}</div><div class="label">需處理</div></div>
  </div>
  <div class="card">
    <div class="card-header"><div class="icon icon-blue">📦</div>硬體設備保固</div>
    <div class="table-wrap"><table>
      <thead><tr><th>名稱</th><th>購買日</th><th>保固(月)</th><th>到期日</th><th>剩餘</th><th>狀態</th><th>收據</th></tr></thead>
      <tbody>{app_rows if app_rows else '<tr><td colspan="7" style="text-align:center;color:#a0aec0;padding:30px">暫無資料</td></tr>'}</tbody>
    </table></div>
  </div>
  <div class="card">
    <div class="card-header"><div class="icon icon-orange">♻️</div>耗材更換追蹤</div>
    <div class="table-wrap"><table>
      <thead><tr><th>名稱</th><th>更換日</th><th>週期(月)</th><th>下次更換</th><th>剩餘</th><th>狀態</th><th>費用</th></tr></thead>
      <tbody>{cons_rows if cons_rows else '<tr><td colspan="7" style="text-align:center;color:#a0aec0;padding:30px">暫無資料</td></tr>'}</tbody>
    </table></div>
  </div>
  <div class="card">
    <div class="card-header"><div class="icon icon-purple">🔔</div>訂閱服務</div>
    <div class="table-wrap"><table>
      <thead><tr><th>名稱</th><th>訂閱日</th><th>週期(月)</th><th>下次續訂</th><th>剩餘</th><th>狀態</th><th>費用</th></tr></thead>
      <tbody>{sub_rows if sub_rows else '<tr><td colspan="7" style="text-align:center;color:#a0aec0;padding:30px">暫無資料</td></tr>'}</tbody>
    </table></div>
  </div>
  <div class="footer">最後更新：{update_time}</div>"""

    # ---- AES 加密處理 ----
    import hashlib, base64
    from os import urandom
    password = "vic2026"
    salt = urandom(16)
    iv = urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=32)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, report_content.encode('utf-8'), None)

    encrypted_b64 = base64.b64encode(ciphertext).decode()
    salt_b64 = base64.b64encode(salt).decode()
    iv_b64 = base64.b64encode(iv).decode()

    # 組合 HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fiona 家務資產儀表板</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); margin: 0; padding: 24px 16px; min-height: 100vh; color: #2d3748; }}
  .container {{ max-width: 920px; margin: auto; }}
  .header {{ text-align: center; margin-bottom: 28px; }}
  .header h1 {{ font-size: 1.6rem; color: #fff; margin: 0 0 6px; }}
  .header .subtitle {{ color: rgba(255,255,255,.75); font-size: .85rem; }}
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 14px; margin-bottom: 28px; }}
  .summary-card {{ background: rgba(255,255,255,.95); border-radius: 14px; padding: 18px 14px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,.08); }}
  .summary-card .num {{ font-size: 1.8rem; font-weight: 800; }}
  .num.green {{ color: #38a169; }} .num.orange {{ color: #dd6b20; }} .num.red {{ color: #e53e3e; }} .num.blue {{ color: #3182ce; }}
  .card {{ background: #fff; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.1); margin-bottom: 24px; overflow: hidden; }}
  .card-header {{ padding: 16px 22px; font-weight: 700; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #edf2f7; }}
  .card-header .icon {{ width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; }}
  .icon-blue {{ background: #ebf4ff; }} .icon-orange {{ background: #fefcbf; }} .icon-purple {{ background: #faf5ff; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #f7fafc; color: #a0aec0; font-size: .72rem; text-transform: uppercase; padding: 12px 18px; text-align: left; border-bottom: 2px solid #edf2f7; }}
  td {{ padding: 14px 18px; font-size: .88rem; border-bottom: 1px solid #f7fafc; white-space: nowrap; }}
  .badge {{ display: inline-block; padding: 5px 14px; border-radius: 50px; font-size: .72rem; font-weight: 700; }}
  .safe {{ background: #f0fff4; color: #38a169; }} .warning {{ background: #fffaf0; color: #dd6b20; }} .danger {{ background: #fff5f5; color: #e53e3e; }} .expired {{ background: #f7fafc; color: #a0aec0; }}
  .receipt-link {{ background: #ebf4ff; color: #3182ce; padding: 4px 12px; border-radius: 6px; text-decoration: none; font-size: .78rem; font-weight: 600; cursor: pointer; }}
  .lightbox {{ display: none; position: fixed; inset: 0; background: rgba(0,0,0,.8); z-index: 9999; justify-content: center; align-items: center; cursor: pointer; }}
  .lightbox.active {{ display: flex; }} .lightbox img {{ max-width: 90%; max-height: 85%; border-radius: 12px; }}
  .footer {{ text-align: center; margin-top: 12px; color: rgba(255,255,255,.6); font-size: .75rem; }}
  .login-overlay {{ position: fixed; inset: 0; background: linear-gradient(135deg, #667eea, #764ba2); z-index: 99999; display: flex; justify-content: center; align-items: center; }}
  .login-box {{ background: #fff; border-radius: 20px; padding: 40px; text-align: center; width: 320px; }}
  .login-box input {{ width: 100%; padding: 12px; margin: 20px 0 10px; border: 2px solid #e2e8f0; border-radius: 10px; }}
  .login-box button {{ width: 100%; padding: 12px; background: #667eea; color: #fff; border: none; border-radius: 10px; font-weight: 700; cursor: pointer; }}
  .hidden {{ display: none; }}
</style>
</head>
<body>
<div class="login-overlay" id="loginOverlay">
  <div class="login-box">
    <h2>🔒 需要驗證</h2>
    <input type="password" id="pwdInput" placeholder="輸入密碼" onkeydown="if(event.key==='Enter')checkPwd()">
    <button onclick="checkPwd()">解鎖</button>
  </div>
</div>
<div class="container" id="mainContent"></div>
<div class="lightbox" id="lightbox" onclick="this.classList.remove('active')"><img id="lbImg"></div>
<script>
function showReceipt(s){{document.getElementById('lbImg').src=s;document.getElementById('lightbox').classList.add('active')}}
const E="{encrypted_b64}",S="{salt_b64}",I="{iv_b64}";
async function checkPwd(){{
  try{{
    const pw=document.getElementById('pwdInput').value;
    const salt=Uint8Array.from(atob(S),c=>c.charCodeAt(0)),iv=Uint8Array.from(atob(I),c=>c.charCodeAt(0)),ct=Uint8Array.from(atob(E),c=>c.charCodeAt(0));
    const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pw),{{name:'PBKDF2'}},false,['deriveKey']);
    const key=await crypto.subtle.deriveKey({{name:'PBKDF2',salt,iterations:100000,hash:'SHA-256'}},km,{{name:'AES-GCM',length:256}},false,['decrypt']);
    const dec=await crypto.subtle.decrypt({{name:'AES-GCM',iv}},key,ct);
    document.getElementById('mainContent').innerHTML=new TextDecoder().decode(dec);
    document.getElementById('loginOverlay').classList.add('hidden');
  }}catch(e){{alert('密碼錯誤');}}
}}
</script>
</body>
</html>"""

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    os.makedirs("Daily_Report", exist_ok=True)
    with open(f"Daily_Report/warranty_{today.strftime('%Y-%m-%d')}.html", "w", encoding="utf-8") as f:
        f.write(html)

    if os.path.isdir("receipts"):
        import shutil
        dr = os.path.join("docs", "receipts")
        if os.path.isdir(dr): shutil.rmtree(dr)
        shutil.copytree("receipts", dr)

    return soon_list, expired_list, today.strftime('%Y-%m-%d')


# ==========================================
# 4. 主程式
# ==========================================
REPORT_BASE_URL = "https://gn1179076-wq.github.io/Stock_Bot_2/"

if __name__ == "__main__":
    tz = timezone(timedelta(hours=8))
    print("🚀 啟動資產檢查任務 (Telegram 版)...")
    soon_l, expired_l, d_s = process_data()
    
    # 組合 Telegram 訊息 (支援 HTML 語法)
    parts = [f"<b>🏠 Fiona 家務提醒 {d_s}</b>"]

    if expired_l or soon_l:
        if expired_l:
            parts.append("\n⛔ <b>已逾期 / 需處理：</b>")
            parts.append("\n".join(expired_l))
        if soon_l:
            parts.append("\n⚠️ <b>即將到期 (20天內)：</b>")
            parts.append("\n".join(soon_l))
    else:
        parts.append("\n🎉 所有設備及耗材狀態正常！")

    # 加入傳送門連結
    parts.append(f"\n📋 <a href='{REPORT_BASE_URL}'>查看儀表板</a>")
    parts.append(f"🛠 <a href='{ADMIN_URL}'>管理後台</a>")
    
    msg_text = "\n".join(parts)
    push_tg_message(msg_text)
