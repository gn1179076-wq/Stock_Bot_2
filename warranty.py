# -*- coding: utf-8 -*-
import requests
import os
import json
import hashlib
import base64
from datetime import datetime, timedelta, timezone
from os import urandom
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ==========================================
# 1. 設定區
# ==========================================
# --- 機密資料 (從環境變數讀取) ---
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHAT_ID = os.getenv("TG_CHAT_ID")
LINE_CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
LINE_USER_ID = os.getenv("LINE_USER_ID")
REPORT_PWD = os.getenv("REPORT_PWD")  # 解鎖密碼

# --- 一般設定 (可以直接在這裡修改) ---
NOTIFY_TARGET = "both"  # 👉 在此修改推播目標："telegram" / "line" / "both"
REPORT_BASE_URL = "https://gn1179076-wq.github.io/Stock_Bot_2/"
ADMIN_URL = "https://gn1179076-wq.github.io/Stock_Bot_2/admin.html"
ASSETS_FILE = "home_assets.json"

# ==========================================
# 2. 推播函式 (Telegram & LINE Bot API)
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
        res = requests.post(url, json=payload, timeout=15)
        if res.status_code == 200:
            print("✅ Telegram 訊息發送成功！")
        else:
            print(f"❌ Telegram 發送失敗 ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Telegram 連線異常: {e}")


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

        # 第二步：使用 Access Token 與 User ID 發送 Push Message
        push_url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "to": LINE_USER_ID,
            "messages":[{"type": "text", "text": text}]
        }
        
        push_res = requests.post(push_url, headers=headers, json=payload, timeout=15)
        if push_res.status_code == 200:
            print("✅ LINE 訊息發送成功！")
        else:
            print(f"❌ LINE 發送失敗 ({push_res.status_code}): {push_res.text}")

    except Exception as e:
        print(f"❌ LINE 連線異常: {e}")

