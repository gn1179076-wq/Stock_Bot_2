# -*- coding: utf-8 -*-
import yfinance as yf
import requests
import os
import math
import json
import hashlib
import base64
import re  
from os import urandom
from datetime import datetime, timedelta, timezone
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
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")  # ← 加這行
REPORT_PWD = os.getenv("REPORT_PWD")  # <--- 報表解鎖密碼

# --- 一般設定 (可以直接在這裡修改) ---
NOTIFY_TARGET = "discord"  # 👉 在此修改推播目標："telegram" / "line" / "both"
REPORT_BASE_URL = "https://gn1179076-wq.github.io/Stock_Bot_2/portfolio.html"
PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到持股檔案：{PORTFOLIO_FILE}")
        return[]
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤：{e}")
        return[]

# ==========================================
# 2. Telegram 推播函式
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
        res = requests.post(url, json=payload, timeout=30)
        if res.status_code == 200:
            print("✅ Telegram 股票日報發送成功！")
        else:
            print(f"❌ Telegram 發送失敗 ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Telegram 連線異常: {e}")

# ==========================================
# 3. LINE 推播函式 (自動取得 Token + 拔除 HTML 標籤)
# ==========================================
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

        # 第二步：過濾掉 HTML 標籤 (因為 LINE 不支援 Telegram 的 HTML 標籤)
        clean_text = re.sub('<.*?>', '', text)

        # 第三步：發送訊息
        push_url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "to": LINE_USER_ID,
            "messages":[{"type": "text", "text": clean_text}]
        }
        
        push_res = requests.post(push_url, headers=headers, json=payload, timeout=15)
        if push_res.status_code == 200:
            print("✅ LINE 股票日報發送成功！")
        else:
            print(f"❌ LINE 發送失敗 ({push_res.status_code}): {push_res.text}")

    except Exception as e:
        print(f"❌ LINE 連線異常: {e}")

# ==========================================
# 4. Discord 推播函式
# ==========================================
def push_discord_message(text):
    if not DISCORD_WEBHOOK_URL:
        return

    is_danger = any(icon in text for icon in ["📉", "🔴", "⛔"])
    embed_color = 15158332 if is_danger else 3066993
    
    # 1. 徹底拔除內容中的所有 HTML 連結文字，確保數據純淨
    clean_text = re.sub(r'<a href=[\'"]([^\'"]+)[\'"]>(.*?)</a>', '', text)
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    
    redundant_texts = ["📋 查看儀表板", "📋 查看完整投資組合儀表板", "⚙️ 管理後台"]
    for rt in redundant_texts:
        clean_text = clean_text.replace(rt, "")

    # 2. 關鍵改動：不使用 title/url 欄位，把連結藏在 description 第一行並加 < >
    # 這樣 Discord 就不會抓取 Favicon 圖示，也不會產生底部預覽
    display_text = f"📊 **[點我進入完整儀表板](<{REPORT_BASE_URL}>)**\n\n" + clean_text.strip()

    payload = {
        "username": "Fiona 智慧管家",
        "avatar_url": "https://github.com/fluidicon.png", 
        "embeds": [{
            "description": display_text, # 連結在這裡，且有 < > 保護
            "color": embed_color,
            "fields": [
                {
                    "name": "🌐 運行分支", 
                    "value": f"`{os.getenv('GITHUB_REF_NAME', 'main')}`", 
                    "inline": True
                },
                {
                    "name": "⚙️ 任務來源", 
                    "value": f"`{os.getenv('GITHUB_WORKFLOW', 'Manual')}`", 
                    "inline": True
                }
            ],
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat()
        }]
    }

    try:
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=15)
    except Exception as e:
        print(f"❌ Discord 連線異常: {e}")
        
