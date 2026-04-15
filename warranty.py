# -*- coding: utf-8 -*-
import requests
import os
import json
from datetime import datetime, timedelta, timezone

# ==========================================
# 1. 取得 Token
# ==========================================
def get_channel_access_token():
    long_lived_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if long_lived_token:
        print("✅ 使用長期 Channel Access Token")
        return long_lived_token

    cid = os.getenv("LINE_CHANNEL_ID")
    csecret = os.getenv("LINE_CHANNEL_SECRET")
    if not cid or not csecret:
        print("❌ 錯誤：請設定 LINE_CHANNEL_ACCESS_TOKEN 或 LINE_CHANNEL_ID + LINE_CHANNEL_SECRET")
        return None

    url = "https://api.line.me/v2/oauth/accessToken"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {"grant_type": "client_credentials", "client_id": cid, "client_secret": csecret}
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


# ==========================================
# 2. 讀取家務資產清單 (從 JSON 檔案)
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
# 3. 資料處理 & HTML 報表
# ==========================================
def process_data():
    tz = timezone(timedelta(hours=8))
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    home_assets = load_assets()
    app_rows, cons_rows, soon_list, expired_list, full_list_str = "", "", [], [], ""

    # 統計數據
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
                badge_class = "danger" if is_c else "expired"
                badge_text = "需更換" if is_c else "已過期"
                icon = "🔴"
                days_display = '<span class="days-cell danger-text">已逾期</span>'
                expired_list.append(f"🔴 {item['name']} ({'需更換' if is_c else '已過期'})")
                danger_count += 1
            elif rem <= 20:
                badge_class = "warning"
                badge_text = "即將到期"
                icon = "⚠️"
                days_display = f'<span class="days-cell warning-text">{rem} 天</span>'
                soon_list.append(f"🔸 {item['name']} (剩 {rem} 天)")
                warning_count += 1
            else:
                badge_class = "safe"
                badge_text = "正常"
                icon = "✅"
                days_display = f'<span class="days-cell">{rem} 天</span>'
                safe_count += 1

            # 收據連結（圖片彈出大圖，PDF 開新分頁）
            receipt = item.get('receipt', '')
            if receipt:
                if receipt.lower().endswith('.pdf'):
                    receipt_cell = f"<td><a class='receipt-link' href='{receipt}' target='_blank'>📄 PDF</a></td>"
                else:
                    receipt_cell = f"<td><a class='receipt-link' onclick=\"showReceipt('{receipt}')\">📎 查看</a></td>"
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

            if is_c:
                cons_rows += row
            else:
                app_rows += row
            full_list_str += f"{icon} {n} (剩 {max(0, rem)}天)\n"
        except Exception as e:
            print(f"跳過項目 {item.get('name')}: {e}")
            continue

    update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fiona 家務資產儀表板</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    margin: 0; padding: 24px 16px;
    min-height: 100vh;
    color: #2d3748;
  }}

  .container {{ max-width: 920px; margin: auto; }}

  /* ---- Header ---- */
  .header {{
    text-align: center; margin-bottom: 28px;
  }}
  .header h1 {{
    font-size: 1.6rem; color: #fff; margin: 0 0 6px;
    text-shadow: 0 2px 8px rgba(0,0,0,.15);
  }}
  .header .subtitle {{
    color: rgba(255,255,255,.75); font-size: .85rem;
  }}

  /* ---- Summary Cards ---- */
  .summary {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 14px;
    margin-bottom: 28px;
  }}
  .summary-card {{
    background: rgba(255,255,255,.95);
    border-radius: 14px;
    padding: 18px 14px;
    text-align: center;
    box-shadow: 0 4px 15px rgba(0,0,0,.08);
    backdrop-filter: blur(10px);
  }}
  .summary-card .num {{
    font-size: 1.8rem; font-weight: 800; line-height: 1;
  }}
  .summary-card .label {{
    font-size: .75rem; color: #718096; margin-top: 6px; font-weight: 600;
    text-transform: uppercase; letter-spacing: .5px;
  }}
  .num.green  {{ color: #38a169; }}
  .num.orange {{ color: #dd6b20; }}
  .num.red    {{ color: #e53e3e; }}
  .num.blue   {{ color: #3182ce; }}

  /* ---- Table Card ---- */
  .card {{
    background: #fff;
    border-radius: 16px;
    box-shadow: 0 10px 30px rgba(0,0,0,.1);
    margin-bottom: 24px;
    overflow: hidden;
  }}
  .card-header {{
    padding: 16px 22px;
    font-weight: 700; font-size: 1rem;
    display: flex; align-items: center; gap: 10px;
    border-bottom: 1px solid #edf2f7;
  }}
  .card-header .icon {{
    width: 36px; height: 36px; border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.1rem;
  }}
  .icon-blue  {{ background: #ebf4ff; }}
  .icon-orange {{ background: #fefcbf; }}

  .table-wrap {{ overflow-x: auto; }}

  table {{
    width: 100%; border-collapse: collapse;
  }}
  th {{
    background: #f7fafc; color: #a0aec0;
    font-size: .72rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: .6px;
    padding: 12px 18px; text-align: left;
    border-bottom: 2px solid #edf2f7;
    white-space: nowrap;
  }}
  td {{
    padding: 14px 18px; font-size: .88rem;
    border-bottom: 1px solid #f7fafc;
    white-space: nowrap;
  }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover {{ background: #f7fafc; }}

  .item-name {{ font-weight: 600; color: #2d3748; }}
  .center {{ text-align: center; }}

  .days-cell {{
    font-family: 'SF Mono', 'Monaco', 'Menlo', monospace;
    font-weight: 700; font-size: .85rem; color: #2d3748;
  }}
  .warning-text {{ color: #dd6b20; }}
  .danger-text  {{ color: #e53e3e; }}

  /* ---- Badges ---- */
  .badge {{
    display: inline-block;
    padding: 5px 14px; border-radius: 50px;
    font-size: .72rem; font-weight: 700;
    letter-spacing: .3px;
  }}
  .safe    {{ background: #f0fff4; color: #38a169; }}
  .warning {{ background: #fffaf0; color: #dd6b20; }}
  .danger  {{ background: #fff5f5; color: #e53e3e; }}
  .expired {{ background: #f7fafc; color: #a0aec0; }}

  /* ---- Receipt ---- */
  .receipt-link {{
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 12px; border-radius: 6px;
    background: #ebf4ff; color: #3182ce;
    font-size: .78rem; font-weight: 600;
    text-decoration: none; cursor: pointer;
    transition: background .2s;
  }}
  .receipt-link:hover {{ background: #bee3f8; }}
  .no-receipt {{ color: #cbd5e0; font-size: .78rem; }}
  .lightbox {{
    display: none; position: fixed; top: 0; left: 0;
    width: 100%; height: 100%;
    background: rgba(0,0,0,.75);
    z-index: 9999;
    justify-content: center; align-items: center; cursor: pointer;
  }}
  .lightbox.active {{ display: flex; }}
  .lightbox img {{ max-width: 90%; max-height: 85%; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,.4); }}
  .lightbox-close {{ position: absolute; top: 20px; right: 28px; color: #fff; font-size: 2rem; cursor: pointer; font-weight: 300; }}

  /* ---- Footer ---- */
  .footer {{
    text-align: center; margin-top: 12px;
    color: rgba(255,255,255,.6); font-size: .75rem;
  }}

  /* ---- Password Protection ---- */
  .login-overlay {{
    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    z-index: 99999;
    display: flex; justify-content: center; align-items: center;
  }}
  .login-overlay.hidden {{ display: none; }}
  .login-box {{
    background: rgba(255,255,255,.95); border-radius: 20px;
    padding: 40px 36px; text-align: center; width: 340px;
    box-shadow: 0 20px 60px rgba(0,0,0,.2);
  }}
  .login-box h2 {{ margin: 0 0 8px; font-size: 1.3rem; color: #2d3748; }}
  .login-box p {{ margin: 0 0 24px; font-size: .85rem; color: #718096; }}
  .login-box input {{
    width: 100%; padding: 12px 16px; border: 2px solid #e2e8f0;
    border-radius: 10px; font-size: 1rem; outline: none;
    transition: border-color .2s;
  }}
  .login-box input:focus {{ border-color: #667eea; }}
  .login-box button {{
    width: 100%; margin-top: 14px; padding: 12px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: #fff; border: none; border-radius: 10px;
    font-size: 1rem; font-weight: 700; cursor: pointer;
    transition: opacity .2s;
  }}
  .login-box button:hover {{ opacity: .9; }}
  .login-error {{ color: #e53e3e; font-size: .82rem; margin-top: 10px; display: none; }}

  /* ---- Responsive ---- */
  @media (max-width: 600px) {{
    body {{ padding: 16px 10px; }}
    th, td {{ padding: 10px 12px; font-size: .82rem; }}
    .summary {{ grid-template-columns: repeat(2, 1fr); gap: 10px; }}
    .header h1 {{ font-size: 1.3rem; }}
  }}
</style>
</head>
<body>

<!-- 密碼保護 -->
<div class="login-overlay" id="loginOverlay">
  <div class="login-box">
    <h2>🔒 需要驗證</h2>
    <p>請輸入密碼以查看報表</p>
    <input type="password" id="pwdInput" placeholder="輸入密碼" onkeydown="if(event.key==='Enter')checkPwd()">
    <button onclick="checkPwd()">解鎖</button>
    <div class="login-error" id="pwdError">密碼錯誤，請重試</div>
  </div>
</div>

<div class="container" id="mainContent" style="display:none">

  <div class="header">
    <h1>🏠 Fiona 家務資產儀表板</h1>
    <div class="subtitle">自動追蹤保固 &amp; 耗材更換週期</div>
  </div>

  <div class="summary">
    <div class="summary-card">
      <div class="num blue">{total_items}</div>
      <div class="label">管理項目</div>
    </div>
    <div class="summary-card">
      <div class="num green">{safe_count}</div>
      <div class="label">狀態正常</div>
    </div>
    <div class="summary-card">
      <div class="num orange">{warning_count}</div>
      <div class="label">即將到期</div>
    </div>
    <div class="summary-card">
      <div class="num red">{danger_count}</div>
      <div class="label">需處理</div>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <div class="icon icon-blue">📦</div>
      硬體設備保固
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>名稱</th><th>購買日</th><th>保固(月)</th><th>到期日</th><th>剩餘</th><th>狀態</th><th>收據</th></tr></thead>
        <tbody>{app_rows if app_rows else '<tr><td colspan="7" style="text-align:center;color:#a0aec0;padding:30px">暫無資料</td></tr>'}</tbody>
      </table>
    </div>
  </div>

  <div class="card">
    <div class="card-header">
      <div class="icon icon-orange">♻️</div>
      耗材更換追蹤
    </div>
    <div class="table-wrap">
      <table>
        <thead><tr><th>名稱</th><th>更換日</th><th>週期(月)</th><th>下次更換</th><th>剩餘</th><th>狀態</th><th>收據</th></tr></thead>
        <tbody>{cons_rows if cons_rows else '<tr><td colspan="7" style="text-align:center;color:#a0aec0;padding:30px">暫無資料</td></tr>'}</tbody>
      </table>
    </div>
  </div>

  <div class="footer">最後更新：{update_time}</div>

</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <span class="lightbox-close">&times;</span>
  <img id="lightbox-img" src="" alt="收據">
</div>

<script>
const HASH = '4c6f4f2eb1b43c025e7efe4ae31a0a9e920c428aa014ba5babcf4eb42c60c552b802241fb4a1cecd319e97326084c274';
async function sha384(str) {{
  const buf = await crypto.subtle.digest('SHA-384', new TextEncoder().encode(str));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,'0')).join('');
}}
async function checkPwd() {{
  const input = document.getElementById('pwdInput').value;
  const hash = await sha384(input);
  if (hash === HASH) {{
    document.getElementById('loginOverlay').classList.add('hidden');
    document.getElementById('mainContent').style.display = '';
  }} else {{
    document.getElementById('pwdError').style.display = 'block';
    document.getElementById('pwdInput').value = '';
    document.getElementById('pwdInput').focus();
  }}
}}
function showReceipt(src) {{
  document.getElementById('lightbox-img').src = src;
  document.getElementById('lightbox').classList.add('active');
}}
function closeLightbox() {{
  document.getElementById('lightbox').classList.remove('active');
}}
</script>
</body>
</html>"""

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    # 複製收據資料夾到 docs/ 讓 GitHub Pages 能讀取
    if os.path.isdir("receipts"):
        import shutil
        docs_receipts = os.path.join("docs", "receipts")
        if os.path.isdir(docs_receipts):
            shutil.rmtree(docs_receipts)
        shutil.copytree("receipts", docs_receipts)

    return soon_list, expired_list, full_list_str, today.strftime('%Y-%m-%d')


# ==========================================
# 4. LINE 推播訊息
# ==========================================
def push_message(token, text):
    user_id = os.getenv("LINE_USER_ID")
    if not user_id or not token:
        print("❌ 缺少 Token 或 LINE_USER_ID")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}]
    }

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            print("✅ LINE 訊息發送成功！")
        else:
            print(f"❌ 發送失敗 ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ 網路連線錯誤: {e}")


# ==========================================
# 5. 主程式
# ==========================================
REPORT_BASE_URL = "https://gn1179076-wq.github.io/Stock_Bot_2/"

if __name__ == "__main__":
    # 加時間戳破快取
    cache_bust = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d%H%M')
    REPORT_URL = f"{REPORT_BASE_URL}?t={cache_bust}"
    print("🚀 啟動資產檢查任務...")
    soon_l, expired_l, full_list_str, d_s = process_data()
    token = get_channel_access_token()

    if token:
        # 只在有「已到期」或「即將到期」項目時才發送 LINE 通知
        if expired_l or soon_l:
            parts = [f"【Fiona 家務提醒 {d_s}】"]

            if expired_l:
                parts.append("⛔ 已到期 / 需更換：")
                parts.append("\n".join(expired_l))

            if soon_l:
                parts.append("⚠️ 即將到期（20天內）：")
                parts.append("\n".join(soon_l))

            parts.append(f"📋 完整報告：{REPORT_URL}")

            msg_text = "\n------------------\n".join(parts)
            push_message(token, msg_text)
        else:
            msg_text = f"【Fiona 家務提醒 {d_s}】\n🎉 所有設備及耗材狀態正常！\n------------------\n📋 完整報告：{REPORT_URL}"
            push_message(token, msg_text)
    else:
        print("❌ 任務失敗：無法取得 Token")
