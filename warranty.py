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
    app_rows, cons_rows, sub_rows, soon_list, expired_list, full_list_str = "", "", "", [], [], ""

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

            if rem < 0:
                if is_s:
                    badge_class, badge_text = "danger", "需續訂"
                elif is_c:
                    badge_class, badge_text = "danger", "需更換"
                else:
                    badge_class, badge_text = "expired", "已過期"
                icon = "🔴"
                days_display = '<span class="days-cell danger-text">已逾期</span>'
                expired_list.append(f"🔴 {item['name']} ({badge_text})")
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

            if is_s:
                sub_rows += row
            elif is_c:
                cons_rows += row
            else:
                app_rows += row
            full_list_str += f"{icon} {n} (剩 {max(0, rem)}天)\n"
        except Exception as e:
            print(f"跳過項目 {item.get('name')}: {e}")
            continue

    update_time = datetime.now(tz).strftime('%Y-%m-%d %H:%M')

    # ---- 報表內容（密碼正確後才會顯示）----
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
      <thead><tr><th>名稱</th><th>更換日</th><th>週期(月)</th><th>下次更換</th><th>剩餘</th><th>狀態</th><th>收據</th></tr></thead>
      <tbody>{cons_rows if cons_rows else '<tr><td colspan="7" style="text-align:center;color:#a0aec0;padding:30px">暫無資料</td></tr>'}</tbody>
    </table></div>
  </div>
  <div class="card">
    <div class="card-header"><div class="icon icon-purple">🔔</div>訂閱服務</div>
    <div class="table-wrap"><table>
      <thead><tr><th>名稱</th><th>訂閱日</th><th>週期(月)</th><th>下次續訂</th><th>剩餘</th><th>狀態</th><th>收據</th></tr></thead>
      <tbody>{sub_rows if sub_rows else '<tr><td colspan="7" style="text-align:center;color:#a0aec0;padding:30px">暫無資料</td></tr>'}</tbody>
    </table></div>
  </div>
  <div class="footer">最後更新：{update_time}</div>"""

    # ---- AES 加密報表內容 ----
    import hashlib, base64
    from os import urandom
    password = "vic2026"
    salt = urandom(16)
    iv = urandom(12)
    # 用 PBKDF2 從密碼推導 AES key
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=32)

    # AES-GCM 加密
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)
    plaintext = report_content.encode('utf-8')
    ciphertext = aesgcm.encrypt(iv, plaintext, None)

    encrypted_b64 = base64.b64encode(ciphertext).decode()
    salt_b64 = base64.b64encode(salt).decode()
    iv_b64 = base64.b64encode(iv).decode()

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
    margin: 0; padding: 24px 16px; min-height: 100vh; color: #2d3748;
  }}
  .container {{ max-width: 920px; margin: auto; }}
  .header {{ text-align: center; margin-bottom: 28px; }}
  .header h1 {{ font-size: 1.6rem; color: #fff; margin: 0 0 6px; text-shadow: 0 2px 8px rgba(0,0,0,.15); }}
  .header .subtitle {{ color: rgba(255,255,255,.75); font-size: .85rem; }}
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 14px; margin-bottom: 28px; }}
  .summary-card {{ background: rgba(255,255,255,.95); border-radius: 14px; padding: 18px 14px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,.08); }}
  .summary-card .num {{ font-size: 1.8rem; font-weight: 800; line-height: 1; }}
  .summary-card .label {{ font-size: .75rem; color: #718096; margin-top: 6px; font-weight: 600; text-transform: uppercase; letter-spacing: .5px; }}
  .num.green {{ color: #38a169; }} .num.orange {{ color: #dd6b20; }} .num.red {{ color: #e53e3e; }} .num.blue {{ color: #3182ce; }}
  .card {{ background: #fff; border-radius: 16px; box-shadow: 0 10px 30px rgba(0,0,0,.1); margin-bottom: 24px; overflow: hidden; }}
  .card-header {{ padding: 16px 22px; font-weight: 700; font-size: 1rem; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #edf2f7; }}
  .card-header .icon {{ width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 1.1rem; }}
  .icon-blue {{ background: #ebf4ff; }} .icon-orange {{ background: #fefcbf; }} .icon-purple {{ background: #faf5ff; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: #f7fafc; color: #a0aec0; font-size: .72rem; font-weight: 700; text-transform: uppercase; letter-spacing: .6px; padding: 12px 18px; text-align: left; border-bottom: 2px solid #edf2f7; white-space: nowrap; }}
  td {{ padding: 14px 18px; font-size: .88rem; border-bottom: 1px solid #f7fafc; white-space: nowrap; }}
  tr:last-child td {{ border-bottom: none; }} tr:hover {{ background: #f7fafc; }}
  .item-name {{ font-weight: 600; color: #2d3748; }} .center {{ text-align: center; }}
  .days-cell {{ font-family: 'SF Mono','Monaco','Menlo', monospace; font-weight: 700; font-size: .85rem; color: #2d3748; }}
  .warning-text {{ color: #dd6b20; }} .danger-text {{ color: #e53e3e; }}
  .badge {{ display: inline-block; padding: 5px 14px; border-radius: 50px; font-size: .72rem; font-weight: 700; letter-spacing: .3px; }}
  .safe {{ background: #f0fff4; color: #38a169; }} .warning {{ background: #fffaf0; color: #dd6b20; }}
  .danger {{ background: #fff5f5; color: #e53e3e; }} .expired {{ background: #f7fafc; color: #a0aec0; }}
  .receipt-link {{ display: inline-flex; align-items: center; gap: 4px; padding: 4px 12px; border-radius: 6px; background: #ebf4ff; color: #3182ce; font-size: .78rem; font-weight: 600; text-decoration: none; cursor: pointer; transition: background .2s; }}
  .receipt-link:hover {{ background: #bee3f8; }}
  .no-receipt {{ color: #cbd5e0; font-size: .78rem; }}
  .lightbox {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,.75); z-index: 9999; justify-content: center; align-items: center; cursor: pointer; }}
  .lightbox.active {{ display: flex; }}
  .lightbox img {{ max-width: 90%; max-height: 85%; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,.4); }}
  .lightbox-close {{ position: absolute; top: 20px; right: 28px; color: #fff; font-size: 2rem; cursor: pointer; font-weight: 300; }}
  .footer {{ text-align: center; margin-top: 12px; color: rgba(255,255,255,.6); font-size: .75rem; }}
  .login-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); z-index: 99999; display: flex; justify-content: center; align-items: center; }}
  .login-overlay.hidden {{ display: none; }}
  .login-box {{ background: rgba(255,255,255,.95); border-radius: 20px; padding: 40px 36px; text-align: center; width: 340px; box-shadow: 0 20px 60px rgba(0,0,0,.2); }}
  .login-box h2 {{ margin: 0 0 8px; font-size: 1.3rem; color: #2d3748; }}
  .login-box p {{ margin: 0 0 24px; font-size: .85rem; color: #718096; }}
  .login-box input {{ width: 100%; padding: 12px 16px; border: 2px solid #e2e8f0; border-radius: 10px; font-size: 1rem; outline: none; transition: border-color .2s; }}
  .login-box input:focus {{ border-color: #667eea; }}
  .login-box button {{ width: 100%; margin-top: 14px; padding: 12px; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; border: none; border-radius: 10px; font-size: 1rem; font-weight: 700; cursor: pointer; transition: opacity .2s; }}
  .login-box button:hover {{ opacity: .9; }}
  .login-error {{ color: #e53e3e; font-size: .82rem; margin-top: 10px; display: none; }}
  @media (max-width: 600px) {{ body {{ padding: 16px 10px; }} th, td {{ padding: 10px 12px; font-size: .82rem; }} .summary {{ grid-template-columns: repeat(2, 1fr); gap: 10px; }} .header h1 {{ font-size: 1.3rem; }} }}
</style>
</head>
<body>
<noscript><p style="color:#fff;text-align:center;margin-top:40vh">此報表需要啟用 JavaScript 才能檢視。</p></noscript>

<div class="login-overlay" id="loginOverlay">
  <div class="login-box">
    <h2>🔒 需要驗證</h2>
    <p>請輸入密碼以查看報表</p>
    <input type="password" id="pwdInput" placeholder="輸入密碼" onkeydown="if(event.key==='Enter')checkPwd()">
    <button onclick="checkPwd()">解鎖</button>
    <div class="login-error" id="pwdError">密碼錯誤，請重試</div>
  </div>
</div>

<div class="container" id="mainContent"></div>

<div class="lightbox" id="lightbox" onclick="closeLightbox()">
  <span class="lightbox-close">&times;</span>
  <img id="lightbox-img" src="" alt="收據">
</div>

<script>
function showReceipt(s){{document.getElementById('lightbox-img').src=s;document.getElementById('lightbox').classList.add('active')}}
function closeLightbox(){{document.getElementById('lightbox').classList.remove('active')}}

const E="{encrypted_b64}",S="{salt_b64}",I="{iv_b64}";
function b64(s){{return Uint8Array.from(atob(s),c=>c.charCodeAt(0))}}
async function checkPwd(){{
  try{{
    const pw=document.getElementById('pwdInput').value;
    const salt=b64(S),iv=b64(I),ct=b64(E);
    const km=await crypto.subtle.importKey('raw',new TextEncoder().encode(pw),{{name:'PBKDF2'}},false,['deriveKey']);
    const key=await crypto.subtle.deriveKey({{name:'PBKDF2',salt:salt,iterations:100000,hash:'SHA-256'}},km,{{name:'AES-GCM',length:256}},false,['decrypt']);
    const dec=await crypto.subtle.decrypt({{name:'AES-GCM',iv:iv}},key,ct);
    document.getElementById('mainContent').innerHTML=new TextDecoder().decode(dec);
    document.getElementById('loginOverlay').classList.add('hidden');
  }}catch(e){{
    document.getElementById('pwdError').style.display='block';
    document.getElementById('pwdInput').value='';
    document.getElementById('pwdInput').focus();
  }}
}}
</script>
</body>
</html>"""

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)

    # 存一份到 Daily_Report 目錄，標上日期
    os.makedirs("Daily_Report", exist_ok=True)
    report_date = today.strftime('%Y-%m-%d')
    with open(f"Daily_Report/warranty_{report_date}.html", "w", encoding="utf-8") as f:
        f.write(html)

    # 複製收據資料夾到 docs/ 讓 GitHub Pages 能讀取
    if os.path.isdir("receipts"):
        import shutil
        docs_receipts = os.path.join("docs", "receipts")
        if os.path.isdir(docs_receipts):
            shutil.rmtree(docs_receipts)
        shutil.copytree("receipts", docs_receipts)

    # ---- 生成 Admin 管理頁面 ----
        admin_html = """<!DOCTYPE html>
    <html lang="zh-Hant">
              <head>
              <meta charset="utf-8">
                           <meta name="viewport" content="width=device-width, initial-scale=1.0">
                           <title>管理後台 - 家務資產</title>
                           <style>
                           *,*::before,*::after{box-sizing:border-box}
                           body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f7fafc;margin:0;padding:20px;color:#2d3748}
                           .header{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:20px 24px;border-radius:16px;margin-bottom:24px;display:flex;align-items:center;justify-content:space-between}
                           .header h1{margin:0;font-size:1.4rem}
                           .btn{display:inline-flex;align-items:center;gap:6px;padding:8px 18px;border-radius:8px;border:none;font-size:.9rem;font-weight:600;cursor:pointer;transition:opacity .2s}
                           .btn-primary{background:#667eea;color:#fff}
                           .btn-danger{background:#e53e3e;color:#fff}
                           .btn-success{background:#38a169;color:#fff}
                           .btn-sm{padding:5px 12px;font-size:.8rem}
                           .btn:hover{opacity:.85}
                           .card{background:#fff;border-radius:12px;box-shadow:0 4px 15px rgba(0,0,0,.08);padding:20px;margin-bottom:20px}
                           table{width:100%;border-collapse:collapse}
                           th{background:#f7fafc;color:#718096;font-size:.75rem;font-weight:700;text-transform:uppercase;padding:10px 14px;text-align:left;border-bottom:2px solid #edf2f7}
                           td{padding:12px 14px;font-size:.88rem;border-bottom:1px solid #f7fafc;vertical-align:middle}
                           tr:hover{background:#f7fafc}
                           .badge{display:inline-block;padding:3px 10px;border-radius:50px;font-size:.72rem;font-weight:700}
                           .badge-app{background:#ebf4ff;color:#3182ce}
                           .badge-cons{background:#fefcbf;color:#b7791f}
                           .badge-sub{background:#faf5ff;color:#805ad5}
                           .modal{display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:9999;justify-content:center;align-items:center}
                           .modal.active{display:flex}
                           .modal-box{background:#fff;border-radius:16px;padding:28px;width:480px;max-width:95vw;max-height:90vh;overflow-y:auto}
                           .modal-box h3{margin:0 0 20px;font-size:1.1rem;color:#2d3748}
                           .form-group{margin-bottom:16px}
                           .form-group label{display:block;font-size:.82rem;font-weight:600;color:#4a5568;margin-bottom:6px}
                           .form-group input,.form-group select{width:100%;padding:10px 12px;border:2px solid #e2e8f0;border-radius:8px;font-size:.9rem;outline:none;transition:border-color .2s}
                           .form-group input:focus,.form-group select:focus{border-color:#667eea}
                           .form-row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
                           .modal-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:20px}
                           .token-bar{background:#fff;border-radius:10px;padding:14px 18px;margin-bottom:20px;display:flex;align-items:center;gap:12px;box-shadow:0 2px 8px rgba(0,0,0,.06)}
                           .token-bar input{flex:1;padding:8px 12px;border:2px solid #e2e8f0;border-radius:8px;font-size:.88rem;outline:none}
                           .token-bar input:focus{border-color:#667eea}
                           .status{font-size:.8rem;padding:4px 10px;border-radius:6px}
                           .status.ok{background:#f0fff4;color:#38a169}
                           .status.err{background:#fff5f5;color:#e53e3e}
                           .receipt-thumb{width:40px;height:40px;object-fit:cover;border-radius:6px;cursor:pointer;border:1px solid #e2e8f0}
                           .upload-area{border:2px dashed #cbd5e0;border-radius:8px;padding:16px;text-align:center;cursor:pointer;transition:border-color .2s}
                           .upload-area:hover{border-color:#667eea}
                           .upload-area input{display:none}
                           .upload-preview{margin-top:8px;font-size:.82rem;color:#667eea}
                           #toast{position:fixed;bottom:24px;right:24px;background:#2d3748;color:#fff;padding:12px 20px;border-radius:10px;font-size:.88rem;display:none;z-index:99999;box-shadow:0 4px 15px rgba(0,0,0,.2)}
                           </style>
                           </head>
                           <body>

                           <div class="token-bar">
                             <span style="font-weight:700;color:#4a5568;white-space:nowrap">🔑 GitHub Token</span>
                               <input type="password" id="ghToken" placeholder="ghp_xxxxxxxxxxxx (需要 repo 讀寫權限)">
                                 <button class="btn btn-primary btn-sm" onclick="loadData()">載入</button>
                                   <span id="tokenStatus"></span>
                                   </div>

                                   <div class="header">
                                     <h1>🏠 家務資產管理後台</h1>
                                       <button class="btn btn-success" onclick="openAdd()">＋ 新增項目</button>
                                       </div>

                                       <div class="card" id="tableArea">
                                         <p style="text-align:center;color:#a0aec0;padding:40px 0">請先輸入 GitHub Token 並點擊「載入」</p>
                                         </div>

                                         <!-- 新增/編輯 Modal -->
                                         <div class="modal" id="editModal">
                                           <div class="modal-box">
                                               <h3 id="modalTitle">新增項目</h3>
                                                   <div class="form-group">
                                                         <label>名稱</label>
                                                               <input type="text" id="fName" placeholder="例：iPhone 17 / [耗材] 濾網 / [訂閱] Claude">
                                                                   </div>
                                                                       <div class="form-row">
                                                                             <div class="form-group">
                                                                                     <label>購買/訂閱日期</label>
                                                                                             <input type="date" id="fDate">
                                                                                                   </div>
                                                                                                         <div class="form-group">
                                                                                                                 <label>保固/週期（月）</label>
                                                                                                                         <input type="number" id="fMonths" min="1" placeholder="12">
                                                                                                                               </div>
                                                                                                                                   </div>
                                                                                                                                       <div class="form-group">
                                                                                                                                             <label>收據圖片（選填）</label>
                                                                                                                                                   <div class="upload-area" onclick="document.getElementById('fFile').click()">
                                                                                                                                                           <div>📎 點擊上傳圖片（JPG / PNG / PDF）</div>
                                                                                                                                                                   <div class="upload-preview" id="uploadPreview"></div>
                                                                                                                                                                           <input type="file" id="fFile" accept="image/*,.pdf" onchange="previewFile()">
                                                                                                                                                                                 </div>
                                                                                                                                                                                       <div style="margin-top:8px;font-size:.8rem;color:#a0aec0">或直接輸入現有路徑：</div>
                                                                                                                                                                                             <input type="text" id="fReceipt" placeholder="receipts/xxx.jpg" style="margin-top:6px">
                                                                                                                                                                                                 </div>
                                                                                                                                                                                                     <div class="modal-actions">
                                                                                                                                                                                                           <button class="btn" onclick="closeModal()" style="background:#e2e8f0;color:#4a5568">取消</button>
                                                                                                                                                                                                                 <button class="btn btn-primary" id="saveBtn" onclick="saveItem()">儲存</button>
                                                                                                                                                                                                                     </div>
                                                                                                                                                                                                                       </div>
                                                                                                                                                                                                                       </div>
                                                                                                                                                                                                                       
                                                                                                                                                                                                                       <!-- Lightbox -->
                                                                                                                                                                                                                       <div class="modal" id="lightbox" onclick="this.classList.remove('active')">
                                                                                                                                                                                                                         <img id="lbImg" src="" style="max-width:90%;max-height:85%;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.4)">
                                                                                                                                                                                                                         </div>
                                                                                                                                                                                                                         
                                                                                                                                                                                                                         <div id="toast"></div>
                                                                                                                                                                                                                         
                                                                                                                                                                                                                         <script>
                                                                                                                                                                                                                         const REPO = "gn1179076-wq/Stock_Bot_2";
                                                                                                                                                                                                                         const BRANCH = "main";
                                                                                                                                                                                                                         const FILE_PATH = "home_assets.json";
                                                                                                                                                                                                                         const BASE_URL = "https://gn1179076-wq.github.io/Stock_Bot_2";
                                                                                                                                                                                                                         let assets = [], fileSha = "", editIndex = -1;
                                                                                                                                                                                                                         
                                                                                                                                                                                                                         function token(){return document.getElementById('ghToken').value.trim()}
                                                                                                                                                                                                                         
                                                                                                                                                                                                                         async function apiGet(path){
                                                                                                                                                                                                                           const r = await fetch(`https://api.github.com/repos/${REPO}/${path}`,
                                                                                                                                                                                                                               {headers:{Authorization:`Bearer ${token()}`,Accept:'application/vnd.github+json'}});
                                                                                                                                                                                                                                 if(!r.ok) throw new Error(r.status);
                                                                                                                                                                                                                                   return r.json();
                                                                                                                                                                                                                                   }
                                                                                                                                                                                                                                   async function apiPut(path, body){
                                                                                                                                                                                                                                     const r = await fetch(`https://api.github.com/repos/${REPO}/${path}`,
                                                                                                                                                                                                                                         {method:'PUT',headers:{Authorization:`Bearer ${token()}`,Accept:'application/vnd.github+json','Content-Type':'application/json'},body:JSON.stringify(body)});
                                                                                                                                                                                                                                           if(!r.ok){const e=await r.json();throw new Error(e.message||r.status);}
                                                                                                                                                                                                                                             return r.json();
                                                                                                                                                                                                                                             }
                                                                                                                                                                                                                                             
                                                                                                                                                                                                                                             async function loadData(){
                                                                                                                                                                                                                                               const st = document.getElementById('tokenStatus');
                                                                                                                                                                                                                                                 st.innerHTML='';
                                                                                                                                                                                                                                                   try{
                                                                                                                                                                                                                                                       const data = await apiGet(`contents/${FILE_PATH}?ref=${BRANCH}`);
                                                                                                                                                                                                                                                           fileSha = data.sha;
                                                                                                                                                                                                                                                               const json = atob(data.content.replace(/\\n/g,''));
                                                                                                                                                                                                                                                                   assets = JSON.parse(json);
                                                                                                                                                                                                                                                                       st.innerHTML='<span class="status ok">✓ 已連線</span>';
                                                                                                                                                                                                                                                                           renderTable();
                                                                                                                                                                                                                                                                             }catch(e){
                                                                                                                                                                                                                                                                                 st.innerHTML='<span class="status err">✗ 失敗：'+e.message+'</span>';
                                                                                                                                                                                                                                                                                   }
                                                                                                                                                                                                                                                                                   }
                                                                                                                                                                                                                                                                                   
                                                                                                                                                                                                                                                                                   function renderTable(){
                                                                                                                                                                                                                                                                                     const cats = [
                                                                                                                                                                                                                                                                                         {label:'📦 硬體設備保固', filter:a=>!a.name.includes('[耗材]')&&!a.name.includes('[訂閱]'), badge:'badge-app'},
                                                                                                                                                                                                                                                                                             {label:'♻️ 耗材更換追蹤', filter:a=>a.name.includes('[耗材]'), badge:'badge-cons'},
                                                                                                                                                                                                                                                                                                 {label:'🔔 訂閱服務', filter:a=>a.name.includes('[訂閱]'), badge:'badge-sub'},
                                                                                                                                                                                                                                                                                                   ];
                                                                                                                                                                                                                                                                                                     let html='';
                                                                                                                                                                                                                                                                                                       cats.forEach(cat=>{
                                                                                                                                                                                                                                                                                                           const items=assets.map((a,i)=>({a,i})).filter(({a})=>cat.filter(a));
                                                                                                                                                                                                                                                                                                               if(!items.length) return;
                                                                                                                                                                                                                                                                                                                   html+=`<h3 style="margin:20px 0 10px;font-size:.95rem;color:#4a5568">${cat.label}</h3>
                                                                                                                                                                                                                                                                                                                       <div style="overflow-x:auto"><table>
                                                                                                                                                                                                                                                                                                                           <thead><tr><th>名稱</th><th>日期</th><th>月數</th><th>收據</th><th>操作</th></tr></thead><tbody>`;
                                                                                                                                                                                                                                                                                                                               items.forEach(({a,i})=>{
                                                                                                                                                                                                                                                                                                                                     const rec = a.receipt
                                                                                                                                                                                                                                                                                                                                             ? `<img class="receipt-thumb" src="${BASE_URL}/${a.receipt}" onerror="this.style.display='none'"
                                                                                                                                                                                                                                                                                                                                                         onclick="event.stopPropagation();showLb('${BASE_URL}/${a.receipt}')">`
                                                                                                                                                                                                                                                                                                                                                                 : '<span style="color:#cbd5e0;font-size:.78rem">—</span>';
                                                                                                                                                                                                                                                                                                                                                                       html+=`<tr>
                                                                                                                                                                                                                                                                                                                                                                               <td><strong>${a.name}</strong></td>
                                                                                                                                                                                                                                                                                                                                                                                       <td>${a.purchase_date}</td>
                                                                                                                                                                                                                                                                                                                                                                                               <td style="text-align:center">${a.warranty_months}</td>
                                                                                                                                                                                                                                                                                                                                                                                                       <td>${rec}</td>
                                                                                                                                                                                                                                                                                                                                                                                                               <td><button class="btn btn-primary btn-sm" onclick="openEdit(${i})">✏️</button>
                                                                                                                                                                                                                                                                                                                                                                                                                           <button class="btn btn-danger btn-sm" style="margin-left:6px" onclick="deleteItem(${i})">🗑️</button></td>
                                                                                                                                                                                                                                                                                                                                                                                                                                 </tr>`;
                                                                                                                                                                                                                                                                                                                                                                                                                                     });
                                                                                                                                                                                                                                                                                                                                                                                                                                         html+='</tbody></table></div>';
                                                                                                                                                                                                                                                                                                                                                                                                                                           });
                                                                                                                                                                                                                                                                                                                                                                                                                                             document.getElementById('tableArea').innerHTML=html||'<p style="text-align:center;color:#a0aec0;padding:20px">暫無資料</p>';
                                                                                                                                                                                                                                                                                                                                                                                                                                             }
                                                                                                                                                                                                                                                                                                                                                                                                                                             
                                                                                                                                                                                                                                                                                                                                                                                                                                             function openAdd(){
                                                                                                                                                                                                                                                                                                                                                                                                                                               editIndex=-1;
                                                                                                                                                                                                                                                                                                                                                                                                                                                 document.getElementById('modalTitle').textContent='新增項目';
                                                                                                                                                                                                                                                                                                                                                                                                                                                   document.getElementById('fName').value='';
                                                                                                                                                                                                                                                                                                                                                                                                                                                     document.getElementById('fDate').value=new Date().toISOString().slice(0,10);
                                                                                                                                                                                                                                                                                                                                                                                                                                                       document.getElementById('fMonths').value='12';
                                                                                                                                                                                                                                                                                                                                                                                                                                                         document.getElementById('fReceipt').value='';
                                                                                                                                                                                                                                                                                                                                                                                                                                                           document.getElementById('fFile').value='';
                                                                                                                                                                                                                                                                                                                                                                                                                                                             document.getElementById('uploadPreview').textContent='';
                                                                                                                                                                                                                                                                                                                                                                                                                                                               document.getElementById('editModal').classList.add('active');
                                                                                                                                                                                                                                                                                                                                                                                                                                                               }
                                                                                                                                                                                                                                                                                                                                                                                                                                                               function openEdit(i){
                                                                                                                                                                                                                                                                                                                                                                                                                                                                 editIndex=i;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                   const a=assets[i];
                                                                                                                                                                                                                                                                                                                                                                                                                                                                     document.getElementById('modalTitle').textContent='編輯項目';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                       document.getElementById('fName').value=a.name;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                         document.getElementById('fDate').value=a.purchase_date;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                           document.getElementById('fMonths').value=a.warranty_months;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                             document.getElementById('fReceipt').value=a.receipt||'';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                               document.getElementById('fFile').value='';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 document.getElementById('uploadPreview').textContent='';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   document.getElementById('editModal').classList.add('active');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   function closeModal(){document.getElementById('editModal').classList.remove('active')}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   function previewFile(){
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     const f=document.getElementById('fFile').files[0];
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       if(f){
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           document.getElementById('uploadPreview').textContent='已選：'+f.name;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               document.getElementById('fReceipt').value='receipts/'+f.name;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 async function uploadFile(){
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   const fileInput=document.getElementById('fFile');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     const f=fileInput.files[0];
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       if(!f) return null;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         return new Promise((resolve,reject)=>{
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             const reader=new FileReader();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 reader.onload=async e=>{
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       const b64=e.target.result.split(',')[1];
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             const path=`receipts/${f.name}`;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   try{
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           let sha='';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   try{const ex=await apiGet(`contents/${path}`);sha=ex.sha;}catch(e){}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           await apiPut(`contents/${path}`,{message:`Upload receipt: ${f.name}`,content:b64,sha:sha||undefined,branch:BRANCH});
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   resolve(path);
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         }catch(err){reject(err);}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             };
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 reader.readAsDataURL(f);
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   });
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   async function saveItem(){
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     const btn=document.getElementById('saveBtn');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       btn.disabled=true; btn.textContent='儲存中...';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         try{
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             let receiptPath=document.getElementById('fReceipt').value.trim();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 if(document.getElementById('fFile').files[0]){
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       toast('上傳收據中...');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             receiptPath=await uploadFile();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     const item={
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           name:document.getElementById('fName').value.trim(),
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 purchase_date:document.getElementById('fDate').value,
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       warranty_months:parseInt(document.getElementById('fMonths').value)||12,
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           };
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               if(receiptPath) item.receipt=receiptPath;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   if(!item.name||!item.purchase_date){alert('請填寫名稱和日期');return;}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       if(editIndex>=0) assets[editIndex]=item;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           else assets.push(item);
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               await commitAssets('Update home_assets.json');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   closeModal();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       renderTable();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           toast('✅ 已儲存！');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             }catch(e){toast('❌ 錯誤：'+e.message);}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               finally{btn.disabled=false;btn.textContent='儲存';}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               async function deleteItem(i){
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 if(!confirm(`確定要刪除「${assets[i].name}」？`)) return;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   assets.splice(i,1);
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     try{
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         await commitAssets('Delete item from home_assets.json');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             renderTable();
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 toast('✅ 已刪除！');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   }catch(e){toast('❌ 錯誤：'+e.message);}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   async function commitAssets(msg){
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     const content=btoa(unescape(encodeURIComponent(JSON.stringify(assets,null,4))));
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       const result=await apiPut(`contents/${FILE_PATH}`,{message:msg,content,sha:fileSha,branch:BRANCH});
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         fileSha=result.content.sha;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         function showLb(src){document.getElementById('lbImg').src=src;document.getElementById('lightbox').classList.add('active')}
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         let toastTimer;
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         function toast(msg){
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           const el=document.getElementById('toast');
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             el.textContent=msg;el.style.display='block';
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               clearTimeout(toastTimer);
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 toastTimer=setTimeout(()=>el.style.display='none',3000);
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 }
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 </script>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 </body>
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 </html>"""
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     with open("docs/admin.html", "w", encoding="utf-8") as f:
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             f.write(admin_html)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             
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