# ==========================================
# 4. 抓取資料 & 產生報表
# ==========================================
def get_stock_summary(report_url, git_branch="unknown_branch"):
    print("正在分析資產狀況與黃金價格...")
    portfolio_data = load_portfolio()
    rates = {"US": 32.5, "HK": 4.15, "JP": 0.21, "TW": 1.0}
    gold_usd = 0.0
    gold_twd_per_mace = 0.0
    try:
        data = yf.download(["USDTWD=X", "HKDTWD=X", "JPYTWD=X", "GC=F"], period="5d", progress=False, timeout=30, threads=False)
        if not data.empty:
            last_data = data['Close'].ffill().iloc[-1]
            if not math.isnan(last_data.get("USDTWD=X", float('nan'))): rates["US"] = float(last_data["USDTWD=X"])
            if not math.isnan(last_data.get("HKDTWD=X", float('nan'))): rates["HK"] = float(last_data["HKDTWD=X"])
            if not math.isnan(last_data.get("JPYTWD=X", float('nan'))): rates["JP"] = float(last_data["JPYTWD=X"])
            gold_usd_raw = last_data.get("GC=F", 0)
            if not math.isnan(gold_usd_raw):
                gold_usd = float(gold_usd_raw)
                gold_twd_per_mace = (gold_usd / 31.1035 * 3.75) * rates["US"]
    except Exception as e:
        print(f"匯率或金價抓取失敗: {e}")

    DEFAULT_RATES = {"US": 32.5, "HK": 4.15, "JP": 0.21, "TW": 1.0}
    for k, v in DEFAULT_RATES.items():
        r = rates.get(k)
        if r is None or (isinstance(r, float) and (r == 0 or math.isnan(r))):
            rates[k] = v

    total_cost, total_value = 0.0, 0.0
    loss_details = ""
    html_rows = ""
    for item in portfolio_data:
        try:
            stock = yf.Ticker(item['ticker'])
            hist = stock.history(period="5d", timeout=30)
            current = hist['Close'].ffill().iloc[-1] if not hist.empty else item['cost_price']
            rate = rates.get(item['market'], 1.0)
            c_twd = item['shares'] * item['cost_price'] * rate
            v_twd = item['shares'] * current * rate
            total_cost += c_twd
            total_value += v_twd
            roi = ((v_twd - c_twd) / c_twd) * 100 if c_twd != 0 else 0
            symbol = {"US": "$", "HK": "HK$", "JP": "¥", "TW": "$"}.get(item['market'], "$")
            if roi < 0:
                loss_amt = int(v_twd - c_twd)
                loss_details += f"📉 <b>{item['name']}</b>\n  <code>{symbol}{item['cost_price']:,.2f} → {symbol}{current:,.2f}</code> (<b>{roi:.1f}%</b> / {loss_amt:,})\n"
            display_name = item['name'].split(' ', 1)[-1] if ' ' in item['name'] else item['name']
            market_tag_class = {"TW": "tag-tw", "US": "tag-us", "HK": "tag-hk", "JP": "tag-jp"}.get(item['market'], "tag-tw")
            badge_class = "badge-up" if roi >= 0 else "badge-down"
            profit_amt = int(v_twd - c_twd)
            profit_color = "text-green" if profit_amt >= 0 else "text-red"
            html_rows += (
                "<tr>"
                f"<td><div class='stock-name'>{display_name}</div><div class='stock-ticker'>{item['ticker']}</div></td>"
                f"<td><span class='market-tag {market_tag_class}'>{item['market']}</span></td>"
                f"<td class='right mono'>{item['shares']:,}</td>"
                f"<td class='right mono'>{symbol}{item['cost_price']:,.2f}</td>"
                f"<td class='right mono'>{symbol}{current:,.2f}</td>"
                f"<td class='right mono'>${int(v_twd):,}</td>"
                f"<td class='right mono {profit_color}'>{profit_amt:+,}</td>"
                f"<td class='right'><span class='badge {badge_class}'>{roi:+.1f}%</span></td>"
                "</tr>"
            )
        except Exception as e:
            print(f"處理出錯: {e}")
            continue

    profit_total = total_value - total_cost
    roi_total = (profit_total / total_cost) * 100 if total_cost > 0 else 0
    total_icon = "🔴" if profit_total >= 0 else "🟢"
    tw_tz = timezone(timedelta(hours=8))
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M')
    gold_display = f"${int(gold_twd_per_mace):,}" if gold_twd_per_mace > 0 else "暫無資料"
    jp_rate = rates.get('JP', 0)
    jpy_per_twd = (1 / jp_rate) if jp_rate else 0

    tg_msg = f"""<b>📊 Fiona 持股資產日報 ({git_branch})</b>
📅 {current_time}
--------------------------
🟡 國際金價: <code>${gold_usd:.1f}</code>
💰 台灣金價: <code>{gold_display}</code> (錢)
💱 美元匯率: <code>{rates['US']:.2f}</code>
💴 日圓匯率: 1 TWD = <code>{jpy_per_twd:.2f}</code> JPY
--------------------------
💰 總投入: <code>${int(total_cost):,}</code>
📈 總現值: <code>${int(total_value):,}</code>
🔥 總損益: <b>{int(profit_total):+,}</b> ({total_icon} <b>{roi_total:+.2f}%</b>)
--------------------------
{'🟢 <b>持股虧損清單：</b>' if loss_details else '🎉 全部持股皆為正報酬！'}
{loss_details}
📋 <a href='{report_url}'>查看完整投資組合儀表板</a>
--------------------------
💳 信用卡繳款日提醒
🏦 國泰世華｜每月 2 日（自動扣繳）
🏦 玉山信用卡｜每月 3～5 日
🏦 台北富邦｜每月 9～12 日
🏦 中國信託｜每月 28 日
🏦 星展銀行｜請登入 DBS Card+ 確認"""

    generate_html_report(html_rows, gold_usd, gold_display, rates, total_cost, total_value, profit_total, roi_total, current_time)
    return tg_msg


