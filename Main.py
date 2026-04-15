# -*- coding: utf-8 -*-
import yfinance as yf
import requests
import os
import math
import json
from datetime import datetime, timedelta, timezone


# ==========================================
# 1. 安全設定區
# ==========================================
CHANNEL_ID = os.getenv("LINE_CHANNEL_ID")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
USER_ID = os.getenv("LINE_USER_ID")
REPORT_BASE_URL = "https://gn1179076-wq.github.io/Stock_Bot_2/portfolio.html"

PORTFOLIO_FILE = "portfolio.json"

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ 找不到持股檔案：{PORTFOLIO_FILE}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式錯誤：{e}")
        return []

def get_channel_access_token():
    url = "https://api.line.me/v2/oauth/accessToken"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "grant_type": "client_credentials",
        "client_id": CHANNEL_ID,
        "client_secret": CHANNEL_SECRET
    }
    response = requests.post(url, headers=headers, data=payload)
    if response.status_code == 200:
        return response.json().get("access_token")
    return None


# ==========================================
# 2. 抓取資料 & 產生 LINE 訊息 + HTML 報表
# ==========================================
def get_stock_summary():
    print("正在分析資產狀況與黃金價格...")
    portfolio_data = load_portfolio()

    rates = {"US": 32.5, "HK": 4.15, "JP": 0.21, "TW": 1.0}
    gold_usd = 0.0
    gold_twd_per_mace = 0.0

    try:
        data = yf.download(["USDTWD=X", "HKDTWD=X", "JPYTWD=X", "GC=F"], period="5d", progress=False, timeout=15, threads=False)
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
        print(f"匯率抓取失敗: {e}")

    total_cost, total_value = 0.0, 0.0
    details = ""
    html_rows = ""

    for item in portfolio_data:
        try:
            stock = yf.Ticker(item['ticker'])
            hist = stock.history(period="5d")
            current = hist['Close'].ffill().iloc[-1] if not hist.empty else item['cost_price']

            rate = rates.get(item['market'], 1.0)
            c_twd = item['shares'] * item['cost_price'] * rate
            v_twd = item['shares'] * current * rate

            total_cost += c_twd
            total_value += v_twd

            roi = ((v_twd - c_twd) / c_twd) * 100 if c_twd != 0 else 0

            # LINE 文字（只顯示虧損的股票）
            trend_icon = "🔴" if roi >= 0 else "🟢"
            symbol = {"US": "$", "HK": "HK$", "JP": "¥", "TW": "$"}.get(item['market'], "$")
            cost_p = item['cost_price']
            if roi < 0:
                loss_amt = int(v_twd - c_twd)
                details += f"📉 {item['name']}\n   {symbol}{cost_p:,.2f} → {symbol}{current:,.2f} ({roi:+.1f}% / ${loss_amt:,})\n"

            # HTML 表格行
            display_name = item['name'].split(' ', 1)[-1] if ' ' in item['name'] else item['name']
            ticker_display = item['ticker'].replace('.TW', '').replace('.HK', '').replace('.T', '')
            market_tag_class = {"TW": "tag-tw", "US": "tag-us", "HK": "tag-hk", "JP": "tag-jp"}.get(item['market'], "tag-tw")
            badge_class = "badge-up" if roi >= 0 else "badge-down"
            sign = "+" if roi >= 0 else ""
            profit_amt = int(v_twd - c_twd)
            profit_color = "text-green" if profit_amt >= 0 else "text-red"
            profit_display = f"+${profit_amt:,}" if profit_amt >= 0 else f"-${abs(profit_amt):,}"

            html_rows += (
                f"<tr>"
                f"<td><div class='stock-name'>{display_name}</div><div class='stock-ticker'>{item['ticker']}</div></td>"
                f"<td><span class='market-tag {market_tag_class}'>{item['market']}</span></td>"
                f"<td class='right mono'>{item['shares']:,}</td>"
                f"<td class='right mono'>{symbol}{cost_p:,.2f}</td>"
                f"<td class='right mono'>{symbol}{current:,.2f}</td>"
                f"<td class='right mono'>${int(v_twd):,}</td>"
                f"<td class='right mono {profit_color}'>{profit_display}</td>"
                f"<td class='right'><span class='badge {badge_class}'>{sign}{roi:.1f}%</span></td>"
                f"</tr>"
            )

        except Exception as e:
            print(f"處理 {item['name']} 時出錯: {e}")
            continue

    profit_total = total_value - total_cost
    roi_total = (profit_total / total_cost) * 100 if total_cost > 0 else 0
    total_trend_icon = "🔴" if profit_total >= 0 else "🟢"

    tw_tz = timezone(timedelta(hours=8))
    current_time = datetime.now(tw_tz).strftime('%Y-%m-%d %H:%M:%S')
    gold_display = f"${int(gold_twd_per_mace):,}" if gold_twd_per_mace > 0 else "暫無資料"

    # ---- LINE 文字訊息 ----
    loss_section = f"🟢 虧損持股：\n{details}" if details else "🎉 全部持股皆為正報酬！"
    message = (
        f"【Fiona 資產日報】\n"
        f"📅 {current_time}\n"
        f"------------------\n"
        f"🟡 國際金價: ${gold_usd:.1f} (USD)\n"
        f"💰 台灣金價: {gold_display} (TWD/錢)\n"
        f"💱 美元匯率: {rates['US']:.2f} (USD/TWD)\n"
        f"💱 日幣匯率: {rates['JP']:.4f} (JPY/TWD)\n"
        f"------------------\n"
        f"💰 總投入: ${int(total_cost):,}\n"
        f"📊 總現值: ${int(total_value):,}\n"
        f"🔥 總損益: ${int(profit_total):,} ({total_trend_icon} {roi_total:+.2f}%)\n"
        f"------------------\n"
        f"{loss_section}\n"
        f"------------------\n"
        f"📋 完整報告：{REPORT_URL}"
    )

    # ---- HTML 儀表板 ----
    profit_color = "text-green" if profit_total >= 0 else "text-red"
    profit_sign = "+" if profit_total >= 0 else ""
    usd_twd_display = f"{rates['US']:.2f}"
    jpy_twd_display = f"{rates['JP']:.4f}"

    # 報表內容（密碼正確後才解密顯示）
    report_content = f"""
  <div class="header">
    <h1>📊 Fiona 資產日報</h1>
    <div class="time">{current_time}</div>
  </div>
  <div class="gold-bar">
    <div class="gold-item"><div class="gold-label">🟡 國際金價</div><div class="gold-value">${gold_usd:,.1f} USD</div></div>
    <div class="gold-item"><div class="gold-label">💰 台灣金價</div><div class="gold-value">{gold_display} TWD/錢</div></div>
    <div class="gold-item"><div class="gold-label">💱 USD/TWD</div><div class="gold-value">{usd_twd_display}</div></div>
    <div class="gold-item"><div class="gold-label">💱 JPY/TWD</div><div class="gold-value">{jpy_twd_display}</div></div>
  </div>
  <div class="summary">
    <div class="summary-card"><div class="label">總投入</div><div class="value text-white">${int(total_cost):,}</div></div>
    <div class="summary-card"><div class="label">總現值</div><div class="value text-white">${int(total_value):,}</div></div>
    <div class="summary-card"><div class="label">總損益</div><div class="value {profit_color}">{profit_sign}${int(abs(profit_total)):,}</div><div class="sub {profit_color}">{profit_sign}{roi_total:.2f}%</div></div>
  </div>
  <div class="card">
    <div class="card-header">📈 持股明細</div>
    <div class="table-wrap"><table>
      <thead><tr><th>股票</th><th>市場</th><th class="right">股數</th><th class="right">成本價</th><th class="right">現價</th><th class="right">現值 (TWD)</th><th class="right">損益 (TWD)</th><th class="right">報酬率</th></tr></thead>
      <tbody>{html_rows}</tbody>
    </table></div>
  </div>
  <div class="footer">資料來源：Yahoo Finance｜最後更新：{current_time}</div>"""

    # ---- AES 加密報表內容 ----
    import hashlib, base64
    from os import urandom
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    password = "vic2026"
    salt = urandom(16)
    iv = urandom(12)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000, dklen=32)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(iv, report_content.encode('utf-8'), None)
    encrypted_b64 = base64.b64encode(ciphertext).decode()
    salt_b64 = base64.b64encode(salt).decode()
    iv_b64 = base64.b64encode(iv).decode()

    html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fiona 資產日報</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700&family=JetBrains+Mono:wght@500;700&display=swap');
  *, *::before, *::after {{ box-sizing: border-box; }}
  body {{ font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif; background: #0f1117; margin: 0; padding: 24px 16px; min-height: 100vh; color: #e2e8f0; }}
  .container {{ max-width: 960px; margin: auto; }}
  .header {{ text-align: center; margin-bottom: 32px; }}
  .header h1 {{ font-size: 1.5rem; font-weight: 700; color: #f7fafc; margin: 0 0 4px; letter-spacing: -0.5px; }}
  .header .time {{ font-family: 'JetBrains Mono', monospace; color: #718096; font-size: .8rem; }}
  .gold-bar {{ display: flex; justify-content: center; gap: 32px; background: linear-gradient(135deg, #2d2006 0%, #1a1a2e 100%); border: 1px solid #44381f; border-radius: 12px; padding: 16px 24px; margin-bottom: 24px; }}
  .gold-item {{ text-align: center; }}
  .gold-item .gold-label {{ font-size: .7rem; color: #a08c5b; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }}
  .gold-item .gold-value {{ font-family: 'JetBrains Mono', monospace; font-size: 1.1rem; font-weight: 700; color: #f6e05e; margin-top: 4px; }}
  .summary {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 28px; }}
  .summary-card {{ background: #1a1d2e; border: 1px solid #2d3148; border-radius: 14px; padding: 20px 16px; text-align: center; }}
  .summary-card .label {{ font-size: .68rem; color: #718096; font-weight: 700; text-transform: uppercase; letter-spacing: .8px; margin-bottom: 8px; }}
  .summary-card .value {{ font-family: 'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 700; }}
  .summary-card .sub {{ font-family: 'JetBrains Mono', monospace; font-size: .82rem; margin-top: 4px; }}
  .text-green {{ color: #48bb78; }} .text-red {{ color: #fc8181; }} .text-white {{ color: #f7fafc; }}
  .card {{ background: #1a1d2e; border: 1px solid #2d3148; border-radius: 16px; overflow: hidden; margin-bottom: 24px; }}
  .card-header {{ padding: 16px 22px; font-weight: 700; font-size: .95rem; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid #2d3148; color: #e2e8f0; }}
  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ color: #4a5568; font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .8px; padding: 12px 18px; text-align: left; border-bottom: 1px solid #2d3148; white-space: nowrap; }}
  td {{ padding: 14px 18px; font-size: .88rem; border-bottom: 1px solid #1e2234; white-space: nowrap; color: #cbd5e0; }}
  tr:last-child td {{ border-bottom: none; }} tr:hover {{ background: #1e2234; }}
  .stock-name {{ font-weight: 700; color: #f7fafc; }}
  .stock-ticker {{ font-family: 'JetBrains Mono', monospace; font-size: .75rem; color: #718096; margin-top: 2px; }}
  .mono {{ font-family: 'JetBrains Mono', monospace; font-weight: 500; }}
  .right {{ text-align: right; }}
  .badge {{ display: inline-block; padding: 4px 10px; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: .78rem; font-weight: 700; }}
  .badge-up {{ background: rgba(72, 187, 120, .15); color: #48bb78; }}
  .badge-down {{ background: rgba(252, 129, 129, .15); color: #fc8181; }}
  .market-tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: .65rem; font-weight: 700; letter-spacing: .5px; }}
  .tag-tw {{ background: #2a4365; color: #90cdf4; }} .tag-us {{ background: #2c3a2e; color: #9ae6b4; }}
  .tag-hk {{ background: #44337a; color: #d6bcfa; }} .tag-jp {{ background: #4a3728; color: #fbd38d; }}
  .footer {{ text-align: center; margin-top: 16px; color: #4a5568; font-size: .72rem; }}
  .login-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: #0f1117; z-index: 99999; display: flex; justify-content: center; align-items: center; }}
  .login-overlay.hidden {{ display: none; }}
  .login-box {{ background: #1a1d2e; border: 1px solid #2d3148; border-radius: 20px; padding: 40px 36px; text-align: center; width: 340px; box-shadow: 0 20px 60px rgba(0,0,0,.4); }}
  .login-box h2 {{ margin: 0 0 8px; font-size: 1.3rem; color: #f7fafc; }}
  .login-box p {{ margin: 0 0 24px; font-size: .85rem; color: #718096; }}
  .login-box input {{ width: 100%; padding: 12px 16px; border: 2px solid #2d3148; border-radius: 10px; font-size: 1rem; outline: none; background: #0f1117; color: #e2e8f0; transition: border-color .2s; }}
  .login-box input:focus {{ border-color: #667eea; }}
  .login-box button {{ width: 100%; margin-top: 14px; padding: 12px; background: linear-gradient(135deg, #667eea, #764ba2); color: #fff; border: none; border-radius: 10px; font-size: 1rem; font-weight: 700; cursor: pointer; transition: opacity .2s; }}
  .login-box button:hover {{ opacity: .9; }}
  .login-error {{ color: #fc8181; font-size: .82rem; margin-top: 10px; display: none; }}
  @media (max-width: 600px) {{ body {{ padding: 16px 10px; }} .summary {{ grid-template-columns: 1fr; }} .gold-bar {{ flex-direction: column; gap: 12px; }} th, td {{ padding: 10px 12px; font-size: .82rem; }} }}
</style>
</head>
<body>
<noscript><p style="color:#e2e8f0;text-align:center;margin-top:40vh">此報表需要啟用 JavaScript 才能檢視。</p></noscript>

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

<script>
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
    with open("docs/portfolio.html", "w", encoding="utf-8") as f:
        f.write(html)

    return message


# ==========================================
# 3. LINE 推播訊息
# ==========================================
def push_message(token, text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    payload = {"to": USER_ID, "messages": [{"type": "text", "text": text}]}
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print("LINE 訊息發送成功！")


# ==========================================
# 4. 主程式
# ==========================================
if __name__ == "__main__":
    # 加時間戳破快取
    cache_bust = datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d%H%M')
    REPORT_URL = f"{REPORT_BASE_URL}?t={cache_bust}"
    token = get_channel_access_token()
    if token:
        msg_text = get_stock_summary()
        push_message(token, msg_text)