# ==========================================
# 3. 讀取資產清單
# ==========================================
def load_assets():
    try:
        with open(ASSETS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到資產檔案：{ASSETS_FILE}")
        return[]
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤：{e}")
        return[]

# ==========================================
# 4. 資料處理 & HTML 報表產生
# ==========================================
def process_data():
    if not REPORT_PWD:
        print("❌ 錯誤：找不到解鎖密碼 REPORT_PWD 環境變數")
        return None, None, None, None

    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    home_assets = load_assets()
    
    # 按到期日排序
    home_assets = sorted(home_assets, key=lambda x: datetime.strptime(x['purchase_date'], "%Y-%m-%d") + timedelta(days=x['warranty_months'] * 30.44))
    
    app_rows, cons_rows, sub_rows = "", "", ""
    soon_list, expired_list = [],[]
    line_alerts =[] # 專門存給 LINE 的耗材警報
    
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

            # 如果是耗材，且 7 天內到期，加入 LINE 警報清單
            if is_c and rem <= 7:
                if rem < 0:
                    line_alerts.append(f"🔴 {n} (已逾期 {-rem} 天)")
                elif rem == 0:
                    line_alerts.append(f"⚠️ {n} (今天需更換)")
                else:
                    line_alerts.append(f"⚠️ {n} (剩 {rem} 天)")

            # 狀態判斷
            if rem < 0:
                badge_text = "需續訂" if is_s else ("需更換" if is_c else "已過期")
                badge_class, icon = "danger", "🔴"
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

            # 處理費用或收據
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

            row_html = (
                f"<tr><td><div class='item-name'>{n}</div></td><td>{item['purchase_date']}</td>"
                f"<td class='center'>{item['warranty_months']}</td><td>{e_d.strftime('%Y-%m-%d')}</td>"
                f"<td>{days_display}</td><td><span class='badge {badge_class}'>{badge_text}</span></td>{extra_cell}</tr>"
            )

            if is_s: sub_rows += row_html
            elif is_c: cons_rows += row_html
            else: app_rows += row_html
            
        except Exception as e:
            print(f"跳過項目 {item.get('name')}: {e}")
            continue

    update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

    # ---- 內部解密後的 HTML 內容 ----
    report_inner = f"""
    <div class="header"><h1>🏠 Fiona 家務資產儀表板</h1><div class="subtitle">自動追蹤保固 & 耗材更換週期</div></div>
    <div class="summary">
        <div class="summary-card"><div class="num blue">{total_items}</div><div class="label">管理項目</div></div>
        <div class="summary-card"><div class="num green">{safe_count}</div><div class="label">狀態正常</div></div>
        <div class="summary-card"><div class="num orange">{warning_count}</div><div class="label">即將到期</div></div>
        <div class="summary-card"><div class="num red">{danger_count}</div><div class="label">需處理</div></div>
    </div>
    <div class="card">
        <div class="card-header">📦 硬體設備保固</div>
        <div class="table-wrap"><table><thead><tr><th>名稱</th><th>購買日</th><th>月</th><th>到期日</th><th>剩餘</th><th>狀態</th><th>收據</th></tr></thead><tbody>{app_rows}</tbody></table></div>
    </div>
    <div class="card">
        <div class="card-header">♻️ 耗材更換追蹤</div>
        <div class="table-wrap"><table><thead><tr><th>名稱</th><th>更換日</th><th>月</th><th>下次更換</th><th>剩餘</th><th>狀態</th><th>費用</th></tr></thead><tbody>{cons_rows}</tbody></table></div>
    </div>
    <div class="card">
        <div class="card-header">🔔 訂閱服務</div>
        <div class="table-wrap"><table><thead><tr><th>名稱</th><th>訂閱日</th><th>月</th><th>下次續訂</th><th>剩餘</th><th>狀態</th><th>費用</th></tr></thead><tbody>{sub_rows}</tbody></table></div>
    </div>
    <div class="footer">最後更新：{update_time}</div>
    """

    # AES 加密
    salt = urandom(16)
    iv = urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', REPORT_PWD.encode(), salt, 100000, dklen=32)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, report_inner.encode('utf-8'), None)

    e_b64 = base64.b64encode(ciphertext).decode()
    s_b64 = base64.b64encode(salt).decode()
    i_b64 = base64.b64encode(iv).decode()

    # ---- HTML 外部模板 ----
    html_template = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fiona 家務資產儀表板</title>
<style>
    * { box-sizing: border-box; }
    body { font-family: -apple-system, sans-serif; background: linear-gradient(135deg, #667eea, #764ba2); margin: 0; padding: 20px; min-height: 100vh; color: #2d3748; }
    .container { max-width: 920px; margin: auto; }
    .header { text-align: center; margin-bottom: 20px; color: white; }
    .summary { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
    .summary-card { flex: 1; background: white; border-radius: 12px; padding: 15px; text-align: center; min-width: 120px; }
    .num { font-size: 1.5rem; font-weight: bold; }
    .blue { color: #3182ce; } .green { color: #38a169; } .orange { color: #dd6b20; } .red { color: #e53e3e; }
    .card { background: white; border-radius: 12px; margin-bottom: 20px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,.1); }
    .card-header { padding: 15px; font-weight: bold; background: #f7fafc; border-bottom: 1px solid #edf2f7; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th { padding: 12px; text-align: left; background: #edf2f7; color: #718096; }
    td { padding: 12px; border-bottom: 1px solid #f7fafc; white-space: nowrap; }
    .badge { padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }
    .safe { background: #f0fff4; color: #38a169; } .warning { background: #fffaf0; color: #dd6b20; } .danger { background: #fff5f5; color: #e53e3e; }
    .receipt-link { color: #3182ce; cursor: pointer; text-decoration: underline; }
    .login-overlay { position: fixed; inset: 0; background: #667eea; z-index: 999; display: flex; justify-content: center; align-items: center; }
    .login-box { background: white; padding: 40px; border-radius: 15px; text-align: center; }
    #pwdInput { padding: 10px; width: 100%; border: 1px solid #ddd; border-radius: 5px; margin: 15px 0; }
    #loginBtn { padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; width: 100%; }
</style>
</head>
<body>
<div class="login-overlay" id="loginOverlay">
    <div class="login-box"><h2>🔒 需要驗證</h2><input type="password" id="pwdInput" placeholder="密碼"><button id="loginBtn" onclick="checkPwd()">解鎖</button></div>
</div>
<div class="container" id="mainContent"></div>
<div id="lightbox" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.8);z-index:1000;justify-content:center;align-items:center;" onclick="this.style.display='none'"><img id="lbImg" style="max-width:90%;max-height:85%;"></div>
<script>
const E="REPLACE_E", S="REPLACE_S", I="REPLACE_I";
function showReceipt(s){ document.getElementById('lbImg').src=s; document.getElementById('lightbox').style.display='flex'; }
async function checkPwd(){
    try {
        const pw = document.getElementById('pwdInput').value;
        const b2b = (b) => Uint8Array.from(atob(b), c => c.charCodeAt(0));
        const salt=b2b(S), iv=b2b(I), ct=b2b(E);
        const enc = new TextEncoder();
        const km = await crypto.subtle.importKey('raw', enc.encode(pw), 'PBKDF2', false, ['deriveKey']);
        const key = await crypto.subtle.deriveKey({name:'PBKDF2', salt, iterations:100000, hash:'SHA-256'}, km, {name:'AES-GCM', length:256}, false, ['decrypt']);
        const dec = await crypto.subtle.decrypt({name:'AES-GCM', iv}, key, ct);
        document.getElementById('mainContent').innerHTML = new TextDecoder().decode(dec);
        document.getElementById('loginOverlay').style.display = 'none';
    } catch(e) { alert('密碼錯誤'); }
}
document.getElementById('pwdInput').addEventListener('keydown', e => { if(e.key==='Enter') checkPwd(); });
</script>
</body>
</html>"""

    # 執行取代
    final_html = html_template.replace("REPLACE_E", e_b64).replace("REPLACE_S", s_b64).replace("REPLACE_I", i_b64)

    # 寫入檔案
    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    # 👇 新增這行印出提示
    print("✅ 主要報表已更新：docs/index.html") 
    os.makedirs("Daily_Report", exist_ok=True)
    today_str = today.strftime('%Y-%m-%d')
    with open(f"Daily_Report/warranty_{today_str}.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    # 👇 新增這行印出提示
    print(f"✅ 歷史備份已存檔：Daily_Report/warranty_{today_str}.html")
    
    # 處理 receipts 目錄
    if os.path.isdir("receipts"):
        import shutil
        target_receipts = os.path.join("docs", "receipts")
        if os.path.exists(target_receipts): shutil.rmtree(target_receipts)
        shutil.copytree("receipts", target_receipts)

    return soon_list, expired_list, today_str, line_alerts

# ==========================================
# 5. 主程式
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動資產檢查任務 (支援 TG & LINE Bot)...")
    git_branch = os.getenv("GITHUB_REF_NAME", "unknown_branch")

    soon_l, expired_l, d_s, line_alerts = process_data()

    if d_s:
        # 在標題後面加上分支名稱
        parts =[f"<b>🏠 Fiona 家務提醒 {d_s} ({git_branch})</b>"]

        if expired_l or soon_l:
            if expired_l:
                parts.append("\n⛔ <b>已逾期 / 需處理：</b>")
                parts.extend(expired_l)
            if soon_l:
                parts.append("\n⚠️ <b>即將到期 (20天內)：</b>")
                parts.extend(soon_l)
        else:
            parts.append("\n🎉 所有設備及耗材狀態正常！")

        parts.append(f"\n📋 <a href='{REPORT_BASE_URL}'>查看儀表板</a>")
        parts.append(f"⚙️ <a href='{ADMIN_URL}'>管理後台</a>")

        tg_msg = "\n".join(parts)

        # ── 開關控制 ──
        if NOTIFY_TARGET in ("telegram", "both"):
            push_tg_message(tg_msg)

        if NOTIFY_TARGET in ("line", "both"):
            if line_alerts:
                line_msg = "🏠 Fiona 耗材更換提醒\n" + "\n".join(line_alerts)
                push_line_message(line_msg)
            else:
                print("ℹ️ 沒有耗材在一週內到期，略過 LINE 發送。")