def generate_html_report(rows, g_usd, g_twd, rates, t_cost, t_value, p_total, r_total, c_time):
    profit_color = "text-green" if p_total >= 0 else "text-red"
    report_inner = f"""
    <div class="header"><h1>📊 Fiona 資產日報</h1><div class="time">{c_time}</div></div>
    <div class="gold-bar">
      <div class="gold-item"><div class="gold-label">🟡 國際金價</div><div class="gold-value">${g_usd:,.1f} USD</div></div>
      <div class="gold-item"><div class="gold-label">💰 台灣金價</div><div class="gold-value">{g_twd} TWD/錢</div></div>
      <div class="gold-item"><div class="gold-label">💱 USD/TWD</div><div class="gold-value">{rates['US']:.2f}</div></div>
      <div class="gold-item"><div class="gold-label">💴 TWD → JPY</div><div class="gold-value">{1 / rates['JP']:.2f}</div></div>
    </div>
    <div class="summary">
      <div class="summary-card"><div class="label">總投入</div><div class="value">${int(t_cost):,}</div></div>
      <div class="summary-card"><div class="label">總現值</div><div class="value">${int(t_value):,}</div></div>
      <div class="summary-card"><div class="label">總損益</div><div class="value {profit_color}">{p_total:+,.0f}</div><div class="sub {profit_color}">{r_total:+.2f}%</div></div>
    </div>
    <div class="card"><div class="card-header">📈 持股明細</div><div class="table-wrap"><table>
      <thead><tr><th>股票</th><th>市場</th><th class="right">股數</th><th class="right">成本</th><th class="right">現價</th><th class="right">現值</th><th class="right">損益</th><th class="right">報酬</th></tr></thead>
      <tbody>{rows}</tbody></table></div></div>
    """

    salt = urandom(16)
    iv = urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', REPORT_PWD.encode(), salt, 100000, dklen=32)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, report_inner.encode('utf-8'), None)
    s_b64 = base64.b64encode(salt).decode()
    i_b64 = base64.b64encode(iv).decode()
    c_b64 = base64.b64encode(ciphertext).decode()

    html_template = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Fiona 資產日報</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0d1117; color: #c9d1d9; font-family: 'Segoe UI', sans-serif; min-height: 100vh; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    #login-screen { background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 40px; width: 320px; text-align: center; }
    #pwd-input { width: 100%; padding: 10px; background: #0d1117; border: 1px solid #30363d; border-radius: 6px; color: #c9d1d9; font-size: 16px; margin-bottom: 12px; }
    #login-btn { width: 100%; padding: 10px; background: #238636; border: none; border-radius: 6px; color: white; cursor: pointer; }
    #error-msg { color: #f85149; margin-top: 10px; font-size: 14px; }
    #report { display: none; width: 100%; max-width: 1000px; padding: 20px; }
    .header { text-align: center; margin-bottom: 20px; }
    .gold-bar, .summary { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
    .gold-item, .summary-card { flex: 1; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; min-width: 140px; }
    .gold-value, .value { font-size: 18px; font-weight: bold; }
    .text-green { color: #3fb950; } .text-red { color: #f85149; }
    .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; overflow: hidden; }
    .card-header { padding: 12px 16px; background: #21262d; font-weight: bold; color: #58a6ff; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 14px; }
    th { background: #21262d; color: #8b949e; padding: 10px 12px; text-align: left; }
    td { padding: 10px 12px; border-top: 1px solid #21262d; }
    .right { text-align: right; } .mono { font-family: monospace; }
    .badge { padding: 3px 8px; border-radius: 10px; font-weight: bold; }
    .badge-up { background: #1f4e3d; color: #3fb950; } .badge-down { background: #4a1e1e; color: #f85149; }
    .market-tag { padding: 2px 6px; border-radius: 4px; font-size: 11px; }
    .tag-tw { background: #1f4e3d; color: #3fb950; } .tag-us { background: #1a3a5c; color: #58a6ff; }
  </style>
</head>
<body>
  <div id="login-screen">
    <h2 style="color:#58a6ff;margin-bottom:20px;">🔐 請輸入密碼</h2>
    <input type="password" id="pwd-input" placeholder="輸入密碼..." />
    <button id="login-btn" onclick="decrypt()">查看報表</button>
    <div id="error-msg"></div>
  </div>
  <div id="report"></div>
  <script>
    const S_B64 = "REPLACE_SALT", I_B64 = "REPLACE_IV", C_B64 = "REPLACE_CT";
    function b2b(b) { const bin = atob(b); return Uint8Array.from(bin, c => c.charCodeAt(0)); }
    async function decrypt() {
      const pw = document.getElementById('pwd-input').value;
      const err = document.getElementById('error-msg');
      try {
        const enc = new TextEncoder();
        const km = await crypto.subtle.importKey('raw', enc.encode(pw), 'PBKDF2', false,['deriveKey']);
        const salt = b2b(S_B64), iv = b2b(I_B64), ct = b2b(C_B64);
        const key = await crypto.subtle.deriveKey(
          { name: 'PBKDF2', salt, iterations: 100000, hash: 'SHA-256' },
          km, { name: 'AES-GCM', length: 256 }, false, ['decrypt']
        );
        const dec = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ct);
        document.getElementById('login-screen').style.display = 'none';
        const r = document.getElementById('report');
        r.style.display = 'block';
        r.innerHTML = new TextDecoder().decode(dec);
      } catch (e) { err.textContent = '❌ 密碼錯誤'; }
    }
    document.getElementById('pwd-input').addEventListener('keydown', e => { if (e.key === 'Enter') decrypt(); });
  </script>
</body>
</html>"""

    final_html = html_template.replace("REPLACE_SALT", s_b64).replace("REPLACE_IV", i_b64).replace("REPLACE_CT", c_b64)

    os.makedirs("docs", exist_ok=True)
    with open("docs/portfolio.html", "w", encoding="utf-8") as f:
        f.write(final_html)
    print("✅ 主要報表已更新：docs/portfolio.html")

    os.makedirs("Daily_Report", exist_ok=True)
    tw_tz = timezone(timedelta(hours=8))
    report_date = datetime.now(tw_tz).strftime('%Y-%m-%d')
    backup_path = f"Daily_Report/portfolio_{report_date}.html"
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(final_html)
    print(f"✅ 歷史備份已存檔：{backup_path}")


# ==========================================
# 5. 主程式
# ==========================================
if __name__ == "__main__":
    print("🚀 啟動資產分析任務 (支援 TG & LINE Bot)...")
    git_branch = os.getenv("GITHUB_REF_NAME", "unknown_branch")

    if not REPORT_PWD:
        print("❌ 嚴重錯誤：找不到環境變數 REPORT_PWD，無法產生加密報表。")
        exit(1)

    tw_tz = timezone(timedelta(hours=8))
    cache_bust = datetime.now(tw_tz).strftime('%Y%m%d%H%M')
    final_url = f"{REPORT_BASE_URL}?t={cache_bust}"
    msg = get_stock_summary(final_url, git_branch)

    # ── 開關控制 ──
    if NOTIFY_TARGET in ("telegram", "both", "all"):
        push_tg_message(msg)
    if NOTIFY_TARGET in ("line", "both", "all"):
        push_line_message(msg)
    if NOTIFY_TARGET in ("discord", "all"):          # 👈 新增這段
        push_discord_message(msg)
